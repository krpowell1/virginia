from __future__ import annotations

import csv
import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Min, Q, Subquery, OuterRef, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AddContactForm,
    AddNoteForm,
    CompleteDeadlineForm,
    ExtendDeadlineForm,
    FeedbackRequestForm,
    QuickAddCaseForm,
    QuickAddDeadlineForm,
)
from .models import (
    ActivityAction,
    ActivityLog,
    Case,
    CaseContact,
    CasePhase,
    CaseStatus,
    CaseType,
    ChangelogEntry,
    ContactRole,
    Deadline,
    FeedbackRequest,
    FeedbackStatus,
    Jurisdiction,
    Note,
    UserChangelogRead,
)


# =========================================================================
# Dashboard
# =========================================================================


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Main dashboard showing overdue, today, this-week deadlines and cases needing attention."""
    today = date.today()

    # RFA auto-admission risk: RFA deadlines overdue or due within 7 days
    rfa_risk = (
        Deadline.objects.filter(
            completed=False,
            due_date__lte=today + timedelta(days=7),
            rule_reference__icontains="Rule 36",
        )
        .select_related("case")
        .order_by("due_date")
    )

    overdue = (
        Deadline.objects.filter(completed=False, due_date__lt=today)
        .select_related("case")
        .order_by("due_date")
    )
    today_deadlines = (
        Deadline.objects.filter(completed=False, due_date=today)
        .select_related("case")
        .order_by("due_date")
    )
    this_week = (
        Deadline.objects.filter(
            completed=False,
            due_date__gt=today,
            due_date__lte=today + timedelta(days=7),
        )
        .select_related("case")
        .order_by("due_date")
    )

    missing_defenses = (
        Case.objects.active()
        .filter(pled_contributory_negligence=False)
        .order_by("short_name", "caption")
    )
    pending_approval = (
        Case.objects.active()
        .filter(client_approved=False)
        .order_by("short_name", "caption")
    )

    # Changelog: check for unread updates
    has_updates = False
    unread_entries: list[ChangelogEntry] = []
    latest_entry = ChangelogEntry.objects.filter(is_published=True).first()
    if latest_entry:
        try:
            read_record = request.user.changelog_read
            unread_entries = list(
                ChangelogEntry.objects.filter(
                    is_published=True,
                    created_at__gt=read_record.last_read_at,
                )
            )
            has_updates = len(unread_entries) > 0
        except UserChangelogRead.DoesNotExist:
            unread_entries = list(
                ChangelogEntry.objects.filter(is_published=True)
            )
            has_updates = True

    return render(request, "cases/dashboard.html", {
        "rfa_risk_deadlines": rfa_risk,
        "overdue_deadlines": overdue,
        "today_deadlines": today_deadlines,
        "this_week_deadlines": this_week,
        "missing_defenses": missing_defenses,
        "pending_approval": pending_approval,
        "has_updates": has_updates,
        "unread_entries": unread_entries,
        "latest_entry": latest_entry,
    })


# =========================================================================
# Case list
# =========================================================================

_PHASE_CHOICES = [("", "All")] + list(CasePhase.choices)


def _filtered_cases(request: HttpRequest):
    """Return filtered/sorted case queryset and filter state from request params."""
    query = request.GET.get("q", "").strip()
    phase = request.GET.get("phase", "")
    sort = request.GET.get("sort", "updated")

    today = date.today()
    qs = (
        Case.objects.active()
        .annotate(
            overdue_count=Count(
                "deadlines",
                filter=Q(deadlines__completed=False, deadlines__due_date__lt=today),
            ),
            next_deadline_date=Min(
                "deadlines__due_date",
                filter=Q(deadlines__completed=False, deadlines__due_date__gte=today),
            ),
        )
    )

    if query:
        qs = qs.filter(
            Q(case_number__icontains=query)
            | Q(caption__icontains=query)
            | Q(short_name__icontains=query)
            | Q(plaintiff_name__icontains=query)
            | Q(defendant_name__icontains=query)
        )

    if phase:
        qs = qs.filter(phase=phase)

    if sort == "deadline":
        qs = qs.order_by("next_deadline_date", "-updated_at")
    elif sort == "name":
        qs = qs.order_by("short_name", "caption")
    else:
        qs = qs.order_by("-updated_at")

    return qs, query, phase, sort


@login_required
def case_list(request: HttpRequest) -> HttpResponse:
    """Full case list page with search, phase tabs, and sort."""
    cases, query, phase, sort = _filtered_cases(request)
    return render(request, "cases/case_list.html", {
        "cases": cases,
        "query": query,
        "active_phase": phase,
        "sort": sort,
        "phase_choices": _PHASE_CHOICES,
    })


@login_required
def case_list_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial: return just the case list results."""
    cases, query, phase, sort = _filtered_cases(request)
    return render(request, "cases/partials/case_list_results.html", {
        "cases": cases,
        "query": query,
        "active_phase": phase,
        "sort": sort,
    })


