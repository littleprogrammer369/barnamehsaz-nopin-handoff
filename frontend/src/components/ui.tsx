/**
 * Minimal reusable presentational components built on the global CSS in
 * src/styles/global.css. No external UI library (lean dependency budget).
 */
import {
  type ReactNode,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { formatJalaliDate, formatJalaliDateTime, formatJalaliDateWithWeekday, weekdayLabel } from "../lib/persian";
import { formatNumber } from "../lib/digits";

// ---------------- form primitives ----------------
export function InputField({
  label, hint, error, className, ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string; error?: string | null }) {

  return (
    <label className={`field ${className ?? ""}`}>
      {label && <span>{label}</span>}
      <input className="input" {...rest} />
      {hint && !error && <div className="hint">{hint}</div>}
      {error && <div className="error">{error}</div>}
    </label>
  );
}

export function SelectInput({
  label, options, hint, ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  options: { value: string | number; label: string | number; disabled?: boolean }[];
  hint?: string;
}) {

  return (
    <label className="field">
      {label && <span>{label}</span>}
      <select className="select" {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>
        ))}
      </select>
      {hint && <div className="hint">{hint}</div>}
    </label>
  );
}

export function TextArea({
  label, hint, error, ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; hint?: string; error?: string | null }) {
  return (
    <label className="field">
      {label && <span>{label}</span>}
      <textarea className="textarea" {...rest} />
      {hint && !error && <div className="hint">{hint}</div>}
      {error && <div className="error">{error}</div>}
    </label>
  );
}

// ---------------- states ----------------
export function Loading() {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" />
      <p className="mt-2 muted">در حال بارگذاری…</p>
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="state state--empty">
      <div className="state-ico">⚑</div>
      <h3>{title}</h3>
      {hint && <p className="muted small">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state" role="alert">
      <div className="alert alert--error" style={{ textAlign: "right", marginBottom: 14 }}>
        <strong>خطا:</strong> {message}
      </div>
      {onRetry && <button className="btn btn--ghost btn--sm" onClick={onRetry}>تلاش دوباره</button>}
    </div>
  );
}

// ---------------- badges ----------------
export type Tone = "ok" | "warn" | "bad" | "info" | "muted";

export function Badge({ tone = "muted", children }: { tone?: Tone; children: ReactNode }) {
  const cls =
    tone === "ok" ? "badge--ok" :
    tone === "warn" ? "badge--warn" :
    tone === "bad" ? "badge--bad" :
    tone === "info" ? "badge--info" : "badge--muted";
  return <span className={`badge ${cls}`}>{children}</span>;
}

const STATUS_MAP: Record<string, { tone: Tone; label: string }> = {
  draft: { tone: "muted", label: "پیش‌نویس" },
  submitted: { tone: "info", label: "ارسال‌شده" },
  needs_changes: { tone: "warn", label: "تغییرات نیازمند" },
  approved: { tone: "ok", label: "تأیید‌شده" },
  rejected: { tone: "bad", label: "ردشده" },
  pending: { tone: "muted", label: "معلق‌ماند" },
  unit_approved: { tone: "ok", label: "تأیید واحد" },
  running: { tone: "info", label: "در حال اجرا" },
  data_gaps: { tone: "warn", label: "کمبود داده" },
  FEASIBLE: { tone: "ok", label: "مجاز" },
  INFEASIBLE: { tone: "bad", label: "غیرممکن" },
  FAILED: { tone: "bad", label: "ناموفق" },
  open: { tone: "info", label: "باز" },
  published: { tone: "ok", label: "منتشرشده" },
  solved: { tone: "ok", label: "درست‌شده" },
  unsolved: { tone: "warn", label: "درست‌نشده" },
  active: { tone: "ok", label: "فعال" },
  inactive: { tone: "muted", label: "غیرفعال" },
  created: { tone: "info", label: "ایجادشده" },
  failed: { tone: "bad", label: "ناموفق" },
};

/** Unified Persian label map: status key → display string. */
export const STATUS_BADGE_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(STATUS_MAP).map(([k, v]) => [k, v.label]),
);

