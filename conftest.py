from __future__ import annotations

import django
from django.conf import settings


def pytest_configure() -> None:
    """Override staticfiles storage for tests.

    CompressedManifestStaticFilesStorage requires collectstatic to have
    been run, which is not the case in the test environment. Use the
    default StaticFilesStorage instead.
    """
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