# =========================================================================
# Case detail + tabs
# =========================================================================


def _get_case_with_counts(pk: str) -> Case:
    """Fetch a case annotated with deadline counts."""
    today = date.today()
    return get_object_or_404(
        Case.objects.annotate(
            overdue_count=Count(
                "deadlines",
                filter=Q(deadlines__completed=False, deadlines__due_date__lt=today),
            ),
            pending_count=Count(
                "deadlines",
                filter=Q(deadlines__completed=False, deadlines__due_date__gte=today),
            ),
        ),
        pk=pk,
    )


@login_required
def case_detail(request: HttpRequest, pk: str) -> HttpResponse:
    """Case detail page with tabbed layout."""
    case = _get_case_with_counts(pk)
    tab = request.GET.get("tab", "overview")

    context: dict = {
        "case": case,
        "active_tab": tab,
    }

    if tab == "deadlines":
        context["deadlines"] = case.deadlines.all().order_by("completed", "due_date")
    elif tab == "contacts":
        context["contacts"] = case.contacts.all()
        context["contact_form"] = AddContactForm()
    elif tab == "notes":
        context["notes"] = case.notes.all().select_related("author")
        context["note_form"] = AddNoteForm()
    elif tab == "activity":
        context["activities"] = case.activity_log.all().select_related("user")

    return render(request, "cases/case_detail.html", context)


@login_required
def tab_overview(request: HttpRequest, pk: str) -> HttpResponse:
    """HTMX partial: overview tab content."""
    case = get_object_or_404(Case, pk=pk)
    return render(request, "cases/partials/tab_overview.html", {"case": case})


@login_required
def tab_deadlines(request: HttpRequest, pk: str) -> HttpResponse:
    """HTMX partial: deadlines tab content."""
    case = get_object_or_404(Case, pk=pk)
    deadlines = case.deadlines.all().order_by("completed", "due_date")
    return render(request, "cases/partials/tab_deadlines.html", {
        "case": case,
        "deadlines": deadlines,
    })


@login_required
def tab_contacts(request: HttpRequest, pk: str) -> HttpResponse:
    """HTMX partial: contacts tab content."""
    case = get_object_or_404(Case, pk=pk)
    return render(request, "cases/partials/tab_contacts.html", {
        "case": case,
        "contacts": case.contacts.all(),
        "contact_form": AddContactForm(),
    })


@login_required
def tab_notes(request: HttpRequest, pk: str) -> HttpResponse:
    """HTMX partial: notes tab content."""
    case = get_object_or_404(Case, pk=pk)
    return render(request, "cases/partials/tab_notes.html", {
        "case": case,
        "notes": case.notes.all().select_related("author"),
        "note_form": AddNoteForm(),
    })


@login_required
def tab_activity(request: HttpRequest, pk: str) -> HttpResponse:
    """HTMX partial: activity log tab content."""
    case = get_object_or_404(Case, pk=pk)
    return render(request, "cases/partials/tab_activity.html", {
        "case": case,
        "activities": case.activity_log.all().select_related("user"),
    })


# =========================================================================
# Deadline actions
# =========================================================================


