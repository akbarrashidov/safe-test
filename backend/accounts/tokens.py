"""
JWT token yaratish — token ichiga `session_id` (uuid) joylanadi.
SingleSessionMiddleware shu claim'ni Redis bilan solishtiradi.
"""
import uuid

from rest_framework_simplejwt.tokens import RefreshToken

from . import session as session_store


def issue_tokens_for_user(user) -> dict:
    """Yangi session_id yaratadi, Redis'ga yozadi, access+refresh qaytaradi."""
    session_id = str(uuid.uuid4())

    refresh = RefreshToken.for_user(user)
    refresh["session_id"] = session_id
    refresh["full_name"] = user.full_name

    access = refresh.access_token
    access["session_id"] = session_id
    access["full_name"] = user.full_name

    # Redis'ga joriy sessiyani yozish (eski sessiyani bekor qiladi)
    session_store.set_session(user.id, session_id)

    return {
        "access": str(access),
        "refresh": str(refresh),
        "session_id": session_id,
    }
