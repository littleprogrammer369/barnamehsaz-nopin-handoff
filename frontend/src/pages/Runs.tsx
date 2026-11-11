/**
 * Run history (list), run detail (snapshot + assignments), and run comparison.
 * 03: «تاریخچهٔ اجراها: لیست قابل‌ردیابی + مقایسهٔ دو اجرا با diff».
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Solver, Cycles, Corrections, Export } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, StatusBadge, Alert,
  SelectInput, JalaliDate, DataTable, Column, Badge,
} from "../components/ui";
import { formatTime, weekdayLabel } from "../lib/persian";
import type { SolverRun, RunComparison, SolverAssignment } from "../lib/types";

// ---------------- List ----------------
export function Runs() {
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const [cycleId, setCycleId] = useState<number>(0);
  const [selA, setSelA] = useState<number>(0);
  const [selB, setSelB] = useState<number>(0);
  const [cmp, setCmp] = useState<RunComparison | null>(null);
  const [cmpBusy, setCmpBusy] = useState(false);
  const [cmpErr, setCmpErr] = useState<string | null>(null);

  const runsQ = useQuery(() => Solver.runs(cycleId || undefined), [cycleId]);
  const runs = runsQ.data ?? [];
  const cycleLabel = (cid: number) => (cyclesQ.data ?? []).find((c) => c.id === cid)?.name ?? cid;

  async function compare() {
    if (!selA || !selB || selA === selB) { setCmpErr("دو اجرای متفاوت انتخاب کنید."); return; }
    setCmpBusy(true); setCmpErr(null); setCmp(null);
    try {
      const r = await Solver.compare(selA, selB);
      setCmp(r);
    } catch (e2) {
      setCmpErr(e2 instanceof Error ? e2.message : "مقایسه ناموفق بود.");
    } finally { setCmpBusy(false); }
  }

  const runCols: Column<SolverRun>[] = [
    { key: "id", header: "شماره", render: (r) => <Link to={`/runs/${r.id}`} className="ltr">#{r.id}</Link> },
    { key: "cycle", header: "چرخه", render: (r) => cycleLabel(r.cycle_id) },
    { key: "status", header: "وضعیت", render: (r) => <StatusBadge status={r.status} /> },
    { key: "score", header: "امتیاز", render: (r) => <span className="ltr">{r.objective_score != null ? Number(r.objective_score).toFixed(3) : "—"}</span> },
    { key: "stale", header: "کهنه", render: (r) => r.stale ? <Badge tone="warn">کهنه</Badge> : <span className="faint">—</span> },
    {
      key: "export",
      header: "عملیات",
      render: (r) => (
        <div className="row btn-row">
          <button
            className="btn btn--sm"
            title="Excel فایل"
            onClick={() => Export.excel(r.id)}
            disabled={r.stale || r.status !== "FEASIBLE"}
          >
            📘 Excel
          </button>
          <button
            className="btn btn--sm"
            title="PDF فایل"
            onClick={() => Export.pdf(r.id)}
            disabled={r.stale || r.status !== "FEASIBLE"}
          >
            📄 PDF
          </button>
        </div>
      ),
    },
    { key: "created", header: "زمان", render: (r) => <JalaliDate value={r.created_at} time /> },
  ];

  return (
    <AppShell title="تاریخچهٔ اجراها">
      <div className="row row-between">
        <h1 style={{ margin: 0 }}>تاریخچهٔ اجراها</h1>
        <SelectInput label="فیلتر بر اساس چرخه" value={cycleId}
          onChange={(e) => setCycleId(Number(e.target.value))}
          options={[
            { value: 0, label: "همهٔ چرخه‌ها" },
            ...(cyclesQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
          ]} />
      </div>

      <div className="mt-2">
        <Card>
          {runsQ.loading ? <Loading /> :
            runsQ.error ? <ErrorState message={runsQ.error} onRetry={runsQ.reload} /> :
            runs.length === 0 ? <EmptyState title="اجرایی ثبت نشده است" action={<Link to="/solve" className="btn btn--teal btn--sm">اجرای حل</Link>} />
            : <DataTable columns={runCols} rows={runs} rowKey={(r) => r.id} empty="موردی ندارد" />}
        </Card>
      </div>

      <div className="mt-2">
        <Card title="مقایسهٔ دو اجرا">
          <div className="grid grid-3" style={{ alignItems: "end" }}>
            <SelectInput label="اجرای الف (A)" value={selA}
              onChange={(e) => setSelA(Number(e.target.value))}
              options={[{ value: 0, label: "— انتخاب —" }, ...runs.map((r) => ({ value: r.id, label: `#${r.id} (${r.status})` }))]} />
            <SelectInput label="اجرای ب (B)" value={selB}
              onChange={(e) => setSelB(Number(e.target.value))}
              options={[{ value: 0, label: "— انتخاب —" }, ...runs.map((r) => ({ value: r.id, label: `#${r.id} (${r.status})` }))]} />
            <button className="btn btn--teal" onClick={compare} disabled={cmpBusy || !selA || !selB}>مقایسه</button>
          </div>
          {cmpErr && <div className="alert alert--error mt-1">{cmpErr}</div>}
          {cmp && <RunComparisonView cmp={cmp} />}
        </Card>
      </div>
    </AppShell>
  );
}

function RunComparisonView({ cmp }: { cmp: RunComparison }) {
  return (
    <div className="mt-2 stack">
      <div className="grid grid-2">
        <div className="card" style={{ padding: 14 }}>
          <div className="row"><strong>الف</strong> <span className="ltr">#{cmp.a.run_id}</span> <StatusBadge status={cmp.a.status} /></div>
          <div className="small muted ltr">امتیاز: {cmp.a.objective_score != null ? Number(cmp.a.objective_score).toFixed(3) : "—"} {cmp.a.stale && "· کهنه"}</div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <div className="row"><strong>ب</strong> <span className="ltr">#{cmp.b.run_id}</span> <StatusBadge status={cmp.b.status} /></div>
          <div className="small muted ltr">امتیاز: {cmp.b.objective_score != null ? Number(cmp.b.objective_score).toFixed(3) : "—"} {cmp.b.stale && "· کهنه"}</div>
        </div>
      </div>

      {cmp.score_delta != null && (
        <Alert kind={cmp.score_delta >= 0 ? "ok" : "warn"}>
          تفاوت امتیاز: <strong className="ltr">{Number(cmp.score_delta).toFixed(3)}</strong>
        </Alert>
      )}

      <div>
        <h3>تغییرات زمان‌بندی ({cmp.schedule_changes.length})</h3>
        {cmp.schedule_changes.length === 0 ? <p className="muted small">تغییری در زمان‌بندی نیست.</p> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>دستگاه</th><th>ظرفیت</th><th>نوع تغییر</th><th>الف</th><th>ب</th></tr></thead>
              <tbody>
                {cmp.schedule_changes.map((c, i) => {
                  const any = c as any;
                  const fmt = (v: unknown) => {
                    if (!Array.isArray(v)) return "—";
                    const [wd, s, e, res] = v;
                    return [weekdayLabel(wd ?? null), `${formatTime(s ?? null)}–${formatTime(e ?? null)}`, res ?? "—"].join(" ");
                  };
                  return (
                    <tr key={i}>
                      <td className="ltr">#{any.offering_id}</td>
                      <td className="ltr">#{any.occurrence_no}</td>
                      <td><Badge tone={any.change === "moved" ? "info" : any.change === "removed_in_b" ? "bad" : "ok"}>{any.change}</Badge></td>
                      <td className="small">{fmt(any.a)}</td>
                      <td className="small">{fmt(any.b)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {cmp.unresolved_warnings.length > 0 && (
        <div>
          <h3>هشدارهای حل‌نشده</h3>
          <ul className="small">
            {cmp.unresolved_warnings.map((w, i) => <li key={i} className="ltr">{(w as any).code ?? "کد ناشناخته"} · {(w as any).message ?? ""}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------- Detail ----------------
export function RunDetailPage() {
  const { runId } = useParams();
  const id = Number(runId);
  const runQ = useQuery(() => Solver.run(id), [id]);
  const corrQ = useQuery(() => Corrections.list(), []);

  if (runQ.loading) return <AppShell title="اجرا"><Loading /></AppShell>;
  if (runQ.error || !runQ.data) {
    return <AppShell title="اجرا"><ErrorState message={runQ.error ?? "اجرا یافت نشد"} onRetry={runQ.reload} /></AppShell>;
  }
  const d = runQ.data;
  const resourceLabel = (rid: number | null) => rid ?? "—";

  const assignCols: Column<SolverAssignment>[] = [
    { key: "offering", header: "دستگاه", render: (a) => <span className="ltr">#{a.offering_id}</span> },
    { key: "occ", header: "ظرفیت", render: (a) => <span className="ltr">#{a.occurrence_no}</span> },
    { key: "weekday", header: "روز", render: (a) => weekdayLabel(a.weekday) },
    { key: "time", header: "زمان", render: (a) => <span className="ltr">{formatTime(a.start_hhmm)}–{formatTime(a.end_hhmm)}</span> },
    { key: "resource", header: "منبع", render: (a) => <span className="ltr">{resourceLabel(a.resource_id)}</span> },
  ];

  return (
    <AppShell title={"اجرا #" + id}>
      <div className="row row-between">
        <div>
          <h1 style={{ margin: 0 }}>اجرا <span className="ltr">#{d.run.id}</span></h1>
          <p className="muted small">چرخه: <span className="ltr">#{d.run.cycle_id}</span> · <JalaliDate value={d.run.created_at} time /></p>
        </div>
        <div className="row row-wrap">
          <StatusBadge status={d.run.status} />
          {d.run.stale && <Badge tone="warn">کهنه</Badge>}
          {d.run.stale_reason && <span className="small muted">{d.run.stale_reason}</span>}
          {d.run.status === "FEASIBLE" && !d.run.stale && (
            <div className="row btn-row">
              <button
                className="btn btn--sm"
                title="Excel (.xlsx)"
                onClick={() => Export.excel(d.run.id)}
              >
                📘 Excel
              </button>
              <button
                className="btn btn--sm"
                title="PDF"
                onClick={() => Export.pdf(d.run.id)}
              >
                📄 PDF
              </button>
            </div>
          )}
        </div>
      </div>

      {d.run.objective_score != null && (
        <div className="mt-1"><Alert kind="info">امتیاز هدف: <strong className="ltr">{Number(d.run.objective_score).toFixed(3)}</strong></Alert></div>
      )}

      <div className="grid grid-2 mt-2">
        <Card title={`تخصیص‌ها (${d.assignments.length})`}>
          {d.assignments.length === 0 ? <EmptyState title="تخصیسی ثبت نشده است" /> :
            <DataTable columns={assignCols} rows={d.assignments} rowKey={(a) => a.id} empty="موردی ندارد" />}
        </Card>

        <div className="stack">
          <Card title="مخزن ورودی / خروجی">
            <div className="small muted ltr" style={{ maxHeight: 260, overflow: "auto", direction: "ltr" }}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {JSON.stringify({ input: d.input_snapshot, result: d.result_snapshot }, null, 2)}
              </pre>
            </div>
          </Card>
          <Card title={`اصلاح‌های مدیر (${corrQ.data?.length ?? 0})`}>
            {(corrQ.data?.length ?? 0) === 0 ? <EmptyState title="اصلاحی ثبت نشده است" /> :
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>فیلد</th><th>از</th><th>به</th><th>دلیل</th></tr></thead>
                  <tbody>
                    {(corrQ.data ?? []).slice(0, 10).map((c) => (
                      <tr key={c.id}>
                        <td className="ltr">{c.field}</td>
                        <td className="small ltr">{c.before_value ?? "—"}</td>
                        <td className="small ltr">{c.after_value ?? "—"}</td>
                        <td className="small">{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            }
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
