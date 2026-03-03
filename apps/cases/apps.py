from __future__ import annotations

from django.apps import AppConfig


class CasesConfig(AppConfig):
    """Configuration for the cases app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cases"
    verbose_name = "Cases"

    def ready(self) -> None:
        """Import signals when the app is ready."""
        import apps.cases.signals  # noqa: F401
