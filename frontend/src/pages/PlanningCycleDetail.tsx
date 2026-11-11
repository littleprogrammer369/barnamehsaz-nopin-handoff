/** Planning cycle detail: header, linked units, offerings, preflight. */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Cycles, CycleUnits, Units, Offerings, Preflight } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, StatusBadge, Alert,
  JalaliDate, PreflightBlockerList,
} from "../components/ui";

export function PlanningCycleDetail() {
  const { cycleId } = useParams();
  const id = Number(cycleId);
  const cycleQ = useQuery(() => Cycles.get(id), [id]);
  const cuQ = useQuery(() => CycleUnits.list(id), [id]);
  const unitsQ = useQuery(() => Units.list(), []);
  const offeringsQ = useQuery(() => Offerings.list(id), [id]);
  const pfQ = useQuery(() => Preflight.run(id), [id]);
  const [tab, setTab] = useState<"units" | "offerings" | "preflight">("preflight");

  if (cycleQ.loading) return <AppShell title="چرخه"><Loading /></AppShell>;
  if (cycleQ.error || !cycleQ.data) {
    return <AppShell title="چرخه"><ErrorState message={cycleQ.error ?? "چرخه یافت نشد"} onRetry={cycleQ.reload} /></AppShell>;
  }

  const cycle = cycleQ.data;
  const unitById = new Map((unitsQ.data ?? []).map((u) => [u.id, u]));
  const cycUnits = (cuQ.data ?? []).map((cu) => ({ ...cu, unit: unitById.get(cu.unit_id) }));

  return (
    <AppShell title={`چرخه: ${cycle.name}`}>
      <div className="row row-between">
        <div>
          <h1 style={{ margin: 0 }}>{cycle.name}</h1>
          <p className="muted small">
            ترم: <strong>{cycle.term || "—"}</strong>
            <span className="tag" style={{ marginInline: 8 }}><StatusBadge status={cycle.status} /></span>
            <span>آغاز: <JalaliDate value={cycle.start_date} /></span>
          </p>
        </div>
        <Link to={`/cycles/${id}/solve`} className="btn btn--teal">حل / پیش‌پرواز</Link>
      </div>

      <div className="row row-wrap mt-2" role="tablist">
        <button className={`btn btn--sm ${tab === "preflight" ? "btn--teal" : "btn--ghost"}`} onClick={() => setTab("preflight")}>پیش‌پرواز</button>
        <button className={`btn btn--sm ${tab === "units" ? "btn--teal" : "btn--ghost"}`} onClick={() => setTab("units")}>واحدها</button>
        <button className={`btn btn--sm ${tab === "offerings" ? "btn--teal" : "btn--ghost"}`} onClick={() => setTab("offerings")}>دستگاه‌ها</button>
      </div>

      {tab === "preflight" && (
        <div className="mt-2">
          <Card title="چک‌های پیش‌پرواز">
            {pfQ.loading ? <Loading /> :
              pfQ.error ? <ErrorState message={pfQ.error} onRetry={pfQ.reload} /> :
              <>
                <PreflightBlockerList blockers={pfQ.data!.blockers} warnings={pfQ.data!.warnings} />
                <div className="mt-2">
                  {pfQ.data!.can_submit
                    ? <Alert kind="ok">همهٔ چک‌ها پاک است — چرخه آمادهٔ حل و انتشار است.</Alert>
                    : <Alert kind="warn">موانع وجود دارد؛ ابتدا آن‌ها را برطرف کنید تا بتوانید حل / انتشار انجام دهید.</Alert>}
                </div>
              </>}
          </Card>
        </div>
      )}

      {tab === "units" && (
        <div className="mt-2">
          <Card title="واحدهای متصل">
            {cuQ.loading ? <Loading /> :
              (cuQ.data?.length ?? 0) === 0 ? <EmptyState title="واحدی به این چرخه متصل نیست" action={<Link to="/cycles" className="btn btn--teal btn--sm">مدیریت</Link>} /> :
              (
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th>واحد</th><th>کد</th><th>کاربر مسئول</th></tr></thead>
                    <tbody>
                      {cycUnits.map((cu) => (
                        <tr key={cu.id}>
                          <td>{cu.unit?.name ?? cu.unit_id}</td>
                          <td className="ltr">{cu.unit?.code ?? "—"}</td>
                          <td>{cu.responsible_user_id ? <span className="ltr">#{cu.responsible_user_id}</span> : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </Card>
        </div>
      )}

      {tab === "offerings" && (
        <div className="mt-2">
          <Card title={`دستگاه‌های این چرخه (${offeringsQ.data?.length ?? 0})`}>
            {offeringsQ.loading ? <Loading /> :
              offeringsQ.error ? <ErrorState message={offeringsQ.error} onRetry={offeringsQ.reload} /> :
              (offeringsQ.data?.length ?? 0) === 0 ? <EmptyState title="دستگاهی ثبت نشده است" action={<Link to={`/offerings`} className="btn btn--teal btn--sm">افزودن دستگاه</Link>} /> :
              (
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th>دستگاه</th><th>جلسات/هفته</th><th>دوره (دقیقه)</th><th>ظرفیت</th></tr></thead>
                    <tbody>
                      {(offeringsQ.data ?? []).map((o) => (
                        <tr key={o.id}>
                          <td><Link to={`/offerings/${o.id}`}>#{o.id} — {o.section ?? "—"}</Link></td>
                          <td>{o.meetings_per_week}</td>
                          <td>{o.duration_minutes}</td>
                          <td>{o.required_room_capacity ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
