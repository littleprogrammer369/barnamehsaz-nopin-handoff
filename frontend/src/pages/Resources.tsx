/**
 * Resources: rooms & instructors list + per-resource availability windows.
 */
import { useState } from "react";
import { AppShell } from "../layouts/AppShell";
import { Resources as ResourcesClient, ResourceAvailabilityClient, Cycles } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, EmptyState, DataTable, Column, SelectInput, InputField,
} from "../components/ui";
import { WEEKDAYS, weekdayLabel, formatTime } from "../lib/persian";
import { toNumber } from "../lib/digits";
import type { Resource, ResourceKind, ResourceAvailability as RA } from "../lib/types";

export function Resources() {
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const [kind, setKind] = useState<ResourceKind>("room");
  const resQ = useQuery(() => ResourcesClient.list(kind), [kind]);

  const [sel, setSel] = useState<Resource | null>(null);
  const availQ = useQuery(
    () => (sel ? ResourceAvailabilityClient.list(sel.id, (cyclesQ.data?.[0])?.id) : Promise.resolve([])),
    [sel?.id, cyclesQ.data?.[0]?.id],
  );

  const [form, setForm] = useState({ name: "", code: "", capacity: "" });
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [avail, setAvail] = useState({ weekday: 0, start: "08:00", end: "10:00", reason: "" });
  const [availBusy, setAvailBusy] = useState(false);

  async function onCreate() {
    if (!sel) return;
    setAvailBusy(true); setErr(null); setFlash(null);
    try {
      await ResourceAvailabilityClient.create(sel.id, {
        cycle_id: (cyclesQ.data?.[0])?.id ?? 0,
        weekday: avail.weekday,
        start_hhmm: avail.start,
        end_hhmm: avail.end,
        reason: avail.reason || null,
      });
      setAvail({ weekday: 0, start: "08:00", end: "10:00", reason: "" });
      availQ.reload();
      setFlash("پنجرهٔ دسترسی ثبت شد.");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "ثبت پنجره ناموفق بود.");
    } finally { setAvailBusy(false); }
  }

  const availCols: Column<RA>[] = [
    { key: "weekday", header: "روز هفته", render: (r) => weekdayLabel(r.weekday) },
    { key: "start", header: "آغاز", render: (r) => <span className="ltr">{formatTime(r.start_hhmm)}</span> },
    { key: "end", header: "پایان", render: (r) => <span className="ltr">{formatTime(r.end_hhmm)}</span> },
    { key: "reason", header: "توضیح", render: (r) => r.reason ?? "—" },
    {
      key: "del", header: "", render: (r) => (
        <button className="btn btn--ghost btn--sm"
          onClick={async () => { await ResourceAvailabilityClient.delete(r.id); availQ.reload(); }}>
          حذف
        </button>
      ),
    },
  ];

  return (
    <AppShell title="منابع و دسترسی">
      <h1>منابع و دسترسی</h1>

      <div className="row row-wrap mt-1">
        <button className={`btn btn--sm ${kind === "room" ? "btn--teal" : "btn--ghost"}`} onClick={() => { setKind("room"); setSel(null); }}>کلاس‌ها</button>
        <button className={`btn btn--sm ${kind === "instructor" ? "btn--teal" : "btn--ghost"}`} onClick={() => { setKind("instructor"); setSel(null); }}>اعضای هیئت علمی</button>
      </div>

      <div className="grid grid-2 mt-2">
        <Card title={`فهرست ${kind === "room" ? "کلاس‌ها" : "اعضای هیئت علمی"}`}>
          {resQ.loading ? <Loading /> :
            resQ.error ? <ErrorState message={resQ.error} onRetry={resQ.reload} /> :
            (resQ.data?.length ?? 0) === 0 ? <EmptyState title="موردی ثبت نشده است" /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>نام</th><th>کد</th><th>ظرفیت</th><th></th></tr></thead>
                  <tbody>
                    {(resQ.data ?? []).map((r) => (
                      <tr key={r.id} style={{ background: sel?.id === r.id ? "var(--color-surface-2)" : "" }}>
                        <td>{r.name}</td>
                        <td className="ltr">{r.code ?? "—"}</td>
                        <td>{r.capacity ?? "—"}</td>
                        <td>
                          <button className="btn btn--ghost btn--sm" onClick={() => setSel(sel?.id === r.id ? null : r)}>
                            {sel?.id === r.id ? "بستن" : "دسترسی"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        <div>
          <Card title="افزودن منبع">
            {flash && <div className="alert alert--ok" style={{ marginBottom: 10 }}>{flash}</div>}
            {err && <div className="alert alert--error" style={{ marginBottom: 10 }}>{err}</div>}
            <div className="grid grid-2">
              <InputField label="نام" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
              <InputField label="کد (اختیاری)" value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} />
            </div>
            {kind === "room" && (
              <InputField label="ظرفیت (اختیاری)" type="number" min={0} value={form.capacity}
                onChange={(e) => setForm((f) => ({ ...f, capacity: e.target.value }))} />
            )}
            <button className="btn btn--teal" disabled={busy || !form.name.trim()}
              onClick={async () => {
                setBusy(true);
                try {
                  await ResourcesClient.create({
                    kind,
                    name: form.name.trim(),
                    code: form.code || null,
                    capacity: kind === "room" && form.capacity ? toNumber(form.capacity) : null,
                  });
                  setForm({ name: "", code: "", capacity: "" });
                  resQ.reload();
                  setFlash("منبع ایجاد شد.");
                } catch (e2) { setErr(e2 instanceof Error ? e2.message : null); }
                finally { setBusy(false); }
              }}>
              {busy ? "در حال ایجاد…" : "ایجاد"}
            </button>
          </Card>

          {sel && (
            <Card title={`دسترسی هفته‌ای — ${sel.name}`}>
              {availQ.loading ? <Loading /> :
                (availQ.data?.length ?? 0) === 0
                  ? <EmptyState title="پنجرهٔ دسترسی ثبت نشده است" />
                  : <DataTable columns={availCols} rows={availQ.data!} empty="موردی ندارد" rowKey={(r) => r.id} />}

              <form onSubmit={(e) => { e.preventDefault(); onCreate(); }} className="mt-2">
                <div className="grid grid-4">
                  <SelectInput label="روز" value={avail.weekday}
                    onChange={(e) => setAvail((a) => ({ ...a, weekday: Number(e.target.value) }))}
                    options={WEEKDAYS.map((w, i) => ({ value: i, label: w }))} />
                  <InputField label="آغاز (HH:MM)" type="time" value={avail.start}
                    onChange={(e) => setAvail((a) => ({ ...a, start: e.target.value }))} />
                  <InputField label="پایان (HH:MM)" type="time" value={avail.end}
                    onChange={(e) => setAvail((a) => ({ ...a, end: e.target.value }))} />
                  <InputField label="توضیح" value={avail.reason}
                    onChange={(e) => setAvail((a) => ({ ...a, reason: e.target.value }))} />
                </div>
                <button className="btn btn--teal btn--sm" disabled={availBusy}>ثبت پنجره</button>
              </form>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}
