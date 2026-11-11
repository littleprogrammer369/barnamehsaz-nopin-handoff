# استقرار روی Ubuntu 24 + Apache + PostgreSQL — DEPLOY_UBUNTU24_APACHE_POSTGRES_FA.md

**نسخه:** 1.0.0  
**تاریخ:** ۱۴۰۵/۰۸/۲۰ (2026-11-11)

---

## پیش‌نیازهای سرور

| مؤلفه | نسخه |
|--------|------|
| OS | Ubuntu 24.04 LTS |
| Python | 3.12+ |
| PostgreSQL | 15+ |
| Node.js | 18+ |
| pip / venv | — |

---

## مرحله ۱: نصب وابستگی‌ها

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Python + pip
sudo apt install -y python3.12 python3.12-venv python3-pip postgresql-client

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Apache
sudo apt install -y apache2 libapache2-mod-proxy-h1
```

---

## مرحله ۲: آماده‌سازی پایگاه‌داده

```bash
# وارد shell پستگرس شوید
sudo -u postgres psql

-- ایجاد دیتابیس و کاربر
CREATE DATABASE barnamehsaz_novin_production;
CREATE USER barnamehsaz_prod WITH PASSWORD '<password-strong-here>';
GRANT ALL PRIVILEGES ON DATABASE barnamehsaz_nopin_production TO barnamehsaz_prod;
\q

# تست اتصال
psql -h localhost -U barnamehsaz_prod -d barnamehsaz_novin_production -c "SELECT 1"
```

---

## مرحله ۳: استقرار بک‌اند

```bash
cd /opt
sudo mkdir -p barnamehsaz_novin
sudo tar xzf /path/to/barnamehsaz_novin_public_release.zip -C /opt/barnamehsaz_novin

# ساخت virtual environment
cd /opt/barnamehsaz_nopin/backend
python3.12 -m venv .venv
source .venv/bin/activate

# نصب وابستگی‌ها
pip install --upgrade pip
pip install -r requirements.lock.txt

# کپی و ویرایش .env
cp .env.example .env
nano .env   # مقادیر زیر را تنظیم کنید:

# .env نمونه برای production:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=barnamehsaz_nopin_production
DB_USER=barnamehsaz_prod
DB_PASSWORD=<strong-password>
SECRET_KEY=<32-char-random-string>
APP_ENV=production
APP_DEBUG=False
API_PREFIX=/api/v1

# اجرای migrations
alembic upgrade head

# تست health endpoint
curl http://localhost:8000/api/v1/health
```

---

## مرحله ۴: استقرار فرانت‌اند

```bash
cd /opt/barnamehsaz_nopin/frontend

# نصب وابستگی‌ها
npm install

# تولید build
npm run build

# خروجی در dist/
ls -la dist/
```

---

## مرحله ۵: پیکربندی Apache (反向代理)

```bash
# فعال کردن ماژول‌های لازم
sudo a2enmod proxy proxy_http headers rewrite

# ایجاد فایل site config
sudo tee /etc/apache2/sites-available/barnamehsaz.conf << 'EOF'
<VirtualHost *:80>
    ServerName your-domain.com

    # Rewrite HTTP to HTTPS (optional, uncomment when using SSL)
    # RewriteEngine On
    # RewriteCond %{HTTPS} off
    # RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

    # Backend API proxy
    ProxyPreserveHost On
    ProxyPass /api/v1 http://127.0.0.1:8000/api/v1
    ProxyPassReverse /api/v1 http://127.0.0.1:8000/api/v1

    # Frontend static files
    Alias /static /opt/barnamehsaz_nopin/frontend/dist/assets
    <Directory /opt/barnamehsaz_nopin/frontend/dist/assets>
        Require all granted
    </Directory>

    # Frontend SPA fallback
    <Directory /opt/barnamehsaz_nopin/frontend/dist>
        Options -Indexes
        AllowOverride None
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/barnamehsaz-error.log
    CustomLog ${APACHE_LOG_DIR}/barnamehsaz-access.log combined
</VirtualHost>
EOF

# فعال‌سازی سایت
sudo a2ensite barnamehsaz.conf
sudo systemctl reload apache2
```

---

## مرحله ۶: سرویس Uvicorn با systemd

```bash
sudo tee /etc/systemd/system/barnamehsaz-api.service << 'EOF'
[Unit]
Description=BarnamehSaz Novin API
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/barnamehsaz_nopin/backend
Environment="PATH=/opt/barnamehsaz_nopin/backend/.venv/bin"
EnvironmentFile=/opt/barnamehsaz_nopin/backend/.env
ExecStart=/opt/barnamehsaz_nopin/backend/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --log-level info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable barnamehsaz-api
sudo systemctl start barnamehsaz-api
sudo systemctl status barnamehsaz-api
```

---

## مرحله ۷: SSL (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-apache
sudo certbot --apache -d your-domain.com --non-interactive --agree-tos -m admin@your-domain.com
```

---

## مرحله ۸: بررسی نهایی

```bash
# سرویس‌ها
sudo systemctl is-active barnamehsaz-api
sudo systemctl is-active apache2
sudo systemctl is-active postgresql

# Health check
curl -s http://localhost:8000/api/v1/health | jq

# تست frontend
curl -I https://your-domain.com

# لاگ‌ها
tail -f /var/log/apache2/barnamehsaz-error.log
journalctl -u barnamehsaz-api -f
```

---

## متغیرهای محیطی ضروری

| متغیر | مقدار dev | مقدار production |
|--------|----------|-----------------|
| `DB_HOST` | localhost | localhost |
| `DB_PORT` | 5433 | 5432 |
| `DB_NAME` | barnamehsaz_nopin_dev | barnamehsaz_nopin_production |
| `DB_USER` | barnamehsaz | barnamehsaz_prod |
| `DB_PASSWORD` | change_me_local | `<strong-password>` |
| `SECRET_KEY` | change_me_in_production | `<random-32char>` |
| `APP_ENV` | development | production |
| `API_PREFIX` | `/api/v1` | `/api/v1` |
| `FRONTEND_API_TARGET` | `http://127.0.0.1:8000` | `https://your-domain.com` |

---

*پایان راهنمای استقرار.*
