# نقشه راه و کارهای باقی‌مانده — ROADMAP_AND_REMAINING_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## فازهای تکمیلی (Priority Order)

### 🔴 P0 — بلافاصله پس از استقرار

| ردیف | کار | زمان تخمینی |
|------|-----|-------------|
| 1 | اجرای `alembic upgrade head` روی سرور | 5 دقیقه |
| 2 | ویرایش `.env` با مقادیر صحیح production | 10 دقیقه |
| 3 | اجرای تست‌های واحد (`pytest tests/`) | 15 دقیقه |
| 4 | تأیید health endpoint پاسخ 200 می‌دهد | 2 دقیقه |
| 5 | تغییر SECRET_KEY پیش‌فرض به مقدار قوی رندوم | 2 دقیقه |
| 6 | غیرفعال کردن app_debug=True در production | 1 دقیقه |

### 🟡 P1 — هفته اول

| ردیف | کار | توضیح |
|------|-----|-------|
| 7 | افزودن CSRF protection middleware | FastAPI `CORSMiddleware` + CSRF token |
| 8 | افزودن HTTPS فقط (حذف plain HTTP) | Let's Encrypt certificate |
| 9 | تنظیم rate limiting global | روی تمام endpoints، نه فقط auth |
| 10 | افزودن health check endpoint کامل | DB connection test + uptime |
| 11 | log rotation برای Apache و Uvicorn | `/etc/logrotate.d/` |
| 12 | backup script خودکار PostgreSQL | `pg_dump` daily cron |

### 🟢 P2 — ماه اول

| ردیف | کار | توضیح |
|------|-----|-------|
| 13 | افزودن single Sign-On (SSO) | LDAP / OAuth2 / SAML |
| 14 | UI accessibility audit | WCAG 2.1 AA compliance |
| 15 | Load testing | k6 یا Locust برای 100 concurrent user |
| 16 | افزودن notification system | Email/SMS برای notifications چرخه |
| 17 | Migration از port 5433 به 5432 | استفاده از پورت استاندارد PG |
| 18 | Docker image optimization | Multi-stage build + slim image |

### 🔵 P3 — بلندمدت

| ردیف | کار | توضیح |
|------|-----|-------|
| 19 | افزودن GraphQL API layer | جایگزین یا مکمل REST |
| 20 | Real-time updates via WebSocket | وضعیت solver به صورت live |
| 21 | افزودن reporting dashboard | نمودارهای آماری برای مدیران |
| 22 | multi-tenancy support | چند سازمان در یک instance |
| 23 | Internationalization (i18n) | پشتیبانی انگلیسی/فارسی toggle |
| 24 | CI/CD pipeline | GitHub Actions برای auto-deploy |

---

## کارهای ناتمام فعلی (Blockerهای شناخته‌شده)

| مشکل | شدت | دلیل | اقدام required |
|------|------|------|----------------|
| DB اتصال برقرار نشده | 🔴 high | Port 5434 در target نیست | ایجاد DB + اجرای migration |
| تست‌ها اجرا نشده‌اند | 🟡 medium | نیاز به DB running | پس از استقرار اجرا شود |
| E2E Playwright tests fail | 🟡 medium | URL نادرست در تست‌ها | اصلاح base URL target |
| فایل `.new` باقیمانده | 🟡 low | نسخه آزمایشی | قبل از deploy بررسی شود |

---

## checklist deployment

```
□ PostgreSQL 15+ نصب شده
□ database و user ساخته شده
□ code unpacked in /opt/barnamehsaz_nopin
□ .venv created and dependencies installed
□ .env configured with production values
□ alembic upgrade head executed successfully
□ uvicorn service started via systemd
□ Apache reverse proxy configured
□ SSL certificate obtained
□ all pytest pass (or documented failures)
□ frontend npm run build succeeds
□ health endpoint returns 200
□ no personal paths in any deployed file
□ SECRET_KEY changed from default
```

---

*پایان نقشه راه.*
