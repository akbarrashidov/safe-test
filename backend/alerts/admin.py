from django.contrib import admin

from .models import AdminAlert


@admin.register(AdminAlert)
class AdminAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "user", "ip", "device_info", "action_taken", "created_at")
    list_filter = ("kind", "action_taken")
    search_fields = ("user__email", "user__full_name", "ip", "detail", "device_info")
    readonly_fields = (
        "user", "kind", "detail", "ip", "device_info", "created_at", "action_taken",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
