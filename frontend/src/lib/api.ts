/**
 * HTTP client + in-memory auth store.
 *
 * Constraint (02 / Phase 5): tokens live in module scope only — never in
 * localStorage / sessionStorage. Browser code never hardcodes a host; it
 * calls the same-origin /api/v1 prefix and Vite's dev proxy (or the
 * deployed reverse-proxy) forwards to the backend.
 */
import type {
  LoginResponse, MeResponse,
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface AuthStore {
  accessToken: string | null;
  refreshToken: string | null;
  user: MeResponse | null;
}

// In-memory only. Cleared on logout / reload. (02: «به هیچ وجه در
// localStorage / sessionStorage ذخیره نشود.»)
const store: AuthStore = {
  accessToken: null,
  refreshToken: null,
  user: null,
};

export function getAuth(): AuthStore {
  return store;
}

export function setAuth(next: Partial<AuthStore>): void {
  Object.assign(store, next);
}

export function clearAuth(): void {
  store.accessToken = null;
  store.refreshToken = null;
  store.user = null;
}

export { store };

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Do not attach the Authorization header (used for /auth/login, /auth/refresh). */
  noAuth?: boolean;
  /** Bypass the automatic single-refresh attempt. */
  noRefresh?: boolean;
}

let refreshing: Promise<void> | null = null;

async function tryRefresh(): Promise<void> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      if (!store.refreshToken) throw new ApiError(401, "no refresh token");
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: store.refreshToken }),
      });
      if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => res.text()));
      const data: LoginResponse = await res.json();
      store.accessToken = data.access_token;
      store.refreshToken = data.refresh_token;
    } finally {
      // clear after a short delay so concurrent callers can observe the result
      setTimeout(() => { refreshing = null; }, 0);
    }
  })();
  return refreshing;
}

export async function api<T = unknown>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const method = opts.method ?? "GET";
  const url = new URL(API_BASE + path, window.location.origin);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (!opts.noAuth && store.accessToken) {
    headers["Authorization"] = `Bearer ${store.accessToken}`;
  }
  const res = await fetch(url.pathname + url.search, {
    method,
    headers,
    credentials: "same-origin",
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });

  // 401 + no-refresh flag → try a single refresh then retry once.
  if (res.status === 401 && !opts.noAuth && !opts.noRefresh && store.refreshToken) {
    await tryRefresh();
    const retryHeaders: Record<string, string> = { ...headers };
    if (store.accessToken) retryHeaders["Authorization"] = `Bearer ${store.accessToken}`;
    const retry = await fetch(url.pathname + url.search, {
      method,
      headers: retryHeaders,
      credentials: "same-origin",
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    return (await parse<T>(retry)) as T;
  }
  return (await parse<T>(res)) as T;
}

async function parse<T>(res: Response): Promise<T> {
  const hasBody = res.status !== 204;
  let detail: unknown = null;
  let json: T | null = null;
  if (hasBody) {
    const text = await res.text();
    if (text) {
      try { json = JSON.parse(text) as T; } catch { /* keep text */ }
    }
    detail = json ?? text;
  }
  if (!res.ok) throw new ApiError(res.status, detail);
  return (json ?? ({} as T)) as T;
}

// ---- typed helpers ------------------------------------------------------

export const Auth = {
  login: (body: { email: string; password: string }) =>
    api<LoginResponse>("/auth/login", {
      method: "POST",
      body,
      noAuth: true,
      noRefresh: true,
    }).then((d) => {
      store.accessToken = d.access_token;
      store.refreshToken = d.refresh_token;
      return d;
    }),
  refresh: (refresh_token: string) =>
    api<LoginResponse>("/auth/refresh", {
      method: "POST",
      body: { refresh_token },
      noAuth: true,
      noRefresh: true,
    }).then((d) => {
      store.accessToken = d.access_token;
      store.refreshToken = d.refresh_token;
      return d;
    }),
  logout: () =>
    api<{ detail: string }>("/auth/logout", { method: "POST" }).catch((e) => {
      // Logout must always clear in-memory state even if the call fails.
      if (e instanceof ApiError && e.status !== 401) console.warn(e);
      clearAuth();
    }),
  me: () => api<MeResponse>("/auth/me"),
  changePassword: (body: { current_password: string; new_password: string; user_id: number }) =>
    api<{ detail: string }>("/auth/change-password", { method: "POST", body }),
};
