from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.cases.models import CalendarToken, Case, Deadline


@pytest.fixture
def user(db: None) -> User:
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def case(user: User) -> Case:
    """Create a test case with a pending deadline."""
    c = Case.objects.create(
        case_number="CV-2026-FEED-001",
        caption="Feed v. Test",
        short_name="Feed test",
        court="Jefferson County Circuit Court",
        county="Jefferson",
        plaintiff_name="Feed Plaintiff",
        defendant_name="Feed Defendant",
        created_by=user,
    )
    Deadline.objects.create(
        case=c,
        title="Discovery response",
        due_date=date.today() + timedelta(days=10),
        deadline_type="DISCOVERY",
    )
    return c


@pytest.fixture
def rfa_overdue(case: Case) -> Deadline:
    """Create an overdue RFA deadline."""
    return Deadline.objects.create(
        case=case,
        title="CRITICAL: Respond to Requests for Admission",
        due_date=date.today() - timedelta(days=2),
        deadline_type="DISCOVERY",
        rule_reference="ARCP Rule 36(a)",
    )


@pytest.fixture
def token(user: User) -> CalendarToken:
    """Create an active calendar token."""
    return CalendarToken.objects.create(user=user)


@pytest.fixture
def client() -> Client:
    """Return an unauthenticated test client."""
    return Client()


class TestCalendarTokenModel:
    """CalendarToken model behavior."""

    def test_token_auto_generated(self, user: User) -> None:
        """Token is automatically generated with 64 characters."""
        t = CalendarToken.objects.create(user=user)
        assert len(t.token) == 64

    def test_token_unique(self, user: User) -> None:
        """Each token is unique."""
        t1 = CalendarToken.objects.create(user=user)
        t2 = CalendarToken.objects.create(user=user)
        assert t1.token != t2.token

    def test_token_str(self, token: CalendarToken) -> None:
        """String representation includes user and status."""
        assert "testuser" in str(token)
        assert "active" in str(token)


class TestCalendarFeedAuth:
    """Calendar feed authentication via token in URL."""

    def test_old_url_returns_404(self, client: Client, case: Case) -> None:
        """The old unauthenticated /cal/deadlines.ics URL returns 404."""
        r = client.get("/cal/deadlines.ics")
        assert r.status_code == 404

    def test_valid_token_returns_ical(self, client: Client, case: Case, token: CalendarToken) -> None:
        """Valid active token returns iCal data."""
        r = client.get(f"/cal/{token.token}/deadlines.ics")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("text/calendar")
        content = r.content.decode()
        assert "VCALENDAR" in content
        assert "Discovery response" in content

    def test_invalid_token_returns_404(self, client: Client, case: Case) -> None:
        """Invalid token returns 404."""
        r = client.get("/cal/invalid-token-string/deadlines.ics")
        assert r.status_code == 404

    def test_inactive_token_returns_404(self, client: Client, case: Case, token: CalendarToken) -> None:
        """Inactive token returns 404."""
        token.is_active = False
        token.save()
        r = client.get(f"/cal/{token.token}/deadlines.ics")
        assert r.status_code == 404

    def test_rfa_overdue_prefix(self, client: Client, case: Case, token: CalendarToken, rfa_overdue: Deadline) -> None:
        """Overdue RFA deadlines have [AUTO-ADMISSION RISK] prefix in feed."""
        r = client.get(f"/cal/{token.token}/deadlines.ics")
        content = r.content.decode()
        assert "AUTO-ADMISSION RISK" in content

    def test_regular_overdue_prefix(self, client: Client, case: Case, token: CalendarToken) -> None:
        """Regular overdue deadlines have [OVERDUE] prefix, not AUTO-ADMISSION."""
        Deadline.objects.create(
            case=case,
            title="Overdue motion",
            due_date=date.today() - timedelta(days=1),
            deadline_type="MOTION",
            rule_reference="ARCP Rule 12",
        )
        r = client.get(f"/cal/{token.token}/deadlines.ics")
        content = r.content.decode()
        assert "[OVERDUE]" in content
