from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView

from alerts.models import AdminAlert
from exams.models import Attempt, TestAccessRequest

from . import session as session_store
from .models import Device, User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .tokens import issue_tokens_for_user


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class RegisterView(APIView):
    """Ro'yxatdan o'tish — multipart (selfie rasm fayli bilan)."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": "Ro'yxatdan o'tildi.", "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        android_id = serializer.validated_data["android_id"]
        model = serializer.validated_data.get("model", "")
        os_version = serializer.validated_data.get("os_version", "")

        primary = user.devices.filter(is_primary=True).first()

        if primary is None:
            # Birinchi login -> bu qurilma primary
            device, _ = Device.objects.get_or_create(
                user=user,
                android_id=android_id,
                defaults={"model": model, "os_version": os_version, "is_primary": True},
            )
            if not device.is_primary:
                device.is_primary = True
                device.save(update_fields=["is_primary"])
        else:
            if primary.android_id != android_id:
                # ===== IKKINCHI QURILMA SIYOSATI =====
                # 1) Ikkala tomon ham tizimdan chiqariladi: joriy sessiya o'chadi
                #    (birinchi qurilma keyingi so'rovda 401 oladi), ikkinchisiga
                #    token berilmaydi.
                # 2) Barcha test ruxsatlari avtomatik RAD etiladi — admin qayta
                #    ko'rib chiqishi shart.
                # 3) Faol urinishlar bekor (void) bo'ladi.
                session_store.clear_session(user.id)
                now = timezone.now()
                TestAccessRequest.objects.filter(
                    user=user,
                    status__in=[
                        TestAccessRequest.Status.PENDING,
                        TestAccessRequest.Status.APPROVED,
                    ],
                ).update(
                    status=TestAccessRequest.Status.REJECTED,
                    reviewed_at=now,
                    comment="Ikkinchi qurilmadan kirish aniqlandi — avtomatik rad etildi.",
                )
                Attempt.objects.filter(
                    user=user, status=Attempt.Status.ACTIVE
                ).update(status=Attempt.Status.VOID, finished_at=now)

                Device.objects.update_or_create(
                    user=user,
                    android_id=android_id,
                    defaults={
                        "model": model,
                        "os_version": os_version,
                        "is_primary": False,
                        "is_blocked": True,
                    },
                )
                AdminAlert.objects.create(
                    user=user,
                    kind=AdminAlert.Kind.SECOND_DEVICE,
                    detail=(
                        f"Boshqa qurilmadan kirishga urinish. android_id={android_id}. "
                        "Ikkala sessiya o'chirildi, test ruxsatlari rad etildi."
                    ),
                    ip=_client_ip(request),
                    device_info=f"{model} / Android {os_version}",
                    action_taken=AdminAlert.Action.SESSION_BLOCKED,
                )
                return Response(
                    {
                        "detail": (
                            "Bu hisob boshqa qurilmaga bog'langan. Ikkala sessiya ham "
                            "tugatildi va test ruxsatlari bekor qilindi. "
                            "Administrator bilan bog'laning."
                        ),
                        "code": "second_device",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if primary.is_blocked:
                return Response(
                    {"detail": "Qurilma bloklangan. Administrator bilan bog'laning.",
                     "code": "device_blocked"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        tokens = issue_tokens_for_user(user)
        return Response(
            {
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_store.clear_session(request.user.id)
        return Response({"detail": "Chiqildi."}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# Refresh token yangilanganda session_id saqlanib qoladi (token ichida bor),
# shuning uchun standart TokenRefreshView yetarli.
class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class SelfieAdminView(APIView):
    """
    Foydalanuvchi selfisini FAQAT admin (staff) ko'ra oladi.
    Django admin sessiyasi (cookie) yoki staff JWT bilan ishlaydi.
    Rasm bazadan (BinaryField) beriladi — diskka bog'liq emas.
    """

    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request, user_id: int):
        user = User.objects.filter(id=user_id).only("id", "selfie_data").first()
        if user is None or not user.selfie_data:
            raise Http404
        return HttpResponse(bytes(user.selfie_data), content_type="image/jpeg")
