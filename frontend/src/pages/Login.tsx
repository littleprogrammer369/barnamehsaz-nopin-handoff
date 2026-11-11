/** Login page. On success: if must_change_password → /change-password, else /dashboard. */
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { Logo } from "../components/logo";

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(email.trim(), password);
      nav(user.must_change_password ? "/change-password" : "/dashboard", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "ایمیل یا رمز عبور نادرست است یا حساب غیرفعال است."
          : "اتصال به سرور برقرار نشد.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-brand">
        <div className="row" style={{ marginBottom: 22 }}>
          <Logo size={48} />
          <div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: "#fff" }}>برنامه‌ساز نوین</div>
            <div className="small" style={{ color: "#9fb0d0" }}>ورود به حساب سازمانی</div>
          </div>
        </div>
        <h1>ورود به سامانه</h1>
        <p style={{ color: "#c3cee4" }}>
          برای ادامه، با ایمیل و رمز عبور سازمانی خود وارد شوید. اگر این اولین
          ورود شماست، پس از ورود ملزم به تغییر رمز خواهید بود.
        </p>
      </div>

      <div className="auth-form-side">
        <form className="card auth-card" onSubmit={onSubmit} noValidate>
          <h2>ورود</h2>
          {error && <div className="alert alert--error" style={{ marginBottom: 14 }}>{error}</div>}
          <label className="field">
            <span>ایمیل</span>
            <input
              className="input ltr"
              type="email"
              dir="ltr"
              autoComplete="email"
              placeholder="you@univ.ac.ir"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>رمز عبور</span>
            <input
              className="input ltr"
              type="password"
              dir="ltr"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button className="btn btn--teal btn--block" type="submit" disabled={busy}>
            {busy ? "در حال ورود…" : "ورود"}
          </button>
          <p className="small muted" style={{ marginTop: 14 }}>
            دسترسی با نقش‌های مدیر کل / مدیر واحد و فقط برای اعضای سازمان فعال است.
          </p>
        </form>
      </div>
    </div>
  );
}
