import math

from django.conf import settings
from django.db import models


class Test(models.Model):
    title = models.CharField("Sarlavha", max_length=200)
    description = models.TextField("Tavsif", blank=True)
    is_active = models.BooleanField("Faol", default=True)
    # Imtihon rejimi parametrlari
    time_limit_min = models.PositiveIntegerField(
        "Imtihon vaqti (daqiqa)", default=25,
        help_text="Imtihon rejimida beriladigan vaqt.",
    )
    exam_question_count = models.PositiveIntegerField(
        "Imtihon savollari soni", default=25,
        help_text="Imtihonda har bo'limdan aralashtirib tanlanadigan savollar soni.",
    )
    # Tayyorlanish rejimi: savollar shu kattalikdagi bo'limlarga bo'linadi
    block_size = models.PositiveIntegerField(
        "Bo'lim kattaligi", default=25,
        help_text="Tayyorlanish rejimida bitta bo'limdagi savollar soni.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def question_count(self) -> int:
        return self.questions.count()

    @property
    def block_count(self) -> int:
        size = self.block_size or 25
        return math.ceil(self.question_count / size) if size else 0


class Question(models.Model):
    test = models.ForeignKey(
        Test, on_delete=models.CASCADE, related_name="questions", verbose_name="Test"
    )
    order = models.PositiveIntegerField("Tartib", default=0)
    text = models.TextField("Savol matni")
    options = models.JSONField("Variantlar (ro'yxat)", default=list)
    # DIQQAT: bu maydon imtihon rejimida HECH QACHON API javobida chiqmaydi.
    # Tayyorlanish rejimida javob tekshirilgach qaytadi (o'rganish uchun).
    correct_index = models.PositiveIntegerField("To'g'ri javob indeksi")

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["test", "order", "id"]

    def __str__(self):
        return f"[{self.test_id}] #{self.order}: {self.text[:40]}"


class TestAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_requests",
        verbose_name="Foydalanuvchi",
    )
    test = models.ForeignKey(
        Test, on_delete=models.CASCADE, related_name="access_requests", verbose_name="Test"
    )
    status = models.CharField(
        "Holat", max_length=16, choices=Status.choices, default=Status.PENDING
    )
    comment = models.TextField("Izoh", blank=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    reviewed_at = models.DateTimeField("Ko'rib chiqilgan", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
        verbose_name="Ko'rib chiqqan admin",
    )

    class Meta:
        verbose_name = "Test ruxsati zayavkasi"
        verbose_name_plural = "Test ruxsati zayavkalari"
        constraints = [
            models.UniqueConstraint(fields=["user", "test"], name="uniq_user_test_request")
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.test} [{self.status}]"


class Attempt(models.Model):
    """
    Imtihon urinishi. Faqat YAKUNIY natija (ball) saqlanadi — har bir savolga
    berilgan javoblar bazada SAQLANMAYDI (jarayon holati Redis'da, TTL bilan).
    Qayta-qayta topshirish mumkin: har start yangi Attempt ochadi.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        FINISHED = "finished", "Tugagan"
        VOID = "void", "Bekor qilingan"

    class Mode(models.TextChoices):
        EXAM = "exam", "Imtihon"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attempts",
        verbose_name="Foydalanuvchi",
    )
    test = models.ForeignKey(
        Test, on_delete=models.CASCADE, related_name="attempts", verbose_name="Test"
    )
    mode = models.CharField(
        "Rejim", max_length=16, choices=Mode.choices, default=Mode.EXAM
    )
    started_at = models.DateTimeField("Boshlangan", auto_now_add=True)
    finished_at = models.DateTimeField("Tugagan", null=True, blank=True)
    score = models.IntegerField("Ball", default=0)
    status = models.CharField(
        "Holat", max_length=16, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        verbose_name = "Urinish"
        verbose_name_plural = "Urinishlar"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} · {self.test} [{self.status}]"
