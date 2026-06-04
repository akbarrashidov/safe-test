from django.conf import settings
from django.db import models


class AdminAlert(models.Model):
    class Kind(models.TextChoices):
        SECOND_DEVICE = "second_device", "Ikkinchi qurilma"
        SESSION_CONFLICT = "session_conflict", "Sessiya konflikti"
        ROOT_DETECTED = "root_detected", "Root aniqlandi"
        FLAG_SECURE_FAILED = "flag_secure_failed", "FLAG_SECURE o'rnatilmadi"
        TAMPER = "tamper", "Buzish urinishi"

    class Action(models.TextChoices):
        LOGGED = "logged", "Faqat log"
        SESSION_BLOCKED = "session_blocked", "Sessiya bloklandi"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        verbose_name="Foydalanuvchi",
    )
    kind = models.CharField("Turi", max_length=32, choices=Kind.choices)
    detail = models.TextField("Tafsilot", blank=True)
    ip = models.CharField("IP", max_length=64, blank=True)
    device_info = models.CharField("Qurilma ma'lumoti", max_length=255, blank=True)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True)
    action_taken = models.CharField(
        "Ko'rilgan chora", max_length=32, choices=Action.choices, default=Action.LOGGED
    )

    class Meta:
        verbose_name = "Xavfsizlik signali"
        verbose_name_plural = "Xavfsizlik signallari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.user} · {self.created_at:%Y-%m-%d %H:%M}"
