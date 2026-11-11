/**
 * Shared-offering approvals index: list shared offerings and their approval
 * status, with a link into the detail page for the decision flow.
 * 03: «دستگاه مشترک: تأیید توسط همهٔ واحدهای دخیل».
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Offerings, OfferingUnits, SharedOfferings } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { Card, Loading, ErrorState, EmptyState, Alert } from "../components/ui";
import type { CourseOffering, OfferingUnit, SharedOfferingApproval } from "../lib/types";

interface Row {
  offering: CourseOffering;
  units: OfferingUnit[];
  approvals: SharedOfferingApproval[];
  shared: boolean;
}

export function SharedOfferingsPage() {
  const offerQ = useQuery(() => Offerings.list(), []);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    (async () => {
      const offers = offerQ.data ?? [];
      const res = await Promise.all(
        offers.map(async (o) => {
          try {
            const [units, approvals] = await Promise.all([
              OfferingUnits.list(o.id),
              SharedOfferings.listApprovals(o.id),
            ]);
            return { offering: o, units: units ?? [], approvals: approvals ?? [], shared: (units ?? []).length > 1 };
          } catch { return null; }
        }),
      );
      if (live) { setRows(res.filter(Boolean) as Row[]); setLoading(false); }
    })();
    return () => { live = false; };
  }, [offerQ.data]);

  return (
    <AppShell title="دستگاه‌های مشترک">
      <h1>دستگاه‌های مشترک (چند واحد)</h1>
      <p className="muted small">
        دستگاه‌هایی که چندین واحد در آن‌ها دخیل است؛ برای حل، هر واحد باید آن را تأیید کند.
      </p>

      <div className="mt-2">
        <Card>
          {offerQ.loading || loading ? <Loading /> :
            offerQ.error ? <ErrorState message={offerQ.error} onRetry={offerQ.reload} /> :
            rows.length === 0 ? <EmptyState title="دستگاهی ثبت نشده است" /> :
            <div className="stack">
              {rows.map((r) => (
                <div key={r.offering.id} className="row row-between" style={{ padding: "10px 0", borderBottom: "1px solid var(--color-border)" }}>
                  <div>
                    <Link to={`/offerings/${r.offering.id}`} style={{ fontWeight: 700 }}>
                      دستگاه <span className="ltr">#{r.offering.id}</span> {r.offering.section ?? ""}
                    </Link>
                    <div className="small muted">واحدهای دخیل: {r.units.length} · جلسات/هفته: {r.offering.meetings_per_week}</div>
                  </div>
                  {r.shared
                    ? (
                      <Alert kind={(r.approvals.filter((a) => a.status === "unit_approved").length === r.units.length) ? "ok" : "warn"}>
                        تأییدشده: {r.approvals.filter((a) => a.status === "unit_approved").length} از {r.units.length}
                      </Alert>
                    )
                    : <span className="tag">دستگاه یک‌واحدی</span>}
                </div>
              ))}
            </div>}
        </Card>
      </div>
    </AppShell>
  );
}
