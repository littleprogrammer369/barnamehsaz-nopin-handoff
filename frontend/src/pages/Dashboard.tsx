/** Role-aware dashboard: planning cycles, submissions, preflight, recent runs. */
import { Link } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { useAuth } from "../lib/auth";
import { Cycles, Submissions, Preflight, Solver } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { Card, StatCard, Loading, ErrorState, StatusBadge, EmptyState, PreflightBlockerList, Alert, JalaliDate } from "../components/ui";

export function Dashboard() {
  const auth = useAuth();
  const cyclesQ = useQuery(() => Cycles.list(), []);
  const subQ = useQuery(() => Submissions.list(), []);
  const pfQ = useQuery(
    () => (cyclesQ.data?.length ? Preflight.run(cyclesQ.data[0].id) : Promise.resolve(null)),
    [cyclesQ.data?.[0]?.id],
  );
  const runsQ = useQuery(() => Solver.runs().then((r) => r.slice(0, 6)), []);

  if (!auth.ready) return <AppShell title="داشبورد"><Loading /></AppShell>;

  const cycles = cyclesQ.data ?? [];
  const submissions = subQ.data ?? [];
  const runs = runsQ.data ?? [];

  const counts = {
    submitted: submissions.filter((s) => s.status === "submitted").length,
    approved: submissions.filter((s) => s.status === "approved").length,
    needsChanges: submissions.filter((s) => s.status === "needs_changes").length,
  };

  return (
    <AppShell title="داشبورد">
      <div className="row row-between mb-0">
        <div>
          <h1 style={{ margin: 0 }}>{auth.role === "admin" ? "پنل مدیر کل" : "پنل مدیر واحد"}</h1>
          <p className="muted small">خلاصهٔ وضعیت برنامه‌ریزی و اجرا</p>
        </div>
        <Link to="/cycles" className="btn btn--teal">ایجاد چرخه</Link>
      </div>

      <div className="grid grid-4 mt-2">
        <StatCard label="چرخه‌های برنامه‌ریزی" value={cycles.length} tone="info" />
        <StatCard label="درخواست‌های ارسال‌شده" value={counts.submitted} tone="info" />
        <StatCard label="تأییدشده" value={counts.approved} tone="ok" />
        <StatCard label="نیاز به تغییر" value={counts.needsChanges} tone="warn" />
      </div>

      {cyclesQ.error && <div className="mt-2"><Alert kind="error">خطا در بارگذاری چرخه‌ها: {cyclesQ.error}</Alert></div>}

      <div className="grid grid-2 mt-2">
        <Card title="چرخه‌های برنامه‌ریزی">
          {cyclesQ.loading ? <Loading /> :
            cycles.length === 0 ? <EmptyState title="چرخه‌ای ایجاد نشده است" action={<Link to="/cycles" className="btn btn--teal btn--sm">ایجاد چرخه</Link>} /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>نام</th><th>ترم</th><th>وضعیت</th><th>آغاز</th></tr></thead>
                  <tbody>
                    {cycles.map((c) => (
                      <tr key={c.id}>
                        <td><Link to={`/cycles/${c.id}`}>{c.name}</Link></td>
                        <td>{c.term}</td>
                        <td><StatusBadge status={c.status} /></td>
                        <td><JalaliDate value={c.start_date} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Card>

        <Card title="پیش‌پرواز (آخرین چرخه)">
          {pfQ.data === null ? <EmptyState title="چرخه‌ای برای پیش‌پرواز در دسترس نیست" /> :
            pfQ.loading ? <Loading /> :
            pfQ.error ? <ErrorState message={pfQ.error} onRetry={pfQ.reload} /> :
            <PreflightBlockerList blockers={pfQ.data!.blockers} warnings={pfQ.data!.warnings} />}
          {!pfQ.error && pfQ.data !== null && (
            <div className="mt-2 row">
              {pfQ.data!.can_submit ? <Alert kind="ok">آمادهٔ حل / انتشار است.</Alert> : <Alert kind="warn">برای حل، ابتدا موانع را برطرف کنید.</Alert>}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-2">
        <Card title="آخرین اجراهای حل‌کننده">
          {runsQ.loading ? <Loading /> :
            runsQ.error ? <ErrorState message={runsQ.error} onRetry={runsQ.reload} /> :
            runs.length === 0 ? <EmptyState title="اجرای ثبت نشده است" action={<Link to="/solve" className="btn btn--teal btn--sm">اجرای حل</Link>} /> :
            (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>شمارهٔ اجرا</th><th>وضعیت</th><th>امتیاز</th><th>کهنه</th><th>زمان</th></tr></thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id}>
                        <td><Link to={`/runs/${r.id}`} className="ltr">#{r.id}</Link></td>
                        <td><StatusBadge status={r.status} /></td>
                        <td className="ltr">{r.objective_score != null ? Number(r.objective_score).toFixed(3) : "—"}</td>
                        <td>{r.stale ? <span className="badge badge--warn">کهنه</span> : <span className="faint">—</span>}</td>
                        <td><JalaliDate value={r.created_at} time /></td>
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