@login_required
@require_POST
def deadline_complete(request: HttpRequest, case_pk: str, deadline_pk: str) -> HttpResponse:
    """Mark a deadline as complete."""
    deadline = get_object_or_404(Deadline, pk=deadline_pk, case_id=case_pk)
    form = CompleteDeadlineForm(request.POST)

    if form.is_valid():
        deadline.mark_complete(request.user, notes=form.cleaned_data.get("notes", ""))
        ActivityLog.objects.create(
            case=deadline.case,
            user=request.user,
            action=ActivityAction.DEADLINE_COMPLETED,
            description=f"Completed: {deadline.title}",
        )

        if request.htmx:
            response = render(request, "cases/partials/deadline_row.html", {
                "deadline": deadline,
                "case": deadline.case,
                "show_case": False,
            })
            response["HX-Trigger"] = json.dumps({
                "show-toast": {"message": f'Completed: {deadline.title}', "type": "success"},
            })
            return response

        messages.success(request, f'Completed: {deadline.title}')

    return redirect(reverse("cases:detail", args=[case_pk]) + "?tab=deadlines")


@login_required
@require_POST
def deadline_extend(request: HttpRequest, case_pk: str, deadline_pk: str) -> HttpResponse:
    """Extend a deadline's due date."""
    deadline = get_object_or_404(Deadline, pk=deadline_pk, case_id=case_pk)

    if not deadline.is_extendable:
        if request.htmx:
            response = HttpResponse(status=422)
            response["HX-Trigger"] = json.dumps({
                "show-toast": {"message": "This deadline cannot be extended.", "type": "error"},
            })
            return response
        messages.error(request, "This deadline cannot be extended.")
        return redirect(reverse("cases:detail", args=[case_pk]) + "?tab=deadlines")

    form = ExtendDeadlineForm(request.POST)
    if form.is_valid():
        old_date = deadline.due_date
        deadline.due_date = form.cleaned_data["new_due_date"]
        deadline.save(update_fields=["due_date", "updated_at"])

        ActivityLog.objects.create(
            case=deadline.case,
            user=request.user,
            action=ActivityAction.DEADLINE_UPDATED,
            description=(
                f"Extended: {deadline.title} from {old_date} to {deadline.due_date}. "
                f"Reason: {form.cleaned_data['reason']}"
            ),
        )

        if request.htmx:
            response = render(request, "cases/partials/deadline_row.html", {
                "deadline": deadline,
                "case": deadline.case,
                "show_case": False,
            })
            response["HX-Trigger"] = json.dumps({
                "show-toast": {"message": f'Extended: {deadline.title} to {deadline.due_date}', "type": "success"},
            })
            return response

        messages.success(request, f'Extended: {deadline.title} to {deadline.due_date}')

    return redirect(reverse("cases:detail", args=[case_pk]) + "?tab=deadlines")


# =========================================================================
# Note / Contact add
# =========================================================================


@login_required
@require_POST
def note_add(request: HttpRequest, pk: str) -> HttpResponse:
    """Add a note to a case."""
    case = get_object_or_404(Case, pk=pk)
    form = AddNoteForm(request.POST)

    if form.is_valid():
        note = form.save(commit=False)
        note.case = case
        note.author = request.user
        note.save()

        ActivityLog.objects.create(
            case=case,
            user=request.user,
            action=ActivityAction.NOTE_ADDED,
            description=f"Added {note.get_note_type_display()} note",
        )

        if request.htmx:
            response = render(request, "cases/partials/tab_notes.html", {
                "case": case,
                "notes": case.notes.all().select_related("author"),
                "note_form": AddNoteForm(),
            })
            response["HX-Trigger"] = json.dumps({
                "show-toast": {"message": "Note added", "type": "success"},
            })
            return response

        messages.success(request, "Note added")
        return redirect(reverse("cases:detail", args=[pk]) + "?tab=notes")

    # Form invalid — re-render with errors
    if request.htmx:
        return render(request, "cases/partials/tab_notes.html", {
            "case": case,
            "notes": case.notes.all().select_related("author"),
            "note_form": form,
        })

    return render(request, "cases/case_detail.html", {
        "case": case,
        "active_tab": "notes",
        "notes": case.notes.all().select_related("author"),
        "note_form": form,
    })


