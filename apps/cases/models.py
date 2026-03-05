from __future__ import annotations

import secrets
import uuid
from datetime import date
from typing import ClassVar

from django.conf import settings
from django.db import models

from .managers import CaseQuerySet, DeadlineQuerySet


# ===========================================================================
# TextChoices enums
# ===========================================================================


class CaseStatus(models.TextChoices):
    """Lifecycle status of a case."""

    ACTIVE = "ACTIVE", "Active"
    SETTLED = "SETTLED", "Settled"
    DISMISSED = "DISMISSED", "Dismissed"
    CLOSED = "CLOSED", "Closed"
    ON_APPEAL = "ON_APPEAL", "On Appeal"


class CasePhase(models.TextChoices):
    """Current litigation phase."""

    PLEADING = "PLEADING", "Pleading"
    DISCOVERY = "DISCOVERY", "Discovery"
    DISPOSITIVE_MOTIONS = "DISPOSITIVE_MOTIONS", "Dispositive Motions"
    TRIAL_PREP = "TRIAL_PREP", "Trial Preparation"
    TRIAL = "TRIAL", "Trial"
    POST_TRIAL = "POST_TRIAL", "Post-Trial"
    APPEAL = "APPEAL", "Appeal"


class Jurisdiction(models.TextChoices):
    """Court system for the case."""

    STATE = "STATE", "State"
    FEDERAL = "FEDERAL", "Federal"


class CaseType(models.TextChoices):
    """Category of litigation."""

    PREMISES_LIABILITY = "PREMISES_LIABILITY", "Premises Liability"
    AUTO_ACCIDENT = "AUTO_ACCIDENT", "Auto Accident"
    PRODUCTS_LIABILITY = "PRODUCTS_LIABILITY", "Products Liability"
    MEDICAL_MALPRACTICE = "MEDICAL_MALPRACTICE", "Medical Malpractice"
    GENERAL_LIABILITY = "GENERAL_LIABILITY", "General Liability"
    WORKERS_COMP = "WORKERS_COMP", "Workers' Compensation"
    OTHER = "OTHER", "Other"


class ServiceMethod(models.TextChoices):
    """How the defendant was served."""

    PERSONAL = "PERSONAL", "Personal Service"
    CERTIFIED_MAIL = "CERTIFIED_MAIL", "Certified Mail"
    PUBLICATION = "PUBLICATION", "Service by Publication"
    EFILE = "EFILE", "E-File / E-Service"
    PROCESS_SERVER = "PROCESS_SERVER", "Process Server"
    WAIVER = "WAIVER", "Waiver of Service"


class DeadlineType(models.TextChoices):
    """Category of deadline."""

    ANSWER = "ANSWER", "Answer"
    REMOVAL = "REMOVAL", "Federal Removal"
    DISCOVERY = "DISCOVERY", "Discovery"
    MOTION = "MOTION", "Motion"
    TRIAL = "TRIAL", "Trial"
    PRETRIAL = "PRETRIAL", "Pretrial"
    MEDIATION = "MEDIATION", "Mediation"
    APPEAL = "APPEAL", "Appeal"
    POST_JUDGMENT = "POST_JUDGMENT", "Post-Judgment"
    INTERNAL = "INTERNAL", "Internal"
    OTHER = "OTHER", "Other"


class ContactRole(models.TextChoices):
    """Role a contact plays in a case."""

    PLAINTIFF_ATTORNEY = "PLAINTIFF_ATTORNEY", "Plaintiff Attorney"
    CO_DEFENDANT_ATTORNEY = "CO_DEFENDANT_ATTORNEY", "Co-Defendant Attorney"
    EXPERT_WITNESS = "EXPERT_WITNESS", "Expert Witness"
    FACT_WITNESS = "FACT_WITNESS", "Fact Witness"
    INSURANCE_ADJUSTER = "INSURANCE_ADJUSTER", "Insurance Adjuster"
    MEDIATOR = "MEDIATOR", "Mediator"
    COURT_REPORTER = "COURT_REPORTER", "Court Reporter"
    JUDGE = "JUDGE", "Judge"
    CLERK = "CLERK", "Clerk"
    OTHER = "OTHER", "Other"


class NoteType(models.TextChoices):
    """Category of case note."""

    GENERAL = "GENERAL", "General"
    RESEARCH = "RESEARCH", "Research"
    STRATEGY = "STRATEGY", "Strategy"
    CLIENT_COMMUNICATION = "CLIENT_COMMUNICATION", "Client Communication"
    COURT_FILING = "COURT_FILING", "Court Filing"
    INTERNAL = "INTERNAL", "Internal"


