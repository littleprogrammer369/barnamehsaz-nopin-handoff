# مدل داده و گردش کار — DATA_MODEL_AND_WORKFLOWS_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## ۱) جداول پایگاه‌داده

### Phase 1 — پایه (base.py)

| جدول | ستون‌های کلیدی | توضیح |
|-------|--------------|-------|
| `organizations` | id, name, slug, timezone | سازمان‌های دانشگاهی |
| `users` | id, email, password_hash, full_name, is_active, must_change_password, organization_id | کاربران با RBAC |
| `memberships` | id, user_id, organization_id, role, unit_id | نقش کاربر در سازمان + وابستگی به واحد |

### Phase 2 — چرخه‌ها (phase2.py)

| جدول | ستون‌های کلیدی | توضیح |
|-------|--------------|-------|
| `planning_cycles` | id, organization_id, name, status, term, published_at | چرخه برنامه‌ریزی |
| `meeting_requirements` | id, cycle_id, unit_id, offering_id, room_type, max_students | نیازمندی جلسات |
| `units` | id, organization_id, name, slug | واحدهای آموزشی |

### Phase 3 — پیشنهادها و تأییدیه‌ها (phase3.py)

| جدول | ستون‌های کلیدی | توضیح |
|-------|--------------|-------|
| `course_offerings` | id, cycle_id, unit_id, instructor_id, shared, version, status | پیشنهاد درس |
| `offering_approvals` | id, offering_id, approver_id, status, approved_at, reason | زنجیرهٔ approval |
| `submission_versions` | id, offering_id, snapshot_json, submitted_by, submitted_at | نسخه‌های submit شده |

### Phase 4 — حل‌کننده (phase4.py)

| جدول | ستون‌های کلیدی | توضیح |
|-------|--------------|-------|
| `solver_runs` | id, cycle_id, input_snapshot, status, objective_score, started_at, finished_at | اجرای solver |
| `solver_assignments` | id, run_id, offering_id, day, period, room_id | تکلیف زمانی-مکانی |
| `offering_corrections` | id, run_id, offering_id, actor_id, reason, before_json, after_json | اصلاح دستی |
| `published_schedules` | id, cycle_id, run_id, published_by, published_at, is_current | نسخه منتشرشده |
| `audit_events` | id, organization_id, actor_id, action, entity_type, entity_id, extra_json, created_at | لاگ فعالیت |

---

## ۲) وضعیت‌های کلیدی

### planning_cycles.status
```
draft → active → solving → solved → published → archived
```

### course_offerings.status
```
draft → submitted → approved → rejected → stale
```

### solver_runs.status
```
queued → running → feasible / infeasible / failed
```

### offering_approvals.status
```
pending → approved / rejected → stale (وقتی داده منبع تغییر کند)
```

---

## ۳) گردش کار فاز به فاز

### فاز ۱ — احراز هویت و RBAC
1. ساخت组织 + کاربران
2. تعیین نقش: admin / manager / solver / viewer
3. رمز عبور Argon2id + JWT token

### فاز ۲ — مدیریت چرخه‌ها
1. ایجاد چرخه جدید (draft)
2. تعریف واحدها (Units)
3. افزودن نیازمندی‌های جلسه (Meeting Requirements)
4. فعال‌سازی چرخه (active)

### فاز ۳ — پیشنهاد و تأیید
1. اساتید Offering ارسال می‌کنند (draft → submitted)
2. مدیر واحد بررسی و تأیید/رد می‌کند
3. offerings approved وارد فاز حل می‌شوند
4. تغییر بعد از approval → علامت `stale` → re-approval

### فاز ۴ — حل زمان‌بندی
1. preflight check (blockers + warnings)
2. اجرای OR-Tools CP-SAT
3. نتیجه در `solver_assignments` ذخیره می‌شود
4. Manager می‌تواند correction اعمال کند
5. انتشار نهایی → `published_schedules`

---

## ۴) روابط کلیدی (ER diagram خلاصه)

```
Organization ──1:N── User
Organization ──1:N── Membership ──N:1── Unit
Organization ──1:N── PlanningCycle
PlanningCycle ──1:N── MeetingRequirement
PlanningCycle ──1:N── CourseOffering
CourseOffering ──1:N── OfferingApproval
CourseOffering ──1:N── SubmissionVersion
SolverRun ──1:N── SolverAssignment
SolverRun ──1:N── OfferingCorrection
PlanningCycle ──1:N── PublishedSchedule
```

---

*پایان مدل داده.*