@login_required
@require_POST
def contact_add(request: HttpRequest, pk: str) -> HttpResponse:
    """Add a contact to a case."""
    case = get_object_or_404(Case, pk=pk)
    form = AddContactForm(request.POST)

    if form.is_valid():
        contact = form.save(commit=False)
        contact.case = case
        contact.save()

        ActivityLog.objects.create(
            case=case,
            user=request.user,
            action=ActivityAction.CONTACT_ADDED,
            description=f"Added contact: {contact.name} ({contact.get_role_display()})",
        )

        if request.htmx:
            response = render(request, "cases/partials/tab_contacts.html", {
                "case": case,
                "contacts": case.contacts.all(),
                "contact_form": AddContactForm(),
            })
            response["HX-Trigger"] = json.dumps({
                "show-toast": {"message": f"Contact added: {contact.name}", "type": "success"},
            })
            return response

        messages.success(request, f"Contact added: {contact.name}")
        return redirect(reverse("cases:detail", args=[pk]) + "?tab=contacts")

    if request.htmx:
        return render(request, "cases/partials/tab_contacts.html", {
            "case": case,
            "contacts": case.contacts.all(),
            "contact_form": form,
        })

    return render(request, "cases/case_detail.html", {
        "case": case,
        "active_tab": "contacts",
        "contacts": case.contacts.all(),
        "contact_form": form,
    })


# =========================================================================
# Quick-add (case + deadline)
# =========================================================================


@login_required
def case_add(request: HttpRequest) -> HttpResponse:
    """Quick-add a new case."""
    if request.method == "POST":
        form = QuickAddCaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.created_by = request.user
            case.save()

            ActivityLog.objects.create(
                case=case,
                user=request.user,
                action=ActivityAction.CASE_CREATED,
                description=f"Created case: {case.caption}",
            )

            messages.success(request, f"Case created: {case.case_number}")

            if request.htmx:
                response = HttpResponse(status=204)
                response["HX-Redirect"] = reverse("cases:detail", args=[case.pk])
                return response

            return redirect("cases:detail", pk=case.pk)

        # Invalid form
        if request.htmx:
            return render(request, "cases/partials/quick_add_case.html", {"case_form": form})

    else:
        form = QuickAddCaseForm()

    # Non-HTMX GET or invalid form fallback
    if request.htmx:
        return render(request, "cases/partials/quick_add_case.html", {"case_form": form})

    return render(request, "cases/case_add.html", {"case_form": form})


@login_required
def deadline_add(request: HttpRequest) -> HttpResponse:
    """Quick-add a new deadline."""
    if request.method == "POST":
        form = QuickAddDeadlineForm(request.POST)
        if form.is_valid():
            deadline = form.save()

            ActivityLog.objects.create(
                case=deadline.case,
                user=request.user,
                action=ActivityAction.DEADLINE_CREATED,
                description=f"Created deadline: {deadline.title} (due {deadline.due_date})",
            )

            messages.success(request, f"Deadline created: {deadline.title}")

            if request.htmx:
                response = HttpResponse(status=204)
                response["HX-Redirect"] = (
                    reverse("cases:detail", args=[deadline.case_id]) + "?tab=deadlines"
                )
                return response

            return redirect(
                reverse("cases:detail", args=[deadline.case_id]) + "?tab=deadlines"
            )

        if request.htmx:
            return render(request, "cases/partials/quick_add_deadline.html", {"deadline_form": form})

    else:
        form = QuickAddDeadlineForm()

    if request.htmx:
        return render(request, "cases/partials/quick_add_deadline.html", {"deadline_form": form})

    return render(request, "cases/deadline_add.html", {"deadline_form": form})


# =========================================================================
# Changelog
# =========================================================================


@login_required
def changelog(request: HttpRequest) -> HttpResponse:
    """Show all published changelog entries, newest first."""
    entries = ChangelogEntry.objects.filter(is_published=True)
    return render(request, "cases/changelog.html", {"entries": entries})


@login_required
@require_POST
def changelog_dismiss(request: HttpRequest) -> HttpResponse:
    """Mark the user as having read through the current changelog."""
    latest = ChangelogEntry.objects.filter(is_published=True).first()
    if latest:
        UserChangelogRead.objects.update_or_create(
            user=request.user,
            defaults={"last_read_version": latest.version},
        )

    if request.htmx:
        return HttpResponse("")

    return redirect("cases:dashboard")


# =========================================================================
# Reports
# =========================================================================

