/**
 * Auth React context: in-memory tokens, login/refresh/logout,
 * forced-password-change gate. No browser storage.
 */
import {
  createContext, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { api, Auth, clearAuth, getAuth, setAuth } from "./api";
import type { LoginUser, MeResponse } from "./types";

export interface AuthContextValue {
  accessToken: string | null;
  refreshToken: string | null;
  user: MeResponse | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<LoginUser>;
  logout: () => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  mustChangePassword: boolean;
  role: "admin" | "unit_manager" | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [user, setUser] = useState<MeResponse | null>(null);
  const [role, setRole] = useState<"admin" | "unit_manager" | null>(null);
  const [ready, setReady] = useState(false);

  // Re-validate any in-memory token on mount. No storage rehydration (02).
  useEffect(() => {
    const mem = getAuth();
    if (mem.accessToken) {
      setAccessToken(mem.accessToken);
      setRefreshToken(mem.refreshToken);
      if (mem.user) setUser(mem.user);
      api<MeResponse>("/auth/me")
        .then((me) => {
          setUser(me);
          setRole(inferRole(me));
          setAuth({ user: me });
        })
        .catch(() => {
          clearAuth();
          setUser(null);
          setRole(null);
          setAccessToken(null);
          setRefreshToken(null);
        })
        .finally(() => setReady(true));
    } else {
      setReady(true);
    }
  }, []);

  async function login(email: string, password: string) {
    const d = await Auth.login({ email, password });
    setAccessToken(d.access_token);
    setRefreshToken(d.refresh_token);
    const me = await api<MeResponse>("/auth/me");
    setUser(me);
    setRole(inferRole(me));
    setAuth({ user: me });
    return d.user;
  }

  async function logout() {
    await Auth.logout();
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
    setRole(null);
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await Auth.changePassword({
      current_password: oldPassword,
      new_password: newPassword,
      user_id: user!.id,
    });
    setUser((u) => (u ? { ...u, must_change_password: false } : u));
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      refreshToken,
      user,
      ready,
      login,
      logout,
      changePassword,
      mustChangePassword: user?.must_change_password ?? false,
      role,
    }),
    [accessToken, refreshToken, user, ready, role],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function inferRole(
  me: MeResponse,
): "admin" | "unit_manager" | null {
  const roles = (me.memberships ?? []).map((m) => m.role);
  if (roles.includes("admin")) return "admin";
  if (roles.includes("unit_manager")) return "unit_manager";
  return null;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

export function useRequireAuth(): AuthContextValue {
  const auth = useAuth();
  if (!auth.ready) {
    throw new Error("Auth not ready; call only after AuthProvider settled");
  }
  if (!auth.accessToken) {
    throw new Error("Unauthorized: no active access token");
  }
  return auth;
}
