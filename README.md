# برنامه‌ساز نوین (Modern Programmer)

سامانهٔ برنامه‌ریزی هماهنگ، از منابع و فعالیت‌ها تا انتشار نسخه‌های قابل‌پیگیری.

## سریع شروع

```bash
# 1. محیط توسعه (می‌تواند فقط درون دیمون Docker)
docker compose up -d

# 2. احداث پایگاه داده (dev + test)
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -f backend/alembic/versions/xxxx_init.sql

# 3. Alembic migration
cd backend
alembic upgrade head

# 4. بک‌اند
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. فرانت‌اند (پس از نصب وابستگی‌ها)
cd frontend
npm run dev
```

- API Base: http://localhost:8000/api/v1
- Frontend: http://localhost:5173

## پوشه‌بندی

```
.
├── backend/          # اپ FastAPI
│   ├── app/
│   │   ├── api/      # لایه دسترسی API
│   │   ├── core/     # تنظیمات، امنیت، سشن
│   │   ├── database/ # اتصال PostgreSQL
│   │   ├── models/   # پیکربندی Alembic
│   │   ├── schemas/  # Pydantic v2 schemas
│   │   └── ...
│   ├── alembic/      # migration
│   └── tests/        # تست‌های ایزوله
├── frontend/         # React + TypeScript + Vite
├── docker/           # فایل‌های Docker (به‌صورت مجزا)
└── docs/             # سند‌های فنی
```

## کلمات کلیدی

| فاز | محتوا | خروجی |
|---|---|---|
| ۱ | foundation + authentication + RBAC + test accounts + isolated tests | PHASE_01_AUTH.md |

**قانون اول:** هیچ migration روی DB واقعی، hiç deployment، restart، Apache، UFW، volumeهای موجود یا networkهای موجود انجام نمی‌شود. دیتابیس جدید، volume و credentialهای استقلال‌آمیز است.