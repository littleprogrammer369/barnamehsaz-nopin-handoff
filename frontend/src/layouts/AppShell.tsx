/**
 * App shell: RTL side navigation + top bar with user chip and logout.
 * All protected pages render inside this layout.
 */
import { Link, useLocation, useNavigate, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth, useRequireAuth } from "../lib/auth";
import { Logo, Icon } from "../components/logo";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  adminOnly?: boolean;
}

const NAV: NavItem[] = [
  { to: "/dashboard", label: "داشبورد", icon: "home" },
  { to: "/cycles", label: "چرخه‌های برنامه‌ریزی", icon: "cycles" },
  { to: "/resources", label: "منابع و دسترسی", icon: "resources" },
  { to: "/offerings", label: "دستگاه‌ها", icon: "offerings" },
  { to: "/submissions", label: "درخواست‌ها و ویزارد", icon: "wizard" },
  { to: "/shared", label: "تأیید دستگاه مشترک", icon: "offerings" },
  { to: "/preflight", label: "پیش‌پرواز", icon: "preflight" },
  { to: "/solve", label: "حل‌کننده و اجرا", icon: "solve" },
  { to: "/runs", label: "تاریخچهٔ اجراها", icon: "runs" },
  { to: "/audit", label: "گزارش کار", icon: "audit", adminOnly: true },
];

export function AppShell({ title, children }: { title?: string; children: ReactNode }) {
  const auth = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  // If not authenticated yet, redirect to login.
  if (!auth.accessToken) {
    return <Navigate to="/login" replace />;
  }

  // Forced password change gate (02/03: «پسورد اولیه باید در اولین ورود تعویض شود»).
  if (auth.mustChangePassword) {
    return <Navigate to="/change-password" replace />;
  }

  const active = (to: string) =>
    loc.pathname === to || loc.pathname.startsWith(to + "/");

  const initials = (auth.user?.full_name ?? "").slice(0, 1).toUpperCase() || "؟";

  return (
    <div className="shell">
      <aside className="shell-nav" aria-label="ناوبری اصلی">
        <div className="brand">
          <Logo size={36} />
          <div>
            <div className="name">برنامه‌ساز نوین</div>
            <div className="sub">BarnamehSaz Novin</div>
          </div>
        </div>

        <div className="nav-section">پانل مدیریت</div>
        {NAV.map((n) =>
          n.adminOnly && auth.role !== "admin" ? null : (
            <Link
              key={n.to}
              to={n.to}
              className={`nav-link ${active(n.to) ? "is-active" : ""}`}
            >
              <Icon name={n.icon} size={18} />
              {n.label}
            </Link>
          ),
        )}

        <div className="nav-sep" />
        <button
          className="nav-link"
          onClick={async () => {
            await auth.logout();
            nav("/login");
          }}
          style={{ justifyContent: "flex-start" }}
        >
          <Icon name="home" size={18} />
          خروج از حساب
        </button>
      </aside>

      <div className="shell-main">
        <header className="shell-top">
          <div className="crumb">{title ?? "پنل"}</div>
          <div className="user-chip">
            <span className="avatar">{initials}</span>
            <div className="small">
              <div style={{ fontWeight: 700 }}>{auth.user?.full_name}</div>
              <div className="faint">
                {auth.role === "admin" ? "مدیر کل" : "مدیر واحد"}
              </div>
            </div>
          </div>
        </header>
        <div className="container page">{children}</div>
      </div>
    </div>
  );
}

export function useRequireShell() {
  return useRequireAuth();
}