# Column definitions: (key, label, is_sortable)
_REPORT_COLUMNS: list[tuple[str, str, bool]] = [
    ("case_number", "Case Number", True),
    ("case_name", "Case Name", True),
    ("phase", "Phase", True),
    ("status", "Status", True),
    ("case_type", "Case Type", True),
    ("county", "County", True),
    ("jurisdiction", "Jurisdiction", True),
    ("court", "Court", True),
    ("judge", "Judge", True),
    ("date_filed", "Date Filed", True),
    ("date_served", "Date Served", True),
    ("date_of_loss", "Date of Loss", True),
    ("sol_expiration", "SOL Expiration", True),
    ("plaintiff_name", "Plaintiff", True),
    ("plaintiff_attorney", "Plaintiff Attorney", False),
    ("insurance_carrier", "Insurance Carrier", True),
    ("contrib_neg", "Contrib. Neg. Pled", True),
    ("next_deadline", "Next Deadline", True),
    ("overdue_count", "Overdue", True),
    ("supervising_partner", "Partner", True),
    ("assigned_paralegal", "Paralegal", True),
]

_DEFAULT_COLUMNS = {"case_number", "case_name", "phase", "county", "next_deadline", "overdue_count"}

# Sort field mapping — column key -> ORM field(s)
_SORT_FIELDS: dict[str, str] = {
    "case_number": "case_number",
    "case_name": "short_name",
    "phase": "phase",
    "status": "status",
    "case_type": "case_type",
    "county": "county",
    "jurisdiction": "jurisdiction",
    "court": "court",
    "judge": "_judge_name",
    "date_filed": "date_filed",
    "date_served": "date_served",
    "date_of_loss": "date_of_loss",
    "sol_expiration": "statute_of_limitations",
    "plaintiff_name": "plaintiff_name",
    "insurance_carrier": "insurance_carrier",
    "contrib_neg": "pled_contributory_negligence",
    "next_deadline": "_next_deadline",
    "overdue_count": "_overdue_count",
    "supervising_partner": "supervising_partner",
    "assigned_paralegal": "assigned_paralegal",
}


def _report_queryset(params: dict[str, str | list[str]]) -> tuple[QuerySet, int]:
    """Build filtered and sorted report queryset.

    Returns:
        Tuple of (filtered queryset, total unfiltered count).
    """
    today = date.today()

    # Base queryset with annotations for computed columns.
    qs = Case.objects.annotate(
        _overdue_count=Count(
            "deadlines",
            filter=Q(deadlines__completed=False, deadlines__due_date__lt=today),
        ),
        _next_deadline=Min(
            "deadlines__due_date",
            filter=Q(deadlines__completed=False, deadlines__due_date__gte=today),
        ),
        _judge_name=Subquery(
            CaseContact.objects.filter(
                case=OuterRef("pk"),
                role=ContactRole.JUDGE,
            ).values("name")[:1]
        ),
        _plaintiff_attorney=Subquery(
            CaseContact.objects.filter(
                case=OuterRef("pk"),
                role=ContactRole.PLAINTIFF_ATTORNEY,
            ).values("name")[:1]
        ),
    )

    total = qs.count()

    # Multi-select filters
    def _multi(key: str) -> list[str]:
        val = params.get(key)
        if isinstance(val, list):
            return [v for v in val if v]
        if isinstance(val, str) and val:
            return [val]
        return []

    phases = _multi("phase")
    if phases:
        qs = qs.filter(phase__in=phases)

    statuses = _multi("status")
    if statuses:
        qs = qs.filter(status__in=statuses)

    counties = _multi("county")
    if counties:
        qs = qs.filter(county__in=counties)

    jurisdictions = _multi("jurisdiction")
    if jurisdictions:
        qs = qs.filter(jurisdiction__in=jurisdictions)

    case_types = _multi("case_type")
    if case_types:
        qs = qs.filter(case_type__in=case_types)

    partners = _multi("partner")
    if partners:
        qs = qs.filter(supervising_partner__in=partners)

    # Boolean filters
    if params.get("has_overdue") == "yes":
        qs = qs.filter(_overdue_count__gt=0)

    if params.get("no_contrib_neg") == "yes":
        qs = qs.filter(pled_contributory_negligence=False)

    # Date range filters
    for field_key, orm_field in [
        ("date_filed", "date_filed"),
        ("date_served", "date_served"),
        ("date_of_loss", "date_of_loss"),
        ("sol_expiration", "statute_of_limitations"),
    ]:
        from_val = params.get(f"{field_key}_from", "")
        to_val = params.get(f"{field_key}_to", "")
        if isinstance(from_val, str) and from_val:
            qs = qs.filter(**{f"{orm_field}__gte": from_val})
        if isinstance(to_val, str) and to_val:
            qs = qs.filter(**{f"{orm_field}__lte": to_val})

    # Sorting
    sort_col = params.get("sort", "case_number")
    if isinstance(sort_col, list):
        sort_col = sort_col[0] if sort_col else "case_number"
    sort_dir = params.get("dir", "asc")
    if isinstance(sort_dir, list):
        sort_dir = sort_dir[0] if sort_dir else "asc"

    orm_field = _SORT_FIELDS.get(sort_col, "case_number")
    if sort_dir == "desc":
        orm_field = f"-{orm_field}"
    qs = qs.order_by(orm_field, "case_number")

    return qs, total