class ActivityAction(models.TextChoices):
    """Type of activity logged."""

    CASE_CREATED = "CASE_CREATED", "Case Created"
    CASE_UPDATED = "CASE_UPDATED", "Case Updated"
    CASE_CLOSED = "CASE_CLOSED", "Case Closed"
    DEADLINE_CREATED = "DEADLINE_CREATED", "Deadline Created"
    DEADLINE_COMPLETED = "DEADLINE_COMPLETED", "Deadline Completed"
    DEADLINE_UPDATED = "DEADLINE_UPDATED", "Deadline Updated"
    DEADLINE_AUTO_GENERATED = "DEADLINE_AUTO_GENERATED", "Deadline Auto-Generated"
    CONTACT_ADDED = "CONTACT_ADDED", "Contact Added"
    CONTACT_UPDATED = "CONTACT_UPDATED", "Contact Updated"
    NOTE_ADDED = "NOTE_ADDED", "Note Added"


# ===========================================================================
# Models
# ===========================================================================


class Case(models.Model):
    """A defense litigation case.

    Tracks all metadata, parties, and dates for a single lawsuit where
    our client is the defendant. The county field is critical for
    determining court holidays (e.g., Mardi Gras in Mobile/Baldwin).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identifiers
    case_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Court-assigned case number (e.g., CV-2024-900123).",
    )
    internal_reference = models.CharField(
        max_length=50,
        blank=True,
        help_text="Firm's internal file/matter number.",
    )
    caption = models.CharField(
        max_length=255,
        help_text="Case caption, e.g., 'Smith v. Jones Properties LLC'.",
    )
    short_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Short reference name, e.g., 'Smith premises'.",
    )

    # Court info
    court = models.CharField(
        max_length=200,
        help_text="Full court name, e.g., 'Jefferson County Circuit Court'.",
    )
    county = models.CharField(
        max_length=50,
        help_text="Alabama county. Affects holiday calendar (Mardi Gras in Mobile/Baldwin).",
    )
    jurisdiction = models.CharField(
        max_length=10,
        choices=Jurisdiction.choices,
        default=Jurisdiction.STATE,
    )
    case_type = models.CharField(
        max_length=25,
        choices=CaseType.choices,
        default=CaseType.PREMISES_LIABILITY,
    )
    status = models.CharField(
        max_length=15,
        choices=CaseStatus.choices,
        default=CaseStatus.ACTIVE,
    )
    phase = models.CharField(
        max_length=25,
        choices=CasePhase.choices,
        default=CasePhase.PLEADING,
    )

    # Parties
    plaintiff_name = models.CharField(max_length=255)
    defendant_name = models.CharField(
        max_length=255,
        help_text="Our client (the defendant we represent).",
    )

    # Service
    date_filed = models.DateField(null=True, blank=True)
    date_served = models.DateField(
        null=True,
        blank=True,
        help_text="Date defendant was served. Setting this triggers automatic deadline generation.",
    )
    service_method = models.CharField(
        max_length=20,
        choices=ServiceMethod.choices,
        blank=True,
    )

    # Key dates
    date_answer_due = models.DateField(null=True, blank=True)
    date_closed = models.DateField(null=True, blank=True)
    date_of_loss = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the incident or accident.",
    )
    statute_of_limitations = models.DateField(
        null=True,
        blank=True,
        help_text="SOL expiry. Auto-calculated for premises liability (2 years from loss).",
    )

    # Affirmative defenses
    pled_contributory_negligence = models.BooleanField(
        default=False,
        help_text=(
            "Has contributory negligence been pled in the Answer? "
            "Alabama is a pure contributory negligence state — waived if not pled."
        ),
    )
    pled_assumption_of_risk = models.BooleanField(
        default=False,
        help_text="Has assumption of risk been pled in the Answer?",
    )

    # Insurance
    insurance_carrier = models.CharField(max_length=200, blank=True)
    claim_number = models.CharField(max_length=100, blank=True)
    policy_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Policy limit in dollars.",
    )
    reserve_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Insurance reserve amount in dollars.",
    )
    client_approved = models.BooleanField(
        default=False,
        help_text="Has the client/carrier approved the defense strategy?",
    )

    # Team
    supervising_partner = models.CharField(max_length=100, default="Warren")
    assigned_paralegal = models.CharField(max_length=100, default="Mary")

    # Description
    description = models.TextField(
        blank=True,
        help_text="Brief case summary or notes.",
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cases",
    )

    objects: ClassVar[CaseQuerySet] = CaseQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.case_number} — {self.caption}"


class Deadline(models.Model):
    """A deadline or due date tied to a case.

    Status (overdue, pending, etc.) is computed via properties — never
    stored in the database. This eliminates the need for cron jobs or
    periodic status updates.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField(db_index=True)

    # Completion tracking
    completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_deadlines",
    )
    completion_notes = models.TextField(blank=True)

    # Assignment
    assigned_to = models.CharField(
        max_length=100,
        blank=True,
        help_text="Person responsible for this deadline.",
    )

    # Rule metadata
    rule_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Applicable rule, e.g., 'ARCP Rule 12(a)' or '28 U.S.C. 1446'.",
    )
    deadline_type = models.CharField(
        max_length=20,
        choices=DeadlineType.choices,
        default=DeadlineType.OTHER,
    )
    is_extendable = models.BooleanField(
        default=True,
        help_text="False for jurisdictional deadlines that cannot be extended.",
    )
    is_jurisdictional = models.BooleanField(
        default=False,
        help_text="True if missing this deadline results in loss of jurisdiction.",
    )
    alert_days_before = models.PositiveIntegerField(
        default=7,
        help_text="Number of days before due_date to trigger a calendar alert.",
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ClassVar[DeadlineQuerySet] = DeadlineQuerySet.as_manager()  # type: ignore[assignment]

    class Meta:
        ordering = ["due_date"]

    def __str__(self) -> str:
        status = "DONE" if self.completed else self.urgency_level
        return f"[{status}] {self.title} — {self.due_date}"

    # ------------------------------------------------------------------
    # Computed properties (NEVER stored in DB)
    # ------------------------------------------------------------------

    @property
    def days_remaining(self) -> int:
        """Days until the deadline. Negative means overdue."""
        return (self.due_date - date.today()).days

    @property
    def is_overdue(self) -> bool:
        """True if the deadline is past due and not completed."""
        return not self.completed and self.due_date < date.today()

    @property
    def urgency_level(self) -> str:
        """Categorize urgency based on days remaining.

        Returns one of: OVERDUE, URGENT (0-3 days), WARNING (4-7 days), NORMAL.
        """
        if self.completed:
            return "COMPLETED"
        remaining = self.days_remaining
        if remaining < 0:
            return "OVERDUE"
        if remaining <= 3:
            return "URGENT"
        if remaining <= 7:
            return "WARNING"
        return "NORMAL"

    @property
    def status(self) -> str:
        """Human-readable status string.

        Returns one of: COMPLETED, OVERDUE, DUE_TODAY, PENDING.
        """
        if self.completed:
            return "COMPLETED"
        remaining = self.days_remaining
        if remaining < 0:
            return "OVERDUE"
        if remaining == 0:
            return "DUE_TODAY"
        return "PENDING"

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def mark_complete(self, user: settings.AUTH_USER_MODEL, notes: str = "") -> None:
        """Mark this deadline as completed.

        Args:
            user: The user completing the deadline.
            notes: Optional completion notes.
        """
        self.completed = True
        self.completed_date = date.today()
        self.completed_by = user  # type: ignore[assignment]
        self.completion_notes = notes
        self.save(update_fields=[
            "completed",
            "completed_date",
            "completed_by",
            "completion_notes",
            "updated_at",
        ])


class CaseContact(models.Model):
    """A contact associated with a specific case.

    In Phase 1, contacts are case-scoped: the same person appearing in
    multiple cases will have separate CaseContact records. This will be
    refactored to a M2M relationship in Phase 2.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="contacts",
    )

    name = models.CharField(max_length=255)
    role = models.CharField(
        max_length=25,
        choices=ContactRole.choices,
        default=ContactRole.OTHER,
    )
    firm = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_role_display()})"


class Note(models.Model):
    """A chronological note attached to a case.

    Separate from Case.description to support a full history of notes
    with attribution, timestamps, and privilege flags.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="case_notes",
    )

    content = models.TextField()
    note_type = models.CharField(
        max_length=25,
        choices=NoteType.choices,
        default=NoteType.GENERAL,
    )
    is_privileged = models.BooleanField(
        default=False,
        help_text="Attorney-client privileged communication. Handle with care in discovery.",
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        prefix = "[PRIVILEGED] " if self.is_privileged else ""
        return f"{prefix}{self.get_note_type_display()} — {self.created_at:%Y-%m-%d}"


class ActivityLog(models.Model):
    """Immutable audit trail for all case mutations.

    ActivityLog entries cannot be edited or deleted. The save() method
    prevents updates to existing records, and delete() is disabled.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name="activity_log",
        null=True,
        blank=True,
        help_text="Null for system-level events not tied to a specific case.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_log",
    )
    action = models.CharField(
        max_length=30,
        choices=ActivityAction.choices,
    )
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.get_action_display()}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Only allow creation of new records, not updates to existing ones."""
        if self.pk and ActivityLog.objects.filter(pk=self.pk).exists():
            raise ValueError("ActivityLog entries are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        """Prevent deletion of audit trail records."""
        raise ValueError("ActivityLog entries cannot be deleted.")


def _generate_calendar_token() -> str:
    """Generate a 64-character URL-safe token for calendar subscriptions."""
    return secrets.token_urlsafe(48)


class ChangelogEntry(models.Model):
    """A user-facing changelog entry describing what changed in a release.

    Written in plain language for Virginia, not developer jargon.
    Entries are displayed newest-first on the "What's New" page and
    trigger a dashboard banner when unread.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.CharField(
        max_length=20,
        unique=True,
        help_text="Semantic version string, e.g. '1.1.0'.",
    )
    title = models.CharField(
        max_length=200,
        help_text="Short headline, e.g. 'Peach Pink Theme'.",
    )
    description = models.TextField(
        help_text="Plain-language summary written for Virginia, not dev notes.",
    )
    is_published = models.BooleanField(
        default=True,
        help_text="Unpublished entries are hidden from the changelog page.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "changelog entries"

    def __str__(self) -> str:
        return f"v{self.version} — {self.title}"


class UserChangelogRead(models.Model):
    """Tracks the last changelog version a user has seen.

    Used to determine whether to show the 'What's New' banner on the dashboard.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="changelog_read",
    )
    last_read_version = models.CharField(
        max_length=20,
        help_text="The version string the user last dismissed.",
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "user changelog read"
        verbose_name_plural = "user changelog reads"

    def __str__(self) -> str:
        return f"{self.user} read through v{self.last_read_version}"


class FeedbackType(models.TextChoices):
    """Type of feedback request."""

    FEATURE = "FEATURE", "Feature Request"
    BUG = "BUG", "Bug Report"
    CHANGE = "CHANGE", "Change Request"
    OTHER = "OTHER", "Other"


class FeedbackPriority(models.TextChoices):
    """Priority level for a feedback request."""

    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"


class FeedbackStatus(models.TextChoices):
    """Status of a feedback request."""

    NEW = "NEW", "New"
    REVIEWED = "REVIEWED", "Reviewed"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    DONE = "DONE", "Done"
    WONT_DO = "WONT_DO", "Won't Do"


class FeedbackRequest(models.Model):
    """A feedback request from Virginia to Kasey.

    Casual, lightweight way for Virginia to request features, report bugs,
    or suggest changes. Kasey reviews and responds via Django admin.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_requests",
    )
    request_type = models.CharField(
        max_length=10,
        choices=FeedbackType.choices,
        default=FeedbackType.FEATURE,
        help_text="What kind of request this is.",
    )
    title = models.CharField(
        max_length=200,
        help_text="Short summary of the request.",
    )
    description = models.TextField(
        help_text="The details in her own words.",
    )
    priority = models.CharField(
        max_length=10,
        choices=FeedbackPriority.choices,
        default=FeedbackPriority.MEDIUM,
    )
    status = models.CharField(
        max_length=15,
        choices=FeedbackStatus.choices,
        default=FeedbackStatus.NEW,
    )
    admin_notes = models.TextField(
        blank=True,
        help_text="Kasey's notes on what he did or why he won't do it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this request was marked done.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_request_type_display()}] {self.title}"


class CalendarToken(models.Model):
    """Token for authenticating webcal feed subscriptions.

    Each user can have one or more tokens. The token is embedded in the
    webcal:// URL and validated on every request. Deactivating a token
    immediately revokes calendar access without affecting the user account.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_tokens",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_calendar_token,
        help_text="URL-safe token embedded in the webcal subscription URL.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive tokens are rejected. Deactivate instead of deleting.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"Calendar token for {self.user} ({status})"
