/**
 * Audit timeline page (admin). Append-only, readable history of domain actions.
 * 03: «گزارش کار: یک نمای کلی و قابل‌ردیابی از تغییرات».
 */
import { useState } from "react";
import { AppShell } from "../layouts/AppShell";
import { Audit as AuditClient, Corrections } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, Timeline, SelectInput, JalaliDate, DataTable, Column,
} from "../components/ui";
import { useAuth } from "../lib/auth";
import type { Correction } from "../lib/types";

const ACTIONS = ["", "login", "submit", "approve", "request_changes", "shared_approval", "solve", "solve_blocked", "offering_correction", "comment_add"];

export function Audit() {
  const auth = useAuth();
  const [limit, setLimit] = useState<number>(50);
  const [action, setAction] = useState("");
  const evQ = useQuery(() => AuditClient.list({ limit, subject_type: action || undefined }), [limit, action]);
  const corrQ = useQuery(() => Corrections.list(), []);

  // Admin-only guard
  if (auth.role !== "admin") {
    return <AppShell title="گزارش کار"><Card><EmptyState title="دسترسی به گزارش کار فقط برای مدیر کل است." /></Card></AppShell>;
  }

  const actionLabel = (a: string) => {
    const m: Record<string, string> = {
      login: "ورود", submit: "ارسال", approve: "تأیید", request_changes: "بازگشت به اصلاح",
      shared_approval: "تأیید دستگاه مشترک", shared_approve: "نهایی‌سازی تأیید", shared_return: "بازگشت دستگاه مشترک",
      solve: "اجرای حل", solve_blocked: "مسدودسازی حل", offering_correction: "اصلاح مدیریتی",
      comment_add: "افزودن نظر", submission_create: "ایجاد درخواست", submission_update: "به‌روزرسانی درخواست",
    };
    return m[a] ?? a;
  };

  const corrCols: Column<Correction>[] = [
    { key: "off", header: "دستگاه", render: (c) => <span className="ltr">#{c.offering_id}</span> },
    { key: "field", header: "فیلد", render: (c) => <span className="ltr">{c.field}</span> },
    { key: "from", header: "از", render: (c) => <span className="small ltr">{c.before_value ?? "—"}</span> },
    { key: "to", header: "به", render: (c) => <span className="small ltr">{c.after_value ?? "—"}</span> },
    { key: "reason", header: "دلیل", render: (c) => <span className="small">{c.reason}</span> },
    { key: "stale", header: "تأییدهای کهنه", render: (c) => c.approvals_marked_stale ? "بله" : "خیر" },
    { key: "time", header: "زمان", render: (c) => <JalaliDate value={c.created_at} time /> },
  ];

  return (
    <AppShell title="گزارش کار (Audit)">
      <div className="row row-between">
        <h1 style={{ margin: 0 }}>گزارش کار و رده‌بندی</h1>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <SelectInput label="فیلتر عمل" value={action} onChange={(e) => setAction(e.target.value)}
            options={[{ value: "", label: "همه" }, ...ACTIONS.slice(1).map((a) => ({ value: a, label: actionLabel(a) }))]} />
          <SelectInput label="تعداد" value={limit} onChange={(e) => setLimit(Number(e.target.value))}
            options={[20, 50, 100].map((n) => ({ value: n, label: String(n) }))} />
        </div>
      </div>

      <div className="grid grid-2 mt-2">
        <Card title={"رویدادهای دامنه (" + (evQ.data?.length ?? 0) + ")"}>
          {evQ.loading ? <Loading /> :
            evQ.error ? <ErrorState message={evQ.error} onRetry={evQ.reload} /> :
            (evQ.data?.length ?? 0) === 0 ? <EmptyState title="رویدادی یافت نشد" /> :
            <Timeline items={(evQ.data ?? []).map((e) => ({
              label: actionLabel(e.action),
              sub: [e.subject_type, e.subject_id != null ? ("#" + e.subject_id) : ""].filter(Boolean).join(" — ") || undefined,
              time: e.created_at ?? undefined,
            }))} />}
        </Card>

        <Card title={`اصلاح‌های مدیر (${corrQ.data?.length ?? 0})`}>
          {corrQ.loading ? <Loading /> :
            corrQ.error ? <ErrorState message={corrQ.error} onRetry={corrQ.reload} /> :
            (corrQ.data?.length ?? 0) === 0 ? <EmptyState title="اصلاحی ثبت نشده است" /> :
            <DataTable columns={corrCols} rows={corrQ.data!} rowKey={(c) => c.id} empty="موردی ندارد" />}
        </Card>
      </div>
    </AppShell>
  );
}
