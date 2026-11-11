# تست و پذیرش — TESTING_AND_ACCEPTANCE_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## ۱) فهرست تست‌ها

### بک‌اند (pytest — 13 فایل)

| فایل | پوشش |
|------|------|
| `conftest.py` | fixtureهای مشترک، guard اتصال DB |
| `test_auth_api.py` | ثبت‌نام، ورود، refresh token، change-password |
| `test_phase2_api.py` | CRUD planning cycles، list units |
| `test_phase3_api.py` | ایجاد offering، approval workflow |
| `test_phase4_api.py` | solver run، corrections، publish schedule |
| `test_access_control.py` | RBAC enforcement (admin vs viewer) |
| `test_export.py` | Excel/PDF export endpoints |
| `test_password_utils.py` | argon2id hash verify |
| `test_rbac.py` | role-checking utility functions |
| `test_rbac_real.py` | RBAC با اتصال واقعی (requires DB) |
| `test_session_utils.py` | session timeout logic |
| `test_seed_guard.py` | guard against seeding in production |
| `test_phase2_access_control.py` | access control on phase2 endpoints |

### فرانت‌اند (Vitest — 4 فایل)

| فایل | پوشش |
|------|------|
| `tests/digits.test.ts` | تبدیل اعداد فارسی↔انگلیسی |
| `tests/persian.ts` | توابع تاریخ شمسی و formatting |
| `tests/status.test.tsx` | کامپوننت‌های نمایش status |
| `tests/setup.ts` | vitest setup globals |

---

## ۲) معیارهای پذیرش (Acceptance Criteria)

### P0 — حیاتی (قبل از deployment)
- [ ] `alembic upgrade head` بدون خطا اجرا شود
- [ ] همه 13 تست بک‌اند green شوند
- [ ] `npm run build` فرانت‌اند بدون خطا اجرا شود
- [ ] health endpoint (`/api/v1/health`) پاسخ 200 دهد
- [ ] login flow کامل کار کند (register → login → JWT)

### P1 — مهم
- [ ] CRUD چرخه‌ها کار کند
- [ ] solver run producing feasible result
- [ ] export Excel/PDF output معتبر باشد
- [ ] RBAC correct roles blocks unauthorized access

### P2 — مطلوب
- [ ] UI responsive on tablet
- [ ] Dark mode works
- [ ] Persian date picker integrated

---

## ۳) دستورات اجرا

```bash
# بک‌اند
cd backend
export $(cat .env | xargs)
python -m pytest tests/ -v --tb=short

# فرانت‌اند
cd frontend
npm install
npm run test       # Vitest
npm run build      # produce dist/
```

---

## ۴) گزارش وضعیت

| دسته | تعداد | وضعیت |
|------|-------|--------|
| تست‌های نوشته‌شده | 17 | ✅ 13 py + 4 ts |
| تست‌های اجراشده | 0 | ⚠️ blocker: DB connection |
| compile errors | 0 | ✅ هیچ |
| type errors (TS) | 0 | ✅ هیچ |

---

*پایان گزارش تست.*
