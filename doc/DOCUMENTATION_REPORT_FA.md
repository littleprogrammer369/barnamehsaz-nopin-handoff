# گزارش اختلافات: مستندات vs کد واقعی

**تاریخ:** 2026-11-10 | **وضعیت:** تطبیق کامل

---

## خلاصه

دو فایل مستندات فارسی تهیه شد:
1. **SYSTEM_REFERENCE_FA.md** — توثیق تکنیکی
2. **USER_GUIDE_FA.md** — راهنمای کاربری

هر دو بر اساس **کد واقعی** و **تست‌های اجرا‌شده** تهیه شدند.

---

## اختلافات شناخت‌شده

### 1. Status Values: TypeScript vs Python

**مشکل:**
- TypeScript: `"data_gaps"|"INFEASIBLE"|"FEASIBLE"|"FAILED"|"running"` (uppercase)
- Python: `"queued"|"running"|"feasible"|"infeasible"|"failed"` (lowercase)

**فایل:** 
- TypeScript: `frontend/src/lib/types.ts:240-246`
- Python: `backend/app/models/phase4.py:41-46`

**وضعیت:** ⚠️ **نیازمند تطبیق** — توثیق شده

**تست مرجع:** `backend/tests/test_phase4_api.py` — API سرور lowercase استفاده می‌کند

---

### 2. Optimistic Lock: Version Tracking

**وضعیت:** ✅ توثیق شده

- **کد:** `backend/app/models/phase3.py:73` — `version: int`
- **تست:** `backend/tests/test_phase3_api.py:test_stale_version_returns_409` — 409 Conflict

---

### 3. Submission Lifecycle: 5 فاز

**وضعیت:** ✅ توثیق شده

- **Status‌های:** draft → submitted → needs_changes/approved
- **تست:** پوشش کامل در test_phase3_api.py
- **مستند:** USER_GUIDE_FA.md فصل "ارسالیات"

---

### 4. Offering Units: جداسازی رشته‌ها

**وضعیت:** ✅ توثیق شده

- **کد:** `backend/app/models/phase2.py` — OfferingUnit جدول
- **تست:** test_phase4_api.py:_mk_offering
- **مثال:** درس جبر برای 3 رشته با تعداد دانشجویان مختلف

---

### 5. Corrections & Stale Marking

**وضعیت:** ✅ توثیق شده

- **کد:** `backend/app/models/phase4.py:150-180` — OfferingCorrection
- **تست:** `test_phase4_api.py:test_correction_marks_run_stale_write_only` (خطوط ~820-915)
- **نکته:** stale **write-only** — هرگز پاکیزا نمی‌شود

---

### 6. Export: Excel & PDF

**وضعیت:** ✅ توثیق شده

- **کد:** `backend/app/routers/export.py`
- **تست:** `backend/tests/test_export.py` — 6/6 ✅
- **مسیرها:**
  - `GET /phase4/runs/{run_id}/export/excel` → .xlsx
  - `GET /phase4/runs/{run_id}/export/pdf` → .pdf

---

## نیازمند تطبیق

1. **TypeScript SolverStatus:** lowercase کردن تمام status values

---

## Pre-existing Issues

**test_phase2_api.py:** خطاهای FK در teardown (عدم ارتباط با Phase 4)

---

## فایل‌های منابع

### مستندات جدید

- `/doc/SYSTEM_REFERENCE_FA.md` — 400+ خط
- `/doc/USER_GUIDE_FA.md` — 250+ خط

### تست‌های مرجع

- `backend/tests/test_phase3_api.py` — ارسالیات
- `backend/tests/test_phase4_api.py` — حل‌کننده، corrections
- `backend/tests/test_export.py` — Excel/PDF

### کد مرجع

- `backend/app/models/phase*.py` — domain models
- `backend/app/routers/phase*.py` — API endpoints
- `backend/app/schemas/phase*.py` — request/response

---

## خلاصهٔ توثیق

✅ تمام جداول و فیلدها  
✅ API endpoints  
✅ Lifecycle‌های ارسالی  
✅ RBAC و organization scoping  
✅ Preflight gates  
✅ Stale marking logic  
✅ Export functionality  

---

**کد/DB/server بدون تغییر ماند. فقط مستندات تطبیق یافتند.**
