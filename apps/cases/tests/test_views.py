from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.cases.models import (
    ActivityLog,
    Case,
    CaseContact,
    Deadline,
    Note,
)


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
    """Create a test case with deadlines."""
    c = Case.objects.create(
        case_number="CV-2026-000100",
        caption="Smith v. Jones Properties LLC",
        short_name="Smith premises",
        court="Jefferson County Circuit Court",
        county="Jefferson",
        plaintiff_name="John Smith",
        defendant_name="Jones Properties LLC",
        created_by=user,
    )
    # Overdue deadline
    Deadline.objects.create(
        case=c,
        title="Overdue deadline",
        due_date=date.today() - timedelta(days=3),
        deadline_type="ANSWER",
    )
    # Today deadline
    Deadline.objects.create(
        case=c,
        title="Today deadline",
        due_date=date.today(),
        deadline_type="DISCOVERY",
    )
    # This week deadline
    Deadline.objects.create(
        case=c,
        title="This week deadline",
        due_date=date.today() + timedelta(days=5),
        deadline_type="MOTION",
        is_extendable=True,
    )
    # Non-extendable deadline
    Deadline.objects.create(
        case=c,
        title="Appeal deadline",
        due_date=date.today() + timedelta(days=30),
        deadline_type="APPEAL",
        is_extendable=False,
        is_jurisdictional=True,
    )
    return c


# =========================================================================
# Authentication
# =========================================================================


