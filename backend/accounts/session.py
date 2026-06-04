"""
Redis asosida bitta aktiv sessiya boshqaruvi.

`session:user:{id}` -> joriy session_id (uuid string).
Har yangi login bu kalitni ustiga yozadi — eski sessiya yaroqsiz bo'ladi.
"""
from django.conf import settings
from django.core.cache import cache

_PREFIX = getattr(settings, "SESSION_REDIS_PREFIX", "session:user:")

# Kalit muddati refresh token muddatiga yaqin (kunlarda)
_TTL_SECONDS = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def _key(user_id) -> str:
    return f"{_PREFIX}{user_id}"


def set_session(user_id, session_id: str) -> None:
    cache.set(_key(user_id), str(session_id), timeout=_TTL_SECONDS)


def get_session(user_id) -> str | None:
    return cache.get(_key(user_id))


def is_current(user_id, session_id: str) -> bool:
    current = get_session(user_id)
    return current is not None and current == str(session_id)


def clear_session(user_id) -> None:
    cache.delete(_key(user_id))
