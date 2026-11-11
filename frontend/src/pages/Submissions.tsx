/**
 * Submissions list + wizard + review (revisions, comments, lifecycle).
 * 03: «درخواست: با ویزارد چندمرحله‌ای… ذخیرهٔ پیش‌نویس قابل بازنگری».
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Submissions as SubClient, Wizard, Cycles, Units } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, StatusBadge,
  SelectInput, InputField, TextArea, JalaliDate,
} from "../components/ui";
import { useAuth } from "../lib/auth";

// ---------------- List ----------------
export function Submissions() {
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const unitsQ = useQuery(() => Units.list(), []);
  const [cycleFilter, setCycleFilter] = useState(0);
  const [reload, setReload] = useState(0);
  const subQ = useQuery(() => SubClient.list(cycleFilter || undefined), [cycleFilter, reload]);

  const unitLabel = (uid: number) => (unitsQ.data ?? []).find((u) => u.id === uid)?.name ?? uid;
  const cycleLabel = (cid: number) => (cyclesQ.data ?? []).find((c) => c.id === cid)?.name ?? cid;

  return (
    <AppShell title="درخواست‌ها">
      <div className="row row-between">
        <h1 style={{ margin: 0 }}>درخواست‌ها</h1>
        <SelectInput label="فیلتر بر اساس چرخه" value={cycleFilter}
          onChange={(e) => { setCycleFilter(Number(e.target.value)); setReload((n) => n + 1); }}
          options={[
            { value: 0, label: "همهٔ چرخه‌ها" },
            ...(cyclesQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
          ]} />
      </div>

      <div className="mt-2">
        <Card>
          {subQ.loading ? <Loading /> :
            subQ.error ? <ErrorState message={subQ.error} onRetry={subQ.reload} /> :
            (subQ.data?.length ?? 0) === 0
              ? <EmptyState title="درخواستی ثبت نشده است" hint="با ویزارد، درخواست برای یک چرخه و واحد بسازید." action={<Link to="/cycles" className="btn btn--teal btn--sm">انتخاب چرخه</Link>} />
              : (
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th>درخواست</th><th>چرخه</th><th>واحد</th><th>وضعیت</th><th>نسخه</th><th>قفل</th><th></th></tr></thead>
                    <tbody>
                      {(subQ.data ?? []).map((s) => (
                        <tr key={s.id}>
                          <td><Link to={`/submissions/${s.id}`} className="ltr">#{s.id}</Link></td>
                          <td>{cycleLabel(s.cycle_id)}</td>
                          <td>{unitLabel(s.unit_id)}</td>
                          <td><StatusBadge status={s.status} /></td>
                          <td className="ltr">v{s.version}</td>
                          <td>{s.locked ? "قفل" : "—"}</td>
                          <td><Link className="btn btn--ghost btn--sm" to={`/submissions/${s.id}`}>ویژارد / بازبینی</Link></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
        </Card>
      </div>
    </AppShell>
  );
}

// ---------------- Wizard / Review ----------------
export function SubmissionWizard() {
  const { submissionId } = useParams();
  const id = Number(submissionId);
  const auth = useAuth();

  const subQ = useQuery(() => SubClient.get(id), [id]);
  const revQ = useQuery(() => SubClient.revisions(id), [id]);
  const comQ = useQuery(() => SubClient.listComments(id), [id]);
  const draftQ = useQuery(
    () => (subQ.data ? Wizard.get(subQ.data.cycle_id, subQ.data.unit_id) : Promise.resolve(null)),
    [subQ.data?.cycle_id, subQ.data?.unit_id],
  );

  const [snap, setSnap] = useState("");
  const [comment, setComment] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (subQ.loading) return <AppShell title="درخواست"><Loading /></AppShell>;
  if (subQ.error || !subQ.data) {
    return <AppShell title="درخواست"><ErrorState message={subQ.error ?? "درخواست یافت نشد"} onRetry={subQ.reload} /></AppShell>;
  }
  const sub = subQ.data;
  const revisions = (revQ.data ?? []).slice().reverse();
  const comments = comQ.data ?? [];
  const myRole = auth.role;
  const canSubmit = sub.status === "draft" || sub.status === "needs_changes";
  const canAdmin = myRole === "admin";

  async function saveDraft() {
    setBusy(true); setErr(null); setFlash(null);
    try {
      await Wizard.upsert({
        cycle_id: sub.cycle_id,
        unit_id: sub.unit_id,
        section_state: snap ? { snapshot: snap } : null,
        completed: false,
      });
      setFlash("پیش‌نویس ذخیره شد.");
      draftQ.reload();
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ذخیره پیش‌نویس ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function doSubmit() {
    setBusy(true); setErr(null); setFlash(null);
    try {
      await SubClient.submit(sub.id, { expected_version: sub.version, input_snapshot: snap ? { snapshot: snap } : null });
      subQ.reload();
      await Wizard.upsert({ cycle_id: sub.cycle_id, unit_id: sub.unit_id, completed: true });
      setFlash("درخواست ارسال و قفل شد.");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ارسال ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function doNeedsChanges() {
    if (reason.trim().length < 3) { setErr("دلیل (حداقل ۳ نویسه) الزامی است."); return; }
    setBusy(true); setErr(null); setFlash(null);
    try {
      await SubClient.needsChanges(sub.id, { reason: reason.trim(), expected_version: sub.version });
      subQ.reload(); setFlash("درخواست به حالت «نیاز به تغییر» بازگشت.");
      setReason("");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function doApprove() {
    setBusy(true); setErr(null); setFlash(null);
    try {
      await SubClient.approve(sub.id, { expected_version: sub.version });
      subQ.reload(); setFlash("درخواست تأیید و قفل شد.");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "تأیید ناموفق بود."); }
    finally { setBusy(false); }
  }

  async function addComment() {
    if (comment.trim().length < 2) { setErr("نظرات حداقل ۲ نویسه دارند."); return; }
    setBusy(true); setErr(null);
    try {
      await SubClient.addComment(sub.id, { text: comment.trim(), target: "submission" });
      comQ.reload(); setComment(""); setFlash("نظر ثبت شد.");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : "ثبت نظر ناموفق بود."); }
    finally { setBusy(false); }
  }

  return (
    <AppShell title={"درخواست #" + id}>
      <div className="row row-between">
        <div>
          <h1 style={{ margin: 0 }}>درخواست <span className="ltr">#{id}</span></h1>
          <p className="muted small">نسخهٔ فعلی: <span className="ltr">v{sub.version}</span> {sub.locked && "· قفل"}</p>
        </div>
        <StatusBadge status={sub.status} />
      </div>

      {flash && <div className="alert alert--ok mt-1">{flash}</div>}
      {err && <div className="alert alert--error mt-1">{err}</div>}

      <div className="grid grid-2 mt-2">
        <Card title="داده / پیش‌نویس" actions={<button className="btn btn--ghost btn--sm" onClick={saveDraft} disabled={busy}>ذخیره پیش‌نویس</button>}>
          <TextArea label="عکس‌برداری داده (JSON / متن)" hint="این مقدار در نسخه‌ها (revisions) و پیش‌پرواز ثبت می‌شود."
            value={snap || ((draftQ.data?.section_state as Record<string, any> | null)?.snapshot ?? "")} onChange={(e) => setSnap(e.target.value)} />
          <div className="small muted">کلیدهای پیش‌نویس ذخیره‌شده: {(draftQ.data?.section_state ? Object.keys(draftQ.data.section_state).length : 0)}</div>
        </Card>

        <Card title="اقدامات چرخهٔ عمر">
          <div className="stack">
            {canSubmit && (
              <div className="row">
                <button className="btn btn--teal" onClick={doSubmit} disabled={busy}>ارسال درخواست</button>
                <span className="small muted">پس از ارسال، قفل و قابل بازبینی مدیر می‌شود.</span>
              </div>
            )}
            {canAdmin && sub.status === "submitted" && (
              <div className="stack">
                <div className="row row-wrap">
                  <button className="btn" onClick={doApprove} disabled={busy}>تأیید</button>
                  <button className="btn btn--ghost" onClick={doNeedsChanges} disabled={busy}>بازگشت به اصلاح</button>
                </div>
                <InputField label="دلیل بازگشت / نظر" value={reason} onChange={(e) => setReason(e.target.value)} />
              </div>
            )}
            <div className="divider" />
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div style={{ flex: 1 }}>
                <InputField label="نظر (بدون تغییر وضعیت)" value={comment} onChange={(e) => setComment(e.target.value)} />
              </div>
              <button className="btn btn--ghost btn--sm" onClick={addComment} disabled={busy}>ثبت</button>
            </div>
          </div>
        </Card>

        <Card title={"تاریخچهٔ نسخه‌ها (" + revisions.length + ")"}>
          {revisions.length === 0 ? <EmptyState title="نسخه‌ای ثبت نشده است" /> : (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>شماره</th><th>مخزن داده</th></tr></thead>
                <tbody>
                  {revisions.map((r) => (
                    <tr key={r.id}>
                      <td className="ltr">#{r.revision_no}</td>
                      <td className="small muted ltr">{r.input_snapshot ? ("تغییر داده — کلیدها: " + Object.keys(r.input_snapshot).length) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title={"نظرات (" + comments.length + ")"}>
          {comments.length === 0 ? <EmptyState title="نظری ثبت نشده است" /> : (
            <ul className="timeline">
              {comments.map((c) => (
                <li key={c.id}>
                  <span className="tl-dot" />
                  <div>
                    <div>{c.text}</div>
                    <div className="small faint"><JalaliDate value={c.created_at ?? undefined} time /> · نویسنده: <span className="ltr">{c.actor_user_id ?? "—"}</span></div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
