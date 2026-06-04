from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts import session as session_store
from exams.models import Attempt

from .models import AdminAlert

# Ilova yuborishi mumkin bo'lgan turlar (foydalanuvchi tomonidan signal)
_REPORTABLE = {
    AdminAlert.Kind.ROOT_DETECTED,
    AdminAlert.Kind.FLAG_SECURE_FAILED,
    AdminAlert.Kind.TAMPER,
    AdminAlert.Kind.SESSION_CONFLICT,
}


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class ReportAlertView(APIView):
    """
    Ilova xavf signali yuboradi (root aniqlandi, FLAG_SECURE o'rnatilmadi va h.k.).
    Rejim: LOG + DARHOL BLOK — Redis sessiya o'chadi, joriy Attempt void bo'ladi.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        kind = request.data.get("kind", "")
        detail = request.data.get("detail", "")
        device_info = request.data.get("device_info", "")

        if kind not in {k.value for k in _REPORTABLE}:
            return Response(
                {"detail": "Noma'lum signal turi."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Joriy faol urinishni bekor qilish
        Attempt.objects.filter(
            user=request.user, status=Attempt.Status.ACTIVE
        ).update(status=Attempt.Status.VOID, finished_at=timezone.now())

        # Sessiyani darhol o'chirish (ilova keyingi so'rovda 401 oladi)
        session_store.clear_session(request.user.id)

        AdminAlert.objects.create(
            user=request.user,
            kind=kind,
            detail=detail,
            ip=_client_ip(request),
            device_info=device_info,
            action_taken=AdminAlert.Action.SESSION_BLOCKED,
        )

        return Response(
            {"detail": "Signal qabul qilindi. Sessiya bloklandi.", "blocked": True},
            status=status.HTTP_200_OK,
        )
