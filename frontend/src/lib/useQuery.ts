/**
 * Tiny data-fetching hook for the loading / empty / error states required by
 * 03 («Loading، empty، success و error states کامل»). No extra dependency.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  status: "idle" | "loading" | "success" | "error";
  reload: () => void;
}

export function useQuery<T>(
  factory: () => Promise<T>,
  deps: unknown[] = [],
): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  const run = useCallback(() => {
    const my = ++seq.current;
    setLoading(true);
    setError(null);
    factory()
      .then((d) => {
        if (my === seq.current) setData(d);
      })
      .catch((e: unknown) => {
        if (my === seq.current) {
          setError(e instanceof ApiError ? detailMessage(e) : "خطا در دریافت داده‌ها");
        }
      })
      .finally(() => {
        if (my === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { run(); /* eslint-disable-next-line */ }, [run]);

  const status = loading ? "loading" : error ? "error" : data != null ? "success" : "success";
  return { data, loading, error, status, reload: run };
}

/** Pull a human Persian message out of an ApiError.detail payload. */
export function detailMessage(e: ApiError): string {
  const d = e.detail as { detail?: unknown; code?: string } | string;
  if (d && typeof d === "object" && "detail" in d) {
    const inner = (d as { detail: unknown }).detail;
    if (typeof inner === "string") return inner;
    if (inner && typeof inner === "object") {
      const msg = (inner as { message?: string }).message;
      if (msg) return msg;
      const code = (inner as { code?: string }).code;
      if (code) return `خطا: ${code}`;
    }
  }
  if (typeof d === "string" && d) return d;
  return `خطای ${e.status}`;
}
