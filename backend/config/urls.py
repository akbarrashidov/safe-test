from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Ochiq health endpoint — uptime monitoring / Render health check uchun.
    Har 5 daqiqada ping qilinsa Render free service uxlamaydi."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("exams.urls")),
    path("api/alerts/", include("alerts.urls")),
]