def _get_cell_value(case: Case, col_key: str) -> str:
    """Get the display value for a report cell."""
    if col_key == "case_number":
        return case.case_number
    if col_key == "case_name":
        return case.short_name or case.caption
    if col_key == "phase":
        return case.get_phase_display()
    if col_key == "status":
        return case.get_status_display()
    if col_key == "case_type":
        return case.get_case_type_display()
    if col_key == "county":
        return case.county
    if col_key == "jurisdiction":
        return case.get_jurisdiction_display()
    if col_key == "court":
        return case.court
    if col_key == "judge":
        return getattr(case, "_judge_name", None) or ""
    if col_key == "date_filed":
        return str(case.date_filed) if case.date_filed else ""
    if col_key == "date_served":
        return str(case.date_served) if case.date_served else ""
    if col_key == "date_of_loss":
        return str(case.date_of_loss) if case.date_of_loss else ""
    if col_key == "sol_expiration":
        return str(case.statute_of_limitations) if case.statute_of_limitations else ""
    if col_key == "plaintiff_name":
        return case.plaintiff_name
    if col_key == "plaintiff_attorney":
        return getattr(case, "_plaintiff_attorney", None) or ""
    if col_key == "insurance_carrier":
        return case.insurance_carrier
    if col_key == "contrib_neg":
        return "Yes" if case.pled_contributory_negligence else "No"
    if col_key == "next_deadline":
        nd = getattr(case, "_next_deadline", None)
        if nd:
            days = (nd - date.today()).days
            return f"{nd} ({days}d)"
        return ""
    if col_key == "overdue_count":
        return str(getattr(case, "_overdue_count", 0))
    if col_key == "supervising_partner":
        return case.supervising_partner
    if col_key == "assigned_paralegal":
        return case.assigned_paralegal
    return ""


def _parse_columns(params: dict[str, str | list[str]]) -> list[str]:
    """Parse selected columns from request params."""
    cols = params.get("cols")
    if isinstance(cols, list):
        valid = {c[0] for c in _REPORT_COLUMNS}
        return [c for c in cols if c in valid]
    if isinstance(cols, str) and cols:
        valid = {c[0] for c in _REPORT_COLUMNS}
        return [c for c in cols.split(",") if c in valid]
    return []


