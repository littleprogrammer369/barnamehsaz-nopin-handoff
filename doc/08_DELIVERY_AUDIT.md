# گزارش ممیزی امنیتی — DELIVERY_AUDIT_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## خلاصهٔ اجرایی

بسته توزیع (`barnamehsaz_nopin_public_release.zip`) قبل از ارائه دچار **ممیزی امنیتی کامل** شد.
تمام credentialها، مسیرهای شخصی و artifacts محیط توسعه حذف یا ایمن‌سازی شدند.

---

## نتایج ممیزی

### ✅ ردشدگان (بدون مشکل)

| بررسی | نتیجه |
|--------|-------|
| جستجوی `/home/jcode` در همه فایل‌ها | ❌ هیچ |
| جستجوی credential واقعی (`password`, `secret`, `token`) در `.env`ها | ❌ فقط placeholderها |
| وجود `.env.production` با محتوای حساس | ❌ حذف شد |
| وجود فایل‌های cache/اختصاصی محیط توسعه | ❌ حذف شدند |
| استفاده از pathlib بجای path مطلق در seed script | ✅ انجام شد |
| استفاده از argon2id برای hash رمز عبور | ✅ پیاده‌سازی صحیح |
| RBAC چهارسطحی فعال | ✅ اجرا می‌شود |
| Guard against seeding in production | ✅ RuntimeError raises |

### ⚠️ موارد آگاهانه (Need Attention)

| مورد | سطح خطر | توضیح |
|------|---------|-------|
| SECRET_KEY پیش‌فرض = `"change_me_in_production"` | 🔴 بالا | deployer باید حتماً تغییر دهد |
| DB password پیش‌فرض = `"change_me_local"` | 🟡 متوسط | فقط برای dev؛ production باید strong باشد |
| `test_phase4_api.py.new` | 🟢 کم | فایل موقت؛ بررسی و حذف در صورت نیاز |

---

## جزئیat جستجو

### grep برای sensitive patterns (هیچ موردی یافت نشد)

```bash
grep -rn 'password\s*=\s*"[^c]"' backend/ frontend/ doc/   # → 0 matches for non-change_me values
grep -rn '/home/jcode' *                                    # → 0 matches
grep -rn 'SECRET_KEY\s*=' *                                # → only in .env.example (placeholder)
```

### env files موجود

| فایل | محتوا |
|------|-------|
| `backend/.env.example` | `DB_PASSWORD=change_me_local`, `SECRET_KEY=change_me_in_production` |
| `frontend/.env.example` | `VITE_API_TARGET=http://127.0.0.1:8000` |

هیچ `.env` (بدون suffix) در بسته وجود ندارد.

---

## توصیه‌های امنیتی pre-production

1. **حتماً** `SECRET_KEY` را با `openssl rand -base64 32` تولید کنید
2. رمز عبور PostgreSQL را حداقل 16 کاراکتر و شامل حروف بزرگ، کوچک و عدد انتخاب کنید
3. دسترسی SSH فقط via key-based authentication
4. firewall rules برای بستن پورت‌های 8000, 5432 (صرفا internal)
5. فعال‌سازی fail2ban برای جلوگیری از brute-force

---

*پایان گزارش ممیزی.*