export function StatusBadge({ status }: { status: string }) {
  const m = STATUS_MAP[status] ?? { tone: "muted" as Tone, label: "نامشخص" };
  return <Badge tone={m.tone}>{m.label}</Badge>;
}

// ---------------- dates / numbers ----------------
export function JalaliDate({
  value, withWeekday = false, time = false,
}: { value: string | null | undefined; withWeekday?: boolean; time?: boolean }) {
  if (time) return <span>{formatJalaliDateTime(value)}</span>;
  if (withWeekday) return <span>{formatJalaliDateWithWeekday(value)}</span>;
  return <span>{formatJalaliDate(value)}</span>;
}

export function WeekdayCell({ index }: { index: number | null | undefined }) {
  return <span>{weekdayLabel(index)}</span>;
}

export function PersNum({ n }: { n: number | null | undefined }) {
  return <span>{n == null ? "—" : formatNumber(n)}</span>;
}

// ---------------- card / list ----------------
export function Card({
  title, children, actions,
}: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="row row-between" style={{ marginBottom: 12 }}>
          {title && <h3 className="card-title mt-0">{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, tone = "muted" }: { label: string; value: ReactNode; tone?: Tone }) {
  const color =
    tone === "ok" ? "var(--color-success)" :
    tone === "warn" ? "#8a5a10" :
    tone === "bad" ? "var(--color-danger)" :
    tone === "info" ? "var(--color-info)" : "var(--color-navy)";
  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="small muted">{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 800, marginTop: 6, color }}>{value}</div>
    </div>
  );
}

export function Alert({ kind, children }: { kind: "error" | "warn" | "ok" | "info"; children: ReactNode }) {
  return <div className={`alert alert--${kind}`}>{children}</div>;
}

// ---------------- data table ----------------
export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "right" | "center" | "left";
}

export function DataTable<T extends { id?: number }>({
  columns, rows, empty, rowKey,
}: {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  rowKey?: (r: T) => string | number;
}) {
  if (rows.length === 0) return <EmptyState title={empty ?? "موردی یافت نشد"} />;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: c.align === "center" ? "center" : "right" }}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i}>
              {columns.map((c) => (
                <td key={c.key} style={{ textAlign: c.align === "center" ? "center" : "right" }}>{c.render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------- preflight ----------------
export function PreflightBlockerList({
  blockers, warnings,
}: { blockers: { code: string; message: string }[]; warnings: { code: string; message: string }[] }) {
  const items: Array<{ type: "blocker" | "warning"; code: string; message: string }> = [
    ...blockers.map((b) => ({ type: "blocker" as const, code: b.code, message: b.message })),
    ...warnings.map((w) => ({ type: "warning" as const, code: w.code, message: w.message })),
  ];
  if (items.length === 0) {
    return (
      <div className="checklist-item is-ok">
        <span className="ico">✓</span>
        <div>
          <strong>همهٔ چک‌های پیش‌پرواز (preflight) پاک است.</strong>
          <div className="small muted">این چرخه آمادهٔ حل / انتشار است.</div>
        </div>
      </div>
    );
  }
  return (
    <div>
      {items.map((it, i) => (
        <div key={i} className={`checklist-item ${it.type === "blocker" ? "is-blocker" : "is-warning"}`}>
          <span className="ico">{it.type === "blocker" ? "!" : "•"}</span>
          <div>
            <strong>{it.type === "blocker" ? "مانع" : "هشدار"}: {it.message}</strong>
            <div className="code">{it.code}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------- timeline ----------------
export function Timeline({ items }: { items: { label: string; sub?: string; time?: string }[] }) {
  if (items.length === 0) return <EmptyState title="رویدادی ثبت نشده است" />;
  return (
    <ul className="timeline">
      {items.map((it, i) => (
        <li key={i}>
          <span className="tl-dot" />
          <div>
            <strong>{it.label}</strong>
            {it.sub && <div className="small muted">{it.sub}</div>}
          </div>
          {it.time && <div className="small faint"><JalaliDate value={it.time} time /></div>}
        </li>
      ))}
    </ul>
  );
}
