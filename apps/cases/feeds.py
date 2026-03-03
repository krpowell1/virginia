"""iCalendar webcal feed for litigation deadlines.

Provides a webcal:// URL that Apple Calendar (and other clients) can
subscribe to. Requires a valid CalendarToken in the URL path.
Deadlines appear as all-day events with appropriate urgency prefixes
and case metadata in the description.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from django.http import Http404, HttpRequest
from django_ical.views import ICalFeed

from .models import CalendarToken, Deadline


class DeadlineFeed(ICalFeed):
    """iCal feed of pending litigation deadlines.

    Returns deadlines from 7 days ago (to show recently-past items)
    through 180 days out. Each event is an all-day entry with the
    case number in the title and full metadata in the description.

    Access requires a valid, active CalendarToken passed via the URL.
    """

    product_id = "-//Defense Case Manager//Deadlines//EN"
    timezone = "America/Chicago"
    title = "Defense Case Manager - Deadlines"
    description = "Upcoming litigation deadlines"

    def get_object(self, request: HttpRequest, token: str) -> CalendarToken:
        """Validate the calendar token from the URL."""
        try:
            cal_token = CalendarToken.objects.select_related("user").get(
                token=token, is_active=True
            )
        except CalendarToken.DoesNotExist:
            raise Http404
        return cal_token

    def items(self, obj: CalendarToken) -> list[Deadline]:
        """Return pending deadlines visible to the token's user."""
        today = date.today()
        return list(
            Deadline.objects.filter(
                completed=False,
                due_date__gte=today - timedelta(days=7),
                due_date__lte=today + timedelta(days=180),
            )
            .select_related("case")
            .order_by("due_date")
        )

    def item_guid(self, item: Deadline) -> str:
        """Globally unique ID for the calendar event."""
        return f"{item.pk}@defensecasemanager"

    def _is_rfa_deadline(self, item: Deadline) -> bool:
        """Check if this is a Request for Admissions deadline."""
        return "ARCP Rule 36" in (item.rule_reference or "")

    def item_title(self, item: Deadline) -> str:
        """Event title with urgency prefix and case number.

        Prefixes:
        - [AUTO-ADMISSION RISK] for overdue RFA deadlines
        - [OVERDUE] for other past-due deadlines
        - [NON-EXTENDABLE] for jurisdictional/non-extendable deadlines
        """
        prefix = ""
        if item.is_overdue and self._is_rfa_deadline(item):
            prefix = "[AUTO-ADMISSION RISK] "
        elif item.is_overdue:
            prefix = "[OVERDUE] "
        elif not item.is_extendable:
            prefix = "[NON-EXTENDABLE] "
        return f"{prefix}[{item.case.case_number}] {item.title}"

    def item_description(self, item: Deadline) -> str:
        """Detailed event description with case metadata."""
        parts: list[str] = [
            f"Case: {item.case.caption}",
            f"Type: {item.get_deadline_type_display()}",
        ]
        if item.rule_reference:
            parts.append(f"Rule: {item.rule_reference}")
        if item.description:
            parts.append(f"Notes: {item.description}")
        if item.assigned_to:
            parts.append(f"Assigned to: {item.assigned_to}")
        if not item.is_extendable:
            parts.append("WARNING: This deadline CANNOT be extended.")
        if item.is_jurisdictional:
            parts.append("JURISDICTIONAL: Missing this deadline = loss of jurisdiction.")

        # Client approval status from the parent case
        if item.case.client_approved:
            parts.append("Client/carrier: APPROVED")
        else:
            parts.append("Client/carrier: Not yet approved")

        return "\n".join(parts)

    def item_start_datetime(self, item: Deadline) -> datetime:
        """Start of the all-day event (midnight Central)."""
        return datetime.combine(
            item.due_date, datetime.min.time(), tzinfo=timezone.utc
        )

    def item_end_datetime(self, item: Deadline) -> datetime:
        """End of the all-day event (end of day)."""
        return datetime.combine(
            item.due_date + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

    def item_link(self, item: Deadline) -> str:
        """No web link in Phase 1."""
        return ""
