/**
 * Offerings: list + detail + shared-offering approvals + meeting requirements.
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import {
  Offerings as OfferingsClient, OfferingUnits, OfferingCohorts, Units, Cohorts,
  Courses, SharedOfferings, Cycles,
} from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, StatusBadge,
  SelectInput, InputField, Badge,
} from "../components/ui";
import { toNumber } from "../lib/digits";

// ---------------- List page ----------------
export function Offerings() {
  const coursesQ = useQuery(() => Courses.list(), []);
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const [form, setForm] = useState({ cycle_id: 0, course_id: 0, section: "", meetings: 2, duration: 90, capacity: "" });
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const offerQ = useQuery(() => OfferingsClient.list(), [reload]);
  const all = offerQ.data ?? [];

  async function onCreate() {
    if (!form.cycle_id || !form.course_id) { setErr("چرخه و دستگاه را انتخاب کنید."); return; }
    setBusy(true); setErr(null);
    try {
      await OfferingsClient.create({
        course_id: form.course_id,
        planning_cycle_id: form.cycle_id,
        section: form.section || null,
        meetings_per_week: form.meetings,
        duration_minutes: form.duration,
        required_room_capacity: form.capacity ? toNumber(form.capacity) : null,
      });
      setFlash("دستگاه ایجاد شد.");
      setReload((n) => n + 1);
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ایجاد دستگاه ناموفق بود."); }
    finally { setBusy(false); setFlash(null); }
  }

  return (
    <AppShell title="دستگاه‌ها">
      <h1>دستگاه‌ها</h1>
      <div className="grid grid-2 mt-2">
        <Card title={`فهرست (${all.length})`}>
          {offerQ.loading ? <Loading /> :
            offerQ.error ? <ErrorState message={offerQ.error} onRetry={offerQ.reload} /> :
            all.length === 0 ? <EmptyState title="دستگاهی ثبت نشده است" /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>دستگاه</th><th>دوره</th><th>جلسات/هفته</th><th>دوره (دقیقه)</th><th></th></tr></thead>
                  <tbody>
                    {all.map((o) => (
                      <tr key={o.id}>
                        <td><Link to={`/offerings/${o.id}`}>#{o.id} {o.section ?? ""}</Link></td>
                        <td className="ltr">{(coursesQ.data ?? []).find((c) => c.id === o.course_id)?.code ?? o.course_id}</td>
                        <td>{o.meetings_per_week}</td>
                        <td>{o.duration_minutes}</td>
                        <td><Link className="btn btn--ghost btn--sm" to={`/offerings/${o.id}`}>جزئیات</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        <div>
          <Card title="افزودن دستگاه">
            {flash && <div className="alert alert--ok" style={{ marginBottom: 10 }}>{flash}</div>}
            {err && <div className="alert alert--error" style={{ marginBottom: 10 }}>{err}</div>}
            <SelectInput label="چرخه برنامه‌ریزی" value={form.cycle_id}
              onChange={(e) => setForm((f) => ({ ...f, cycle_id: Number(e.target.value) }))}
              options={[
                { value: 0, label: "— انتخاب —" },
                ...(cyclesQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
              ]} />
            <SelectInput label="دوره (Course)" value={form.course_id}
              onChange={(e) => setForm((f) => ({ ...f, course_id: Number(e.target.value) }))}
              options={[
                { value: 0, label: "— انتخاب —" },
                ...(coursesQ.data ?? []).map((c) => ({ value: c.id, label: `${c.code} — ${c.title}` })),
              ]} />
            <div className="grid grid-3">
              <InputField label="بخش / سکشن" value={form.section}
                onChange={(e) => setForm((f) => ({ ...f, section: e.target.value }))} />
              <InputField label="جلسات/هفته" type="number" min={1} value={form.meetings}
                onChange={(e) => setForm((f) => ({ ...f, meetings: toNumber(e.target.value) }))} />
              <InputField label="دوره (دقیقه)" type="number" min={30} value={form.duration}
                onChange={(e) => setForm((f) => ({ ...f, duration: toNumber(e.target.value) }))} />
            </div>
            <InputField label="ظرفیت کلاس (اختیاری)" type="number" min={0} value={form.capacity}
              onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))} />
            <button className="btn btn--teal" disabled={busy || !form.cycle_id || !form.course_id} onClick={onCreate}>
              {busy ? "در حال ایجاد…" : "ایجاد"}
            </button>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

// ---------------- Detail page ----------------
export function OfferingDetail() {
  const { offeringId } = useParams();
  const id = Number(offeringId);
  const oQ = useQuery(() => OfferingsClient.get(id), [id]);
  const unitsQ = useQuery(() => OfferingUnits.list(id), [id]);
  const cohortsQ = useQuery(() => OfferingCohorts.list(id), [id]);
  const allUnitsQ = useQuery(() => Units.list(), []);
  const allCohortsQ = useQuery(() => Cohorts.list(), []);
  const approvalsQ = useQuery(() => SharedOfferings.listApprovals(id), [id]);

  const [newUnit, setNewUnit] = useState({ unit_id: 0, enrollment: "" });
  const [newCohort, setNewCohort] = useState({ cohort_id: 0, enrollment: "" });
  const [approval, setApproval] = useState<{ unit_id: number; status: "unit_approved" | "needs_changes"; comment: string }>({
    unit_id: 0,
    status: "unit_approved",
    comment: "",
  });
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (oQ.loading) return <AppShell title="دستگاه"><Loading /></AppShell>;
  if (oQ.error || !oQ.data) {
    return <AppShell title="دستگاه"><ErrorState message={oQ.error ?? "دستگاه یافت نشد"} onRetry={oQ.reload} /></AppShell>;
  }
  const offering = oQ.data;
  const unitLabel = (uid: number) => (allUnitsQ.data ?? []).find((u) => u.id === uid)?.name ?? uid;
  const cohortLabel = (cid: number) => (allCohortsQ.data ?? []).find((c) => c.id === cid)?.name ?? cid;

  const isShared = (unitsQ.data?.length ?? 0) > 1;

  async function onAddUnit() {
    if (!newUnit.unit_id) { setErr("واحد را انتخاب کنید."); return; }
    setBusy(true); setErr(null);
    try {
      await OfferingUnits.add(id, { unit_id: newUnit.unit_id, expected_enrollment: toNumber(newUnit.enrollment) || 0 });
      unitsQ.reload(); setFlash("واحد به دستگاه متصل شد."); setErr(null);
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "اتصال واحد ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function onRecordApproval() {
    if (!approval.unit_id) { setErr("واحد دخیل را مشخص کنید."); return; }
    setBusy(true); setErr(null); setFlash(null);
    try {
      await SharedOfferings.record(id, { status: approval.status, unit_id: approval.unit_id, comment: approval.comment || null });
      approvalsQ.reload(); setFlash("تأیید ثبت شد.");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ثبت تأیید ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function onFinalize(decision: "approve" | "return") {
    setBusy(true); setErr(null);
    try {
      const out = await SharedOfferings.finalize(id, { decision, reason: decision === "return" ? "بازگشت برای اصلاح" : null });
      approvalsQ.reload();
      setFlash(out.outcome === "approved" ? "دستگاه مشترک نهایی‌سازی و تأیید شد." : "تأییدها به حالت در انتظار بازگشت.");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "نهایی‌سازی ناموفق بود."); }
    finally { setBusy(false); }
  }

  return (
    <AppShell title={`دستگاه #${id}`}>
      <div className="row row-between">
        <div>
          <h1 style={{ margin: 0 }}>دستگاه #{id} {offering.section ? `— ${offering.section}` : ""}</h1>
          <p className="muted small">
            جلسات/هفته: <strong>{offering.meetings_per_week}</strong> ·
            دوره: <strong>{offering.duration_minutes}</strong> دقیقه ·
            ظرفیت: <strong>{offering.required_room_capacity ?? "—"}</strong>
          </p>
          {isShared && <Badge tone="info">دستگاه مشترک (چند واحد)</Badge>}
        </div>
      </div>

      {flash && <div className="alert alert--ok mt-1">{flash}</div>}
      {err && <div className="alert alert--error mt-1">{err}</div>}

      <div className="grid grid-2 mt-2">
        <Card title={`واحدهای دخیل (${unitsQ.data?.length ?? 0})`}>
          {unitsQ.loading ? <Loading /> :
            (unitsQ.data?.length ?? 0) === 0 ? <EmptyState title="واحدی متصل نیست" /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>واحد</th><th>دانشجوی مورد انتظار</th><th>اتاق</th><th>دبیر</th></tr></thead>
                  <tbody>
                    {(unitsQ.data ?? []).map((ou) => (
                      <tr key={ou.id}>
                        <td>{unitLabel(ou.unit_id)}</td>
                        <td>{ou.expected_enrollment}</td>
                        <td>{ou.room_resource_id ?? "—"}</td>
                        <td>{ou.instructor_resource_id ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          <div className="grid grid-2 mt-2" style={{ alignItems: "end" }}>
            <SelectInput label="اتصال واحد" value={newUnit.unit_id}
              onChange={(e) => setNewUnit((s) => ({ ...s, unit_id: Number(e.target.value) }))}
              options={[
                { value: 0, label: "— انتخاب —" },
                ...(allUnitsQ.data ?? []).map((u) => ({ value: u.id, label: u.name })),
              ]} />
            <div className="row" style={{ alignItems: "flex-end" }}>
              <InputField label="دانشجوی مورد انتظار" type="number" min={0} value={newUnit.enrollment}
                onChange={(e) => setNewUnit((s) => ({ ...s, enrollment: e.target.value }))} />
              <button className="btn btn--teal" onClick={onAddUnit} disabled={busy || !newUnit.unit_id}>اتصال</button>
            </div>
          </div>
        </Card>

        <Card title={`گروه‌های آموزشی (${cohortsQ.data?.length ?? 0})`}>
          {cohortsQ.loading ? <Loading /> :
            (cohortsQ.data?.length ?? 0) === 0 ? <EmptyState title="گروهی متصل نیست" /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>گروه</th><th>دانشجوی مورد انتظار</th></tr></thead>
                  <tbody>
                    {(cohortsQ.data ?? []).map((oc) => (
                      <tr key={oc.id}><td>{cohortLabel(oc.cohort_id)}</td><td>{oc.expected_enrollment}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          <div className="grid grid-2 mt-2" style={{ alignItems: "end" }}>
            <SelectInput label="اتصال گروه" value={newCohort.cohort_id}
              onChange={(e) => setNewCohort((s) => ({ ...s, cohort_id: Number(e.target.value) }))}
              options={[
                { value: 0, label: "— انتخاب —" },
                ...(allCohortsQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
              ]} />
            <div className="row" style={{ alignItems: "flex-end" }}>
              <InputField label="دانشجوی مورد انتظار" type="number" min={0} value={newCohort.enrollment}
                onChange={(e) => setNewCohort((s) => ({ ...s, enrollment: e.target.value }))} />
              <button className="btn btn--teal" disabled={busy || !newCohort.cohort_id}
                onClick={async () => {
                  setBusy(true); setErr(null);
                  try { await OfferingCohorts.add(id, { cohort_id: newCohort.cohort_id, expected_enrollment: toNumber(newCohort.enrollment) || 0 }); cohortsQ.reload(); }
                  catch (e2) { setErr(e2 instanceof Error ? e2.message : null); }
                  finally { setBusy(false); }
                }}>اتصال</button>
            </div>
          </div>
        </Card>

        {isShared && (
          <Card title="تأییدهای دستگاه مشترک" actions={<Badge tone={(approvalsQ.data?.length ?? 0) === (unitsQ.data?.length ?? 0) ? "ok" : "warn"}>تأییدشده: {(approvalsQ.data ?? []).length} از {unitsQ.data?.length}</Badge>}>
            {approvalsQ.loading ? <Loading /> : (approvalsQ.data?.length ?? 0) === 0 ? <EmptyState title="تأییدی ثبت نشده است" /> : (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>واحد</th><th>وضعیت</th><th>یادداشت</th></tr></thead>
                  <tbody>
                    {(approvalsQ.data ?? []).map((a) => (
                      <tr key={a.id}>
                        <td>{unitLabel(a.unit_id)}</td>
                        <td><StatusBadge status={a.status} /></td>
                        <td>{a.comment ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="grid grid-3 mt-2" style={{ alignItems: "end" }}>
              <SelectInput label="واحد دخیل" value={approval.unit_id}
                onChange={(e) => setApproval((s) => ({ ...s, unit_id: Number(e.target.value) }))}
                options={[
                  { value: 0, label: "— انتخاب —" },
                  ...(unitsQ.data ?? []).map((ou) => ({ value: ou.unit_id, label: unitLabel(ou.unit_id) })),
                ]} />
              <SelectInput label="تصمیم" value={approval.status}
                onChange={(e) => setApproval((s) => ({ ...s, status: e.target.value as "unit_approved" | "needs_changes" }))}
                options={[
                  { value: "unit_approved", label: "تأیید واحد" },
                  { value: "needs_changes", label: "نیاز به تغییر" },
                ]} />
              <button className="btn btn--teal" onClick={onRecordApproval} disabled={busy || !approval.unit_id}>ثبت تأیید</button>
            </div>
            <div className="row mt-2">
              <button className="btn btn--teal" onClick={() => onFinalize("approve")} disabled={busy}>نهایی‌سازی و تأیید</button>
              <button className="btn btn--ghost" onClick={() => onFinalize("return")} disabled={busy}>بازگشت برای اصلاح</button>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
