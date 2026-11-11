# معماری سیستم — SYSTEM_ARCHITECTURE_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## ۱) نمای کلی

سامانهٔ برنامه‌ساز نوین یک اپلیکیشن وب دو‌لایه (two-tier) است:

```
┌─────────────────────────────────────────────────────────────┐
│                     کلاینت (Frontend)                       │
│  React 18 · TypeScript 5.6 · Vite 5                        │
│  react-router-dom 6 · Vitest 2 · Testing Library           │
│  src/pages/ (16 صفحه) · src/components/ · src/lib/         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST (JSON)
                           │ Base: <host>/api/v1
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              سرور (Backend — FastAPI)                        │
│  Python 3.12+ · Uvicorn · SQLAlchemy 2.0                    │
│  routers/: auth, phase2, phase3, phase4, export             │
│  services/: solver(OR-Tools), preflight, stale, export_*    │
│  models/: base (org/user/membership), phase2-4              │
│  schemas/: Pydantic v2 for requests/responses               │
│  core/: config, jwt_utils, password_utils, rbac             │
└──────────────────────────┬──────────────────────────────────┘
                           │ SQLAlchemy ORM (async/sync)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              پایگاه‌داده (PostgreSQL 15+)                    │
│  port 5433 = dev (barnamehsaz_novin_dev)                   │
│  port 5434 = test (barnamehsaz_nopin_test)                 │
│  migrations: Alembic (15 نسخه)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ۲) لایهٔ ورودی (Routers)

| مسیر | وظیفه |
|------|--------|
| `/api/v1/auth/*` | ثبت‌نام، ورود، تغییر رمز، OTP |
| `/api/v1/phase2/*` | سازمان‌ها، چرخه‌های برنامه‌ریزی |
| `/api/v1/phase3/*` | پیشنهاد درس‌ها (Offerings)، تأییدیه‌ها |
| `/api/v1/phase4/*` | حل‌کننده (Solver)،_runs، corrections |
| `/api/v1/export/*` | خروجی Excel/PDF برنامه منتشرشده |

---

## ۳) اجزای کلیدی بک‌اند

### Solver Service (`services/solver.py`)
- استفاده از **Google OR-Tools CP-SAT** (Global Solver)
- ورودی: snapshot immutable از چرخه قبل از solve
- خروجی: `feasible` / `infeasible` / `failed`
- ذخیره assignments در جدول `solver_assignments`
- محاسبه objective score (وزنی: instructor load uniformity + room waste)

### Preflight Service (`services/preflight.py`)
- بررسی block/warning قبل از submit چرخه
- **Blockerها:** `CYCLE_NOT_SOLVABLE`, `UNIT_UNJOINED`, `SUBMISSION_MISSING`, `SHARED_OFFERING_STALE`, `Q12_RESOURCES_NOT_NOMINATED`
- **Warningها:** `NO_RESOURCE_AVAILABILITY`, `RESOURCE_HEAVILY_COMMITTED`

### Stale Detection (`services/stale.py`)
- شناسایی offerings که داده‌های پایه‌شان بعد از approval تغییر کرده
- علامت‌گذاری approved units به عنوان `stale` → نیاز به re-approval

### Export Services
- **Excel:** `openpyxl` — شیت‌های جداگانه برای resources، offerings، schedule
- **PDF:** `reportlab` — layout RTL فارسی با فونت Vazirmatn

---

## ۴) لایهٔ فرانت‌اند

| پوشه | محتوا |
|------|--------|
| `src/pages/` | 16 صفحه: Landing, Login, Dashboard, PlanningCycles, CycleEditPage, PlanningCycleDetail, Offerings, OfferingResourceSelection, SharedOfferings, Submissions, Runs, Solver, Resources, Audit, ChangePassword |
| `src/lib/api.ts` | client با base URL configurable از env |
| `src/lib/auth.tsx` | AuthProvider با JWT token management |
| `src/lib/persian.ts` | ابزارهای تبدیل عدد فارسی، تاریخ شمسی |
| `src/lib/digits.ts` | helper اعداد انگلیسی↔فارسی |
| `src/styles/global.css` | CSS variables برای light/dark theme |

---

## ۵) مقادیر کلیدی پیکربندی

| پارامتر | مقدار پیش‌فرض | منبع |
|---------|--------------|------|
| API Prefix | `/api/v1` | `core/config.py` |
| Default DB Port (dev) | `5433` | `core/config.py` |
| Default DB Name (dev) | `barnamehsaz_novin_dev` | `core/config.py` |
| Token Expire (min) | `30` | `core/config.py` |
| Min Password Length | `8` | `core/config.py` |
| Hash Algorithm | `argon2id` | `core/config.py` |
| Rate Limit Window | `15 min` | `main.py` |
| Rate Limit Max Fails | `5` | `main.py` |
| Frontend API Target (dev) | `http://127.0.0.1:8000` | `frontend/.env.example` |

---

## ۶) امنیت

| لایه | مکانیزم |
|------|---------|
| رمزنگاری رمز عبور | Argon2id (via `passlib`) |
| توکن نشست | JWT امضاشده با SECRET_KEY |
| دسترسی‌بندی | RBAC چهارسطحی: admin > manager > solver > viewer |
| نرخ‌خواه | Rate limiting روی `/api/v1/auth/login` (5 شکست در 15 دقیقه) |
| Guard محیط | `seed_guard` — seed only در development/test مجاز است |

---

*پایان مرجع معماری.*
