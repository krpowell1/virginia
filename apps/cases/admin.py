from __future__ import annotations

from datetime import date

from django.contrib import admin
from django.db.models import Count, Min, Q, QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from .models import (
    ActivityLog,
    CalendarToken,
    Case,
    CaseContact,
    ChangelogEntry,
    Deadline,
    FeedbackRequest,
    FeedbackStatus,
    Note,
)

# ---------------------------------------------------------------------------
# Site branding
# ---------------------------------------------------------------------------
admin.site.site_header = "Defense Case Manager"
admin.site.site_title = "DCM Admin"
admin.site.index_title = "Case Management"


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class DeadlineInline(admin.TabularInline):
    """Inline deadlines on the Case change form."""

    model = Deadline
    extra = 0
    fields = (
        "title",
        "due_date",
        "deadline_type",
        "assigned_to",
        "is_extendable",
        "completed",
        "rule_reference",
    )
    readonly_fields = ("rule_reference",)
    ordering = ("due_date",)
    show_change_link = True


class CaseContactInline(admin.TabularInline):
    """Inline contacts on the Case change form."""

    model = CaseContact
    extra = 0
    fields = ("name", "role", "firm", "email", "phone")


class NoteInline(admin.StackedInline):
    """Inline notes on the Case change form."""

    model = Note
    extra = 1
    fields = ("content", "note_type", "is_privileged", "author")
    readonly_fields = ("author",)

    def save_model(self, request: HttpRequest, obj: Note, form: object, change: bool) -> None:
        """Auto-set author to the current user on new notes."""
        if not obj.pk:
            obj.author = request.user
        super().save_model(request, obj, form, change)


# ---------------------------------------------------------------------------
# CaseAdmin
# ---------------------------------------------------------------------------


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """Admin for defense litigation cases.

    Computed columns show the next upcoming deadline and count of
    overdue deadlines. Contributory negligence is flagged prominently
    when not yet pled.
    """

    list_display = (
        "case_number",
        "short_name",
        "phase",
        "status",
        "county",
        "date_served",
        "next_deadline",
        "overdue_count",
        "contrib_neg_flag",
    )
    list_filter = ("phase", "status", "case_type", "county", "jurisdiction")
    search_fields = ("case_number", "caption", "short_name", "plaintiff_name")
    list_per_page = 25
    date_hierarchy = "created_at"

    fieldsets = (
        ("Case Identification", {
            "fields": (
                "case_number",
                "internal_reference",
                "caption",
                "short_name",
            ),
        }),
        ("Classification", {
            "fields": (
                ("phase", "status"),
                ("case_type", "jurisdiction"),
                ("court", "county"),
            ),
        }),
        ("Parties", {
            "fields": (
                "plaintiff_name",
                "defendant_name",
            ),
        }),
        ("Key Dates", {
            "fields": (
                ("date_filed", "date_of_loss"),
                ("date_served", "service_method"),
                ("date_answer_due", "statute_of_limitations"),
                "date_closed",
            ),
        }),
        ("Insurance", {
            "fields": (
                ("insurance_carrier", "claim_number"),
                ("policy_limit", "reserve_amount"),
                "client_approved",
            ),
        }),
        ("Affirmative Defenses", {
            "fields": (
                "pled_contributory_negligence",
                "pled_assumption_of_risk",
            ),
            "description": (
                "Alabama is a pure contributory negligence state. "
                "Failure to plead = permanent waiver."
            ),
        }),
        ("Team", {
            "fields": (
                ("supervising_partner", "assigned_paralegal"),
                "created_by",
            ),
        }),
        ("Description", {
            "fields": ("description",),
            "classes": ("collapse",),
        }),
    )

    inlines = [DeadlineInline, CaseContactInline, NoteInline]
    readonly_fields = ("created_by",)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Annotate with next deadline date and overdue count."""
        qs = super().get_queryset(request)
        today = date.today()
        return qs.annotate(
            _overdue_count=Count(
                "deadlines",
                filter=Q(
                    deadlines__completed=False,
                    deadlines__due_date__lt=today,
                ),
            ),
            _next_deadline_date=Min(
                "deadlines__due_date",
                filter=Q(
                    deadlines__completed=False,
                    deadlines__due_date__gte=today,
                ),
            ),
        )

    @admin.display(description="Next Deadline", ordering="_next_deadline_date")
    def next_deadline(self, obj: Case) -> str:
        """Show the next upcoming deadline date with days remaining."""
        dt = getattr(obj, "_next_deadline_date", None)
        if dt is None:
            return "\u2014"
        days = (dt - date.today()).days
        if days == 0:
            label = "TODAY"
        elif days == 1:
            label = "1 day"
        else:
            label = f"{days} days"
        return format_html("{} <small>({})</small>", dt, label)

    @admin.display(description="Overdue", ordering="_overdue_count")
    def overdue_count(self, obj: Case) -> str:
        """Show the count of overdue deadlines, red if any."""
        count = getattr(obj, "_overdue_count", 0)
        if count:
            return format_html(
                '<span style="color:red;font-weight:bold;">{}</span>', count
            )
        return "0"

    @admin.display(description="Contrib. Neg.", boolean=False)
    def contrib_neg_flag(self, obj: Case) -> str:
        """Prominently flag when contributory negligence has NOT been pled."""
        if obj.pled_contributory_negligence:
            return format_html('<span style="color:green;">Pled</span>')
        return format_html(
            '<span style="color:red;font-weight:bold;">'
            "NOT PLED"
            "</span>"
        )

    def save_model(self, request: HttpRequest, obj: Case, form: object, change: bool) -> None:
        """Set created_by on new cases."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request: HttpRequest, form: object, formset: object, change: bool) -> None:
        """Auto-set author on new notes created via inline."""
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Note) and not instance.pk:
                instance.author = request.user
            instance.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()


