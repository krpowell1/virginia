from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.cases.models import Case, Deadline


@pytest.fixture
def user(db: None) -> User:
    """Create a test user."""
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def client(user: User) -> Client:
    """Return an authenticated test client."""
    c = Client()
    c.login(username="testuser", password="testpass123")
    return c


@pytest.fixture
def case(user: User) -> Case:
    """Create a test case."""
    return Case.objects.create(
        case_number="CV-2026-RFA-001",
        caption="RFA v. Test",
        short_name="RFA test",
        court="Jefferson County Circuit Court",
        county="Jefferson",
        plaintiff_name="RFA Plaintiff",
        defendant_name="RFA Defendant",
        created_by=user,
    )


class TestRFAAutoAdmissionDashboard:
    """RFA auto-admission risk section on dashboard."""

    def test_overdue_rfa_shows_risk_section(self, client: Client, case: Case) -> None:
        """Overdue RFA deadline appears in the auto-admission risk section."""
        Deadline.objects.create(
            case=case,
            title="CRITICAL: Respond to Requests for Admission",
            due_date=date.today() - timedelta(days=2),
            deadline_type="DISCOVERY",
            rule_reference="ARCP Rule 36(a)",
        )
        r = client.get("/", HTTP_HOST="localhost")
        assert r.status_code == 200
        content = r.content.decode()
        # Check for the rendered heading (h2), not the HTML comment
        assert ">Auto-Admission Risk<" in content
        assert "DEEMED ADMITTED" in content

    def test_upcoming_rfa_shows_days_until(self, client: Client, case: Case) -> None:
        """RFA deadline due within 7 days shows countdown."""
        Deadline.objects.create(
            case=case,
            title="CRITICAL: Respond to Requests for Admission",
            due_date=date.today() + timedelta(days=3),
            deadline_type="DISCOVERY",
            rule_reference="ARCP Rule 36(a)",
        )
        r = client.get("/", HTTP_HOST="localhost")
        content = r.content.decode()
        assert ">Auto-Admission Risk<" in content
        assert "until auto-admission" in content

    def test_rfa_far_out_not_in_risk_section(self, client: Client, case: Case) -> None:
        """RFA deadline more than 7 days out does not appear in risk section."""
        Deadline.objects.create(
            case=case,
            title="CRITICAL: Respond to Requests for Admission",
            due_date=date.today() + timedelta(days=20),
            deadline_type="DISCOVERY",
            rule_reference="ARCP Rule 36(a)",
        )
        r = client.get("/", HTTP_HOST="localhost")
        content = r.content.decode()
        assert ">Auto-Admission Risk<" not in content

    def test_completed_rfa_not_in_risk_section(self, client: Client, case: Case) -> None:
        """Completed RFA deadline does not appear in risk section."""
        Deadline.objects.create(
            case=case,
            title="CRITICAL: Respond to Requests for Admission",
            due_date=date.today() - timedelta(days=1),
            deadline_type="DISCOVERY",
            rule_reference="ARCP Rule 36(a)",
            completed=True,
            completed_date=date.today() - timedelta(days=2),
        )
        r = client.get("/", HTTP_HOST="localhost")
        content = r.content.decode()
        assert ">Auto-Admission Risk<" not in content

    def test_overdue_rfa_shows_deemed_admitted_banner(self, client: Client, case: Case) -> None:
        """Overdue RFA shows the 'may be deemed admitted' warning banner."""
        Deadline.objects.create(
            case=case,
            title="CRITICAL: Respond to Requests for Admission",
            due_date=date.today() - timedelta(days=1),
            deadline_type="DISCOVERY",
            rule_reference="ARCP Rule 36(a)",
        )
        r = client.get("/", HTTP_HOST="localhost")
        content = r.content.decode()
        assert "deemed admitted" in content.lower()
