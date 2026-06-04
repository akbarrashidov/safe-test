from django.urls import path

from .views import ReportAlertView

urlpatterns = [
    path("report/", ReportAlertView.as_view(), name="alert-report"),
]
