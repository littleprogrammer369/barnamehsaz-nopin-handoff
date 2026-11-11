# راهنمای مرجع سیستم برنامه‌ساز نوین

**نسخه:** 1.0 | **تاریخ:** 2026-11-10 | **وضعیت:** توثیق کد واقعی + تست‌ها

## معماری کلی

سیستم یک سامانهٔ زمان‌بندی تعلیمی است با 3 فاز:
- **Phase 2:** چرخه‌ها، واحدها، منابع (اساتید/کلاس‌ها)
- **Phase 3:** ارسالیات واحدها و تأییدیه‌های مشترک
- **Phase 4:** حل‌کننده جهانی و انتشار برنامه

همهٔ داده‌ها **FK-enforced** هستند. هر سازمان داده‌های جدا دارد.

---

## چرخه برنامه‌ریزی

### مدل داده (جدول: `planning_cycles`)

| فیلد | نوع | الزامی | خالی | اعتبارسنجی |
|------|------|---------|--------|-----------|
| `id` | INT | ✓ | ✗ | PK |
| `name` | VARCHAR(255) | ✓ | ✗ | min=1, max=255 |
| `term` | VARCHAR(128) | ✗ | ✓ | max=128 — خالی→NULL |
| `status` | VARCHAR(32) | ✓ | ✗ | IN('draft','open','submitted','reviewed','published') |
| `start_date` | DATE | ✗ | ✓ | end_date ≥ start_date |
| `end_date` | DATE | ✗ | ✓ | — |
| `organization_id` | INT | ✓ | ✗ | FK→organizations |
| `created_at` | DATETIME | ✓ | ✗ | DEFAULT NOW() |
| `updated_at` | DATETIME | ✓ | ✗ | DEFAULT NOW() |
| `deleted_at` | DATETIME | ✗ | ✓ | soft-delete (NULL=فعال) |

**Unique:** `(organization_id, name)` — **هر سازمان نام‌های منحصربه‌فرد دارد**

### API Endpoints

**POST /phase2/planning-cycles** — ایجاد
```json
{
  "name": "پاییز ۱۴۰۳",
  "term": "پاییز",
  "status": "draft",
  "start_date": "2024-09-21",
  "end_date": "2024-12-20"
}
```
**Response:** 201 Created

**GET /phase2/planning-cycles** — لیست

**PUT /phase2/planning-cycles/{id}** — بروزرسانی

**DELETE /phase2/planning-cycles/{id}** — حذف (soft-delete)

**تست مرجع:** `backend/tests/test_phase2_api.py`

---

## واحدها

### مدل (جدول: `units`)

| فیلد | نوع | الزامی | یادداشت |
|------|------|---------|---------|
| `id` | INT | ✓ | PK |
| `name` | VARCHAR(255) | ✓ | نام واحد (دپارتمان) |
| `code` | VARCHAR(64) | ✗ | — |
| `organization_id` | INT | ✓ | FK |
| `created_at` | DATETIME | ✓ | — |
| `updated_at` | DATETIME | ✓ | — |

**Unique:** `(organization_id, name)`

### API

**POST /phase2/units** — ایجاد
```json
{
  "name": "مهندسی برق",
  "code": "EE"
}
```

**POST /phase2/planning-cycles/{cycle_id}/units** — افزودن واحد به چرخه
```json
{
  "unit_id": 5,
  "responsible_user_id": 10
}
```

---

## منابع (اساتید و کلاس‌ها)

### مدل (جدول: `resources`)

| فیلد | نوع | الزامی | خالی | اعتبارسنجی |
|------|------|---------|--------|-----------|
| `id` | INT | ✓ | ✗ | PK |
| `kind` | VARCHAR(16) | ✓ | ✗ | IN('room','instructor') |
| `name` | VARCHAR(255) | ✓ | ✗ | نام استاد یا کلاس |
| `code` | VARCHAR(64) | ✗ | ✓ | — |
| `capacity` | INT | ✗ | ✓ | **الزامی اگر kind='room' و > 0** |
| `details` | TEXT | ✗ | ✓ | — |
| `organization_id` | INT | ✓ | ✗ | FK |
| `created_at` | DATETIME | ✓ | ✗ | — |
| `updated_at` | DATETIME | ✓ | ✗ | — |

