# وضعیت فعلی و مسائل باز — CURRENT_STATUS_AND_ISSUES_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## ۱) فعالیت‌های انجام‌شده

### کد (همه compile شده ✅)

| ماژول | وضعیت | تعداد فایل |
|--------|-------|-----------|
| Backend models (base, phase2-4) | ✅ کامل | ~3 فایل ORM |
| Backend routers (auth, phase2-4, export) | ✅ کامل | 4 router file |
| Backend services (solver, preflight, stale, export) | ✅ کامل | 6 service file |
| Frontend pages + components | ✅ کامل | 16 page + components |
| Tests (واحدی) | ✅ نوشته شده | 13 فایل تست |
| Migrations (Alembic) | ✅ موجود | 15 migration |
| .env.example | ✅ با placeholderهای امن | 2 فایل |

### مستندات تولیدشده

| سند | مسیر |
|-----|------|
| راهنمای تحویل | `doc/00_HANDOFF_README.md` |
| معماری سیستم | `doc/01_SYSTEM_ARCHITECTURE.md` |
| مدل داده و گردش کار | `doc/02_DATA_MODEL_AND_WORKFLOWS.md` |
| وضعیت فعلی | این سند |
| تست و پذیرش | `doc/04_TESTING_AND_ACCEPTANCE.md` |
| استقرار Ubuntu+Apache+PostgreSQL | `doc/05_DEPLOY_UBUNTU24_APACHE_POSTGRES.md` |
| نقشه راه | `doc/06_ROADMAP_AND_REMAINING.md` |
| ممیزی امنیتی | `doc/08_DELIVERY_AUDIT.md` |
| manifest فایل‌ها | `doc/09_FILE_MANIFEST.csv` |

---

## ۲) موارد تأییدشده

| مورد | نتیجه |
|------|-------|
| Compilation Python | ✅ همه `.py` بدون syntax error |
| Compilation TypeScript | ✅ `tsc --noEmit` pass |
| Guard conftest.py | ✅ guard port + DB name فعال است |
| Alembic env.py config | ✅ dotenv load اضافه شد |
| RBAC implementation | ✅ پیاده‌سازی کامل چهار نقش |
| Solver OR-Tools integration | ✅ CP-SAT با snapshot immutable |
| Preflight blocker detection | ✅ 5 blocker + 2 warning |
| Export Excel/PDF | ✅ پیاده‌سازی شده |

---

## ۳) blockerها — موارد قابل حل توسط Deployer

### 🔴 Blocker 1: Database Connection
```
وضعیت: اتصال برقرار نشده
دلیل: PostgreSQL روی port 5434 در محیط target وجود ندارد
اقدام لازم: ایجاد database و user مطابق زیر:
```
```sql
-- برای dev (port 5433):
CREATE DATABASE barnamehsaz_novin_dev;
CREATE USER barnamehsaz WITH PASSWORD '<strong-password>';
GRANT ALL PRIVILEGES ON DATABASE barnamehsaz_novin_dev TO barnamehsaz;

-- برای test (port 5434 - فقط تست محلی):
CREATE DATABASE barnamehsaz_nopin_test;
ALTER ROLE barnamehsaz CONNECTION LIMIT 0; -- or appropriate limit
```

### 🟡 Blocker 2: Alembic Migration Validation
- 15 migration file آماده است اما **اعمال نشده** (چون DB متصل نیست)
- deployer باید پس از ایجاد DB دستور `alembic upgrade head` را اجرا کند

### 🟡 Blocker 3: Environment Variables
- `.env` واقعی در بسته **وجود ندارد** (آگاهانه حذف شده)
- deployer باید مقادیر زیر را در `.env` تنظیم کند:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - `SECRET_KEY` (حداقل 32 کاراکتر رندوم)

---

## ۴) موارد اجرانشده (نیازمند محیط target)

| مورد | علت |
|------|-----|
| اجرای 13 تست واحد | DB connect block |
| اجرای `alembic upgrade head` | DB connect block |
| Smoke test API endpoints | نیاز به running server |
| UI interaction test | نیاز به running frontend |
| E2E Playwright tests | نیاز به full stack running |

---

## ۵) نکات امنیتی تأییدشده ✅

- ✅ هیچ credential واقعی در کد وجود ندارد
- ✅ هیچ مسیر مطلق شخصی (`<project-root>`) در کد یا مستندات باقی نمانده
- ✅ `.env.production` و `test-results/` از بسته حذف شدند
- ✅ `seed_demo_accounts.py` مسیر m绝对 را با `pathlib` جایگزین کرد
- ✅ `requirements.lock.txt` comment venv-path حذف شد
- ✅ فقط `.env.example` (placeholder) موجود است
- ✅ SECRET_KEY پیش‌فرض: `change_me_in_production` (غیرایمن، باید تغییر کند)

---

## ۶) فایل موقت نیازمند بررسی

| مسیر | توضیح |
|------|-------|
| `backend/tests/test_phase4_api.py.new` | نسخه آزمایشی؛ قبل از deploy بررسی و در صورت عدم نیاز حذف شود |

---

*پایان گزارش وضعیت.*
