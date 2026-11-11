/** Planning cycles: list + create + detail link. */
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Cycles } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { Card, Loading, ErrorState, EmptyState, StatusBadge, JalaliDate, InputField, SelectInput, STATUS_BADGE_LABELS } from "../components/ui";
import { useAuth } from "../lib/auth";
import type { PlanningCycleStatus, PlanningCycle } from "../lib/types";

const STATUSES: PlanningCycleStatus[] = ["draft", "open", "submitted", "reviewed", "published"];

export function PlanningCycles() {
  const auth = useAuth();
  const isAdmin = auth.role === "admin";
  const q = useQuery(() => Cycles.list(), []);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", term: "", status: "open" as PlanningCycleStatus });
  const [err, setErr] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setErr("نام چرخه را وارد کنید."); return; }
    setBusy(true); setErr(null);
    try {
      await Cycles.create({ name: form.name.trim(), term: form.term || undefined, status: form.status });
      setForm({ name: "", term: "", status: "open" });
      setFlash("چرخه با موفقیت ایجاد شد.");
      q.reload();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "ایجاد چرخه ناموفق بود.");
    } finally { setBusy(false); }
  }

  async function onDelete(cycle: PlanningCycle) {
    if (!window.confirm(`آیا از archivewing «${cycle.name}» اطمینان دارید؟`)) return;
    setDeletingId(cycle.id);
    try {
      await Cycles.delete(cycle.id);
      setFlash(`چرخهٔ «${cycle.name}» بایگانی شد.`);
      q.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "بایگانی ناموفق بود.");
    } finally { setDeletingId(null); }
  }

  return (
    <AppShell title="چرخه‌های برنامه‌ریزی">
      <div className="row row-between">
        <h1 style={{ margin: 0 }}>چرخه‌های برنامه‌ریزی</h1>
      </div>

      <div className="grid grid-2 mt-2">
        <Card title="فهرست چرخه‌ها">
          {q.loading ? <Loading /> :
            q.error ? <ErrorState message={q.error} onRetry={q.reload} /> :
            (q.data?.length ?? 0) === 0 ? <EmptyState title="چرخه‌ای وجود ندارد" /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>نام</th><th>ترم</th><th>وضعیت</th><th>آغاز</th><th>پایان</th><th>عملیات</th></tr></thead>
                  <tbody>
                    {q.data!.map((c) => (
                      <tr key={c.id}>
                        <td><Link to={`/cycles/${c.id}`}>{c.name}</Link></td>
                        <td>{c.term}</td>
                        <td><StatusBadge status={c.status} /></td>
                        <td><JalaliDate value={c.start_date} /></td>
                        <td><JalaliDate value={c.end_date} /></td>
                        <td>
                          {isAdmin ? (
                            <button
                              className="btn btn--ghost btn--sm"
                              disabled={deletingId === c.id}
                              onClick={() => onDelete(c)}
                            >
                              {deletingId === c.id ? "در حال بایگانی…" : "بایگانی"}
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        {isAdmin && (
          <Card title="ایجاد چرخهٔ جدید">
            <form onSubmit={onCreate}>
              {err && <div className="alert alert--error" style={{ marginBottom: 12 }}>{err}</div>}
              {flash && <div className="alert alert--ok" style={{ marginBottom: 12 }}>{flash}</div>}
              <InputField label="نام چرخه" value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="مثلاً: ترم پاییز ۱۴۰۳" required />
              <InputField label="ترم / برچسب (اختیاری)" value={form.term}
                onChange={(e) => setForm((f) => ({ ...f, term: e.target.value }))} />
              <SelectInput label="وضعیت" value={form.status}
                onChange={(e) => setForm((f) => ({ ...f, status: e.target.value as PlanningCycleStatus }))}
                options={STATUSES.map((s) => ({ value: s, label: STATUS_BADGE_LABELS[s] ?? s }))} />
              <button className="btn btn--teal" type="submit" disabled={busy}>
                {busy ? "در حال ایجاد…" : "ایجاد"}
              </button>
            </form>
            <p className="small muted mt-2">
              نقش مدیر کل یا مدیر واحد برای ایجاد لازم است؛ چرخه پس از ایجاد، واحدها، منابع و دستگاه‌ها را به آن متصل می‌کنید.
            </p>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