**Unique:** `(organization_id, kind, name)`

**Validation:**
- اگر `kind='room'` ⟹ `capacity` الزامی است (ge=1)
- اگر `kind='instructor'` ⟹ `capacity` نباید تنظیم شود

### API

**POST /phase2/resources** — ایجاد استاد
```json
{
  "kind": "instructor",
  "name": "دکتر احمدی",
  "code": "ahmad01"
}
```

**POST /phase2/resources** — ایجاد کلاس
```json
{
  "kind": "room",
  "name": "سالن A۱",
  "capacity": 40
}
```

**Schema:** `app/schemas/phase2.py:ResourceCreate` | `ResourceRead`

---

## دسترس‌پذیری و تعهدات

### مدل

**جدول:** `resource_availability` و `resource_commitments`

| فیلد | نوع | الزامی | مقدار |
|------|------|---------|--------|
| `id` | INT | ✓ | PK |
| `resource_id` | INT | ✓ | FK |
| `cycle_id` | INT | ✓ | FK (per-cycle) |
| `weekday` | INT | ✓ | 0-6 (شنبه-جمعه) |
| `start_hhmm` | VARCHAR(5) | ✓ | "HH:MM" format |
| `end_hhmm` | VARCHAR(5) | ✓ | "HH:MM" (end > start) |
| `reason` | VARCHAR | ✗ | توضیح |
| `deleted_at` | DATETIME | ✗ | soft-delete |

### API

**POST /phase2/resources/{resource_id}/availability** — ایجاد دسترس‌پذیری
```json
{
  "cycle_id": 42,
  "weekday": 2,
  "start_hhmm": "08:00",
  "end_hhmm": "16:00",
  "reason": "دسترس داشتن"
}
```

**POST /phase2/resources/{resource_id}/commitments** — ایجاد تعهد
```json
{
  "cycle_id": 42,
  "weekday": 2,
  "start_hhmm": "14:00",
  "end_hhmm": "16:00",
  "reason": "کلاس دیگری"
}
```

**یادداشت:** غیاب پنجره = "نامعلوم" (نه "آزاد")

---

## ارسالیات (5 فاز)

### مدل (جدول: `submissions`)

| فیلد | نوع | الزامی | مقدار |
|------|------|---------|--------|
| `id` | INT | ✓ | PK |
| `cycle_id` | INT | ✓ | FK |
| `unit_id` | INT | ✓ | FK |
| `status` | VARCHAR | ✓ | draft\|submitted\|needs_changes\|approved |
| `version` | INT | ✓ | optimistic lock (شروع: 0) |
| `locked` | BOOL | ✓ | TRUE=ثابت‌شده |

**Unique:** `(cycle_id, unit_id)` — هر واحد یک ارسالی در هر چرخه دارد

### وضعیت‌های ارسالی

```
draft → submit() → submitted → [needs_changes ← admin | approve() → approved]
                        ↓
                    needs_changes
                        ↓
                    resubmit() → submitted
```

### API

**POST /phase3/submissions** — ایجاد
```json
{"cycle_id": 42, "unit_id": 5, "input_snapshot": {}}
```

**POST /phase3/submissions/{id}/submit** — ارسال
```json
{"input_snapshot": {}, "expected_version": 0}
```
**Optimistic Lock:** اگر `expected_version ≠ version` ⟹ **409 Conflict**

**POST /phase3/submissions/{id}/needs-changes** — درخواست تغییر (admin)

**POST /phase3/submissions/{id}/approve** — تایید (admin)

**تست مرجع:** `backend/tests/test_phase3_api.py:test_stale_version_returns_409`

---

## جداسازی رشته‌ها

### مدل (جدول: `offering_units`)

| فیلد | نوع | الزامی | یادداشت |
|------|------|---------|---------|
| `id` | INT | ✓ | PK |
| `offering_id` | INT | ✓ | FK |
| `unit_id` | INT | ✓ | FK |
| `expected_enrollment` | INT | ✓ | تعداد دانشجویان |
| `room_resource_id` | INT | ✗ | استاد انتخاب‌شده |
| `instructor_resource_id` | INT | ✗ | کلاس انتخاب‌شده |

**مثال:** درس جبر برای 3 رشته

