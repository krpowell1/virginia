from __future__ import annotations

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from apps.accounts.views import register_passkey

app_name = "accounts"

urlpatterns: list = [
    path(
        "login/",
        LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register-passkey/", register_passkey, name="register-passkey"),
]
