"""
Faqat lokal tekshiruv uchun sozlamalar (SQLite + locmem cache).
Production'da ishlatilMAYDI — Docker config.settings ishlatadi.
"""
from .settings import *  # noqa: F401,F403

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
