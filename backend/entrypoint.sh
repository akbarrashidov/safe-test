#!/usr/bin/env bash
set -e

# Docker compose rejimida db tayyor bo'lishini kutamiz.
# Render/Heroku (DATABASE_URL) rejimida bu shart emas — o'tkazib yuboriladi.
if [ -z "${DATABASE_URL:-}" ] && [ -n "${POSTGRES_HOST:-}" ]; then
  echo "==> PostgreSQL kutilmoqda ($POSTGRES_HOST:$POSTGRES_PORT)..."
  until nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 1
  done
  echo "==> PostgreSQL tayyor."
fi

echo "==> Migratsiyalar..."
python manage.py migrate --noinput

echo "==> Statik fayllar..."
python manage.py collectstatic --noinput

# Test savollarini avtomatik import qilish (faqat bazada yo'q bo'lsa).
# O'chirish uchun: AUTO_IMPORT_TESTS=0
if [ "${AUTO_IMPORT_TESTS:-1}" != "0" ] && [ -f "/app/test.json" ]; then
  echo "==> Test savollari tekshirilmoqda (avto-import)..."
  python import_json.py /app/test.json \
    --title "${TESTS_TITLE:-Kiberxavfsizlik testi}" \
    --time-limit "${TESTS_TIME_LIMIT:-25}" \
    --if-missing || echo "!! Avto-import xatosi (server baribir ishga tushadi)"
fi

# Ixtiyoriy: superuser avtomatik yaratish (env to'ldirilgan bo'lsa)
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "==> Superuser tekshirilmoqda..."
  python manage.py shell <<PYEOF
from django.contrib.auth import get_user_model
U = get_user_model()
email = "${DJANGO_SUPERUSER_EMAIL}"
if not U.objects.filter(email=email).exists():
    U.objects.create_superuser(username=email, email=email, password="${DJANGO_SUPERUSER_PASSWORD}", full_name="Admin")
    print("Superuser yaratildi:", email)
else:
    print("Superuser allaqachon mavjud:", email)
PYEOF
fi

# PORT — Render kabi platformalar beradi; docker compose'da 8000.
# WEB_CONCURRENCY — Render CPU bo'yicha beradi; default 3.
echo "==> Gunicorn ishga tushmoqda (port ${PORT:-8000})..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:"${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