```
CourseOffering (جبر):
├── OfferingUnit (برق، 35 دانشجو)
├── OfferingUnit (مکانیک، 28 دانشجو)
└── OfferingUnit (عمران، 22 دانشجو)
```

---

## انتخاب مجدد درس/استاد

### مدل (جدول: `offering_corrections`) — append-only

**POST /phase4/corrections** — ایجاد اصلاح
```json
{
  "cycle_id": 42,
  "offering_id": 10,
  "field": "expected_enrollment",
  "before_value": "35",
  "after_value": "40",
  "reason": "دانشجویان جدید"
}
```
**نقش الزامی:** admin

**نتیجه:**
- اصلاح ثبت می‌شود
- تأییدیه‌های این درس → `status='stale'`
- حل‌های اجرا‌شده → `stale=true`
- **نکته:** stale هرگز خود را پاکیزا نمی‌کند (write-only)

**تست مرجع:** `backend/tests/test_phase4_api.py:test_correction_marks_run_stale_write_only`

---

## حل‌کننده و انتشار

### مدل (جدول: `solver_runs`)

| فیلد | نوع | الزامی | وضعیت |
|------|------|---------|--------|
| `id` | INT | ✓ | PK |
| `cycle_id` | INT | ✓ | FK |
| `status` | VARCHAR | ✓ | queued\|running\|feasible\|infeasible\|failed |
| `objective_score` | FLOAT | ✗ | امتیاز (اگر feasible) |
| `input_snapshot` | JSON | ✗ | داده‌های ورودی |
| `result_snapshot` | JSON | ✗ | نتیجهٔ حل‌کننده |
| `stale` | BOOL | ✓ | TRUE=داده‌ها تغییر کردند |
| `created_at` | DATETIME | ✓ | — |
| `finished_at` | DATETIME | ✗ | زمان پایان |

### API

**POST /phase4/solve** — اجرای حل‌کننده
```json
{
  "cycle_id": 42,
  "objective_weights": {}
}
```

**اگر موانع:** ⟹ **409 Conflict**
```json
{
  "status": "data_gaps",
  "blockers": [{"code": "SUBMISSION_NOT_APPROVED", "message": "..."}],
  "can_publish": false
}
```

**اگر feasible:** ⟹ **200 OK**
```json
{
  "run_id": 555,
  "status": "feasible",
  "objective_score": 123.45,
  "can_publish": true
}
```

**GET /phase4/runs** — لیست اجراها

**GET /phase4/runs/{run_id}** — جزئیات

---

## مجوزها و نقش‌ها

### نقش‌ها

| نقش | اختیارات |
|------|-----------|
| `admin` | کل سیستم |
| `unit_manager` | ارسالیات واحد |

### Org-Scoping

تمام داده‌ها به `organization_id` محدود می‌شوند

**تست:** `backend/tests/test_phase3_api.py:test_cross_org_isolation`

---

## پایگاه‌های داده

### مایگریشن‌ها (مسیر: `backend/alembic/versions/`)

| فایل | توضیح |
|------|--------|
| `0001_base.py` | organizations, users |
| `0008_phase2_core.py` | resources, offerings |
| `0003_phase3.py` | submissions, approvals |
| `0009_phase4_core.py` | solver_runs |
| `0011_published_schedules.py` | published versions |

### تست‌های جدائی

**فایل:** `backend/tests/test_phase4_api.py` (خطوط ~25-112)

```python
_REQUIRED_DB_PORT = "5434"
_REQUIRED_DB_NAME = "barnamehsaz_novin_test"
```

---

## اختلافات شناخت‌شده

### 1. Status Mapping TypeScript ↔ Python

**مشکل:**
- TypeScript: `data_gaps|INFEASIBLE|FEASIBLE|FAILED|running`
- Python: `queued|running|feasible|infeasible|failed`

**نیازمند تطبیق:** TypeScript (`frontend/src/lib/types.ts:240-246`)

### 2. Export API

**وضعیت:** فعال ✅
- `/phase4/runs/{run_id}/export/excel`
- `/phase4/runs/{run_id}/export/pdf`

**تست:** `backend/tests/test_export.py` (6/6 ✅)

---

**مستند بر اساس کد واقعی (Nov 10, 2026)**
