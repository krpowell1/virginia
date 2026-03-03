from __future__ import annotations

from datetime import date, timedelta

from django.db import models


class DeadlineQuerySet(models.QuerySet):
    """Custom queryset for filtering deadlines by status and urgency."""

    def pending(self) -> DeadlineQuerySet:
        """Deadlines that are not yet completed and not overdue."""
        return self.filter(completed=False, due_date__gte=date.today())

    def overdue(self) -> DeadlineQuerySet:
        """Deadlines past due that have not been completed."""
        return self.filter(completed=False, due_date__lt=date.today())

    def due_today(self) -> DeadlineQuerySet:
        """Deadlines due today that have not been completed."""
        return self.filter(completed=False, due_date=date.today())

    def due_this_week(self) -> DeadlineQuerySet:
        """Deadlines due within the next 7 calendar days (incomplete only)."""
        today = date.today()
        return self.filter(
            completed=False,
            due_date__gte=today,
            due_date__lte=today + timedelta(days=7),
        )

    def due_next_30_days(self) -> DeadlineQuerySet:
        """Deadlines due within the next 30 calendar days (incomplete only)."""
        today = date.today()
        return self.filter(
            completed=False,
            due_date__gte=today,
            due_date__lte=today + timedelta(days=30),
        )


class CaseQuerySet(models.QuerySet):
    """Custom queryset for filtering cases by status and attention flags."""

    def active(self) -> CaseQuerySet:
        """Cases with ACTIVE status."""
        return self.filter(status="ACTIVE")

    def with_overdue_deadlines(self) -> CaseQuerySet:
        """Active cases that have at least one overdue, incomplete deadline."""
        return self.active().filter(
            deadlines__completed=False,
            deadlines__due_date__lt=date.today(),
        ).distinct()

    def missing_contributory_negligence(self) -> CaseQuerySet:
        """Active cases where contributory negligence has NOT been pled.

        In Alabama (pure contributory negligence state), this must be pled
        in the Answer or it is permanently waived.
        """
        return self.active().filter(pled_contributory_negligence=False)
