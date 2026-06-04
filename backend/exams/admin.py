from django.contrib import admin
from django.utils import timezone

from accounts.admin import selfie_img_tag

from .models import Attempt, Question, Test, TestAccessRequest


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("order", "text", "options", "correct_index")


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "is_active", "time_limit_min",
        "exam_question_count", "block_size", "question_count", "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("title", "description")
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "test", "order", "short_text", "correct_index")
    list_filter = ("test",)
    search_fields = ("text",)

    @admin.display(description="Savol")
    def short_text(self, obj):
        return obj.text[:60]


@admin.register(TestAccessRequest)
class TestAccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "selfie_thumb", "test", "status",
        "created_at", "reviewed_at", "reviewed_by",
    )
    list_filter = ("status", "test")
    search_fields = ("user__email", "user__full_name", "test__title")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by", "selfie_preview")
    actions = ["approve_requests", "reject_requests"]

    @admin.display(description="Selfi")
    def selfie_thumb(self, obj):
        return selfie_img_tag(obj.user, height=40)

    @admin.display(description="Foydalanuvchi selfisi")
    def selfie_preview(self, obj):
        return selfie_img_tag(obj.user, height=240)

    @admin.action(description="Tasdiqlash")
    def approve_requests(self, request, queryset):
        n = queryset.update(
            status=TestAccessRequest.Status.APPROVED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{n} ta zayavka tasdiqlandi.")

    @admin.action(description="Rad etish")
    def reject_requests(self, request, queryset):
        n = queryset.update(
            status=TestAccessRequest.Status.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{n} ta zayavka rad etildi.")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    """Faqat yakuniy natijalar — savol-javoblar saqlanmaydi."""

    list_display = ("id", "user", "test", "mode", "status", "score",
                    "started_at", "finished_at")
    list_filter = ("status", "mode", "test")
    search_fields = ("user__email", "user__full_name")
    readonly_fields = ("user", "test", "mode", "started_at", "finished_at", "score", "status")

    def has_add_permission(self, request):
        return False
