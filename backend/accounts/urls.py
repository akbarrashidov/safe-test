from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RegisterView,
    SelfieAdminView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("selfie/<int:user_id>/", SelfieAdminView.as_view(), name="selfie-admin"),
]
