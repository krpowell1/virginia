from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.cases.models import CalendarToken

User = get_user_model()


class Command(BaseCommand):
    """Generate a webcal subscription token for a user.

    Usage:
        python manage.py generate_calendar_token <username>

    Prints the full webcal:// URL ready to paste into iPad Safari.
    """

    help = "Generate a calendar subscription token for a user."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument("username", type=str, help="Username to generate token for.")

    def handle(self, *args: object, **kwargs: object) -> None:
        username = kwargs["username"]

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist.')

        token_obj = CalendarToken.objects.create(user=user)

        domain = getattr(settings, "DOMAIN", "localhost")
        scheme = "https" if not getattr(settings, "DEBUG", False) else "http"
        port = ":8000" if settings.DEBUG else ""
        webcal_url = f"webcal://{domain}{port}/cal/{token_obj.token}/deadlines.ics"
        https_url = f"{scheme}://{domain}{port}/cal/{token_obj.token}/deadlines.ics"

        self.stdout.write(self.style.SUCCESS(f"Token created for {username}"))
        self.stdout.write("")
        self.stdout.write(f"  Webcal URL (for iPad Safari):")
        self.stdout.write(f"  {webcal_url}")
        self.stdout.write("")
        self.stdout.write(f"  HTTPS URL (for testing):")
        self.stdout.write(f"  {https_url}")
