from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.cases.feeds import DeadlineFeed

urlpatterns: list = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("otp_webauthn/", include("django_otp_webauthn.urls")),
    path("cal/<str:token>/deadlines.ics", DeadlineFeed(), name="deadline-feed"),
    path("", include("apps.cases.urls")),
]
