/**
 * Preflight page: explicit cycle selector, blocker/warning breakdown.
 * 03: "پیش‌پرواز: موانع و هشدارها را جداگانه و با کد + پیام نشان بده".
 */
import { useState } from "react";
import { AppShell } from "../layouts/AppShell";
import { Preflight, Cycles } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import {
  Card, Loading, ErrorState, Alert, PreflightBlockerList, SelectInput,
} from "../components/ui";

export function PreflightPage() {
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const [cycleId, setCycleId] = useState<number>(0);
  const pfQ = useQuery(() => Preflight.run(cycleId || undefined), [cycleId]);

  return (
    <AppShell title="پیش‌پرواز">
      <div className="row row-between">
        <h1 style={{ margin: 0 }}>پیش‌پرواز</h1>
        <SelectInput label="چرخه" value={cycleId}
          onChange={(e) => setCycleId(Number(e.target.value))}
          options={[
            { value: 0, label: "همهٔ چرخه‌ها" },
            ...(cyclesQ.data ?? []).map((c) => ({ value: c.id, label: c.name })),
          ]} />
      </div>

      <div className="mt-2">
        <Card title="نتیجه">
          {pfQ.loading ? <Loading /> :
            pfQ.error ? <ErrorState message={pfQ.error} onRetry={pfQ.reload} /> :
            <>
              {pfQ.data!.can_submit
                ? <Alert kind="ok">همهٔ چک‌ها پاک است — این مجموعه برای حل / انتشار آماده است.</Alert>
                : <Alert kind="warn">موانع وجود دارد؛ برای حل، ابتدا موانع را برطرف کنید (هشدارها مسدودکننده نیستند).</Alert>}
              <div className="mt-2">
                <h3>موانع و هشدارها</h3>
                <PreflightBlockerList blockers={pfQ.data!.blockers} warnings={pfQ.data!.warnings} />
              </div>
            </>}
        </Card>
      </div>
    </AppShell>
  );
}