def _report_context(request: HttpRequest) -> dict:
    """Build the full context for the report builder."""
    params = request.GET

    selected_cols = _parse_columns(params)
    if not selected_cols:
        selected_cols = [c[0] for c in _REPORT_COLUMNS if c[0] in _DEFAULT_COLUMNS]

    cases, total = _report_queryset(params)
    filtered_count = cases.count()

    # Build row data for selected columns
    column_defs = [(key, label, sortable) for key, label, sortable in _REPORT_COLUMNS if key in selected_cols]
    # Preserve order of _REPORT_COLUMNS
    col_order = {c[0]: i for i, c in enumerate(_REPORT_COLUMNS)}
    column_defs.sort(key=lambda c: col_order[c[0]])

    rows = []
    for c in cases:
        row = {
            "pk": str(c.pk),
            "cells": [_get_cell_value(c, col[0]) for col in column_defs],
            "overdue_count": getattr(c, "_overdue_count", 0),
            "contrib_neg": c.pled_contributory_negligence,
        }
        rows.append(row)

    sort_col = params.get("sort", "case_number")
    sort_dir = params.get("dir", "asc")

    # Gather distinct values for multi-select filters
    counties = list(Case.objects.values_list("county", flat=True).distinct().order_by("county"))
    partners = list(
        Case.objects.exclude(supervising_partner="")
        .values_list("supervising_partner", flat=True)
        .distinct()
        .order_by("supervising_partner")
    )

    return {
        "all_columns": _REPORT_COLUMNS,
        "selected_cols": selected_cols,
        "column_defs": column_defs,
        "rows": rows,
        "total_count": total,
        "filtered_count": filtered_count,
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        "phase_choices": CasePhase.choices,
        "status_choices": CaseStatus.choices,
        "case_type_choices": CaseType.choices,
        "jurisdiction_choices": Jurisdiction.choices,
        "county_values": counties,
        "partner_values": partners,
        "active_filters": {
            "phase": params.getlist("phase"),
            "status": params.getlist("status"),
            "county": params.getlist("county"),
            "jurisdiction": params.getlist("jurisdiction"),
            "case_type": params.getlist("case_type"),
            "partner": params.getlist("partner"),
            "has_overdue": params.get("has_overdue", ""),
            "no_contrib_neg": params.get("no_contrib_neg", ""),
            "date_filed_from": params.get("date_filed_from", ""),
            "date_filed_to": params.get("date_filed_to", ""),
            "date_served_from": params.get("date_served_from", ""),
            "date_served_to": params.get("date_served_to", ""),
            "date_of_loss_from": params.get("date_of_loss_from", ""),
            "date_of_loss_to": params.get("date_of_loss_to", ""),
            "sol_expiration_from": params.get("sol_expiration_from", ""),
            "sol_expiration_to": params.get("sol_expiration_to", ""),
        },
    }


@login_required
def report_builder(request: HttpRequest) -> HttpResponse:
    """Report builder page with column picker, filters, and results table."""
    return render(request, "cases/reports.html", _report_context(request))


@login_required
def report_results(request: HttpRequest) -> HttpResponse:
    """HTMX partial: filtered report results table."""
    return render(request, "cases/partials/report_results.html", _report_context(request))


@login_required
def report_export(request: HttpRequest) -> HttpResponse:
    """Export current filtered report as CSV."""
    params = request.GET
    selected_cols = _parse_columns(params)
    if not selected_cols:
        selected_cols = [c[0] for c in _REPORT_COLUMNS if c[0] in _DEFAULT_COLUMNS]

    cases, _ = _report_queryset(params)

    col_order = {c[0]: i for i, c in enumerate(_REPORT_COLUMNS)}
    column_defs = [(key, label, sortable) for key, label, sortable in _REPORT_COLUMNS if key in selected_cols]
    column_defs.sort(key=lambda c: col_order[c[0]])

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="case_report.csv"'

    writer = csv.writer(response)
    writer.writerow([col[1] for col in column_defs])

    for c in cases:
        writer.writerow([_get_cell_value(c, col[0]) for col in column_defs])

    return response


# =========================================================================
# Global Search
# =========================================================================