class TestAuthentication:
    """Unauthenticated requests redirect to login."""

    def test_dashboard_requires_login(self, db: None) -> None:
        c = Client()
        r = c.get("/", HTTP_HOST="localhost")
        assert r.status_code == 302
        assert "/accounts/login/" in r.url

    def test_case_list_requires_login(self, db: None) -> None:
        c = Client()
        r = c.get("/cases/", HTTP_HOST="localhost")
        assert r.status_code == 302

    def test_login_page_renders(self, db: None) -> None:
        c = Client()
        r = c.get("/accounts/login/", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Sign in" in r.content


# =========================================================================
# Dashboard
# =========================================================================


class TestDashboard:
    """Dashboard view shows deadline sections and attention items."""

    def test_dashboard_renders(self, client: Client, case: Case) -> None:
        r = client.get("/", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Dashboard" in r.content

    def test_dashboard_shows_overdue(self, client: Client, case: Case) -> None:
        r = client.get("/", HTTP_HOST="localhost")
        assert b"Overdue" in r.content
        assert b"Overdue deadline" in r.content

    def test_dashboard_shows_today(self, client: Client, case: Case) -> None:
        r = client.get("/", HTTP_HOST="localhost")
        assert b"Due Today" in r.content
        assert b"Today deadline" in r.content

    def test_dashboard_shows_this_week(self, client: Client, case: Case) -> None:
        r = client.get("/", HTTP_HOST="localhost")
        assert b"This Week" in r.content
        assert b"This week deadline" in r.content

    def test_dashboard_shows_missing_defenses(self, client: Client, case: Case) -> None:
        r = client.get("/", HTTP_HOST="localhost")
        assert b"Needs Attention" in r.content
        assert b"Contrib. neg. not pled" in r.content


# =========================================================================
# Case list
# =========================================================================


class TestCaseList:
    """Case list with search and phase filter."""

    def test_case_list_renders(self, client: Client, case: Case) -> None:
        r = client.get("/cases/", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Smith premises" in r.content

    def test_case_list_search(self, client: Client, case: Case) -> None:
        r = client.get("/cases/partial/?q=Smith", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Smith premises" in r.content

    def test_case_list_search_no_results(self, client: Client, case: Case) -> None:
        r = client.get("/cases/partial/?q=nonexistent", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"No cases found" in r.content

    def test_case_list_phase_filter(self, client: Client, case: Case) -> None:
        r = client.get("/cases/partial/?phase=PLEADING", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Smith premises" in r.content

    def test_case_list_phase_filter_empty(self, client: Client, case: Case) -> None:
        r = client.get("/cases/partial/?phase=TRIAL", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"No cases found" in r.content


# =========================================================================
# Case detail + tabs
# =========================================================================


class TestCaseDetail:
    """Case detail page with tabbed layout."""

    def test_overview_tab(self, client: Client, case: Case) -> None:
        r = client.get(f"/cases/{case.pk}/", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Overview" in r.content
        assert b"Jefferson County Circuit Court" in r.content

    def test_deadlines_tab(self, client: Client, case: Case) -> None:
        r = client.get(f"/cases/{case.pk}/?tab=deadlines", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Overdue deadline" in r.content
        assert b"Appeal deadline" in r.content

    def test_contacts_tab(self, client: Client, case: Case) -> None:
        CaseContact.objects.create(
            case=case, name="Jane Doe", role="PLAINTIFF_ATTORNEY", firm="Doe Law"
        )
        r = client.get(f"/cases/{case.pk}/?tab=contacts", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Jane Doe" in r.content
        assert b"Doe Law" in r.content

    def test_notes_tab(self, client: Client, case: Case, user: User) -> None:
        Note.objects.create(
            case=case, author=user, content="Important note", note_type="STRATEGY"
        )
        r = client.get(f"/cases/{case.pk}/?tab=notes", HTTP_HOST="localhost")
        assert r.status_code == 200
        assert b"Important note" in r.content

    def test_activity_tab(self, client: Client, case: Case) -> None:
        r = client.get(f"/cases/{case.pk}/?tab=activity", HTTP_HOST="localhost")
        assert r.status_code == 200

    def test_htmx_tab_partial(self, client: Client, case: Case) -> None:
        r = client.get(
            f"/cases/{case.pk}/tab/overview/",
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert b"Key Dates" in r.content


# =========================================================================
# Deadline actions
# =========================================================================


class TestDeadlineActions:
    """Mark complete and extend deadline actions."""

    def test_mark_complete_htmx(self, client: Client, case: Case) -> None:
        deadline = case.deadlines.filter(completed=False).first()
        r = client.post(
            f"/cases/{case.pk}/deadlines/{deadline.pk}/complete/",
            {"notes": "Done"},
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert "show-toast" in r["HX-Trigger"]
        deadline.refresh_from_db()
        assert deadline.completed is True

    def test_mark_complete_redirect(self, client: Client, case: Case) -> None:
        deadline = case.deadlines.filter(completed=False).first()
        r = client.post(
            f"/cases/{case.pk}/deadlines/{deadline.pk}/complete/",
            {"notes": ""},
            HTTP_HOST="localhost",
        )
        assert r.status_code == 302

    def test_extend_deadline_htmx(self, client: Client, case: Case) -> None:
        deadline = case.deadlines.filter(is_extendable=True, completed=False).first()
        new_date = date.today() + timedelta(days=14)
        r = client.post(
            f"/cases/{case.pk}/deadlines/{deadline.pk}/extend/",
            {"new_due_date": new_date.isoformat(), "reason": "Agreed extension"},
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        deadline.refresh_from_db()
        assert deadline.due_date == new_date

    def test_extend_non_extendable_rejected(self, client: Client, case: Case) -> None:
        deadline = case.deadlines.filter(is_extendable=False).first()
        r = client.post(
            f"/cases/{case.pk}/deadlines/{deadline.pk}/extend/",
            {"new_due_date": "2026-12-31", "reason": "Try"},
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 422


# =========================================================================
# Note + Contact add
# =========================================================================


class TestNoteAdd:
    """Adding notes to a case."""

    def test_add_note_htmx(self, client: Client, case: Case) -> None:
        r = client.post(
            f"/cases/{case.pk}/notes/add/",
            {"content": "Test note", "note_type": "GENERAL"},
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert Note.objects.filter(case=case, content="Test note").exists()

    def test_add_note_redirect(self, client: Client, case: Case) -> None:
        r = client.post(
            f"/cases/{case.pk}/notes/add/",
            {"content": "Another note", "note_type": "RESEARCH"},
            HTTP_HOST="localhost",
        )
        assert r.status_code == 302

    def test_add_note_creates_activity(self, client: Client, case: Case) -> None:
        client.post(
            f"/cases/{case.pk}/notes/add/",
            {"content": "Activity note", "note_type": "GENERAL"},
            HTTP_HOST="localhost",
        )
        assert ActivityLog.objects.filter(
            case=case, action="NOTE_ADDED"
        ).exists()


class TestContactAdd:
    """Adding contacts to a case."""

    def test_add_contact_htmx(self, client: Client, case: Case) -> None:
        r = client.post(
            f"/cases/{case.pk}/contacts/add/",
            {"name": "Test Attorney", "role": "PLAINTIFF_ATTORNEY"},
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert CaseContact.objects.filter(case=case, name="Test Attorney").exists()


# =========================================================================
# Quick-add
# =========================================================================


class TestQuickAdd:
    """Quick-add case and deadline forms."""

    def test_quick_add_case_htmx(self, client: Client, db: None) -> None:
        r = client.post(
            "/cases/add/",
            {
                "case_number": "CV-2026-QA-001",
                "caption": "QuickAdd v. Test",
                "court": "Jefferson County Circuit Court",
                "county": "Jefferson",
                "case_type": "PREMISES_LIABILITY",
                "jurisdiction": "STATE",
                "plaintiff_name": "QA Plaintiff",
                "defendant_name": "QA Defendant",
            },
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 204
        assert "HX-Redirect" in r
        assert Case.objects.filter(case_number="CV-2026-QA-001").exists()

    def test_quick_add_deadline_htmx(self, client: Client, case: Case) -> None:
        r = client.post(
            "/deadlines/add/",
            {
                "case": str(case.pk),
                "title": "Quick deadline",
                "due_date": (date.today() + timedelta(days=10)).isoformat(),
                "deadline_type": "DISCOVERY",
                "is_extendable": True,
            },
            HTTP_HOST="localhost",
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 204
        assert Deadline.objects.filter(title="Quick deadline").exists()

    def test_case_add_page_renders(self, client: Client, db: None) -> None:
        r = client.get("/cases/add/", HTTP_HOST="localhost")
        assert r.status_code == 200

    def test_deadline_add_page_renders(self, client: Client, db: None) -> None:
        r = client.get("/deadlines/add/", HTTP_HOST="localhost")
        assert r.status_code == 200
