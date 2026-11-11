/** Forced first-login password change (02/03). After success → /dashboard. */
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ApiError } from "../lib/api";
import { Logo } from "../components/logo";

const MIN_LEN = 8;

export function ChangePassword() {
  const { changePassword, logout, accessToken, ready, mustChangePassword } = useAuth();
  const nav = useNavigate();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!ready) return null;
  if (!accessToken) return <Navigate to="/login" replace />;

  // If no longer flagged, allow going to dashboard.
  if (!mustChangePassword) return <Navigate to="/dashboard" replace />;

  function validate(): string | null {
    if (newPw.length < MIN_LEN) return `رمز جدید باید حداقل ${MIN_LEN} نویسه باشد.`;
    if (newPw !== confirm) return "تکرار رمز با رمز جدید یکسان نیست.";
    if (!oldPw) return "رمز فعلی را وارد کنید.";
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const v = validate();
    if (v) { setError(v); return; }
    setBusy(true);
    setError(null);
    try {
      await changePassword(oldPw, newPw);
      nav("/dashboard", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "تغییر رمز ناموفق بود؛ ممکن است رمز فعلی نادرست باشد."
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
            <div className="small" style={{ color: "#9fb0d0" }}>تغییر رمز اولیه</div>
          </div>
        </div>
        <h1>تغییر رمز عبور</h1>
        <p style={{ color: "#c3cee4" }}>
          رمز فعلی موقت است. برای ادامهٔ کار، یک رمز جدید و امن انتخاب کنید.
        </p>
      </div>

      <div className="auth-form-side">
        <form className="card auth-card" onSubmit={onSubmit} noValidate>
          <h2>رمز جدید</h2>
          {error && <div className="alert alert--error" style={{ marginBottom: 14 }}>{error}</div>}
          <label className="field">
            <span>رمز فعلی</span>
            <input className="input ltr" type="password" dir="ltr"
              autoComplete="current-password" value={oldPw}
              onChange={(e) => setOldPw(e.target.value)} required />
          </label>
          <label className="field">
            <span>رمز جدید</span>
            <input className="input ltr" type="password" dir="ltr"
              autoComplete="new-password" value={newPw}
              onChange={(e) => setNewPw(e.target.value)} required />
            <div className="hint">حداقل {MIN_LEN} نویسه.</div>
          </label>
          <label className="field">
            <span>تکرار رمز جدید</span>
            <input className="input ltr" type="password" dir="ltr"
              autoComplete="new-password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} required />
          </label>
          <button className="btn btn--teal btn--block" type="submit" disabled={busy}>
            {busy ? "در حال ثبت…" : "ذخیرهٔ رمز جدید"}
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--block mt-2"
            onClick={async () => { await logout(); nav("/login"); }}
          >
            خروج
          </button>
        </form>
      </div>
    </div>
  );
}
