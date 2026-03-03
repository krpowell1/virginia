from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.cases.models import CalendarToken


@pytest.fixture
def user(db: None) -> User:
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


class TestGenerateCalendarToken:
    """Management command to generate webcal subscription tokens."""

    def test_creates_token(self, user: User) -> None:
        """Command creates a CalendarToken for the specified user."""
        call_command("generate_calendar_token", "testuser")
        assert CalendarToken.objects.filter(user=user).exists()

    def test_prints_webcal_url(self, user: User, capsys: pytest.CaptureFixture) -> None:
        """Command prints the webcal URL."""
        call_command("generate_calendar_token", "testuser")
        output = capsys.readouterr().out
        assert "webcal://" in output
        assert "/cal/" in output
        assert "/deadlines.ics" in output

    def test_nonexistent_user_raises(self, db: None) -> None:
        """Command raises error for nonexistent username."""
        with pytest.raises(CommandError, match="does not exist"):
            call_command("generate_calendar_token", "nobody")

    def test_multiple_tokens_per_user(self, user: User) -> None:
        """Running command twice creates two distinct tokens."""
        call_command("generate_calendar_token", "testuser")
        call_command("generate_calendar_token", "testuser")
        assert CalendarToken.objects.filter(user=user).count() == 2
