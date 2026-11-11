# راهنمای تحویل — HANDOFF_README_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)  
**پروژه:** برنامه‌ساز نوین — سامانهٔ برنامه‌ریزی منابع دانشگاهی  

---

## هدف این بسته

این بسته شامل **کد تولید** (بدون credential، مسیر شخصی یا artifact محلی) و **مستندات کامل** است تا هر توسعه‌دهنده‌ای بتواند:

1. ساختار پروژه را بفهمد
2. محیط توسعه را راه‌اندازی کند
3. مراحل بعدی را دنبال نماید
4. روی سرور Ubuntu 24 استقرار دهد

---

## ساختار فایل‌ها

```
barnamehsaz_novin/
│
├── README.md                     # شروع سریع
├── docker-compose.yml            # container orchestration
├── .gitignore
│
├── backend/                      # سرور FastAPI
│   ├── app/
│   │   ├── main.py               # entrypoint + rate-limiting
│   │   ├── database.py           # اتصال SQLAlchemy
│   │   ├── core/                 # config, JWT, password, RBAC
│   │   ├── models/               # ORM (base + phase2/3/4)
│   │   ├── routers/              # API endpoints (auth, phase2-4, export)
│   │   ├── schemas/              # Pydantic request/response
│   │   └── services/             # solver, preflight, stale, export
│   ├── alembic/                  # migration scripts (15 فایل)
│   ├── tests/                    # تست‌های واحد (13 فایل)
│   ├── scripts/                  # seed_demo_accounts.py
│   ├── assets/fonts/vazirmatn/   # فونت فارسی (مجوز MIT)
│   ├── .env.example              # متغیرهای محیطی (placeholder)
│   ├── pyproject.toml
│   └── requirements.lock.txt     # نسخه‌های قفل‌شده وابستگی‌ها
│
├── frontend/                     # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/                # 16 صفحه UI
│   │   ├── components/           # reusable components
│   │   ├── lib/                  # api client, auth, helpers
│   │   ├── layouts/              # AppShell
│   │   └── styles/global.css     # تم‌ها و استایل پایه
│   ├── tests/                    # 4 تست واحد Vitest
│   ├── package.json
│   └── vite.config.ts
│
├── doc/                          # مستندات (مرتب شده)
│   ├── 00_HANDOFF_README.md      # ⬅ شروع از اینجا
│   ├── 01_SYSTEM_ARCHITECTURE.md
│   ├── 02_DATA_MODEL_AND_WORKFLOWS.md
│   ├── 03_CURRENT_STATUS_AND_ISSUES.md
│   ├── 04_TESTING_AND_ACCEPTANCE.md
│   ├── 05_DEPLOY_UBUNTU24_APACHE_POSTGRES.md
│   ├── 06_ROADMAP_AND_REMAINING.md
│   ├── 07_CLEANUP_MANIFEST.md
│   ├── 08_DELIVERY_AUDIT.md
│   └── 09_FILE_MANIFEST.csv      # SHA-256 فایل‌های دیگر (۱۲۳ فایل؛ خود manifest مستثناست)
│
└── docker/                       # Dockerfiles تکمیلی
    └── init/                     # init-scripts پایگاه‌داده
```

---

## ترتیب مطالعه

| ترتیب | سند | هدف |
|-------|-----|-----|
| 1 | `doc/00_HANDOFF_README.md` | همین فایل — نمای کلی |
| 2 | `doc/01_SYSTEM_ARCHITECTURE.md` | استک فناوری و معماری |
| 3 | `doc/02_DATA_MODEL_AND_WORKFLOWS.md` | مدل داده و گردش کار فازها |
| 4 | `doc/03_CURRENT_STATUS_AND_ISSUES.md` | وضعیت فعلی + blockerها |
| 5 | `doc/04_TESTING_AND_ACCEPTANCE.md` | تست‌ها + معیار پذیرش |
| 6 | `doc/05_DEPLOY_UBUNTU24_APACHE_POSTGRES.md` | استقرار روی سرور |
| 7 | `doc/06_ROADMAP_AND_REMAINING.md` | کارهای باقی‌مانده |

---

## خلاصهٔ فنی سریع

| مؤلفه | انتخاب |
|--------|---------|
| زبان بک‌اند | Python 3.12+ |
| فریم‌ورک بک‌اند | FastAPI + Uvicorn |
| پایگاه‌داده | PostgreSQL 15+ |
| migration | Alembic (15 مرحله) |
| زبان فرانت‌اند | TypeScript 5.6 |
| فریم‌ورک فرانت‌اند | React 18 + Vite 5 |
| solver | Google OR-Tools CP-SAT |
| احراز هویت | JWT (argon2id hashing) |
| دسترسی‌بندی | RBAC (Admin / Manager / Solver / Viewer) |
| فونت فارسی | Vazirmatn (MIT license) |
| API prefix | `/api/v1` |

---

## هشدارهای مهم قبل از شروع

1. **هیچ `.env` واقعی در این بسته وجود ندارد.** فقط `.env.example`. شما باید خودتان مقداردهی کنید.
2. **پورت‌های پیش‌فرض:**_dev = 5433، _test = 5434. برای production پورت استاندارد 5432 را تنظیم کنید.
3. **فایل موقت `test_phase4_api.py.new`:** یک نسخه آزمایشی است؛ قبل از deploy بررسی و در صورت عدم نیاز حذف شود.
4. **تست‌ها اجرا نشده‌اند:** به دلیل عدم دسترسی به پایگاه‌داده، اجرای واقعی pytest ممکن نبود. کد compile می‌شود اما validation نهایی بر عهدهٔ deployer است.

---

*پایان راهنمای تحویل.*
