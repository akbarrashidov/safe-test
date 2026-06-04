from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import Device, User


def selfie_img_tag(user, height=160):
    """Admin uchun selfi <img> tegi — himoyalangan view orqali."""
    if not user or not user.selfie:
        return "—"
    url = reverse("selfie-admin", args=[user.id])
    return format_html(
        '<a href="{0}" target="_blank">'
        '<img src="{0}" style="height:{1}px;border-radius:8px;" /></a>',
        url,
        height,
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "email", "full_name", "phone", "selfie_thumb",
                    "is_staff", "is_active")
    search_fields = ("email", "full_name", "phone", "username")
    ordering = ("id",)
    readonly_fields = ("selfie_preview",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Qo'shimcha", {"fields": ("full_name", "phone", "selfie", "selfie_preview")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Qo'shimcha", {"fields": ("email", "full_name", "phone")}),
    )

    @admin.display(description="Selfi")
    def selfie_thumb(self, obj):
        return selfie_img_tag(obj, height=40)

    @admin.display(description="Selfi (katta)")
    def selfie_preview(self, obj):
        return selfie_img_tag(obj, height=240)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "model", "android_id", "is_primary", "is_blocked", "first_seen")
    list_filter = ("is_primary", "is_blocked")
    search_fields = ("user__email", "user__full_name", "android_id", "model")
    actions = ["unblock_devices", "block_devices", "make_primary"]

    @admin.action(description="Blokdan chiqarish")
    def unblock_devices(self, request, queryset):
        n = queryset.update(is_blocked=False)
        self.message_user(request, f"{n} ta qurilma blokdan chiqarildi.")

    @admin.action(description="Bloklash")
    def block_devices(self, request, queryset):
        n = queryset.update(is_blocked=True)
        self.message_user(request, f"{n} ta qurilma bloklandi.")

    @admin.action(description="Asosiy qurilma qilish (har foydalanuvchida bittadan)")
    def make_primary(self, request, queryset):
        count = 0
        for device in queryset:
            Device.objects.filter(user=device.user).update(is_primary=False)
            device.is_primary = True
            device.is_blocked = False
            device.save(update_fields=["is_primary", "is_blocked"])
            count += 1
        self.message_user(request, f"{count} ta qurilma asosiy qilindi.")
