import os
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


def selfie_upload_path(instance, filename: str) -> str:
    """Selfi fayl nomi taxmin qilib bo'lmaydigan UUID bilan saqlanadi."""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    return f"selfies/{uuid.uuid4().hex}{ext}"


class User(AbstractUser):
    """
    Email asosida kiradigan foydalanuvchi.
    `username` maydoni email bilan to'ldiriladi (admin/createsuperuser uchun).
    """

    full_name = models.CharField("To'liq ism", max_length=150, blank=True)
    phone = models.CharField("Telefon", max_length=32, blank=True)
    email = models.EmailField("Email", unique=True)
    # Ro'yxatdan o'tishda kameradan olingan selfi. Faqat admin ko'ra oladi
    # (media nginx orqali ochiq berilmaydi — himoyalangan view orqali).
    selfie = models.ImageField(
        "Selfi", upload_to=selfie_upload_path, blank=True, null=True
    )

    USERNAME_FIELD = "username"  # AbstractUser bilan moslik; login email orqali qidiriladi
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.full_name or self.email or self.username


class Device(models.Model):
    """
    Foydalanuvchining qurilmasi. Birinchi kirgan qurilma `is_primary`.
    Boshqa qurilmadan kirsa — IKKALA tomon ham tizimdan chiqariladi:
    joriy sessiya o'chadi, test ruxsatlari avtomatik rad etiladi.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="devices", verbose_name="Foydalanuvchi"
    )
    android_id = models.CharField("Android ID", max_length=128)
    model = models.CharField("Model", max_length=128, blank=True)
    os_version = models.CharField("OS versiyasi", max_length=64, blank=True)
    first_seen = models.DateTimeField("Birinchi ko'rinish", auto_now_add=True)
    is_primary = models.BooleanField("Asosiy qurilma", default=False)
    is_blocked = models.BooleanField("Bloklangan", default=False)

    class Meta:
        verbose_name = "Qurilma"
        verbose_name_plural = "Qurilmalar"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "android_id"], name="uniq_user_android_id"
            )
        ]

    def __str__(self):
        flag = "★" if self.is_primary else ""
        return f"{self.user} · {self.model or self.android_id[:8]} {flag}"
