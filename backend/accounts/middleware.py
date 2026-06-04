"""
SingleSessionMiddleware — bitta aktiv sessiya nazorati.

Har himoyalangan so'rovda JWT access token ichidagi `session_id` Redis'dagi
joriy sessiya bilan solishtiriladi. Mos kelmasa -> 401 (eski sessiya o'lgan,
ya'ni boshqa joydan qayta login qilingan).

Bu middleware DRF JWTAuthentication'dan keyin (ya'ni request kengaytirilgach)
ishlashi uchun view bosqichida `request.auth` orqali token payload'iga kiramiz.
Buning uchun DRF token'ni o'qiydigan yengil tekshiruvchi.
"""
import json

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from . import session as session_store

# Bu yo'llar uchun sessiya tekshirilmaydi (token hali yo'q yoki yangilanmoqda)
_EXEMPT_PREFIXES = (
    "/admin",
    "/static",
    "/media",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
)


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._jwt = JWTAuthentication()

    def __call__(self, request):
        path = request.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return self.get_response(request)

        header = self._jwt.get_header(request)
        if header is not None:
            raw_token = self._jwt.get_raw_token(header)
            if raw_token is not None:
                try:
                    validated = self._jwt.get_validated_token(raw_token)
                except (InvalidToken, TokenError):
                    # Token allaqachon yaroqsiz — DRF o'zi 401 qiladi, o'tkazamiz
                    return self.get_response(request)

                user_id = validated.get("user_id")
                session_id = validated.get("session_id")
                if user_id is not None and session_id is not None:
                    if not session_store.is_current(user_id, session_id):
                        return JsonResponse(
                            {"detail": "Sessiya tugagan. Qaytadan kiring.",
                             "code": "session_expired"},
                            status=401,
                        )

        return self.get_response(request)
