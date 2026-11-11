/** Public landing page (pre-login). 03: «صفحهٔ landing / login». */
import { Link } from "react-router-dom";
import { Logo } from "../components/logo";
import { useAuth } from "../lib/auth";

export function Landing() {
  const auth = useAuth();
  if (auth.accessToken) return null; // handled by route redirect

  return (
    <div style={{ minHeight: "100vh" }} className="auth-shell">
      <div className="auth-brand">
        <div className="row" style={{ marginBottom: 22 }}>
          <Logo size={48} />
          <div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#fff" }}>
              برنامه‌ساز نوین
            </div>
            <div className="small" style={{ color: "#9fb0d0" }}>BarnamehSaz Novin</div>
          </div>
        </div>
        <h1>هماهنگی واحد‌ها، بدون تداخل.</h1>
        <p style={{ maxWidth: 460, color: "#c3cee4" }}>
          سامانهٔ داخلی برنامه‌ریزی منابع دانشگاه؛ ایجاد چرخه‌های ترم، ثبت
          درخواست واحد‌ها، حل تداخل با حل‌کنندهٔ جهانی، پیش‌پرواز و انتشار
          نسخهٔ قابل‌ردیابی — همه با تاریخ شمسی و اعداد فارسی.
        </p>
        <ul style={{ listStyle: "none", padding: 0, margin: "18px 0", color: "#c3cee4" }}>
          <li style={{ padding: "6px 0" }}>✓ چرخه‌های برنامه‌ریزی و اتصال واحد‌ها</li>
          <li style={{ padding: "6px 0" }}>✓ درخواست‌ها با ویزارد چندمرحله‌ای و ذخیرهٔ پیش‌نویس</li>
          <li style={{ padding: "6px 0" }}>✓ تأیید دستگاه مشترک توسط همهٔ واحد‌های دخیل</li>
          <li style={{ padding: "6px 0" }}>✓ پیش‌پرواز، حل‌کننده و مقایسهٔ اجراها</li>
        </ul>
        <Link to="/login" className="btn btn--teal">ورود به سامانه</Link>
      </div>
      <div className="auth-form-side" />
    </div>
  );
}