def _search_results(query: str) -> dict:
    """Search across Cases, Contacts, Notes, and Deadlines.

    Returns a dict with grouped results and counts.
    """
    results: dict[str, list] = {
        "cases": [],
        "contacts": [],
        "notes": [],
        "deadlines": [],
    }

    if len(query) < 2:
        return results

    # --- Cases ---
    case_q = (
        Q(case_number__icontains=query)
        | Q(caption__icontains=query)
        | Q(short_name__icontains=query)
        | Q(plaintiff_name__icontains=query)
        | Q(defendant_name__icontains=query)
        | Q(court__icontains=query)
        | Q(county__icontains=query)
        | Q(insurance_carrier__icontains=query)
        | Q(supervising_partner__icontains=query)
        | Q(assigned_paralegal__icontains=query)
    )
    for case in Case.objects.filter(case_q).distinct()[:20]:
        # Determine which field matched for context
        match_field = _find_case_match(case, query)
        results["cases"].append({
            "case": case,
            "match_field": match_field,
        })

    # --- Contacts ---
    contact_q = (
        Q(name__icontains=query)
        | Q(firm__icontains=query)
        | Q(email__icontains=query)
        | Q(phone__icontains=query)
    )
    for contact in (
        CaseContact.objects.filter(contact_q)
        .select_related("case")
        .distinct()[:20]
    ):
        match_field = _find_contact_match(contact, query)
        results["contacts"].append({
            "contact": contact,
            "match_field": match_field,
        })

    # --- Notes ---
    note_q = Q(content__icontains=query)
    for note in (
        Note.objects.filter(note_q)
        .select_related("case", "author")
        .distinct()[:20]
    ):
        # Extract a snippet around the match
        snippet = _extract_snippet(note.content, query)
        results["notes"].append({
            "note": note,
            "snippet": snippet,
        })

    # --- Deadlines ---
    deadline_q = (
        Q(title__icontains=query)
        | Q(description__icontains=query)
    )
    for deadline in (
        Deadline.objects.filter(deadline_q)
        .select_related("case")
        .distinct()[:20]
    ):
        match_field = "title" if query.lower() in deadline.title.lower() else "description"
        results["deadlines"].append({
            "deadline": deadline,
            "match_field": match_field,
        })

    return results


def _find_case_match(case: Case, query: str) -> str:
    """Determine which Case field matched the search query."""
    q = query.lower()
    if q in case.case_number.lower():
        return "case number"
    if q in case.caption.lower():
        return "caption"
    if case.short_name and q in case.short_name.lower():
        return "case name"
    if q in case.plaintiff_name.lower():
        return "plaintiff"
    if q in case.defendant_name.lower():
        return "defendant"
    if q in case.court.lower():
        return "court"
    if q in case.county.lower():
        return "county"
    if q in case.insurance_carrier.lower():
        return "insurance carrier"
    if q in case.supervising_partner.lower():
        return "partner"
    if q in case.assigned_paralegal.lower():
        return "paralegal"
    return "case"


def _find_contact_match(contact: CaseContact, query: str) -> str:
    """Determine which CaseContact field matched the search query."""
    q = query.lower()
    if q in contact.name.lower():
        return "name"
    if contact.firm and q in contact.firm.lower():
        return "firm"
    if contact.email and q in contact.email.lower():
        return "email"
    if contact.phone and q in contact.phone.lower():
        return "phone"
    return "contact"


def _extract_snippet(text: str, query: str, context_chars: int = 60) -> str:
    """Extract a snippet of text around the first occurrence of the query."""
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return text[:120] + ("..." if len(text) > 120 else "")

    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)
    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


@login_required
def global_search(request: HttpRequest) -> HttpResponse:
    """Full-page search view."""
    query = request.GET.get("q", "").strip()
    results = _search_results(query)
    total = sum(len(v) for v in results.values())

    return render(request, "cases/search.html", {
        "query": query,
        "results": results,
        "total": total,
    })


@login_required
def search_results_partial(request: HttpRequest) -> HttpResponse:
    """HTMX partial: return grouped search results."""
    query = request.GET.get("q", "").strip()
    results = _search_results(query)
    total = sum(len(v) for v in results.values())

    return render(request, "cases/partials/search_results.html", {
        "query": query,
        "results": results,
        "total": total,
    })


# =========================================================================
# Feedback
# =========================================================================


@login_required
def feedback_list(request: HttpRequest) -> HttpResponse:
    """List all of the user's feedback requests, newest first."""
    requests_qs = FeedbackRequest.objects.filter(user=request.user)
    return render(request, "cases/feedback_list.html", {
        "feedback_requests": requests_qs,
    })


@login_required
def feedback_create(request: HttpRequest) -> HttpResponse:
    """Create a new feedback request."""
    if request.method == "POST":
        form = FeedbackRequestForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()

            if request.htmx:
                response = HttpResponse(status=204)
                response["HX-Redirect"] = reverse("cases:feedback-list")
                return response

            messages.success(request, "Request sent! Kasey will take a look.")
            return redirect("cases:feedback-list")

        if request.htmx:
            return render(request, "cases/feedback_form.html", {"form": form})

    else:
        form = FeedbackRequestForm()

    return render(request, "cases/feedback_form.html", {"form": form})
