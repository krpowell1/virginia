"""Signals for the cases app.

Auto-generates deadlines when a Case's date_served is set, and
auto-calculates the statute of limitations for premises liability cases.
"""
from __future__ import annotations

import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .deadlines import DeadlineCalculator
from .models import (
    ActivityAction,
    ActivityLog,
    Case,
    CaseType,
    Deadline,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-save: stash old values + auto-calculate SOL
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=Case)
def _pre_save_case(sender: type, instance: Case, **kwargs: object) -> None:
    """Stash previous field values and auto-calculate SOL.

    - Stashes old date_served so post_save can detect the transition
      from None → a date.
    - Auto-sets statute_of_limitations for premises liability cases
      when date_of_loss is provided and SOL is not already set
      (Alabama: 2 years from date of loss).
    """
    # Stash old date_served for deadline generation check
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_date_served = old.date_served  # type: ignore[attr-defined]
        except sender.DoesNotExist:
            instance._old_date_served = None  # type: ignore[attr-defined]
    else:
        instance._old_date_served = None  # type: ignore[attr-defined]

    # Auto-calculate 2-year SOL for premises liability
    instance._sol_auto_calculated = False  # type: ignore[attr-defined]
    if (
        instance.date_of_loss
        and instance.case_type == CaseType.PREMISES_LIABILITY
        and not instance.statute_of_limitations
    ):
        instance.statute_of_limitations = (
            instance.date_of_loss + relativedelta(years=2)
        )
        instance._sol_auto_calculated = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Post-save: generate deadlines + log activity
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Case)
def _post_save_case(
    sender: type,
    instance: Case,
    created: bool,
    **kwargs: object,
) -> None:
    """Generate deadlines when date_served transitions from None to a value.

    Also creates a SOL deadline if the statute_of_limitations was
    auto-calculated in pre_save.
    """
    old_served: date | None = getattr(instance, "_old_date_served", None)

    # Generate service deadlines when date_served is first set
    if instance.date_served and old_served is None:
        _create_service_deadlines(instance)

    # Create SOL deadline if auto-calculated
    if getattr(instance, "_sol_auto_calculated", False):
        _create_sol_deadline(instance)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_service_deadlines(case: Case) -> None:
    """Create Deadline objects from the deadline calculator results.

    Generates answer, removal, and internal review deadlines, plus
    ActivityLog entries for each.
    """
    calc = DeadlineCalculator(county=case.county)
    results = calc.generate_service_deadlines(case)

    for result in results:
        Deadline.objects.create(
            case=case,
            title=result.title,
            description=result.description,
            due_date=result.due_date,
            rule_reference=result.rule_reference,
            deadline_type=result.deadline_type,
            is_extendable=result.is_extendable,
            is_jurisdictional=result.is_jurisdictional,
            alert_days_before=result.alert_days_before,
        )
        ActivityLog.objects.create(
            case=case,
            action=ActivityAction.DEADLINE_AUTO_GENERATED,
            description=(
                f"Auto-generated: {result.title} (due {result.due_date}). "
                f"{result.computation_details}"
            ),
        )

    # Set date_answer_due on the case if not already set
    answer_result = next(
        (r for r in results if r.deadline_type == "ANSWER"), None
    )
    if answer_result and not case.date_answer_due:
        # Use .update() to avoid re-triggering signals
        Case.objects.filter(pk=case.pk).update(
            date_answer_due=answer_result.due_date,
        )

    logger.info(
        "Generated %d deadlines for case %s (served %s)",
        len(results),
        case.case_number,
        case.date_served,
    )


def _create_sol_deadline(case: Case) -> None:
    """Create a statute of limitations deadline and activity log entry.

    Alabama premises liability SOL is 2 years from date of loss.
    """
    if not case.statute_of_limitations:
        return

    Deadline.objects.create(
        case=case,
        title="CRITICAL: Statute of Limitations Expiry",
        description=(
            "Alabama statute of limitations for premises liability: "
            "2 years from date of loss. Case must be filed before this date."
        ),
        due_date=case.statute_of_limitations,
        rule_reference="Ala. Code 6-2-38(l)",
        deadline_type="OTHER",
        is_extendable=False,
        is_jurisdictional=True,
        alert_days_before=90,
    )
    ActivityLog.objects.create(
        case=case,
        action=ActivityAction.DEADLINE_AUTO_GENERATED,
        description=(
            f"Auto-calculated statute of limitations: "
            f"{case.statute_of_limitations} "
            f"(2 years from date of loss {case.date_of_loss})"
        ),
    )
    logger.info(
        "Auto-calculated SOL for case %s: %s",
        case.case_number,
        case.statute_of_limitations,
    )
