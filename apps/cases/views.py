from __future__ import annotations

import json
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Min, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AddContactForm,
    AddNoteForm,
    CompleteDeadlineForm,
    ExtendDeadlineForm,
    QuickAddCaseForm,
    QuickAddDeadlineForm,
)
from .models import (
    ActivityAction,
    ActivityLog,
    Case,
    CasePhase,
    Deadline,
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

    return render(request, "cases/dashboard.html", {
        "rfa_risk_deadlines": rfa_risk,
        "overdue_deadlines": overdue,
        "today_deadlines": today_deadlines,
        "this_week_deadlines": this_week,
        "missing_defenses": missing_defenses,
        "pending_approval": pending_approval,
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