# ---------------------------------------------------------------------------
# DeadlineAdmin
# ---------------------------------------------------------------------------


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    """Admin for individual deadlines with urgency display."""

    list_display = (
        "case",
        "title",
        "due_date",
        "deadline_type",
        "is_extendable",
        "display_status",
        "assigned_to",
        "display_urgency",
    )
    list_filter = ("deadline_type", "is_extendable", "completed", "is_jurisdictional")
    search_fields = ("title", "case__case_number", "case__caption")
    date_hierarchy = "due_date"
    list_per_page = 50

    URGENCY_COLORS: dict[str, str] = {
        "OVERDUE": "#dc2626",
        "URGENT": "#ea580c",
        "WARNING": "#ca8a04",
        "NORMAL": "#16a34a",
        "COMPLETED": "#6b7280",
    }

    @admin.display(description="Status")
    def display_status(self, obj: Deadline) -> str:
        """Show the computed status property."""
        return obj.status

    @admin.display(description="Urgency")
    def display_urgency(self, obj: Deadline) -> str:
        """Show urgency with color coding."""
        level = obj.urgency_level
        color = self.URGENCY_COLORS.get(level, "#000")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>', color, level
        )


# ---------------------------------------------------------------------------
# ActivityLogAdmin (read-only)
# ---------------------------------------------------------------------------


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Read-only admin for the immutable audit trail.

    No add, change, or delete permissions — view only.
    """

    list_display = ("timestamp", "case", "user", "action", "short_description")
    list_filter = ("action",)
    search_fields = ("description", "case__case_number")
    date_hierarchy = "timestamp"
    list_per_page = 50
    readonly_fields = ("id", "case", "user", "action", "description", "timestamp")

    @admin.display(description="Description")
    def short_description(self, obj: ActivityLog) -> str:
        """Truncate description for list view."""
        text = obj.description
        if len(text) > 120:
            return text[:120] + "\u2026"
        return text

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


# ---------------------------------------------------------------------------
# Register remaining models without custom admin
# ---------------------------------------------------------------------------

admin.site.register(CaseContact)
admin.site.register(Note)


# ---------------------------------------------------------------------------
# CalendarTokenAdmin
# ---------------------------------------------------------------------------


@admin.register(ChangelogEntry)
class ChangelogEntryAdmin(admin.ModelAdmin):
    """Admin for changelog entries — Kasey adds these when pushing updates."""

    list_display = ("version", "title", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "description")
    ordering = ("-created_at",)


@admin.register(FeedbackRequest)
class FeedbackRequestAdmin(admin.ModelAdmin):
    """Admin for reviewing and responding to Virginia's feedback requests."""

    list_display = ("title", "user", "request_type", "priority", "status", "created_at")
    list_filter = ("status", "request_type", "priority")
    list_editable = ("status",)
    search_fields = ("title", "description")
    readonly_fields = ("user", "request_type", "title", "description", "priority", "created_at")
    ordering = ("-created_at",)

    fieldsets = (
        ("Request (from Virginia)", {
            "fields": ("user", "request_type", "title", "description", "priority", "created_at"),
        }),
        ("Response (from Kasey)", {
            "fields": ("status", "admin_notes", "resolved_at"),
        }),
    )

    def save_model(self, request: HttpRequest, obj: FeedbackRequest, form: object, change: bool) -> None:
        """Auto-set resolved_at when status changes to DONE."""
        if obj.status == FeedbackStatus.DONE and not obj.resolved_at:
            from django.utils import timezone
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(CalendarToken)
class CalendarTokenAdmin(admin.ModelAdmin):
    """Admin for webcal feed tokens."""

    list_display = ("user", "short_token", "is_active", "created_at")
    list_filter = ("is_active",)
    readonly_fields = ("token", "created_at")

    @admin.display(description="Token")
    def short_token(self, obj: CalendarToken) -> str:
        """Show truncated token for readability."""
        return f"{obj.token[:12]}..."
