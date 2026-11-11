/**
 * Solver: trigger a global solve for a cycle. Gated by preflight.
 * 03: «حل: اجرای Solver و نمایش وضعیت solver_status به‌صورت خوانا».
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Solver, Cycles } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { ApiError } from "../lib/api";
import {
  Card, Alert, PreflightBlockerList, SelectInput, Badge, StatusBadge,
} from "../components/ui";
import type { SolveResult } from "../lib/types";

export function SolverPage() {
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const [cycleId, setCycleId] = useState<number>(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  async function runSolve() {
    if (!cycleId) { setErr("یک چرخه انتخاب کنید."); return; }
    setBusy(true); setErr(null); setFlash(null);
    try {
      const r = await Solver.solve({ cycle_id: cycleId });
      setResult(r);
      if (r.can_publish) setFlash("اجرا موفق و قابل‌انتشار است.");
    } catch (e2) {
      // 409 PREFLIGHT_BLOCKED carries the blocker list in detail
      if (e2 instanceof ApiError && e2.status === 409) {
        const d = (e2.detail as any)?.detail;
        if (d && Array.isArray(d.blockers)) {
          setErr("حل به‌دلیل موانع پیش‌پرواز مسدود است.");
          setResult({
            run_id: -1, cycle_id: cycleId, status: "data_gaps",
            objective_score: null, stale: false, can_publish: false,
            blockers: d.blockers, warnings: d.warnings ?? [], infeasible_causes: [],
          });
        } else {
          setErr(e2.message);
        }
      } else {
        setErr(e2 instanceof Error ? e2.message : "اجرای حل ناموفق بود.");
      }
    } finally { setBusy(false); }
  }

  return (
    <AppShell title="حل‌کننده (Solver)">
      <h1>حل‌کنندهٔ جهانی</h1>
      <p className="muted small">حل، ابتدا پیش‌پرواز را اجرا می‌کند؛ موانع، اجرای Solver را مسدود می‌کنند.</p>

      <div className="row row-between mt-2">
        <SelectInput label="چرخه" value={cycleId}
          onChange={(e) => { setCycleId(Number(e.target.value)); setResult(null); }}
          options={[
            { value: 0, label: "— انتخاب —" },
            ...(cyclesQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
          ]} />
        <button className="btn btn--teal" onClick={runSolve} disabled={busy || !cycleId}>
          {busy ? "در حال حل…" : "اجرای حل"}
        </button>
      </div>

      {flash && <div className="alert alert--ok mt-2">{flash}</div>}
      {err && <div className="alert alert--error mt-2">{err}</div>}

      {result && (
        <div className="mt-2">
          <Card title={"نتیجهٔ اجرای " + result.run_id}>
            <div className="row row-wrap">
              <StatusBadge status={result.status} />
              {result.stale && <Badge tone="warn">کهنه</Badge>}
              {result.can_publish && <Badge tone="ok">قابل‌انتشار</Badge>}
              <span className="small muted">امتیاز هدف: <strong className="ltr">{result.objective_score != null ? Number(result.objective_score).toFixed(3) : "—"}</strong></span>
            </div>
            {result.infeasible_causes.length > 0 && (
              <div className="mt-2">
                <h3>دلایل مجاز نبودن</h3>
                <ul className="small">
                  {result.infeasible_causes.map((c, i) => <li key={i} className="ltr">{(c as any).code ?? "دلیل نامشخص"}: {(c as any).message ?? ""}</li>)}
                </ul>
              </div>
            )}
            <div className="mt-2">
              <h3>موانع / هشدارها</h3>
              <PreflightBlockerList blockers={result.blockers} warnings={result.warnings} />
            </div>
            {result.can_publish && (
              <div className="row mt-2">
                <Link to={`/runs/${result.run_id}`} className="btn">مشاهدهٔ جزئیات اجرا</Link>
                <Alert kind="ok">برای انتشار، نسخهٔ قابل‌ردیابی را با جزئیات اجرا ثبت کنید.</Alert>
              </div>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
