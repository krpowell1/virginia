"""ARCP Rule 6 deadline calculator for Alabama defense litigation.

Implements Alabama Rules of Civil Procedure Rule 6 time computation:
- Periods < 11 days: exclude weekends and court holidays (business days)
- Periods >= 11 days: count all calendar days
- If final day falls on a non-business day: roll to next business day
- Rule 6(e): +3 days for mail, e-file, or certified mail service
- Day 1 is the day AFTER the trigger event
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .alabama_calendar import AlabamaCourtCalendar


@dataclass(frozen=True)
class DeadlineResult:
    """Container for a computed deadline with full audit trail.

    Carries all metadata needed to create a Deadline model instance
    and a human-readable explanation of how the date was calculated.
    """

    due_date: date
    title: str
    description: str
    rule_reference: str
    deadline_type: str
    is_extendable: bool
    is_jurisdictional: bool
    alert_days_before: int
    computation_details: str


# Service method → additional days per ARCP Rule 6(e)
SERVICE_ADDITIONS: dict[str, int] = {
    "PERSONAL": 0,
    "PROCESS_SERVER": 0,
    "WAIVER": 0,
    "PUBLICATION": 0,
    "CERTIFIED_MAIL": 3,
    "MAIL": 3,
    "EFILE": 3,
}

# Rules that are non-extendable (jurisdictional or statutory)
NON_EXTENDABLE_RULES: frozenset[str] = frozenset({
    "Rule 50(b)",
    "Rule 52(b)",
    "Rule 59(b)",
    "Rule 59(e)",
    "Rule 59.1",
    "ARAP 4(a)(1)",
    "28 U.S.C. 1446",
})


class DeadlineCalculator:
    """Computes litigation deadlines per ARCP Rule 6.

    Accepts a county parameter to build the correct court calendar
    (Mardi Gras is a holiday only in Mobile and Baldwin counties).
    """

    def __init__(self, county: str = "Jefferson") -> None:
        self.county: str = county
        self.calendar: AlabamaCourtCalendar = AlabamaCourtCalendar(county=county)

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def compute_deadline(
        self,
        trigger_date: date,
        base_days: int,
        service_method: str | None = None,
    ) -> tuple[date, str]:
        """Compute a deadline date per ARCP Rule 6.

        Args:
            trigger_date: The date of the act/event (Day 0). Counting
                starts the NEXT day.
            base_days: The prescribed period in days.
            service_method: If provided, adds Rule 6(e) days for
                mail/e-file service.

        Returns:
            Tuple of (due_date, computation_details) where
            computation_details is a human-readable audit string.
        """
        service_add = SERVICE_ADDITIONS.get(service_method or "PERSONAL", 0)
        total_days = base_days + service_add

        details_parts: list[str] = [
            f"Trigger date: {trigger_date} ({trigger_date.strftime('%A')})",
            f"Base period: {base_days} days",
        ]
        if service_add:
            details_parts.append(
                f"Service method: {service_method} (+{service_add} days per Rule 6(e))"
            )
            details_parts.append(f"Total period: {total_days} days")

        if total_days < 11:
            # Short period: count business days only
            due_date = self._count_business_days(trigger_date, total_days)
            details_parts.append(
                f"Period < 11 days: counted {total_days} business days"
            )
        else:
            # Long period: count calendar days, then roll if needed
            raw_date = trigger_date + timedelta(days=total_days)
            details_parts.append(
                f"Period >= 11 days: counted {total_days} calendar days → "
                f"{raw_date} ({raw_date.strftime('%A')})"
            )
            due_date = self.calendar.next_business_day(raw_date)
            if due_date != raw_date:
                details_parts.append(
                    f"Rolled to next business day: {due_date} "
                    f"({due_date.strftime('%A')})"
                )

        details_parts.append(
            f"Due date: {due_date} ({due_date.strftime('%A')})"
        )
        return due_date, " | ".join(details_parts)

    def _count_business_days(self, start_date: date, num_days: int) -> date:
        """Count num_days business days starting the day after start_date.

        Skips weekends and court holidays. Returns the date of the
        final counted business day.
        """
        current = start_date
        counted = 0
        while counted < num_days:
            current += timedelta(days=1)
            if self.calendar.is_working_day(current):
                counted += 1
        return current

    # ------------------------------------------------------------------
    # Specific deadline methods
    # ------------------------------------------------------------------

    def answer_deadline(
        self,
        date_served: date,
        service_method: str = "PERSONAL",
    ) -> DeadlineResult:
        """Answer deadline per ARCP Rule 12(a): 30 days from service.

        Args:
            date_served: Date the defendant was served.
            service_method: How service was made (affects Rule 6(e) addition).
        """
        due_date, details = self.compute_deadline(date_served, 30, service_method)
        return DeadlineResult(
            due_date=due_date,
            title="File Answer",
            description=(
                "Deadline to file Answer to Complaint. "
                "REMEMBER: Plead contributory negligence and assumption of risk."
            ),
            rule_reference="ARCP Rule 12(a)",
            deadline_type="ANSWER",
            is_extendable=True,
            is_jurisdictional=False,
            alert_days_before=7,
            computation_details=details,
        )

    def removal_deadline(self, date_served: date) -> DeadlineResult:
        """Federal removal deadline per 28 U.S.C. 1446(b): 30 days.

        No Rule 6(e) service addition — this is a federal jurisdictional
        deadline measured from receipt of the initial pleading.
        """
        due_date, details = self.compute_deadline(date_served, 30)
        return DeadlineResult(
            due_date=due_date,
            title="Federal Removal Deadline",
            description=(
                "Last day to file Notice of Removal to federal court. "
                "Jurisdictional — cannot be extended."
            ),
            rule_reference="28 U.S.C. 1446",
            deadline_type="REMOVAL",
            is_extendable=False,
            is_jurisdictional=True,
            alert_days_before=14,
            computation_details=details,
        )

    def interrogatory_response(
        self,
        date_served: date,
        service_method: str | None = None,
    ) -> DeadlineResult:
        """Interrogatory response deadline per ARCP Rule 33(a): 30 days."""
        due_date, details = self.compute_deadline(date_served, 30, service_method)
        return DeadlineResult(
            due_date=due_date,
            title="Respond to Interrogatories",
            description="Deadline to serve answers to interrogatories.",
            rule_reference="ARCP Rule 33(a)",
            deadline_type="DISCOVERY",
            is_extendable=True,
            is_jurisdictional=False,
            alert_days_before=7,
            computation_details=details,
        )

    def rfa_response(
        self,
        date_served: date,
        service_method: str | None = None,
        early_discovery: bool = False,
    ) -> DeadlineResult:
        """Request for Admissions response per ARCP Rule 36(a).

        Args:
            date_served: Date RFAs were served.
            service_method: How RFAs were served.
            early_discovery: If True, uses 45-day period (served within
                30 days of complaint service).

        Failure to respond = matters deemed admitted. Title flags CRITICAL.
        """
        base_days = 45 if early_discovery else 30
        due_date, details = self.compute_deadline(date_served, base_days, service_method)
        period_label = "45 days (early discovery)" if early_discovery else "30 days"
        return DeadlineResult(
            due_date=due_date,
            title="CRITICAL: Respond to Requests for Admission",
            description=(
                f"Deadline to respond to RFAs ({period_label}). "
                "FAILURE TO RESPOND = MATTERS DEEMED ADMITTED."
            ),
            rule_reference="ARCP Rule 36(a)",
            deadline_type="DISCOVERY",
            is_extendable=True,
            is_jurisdictional=False,
            alert_days_before=14,
            computation_details=details,
        )

    def post_judgment_motion(
        self,
        date_of_judgment: date,
        rule: str = "Rule 59(b)",
    ) -> DeadlineResult:
        """Post-judgment motion deadline: 30 days from judgment.

        Covers Rules 50(b), 52(b), 59(b), 59(e). These are
        non-extendable — the court cannot grant more time.
        """
        due_date, details = self.compute_deadline(date_of_judgment, 30)

        rule_titles = {
            "Rule 50(b)": "File Renewed JML Motion",
            "Rule 52(b)": "File Motion to Amend Findings",
            "Rule 59(b)": "File Motion for New Trial",
            "Rule 59(e)": "File Motion to Alter/Amend Judgment",
        }
        title = rule_titles.get(rule, f"Post-Judgment Motion ({rule})")

        return DeadlineResult(
            due_date=due_date,
            title=title,
            description=(
                f"Non-extendable deadline per {rule}. "
                "Court cannot grant additional time."
            ),
            rule_reference=rule,
            deadline_type="POST_JUDGMENT",
            is_extendable=False,
            is_jurisdictional=False,
            alert_days_before=14,
            computation_details=details,
        )

    def rule_59_1_auto_denial(
        self,
        date_motion_filed: date,
    ) -> DeadlineResult:
        """Rule 59.1 auto-denial: motion deemed denied after 90 days.

        If the court does not rule on a post-judgment motion within
        90 days of filing, the motion is automatically denied by
        operation of law.
        """
        due_date, details = self.compute_deadline(date_motion_filed, 90)
        return DeadlineResult(
            due_date=due_date,
            title="Rule 59.1 Auto-Denial Date",
            description=(
                "If the court has not ruled on the post-judgment motion "
                "by this date, it is AUTOMATICALLY DENIED by operation of law. "
                "Appeal clock starts from this date if motion is not ruled on."
            ),
            rule_reference="Rule 59.1",
            deadline_type="POST_JUDGMENT",
            is_extendable=False,
            is_jurisdictional=False,
            alert_days_before=14,
            computation_details=details,
        )

    def appeal_deadline(
        self,
        date_of_judgment: date,
    ) -> DeadlineResult:
        """Notice of appeal deadline per ARAP 4(a)(1): 42 days.

        Jurisdictional — failure to file timely notice of appeal
        results in permanent loss of appellate jurisdiction.
        """
        due_date, details = self.compute_deadline(date_of_judgment, 42)
        return DeadlineResult(
            due_date=due_date,
            title="File Notice of Appeal",
            description=(
                "Jurisdictional deadline to file Notice of Appeal. "
                "CANNOT BE EXTENDED. Loss of this deadline = loss of appeal rights."
            ),
            rule_reference="ARAP 4(a)(1)",
            deadline_type="APPEAL",
            is_extendable=False,
            is_jurisdictional=True,
            alert_days_before=21,
            computation_details=details,
        )

    # ------------------------------------------------------------------
    # Bulk generation
    # ------------------------------------------------------------------

    def generate_service_deadlines(self, case: object) -> list[DeadlineResult]:
        """Generate standard deadlines triggered by service of complaint.

        Creates three deadlines:
        1. Answer deadline (30 days + service method adjustment)
        2. Federal removal deadline (30 days, jurisdictional)
        3. Internal case review deadline (10 business days)

        Args:
            case: Object with date_served, service_method, county,
                and jurisdiction attributes.
        """
        date_served: date = getattr(case, "date_served")
        service_method: str = getattr(case, "service_method", "PERSONAL") or "PERSONAL"
        results: list[DeadlineResult] = []

        # 1. Answer deadline
        results.append(self.answer_deadline(date_served, service_method))

        # 2. Federal removal deadline (relevant for state court cases)
        results.append(self.removal_deadline(date_served))

        # 3. Internal case review
        internal_due, internal_details = self.compute_deadline(date_served, 10)
        results.append(DeadlineResult(
            due_date=internal_due,
            title="Internal: Initial case review and discovery plan",
            description=(
                "Review complaint, assess claims, prepare initial discovery "
                "requests, and develop case strategy."
            ),
            rule_reference="Firm policy",
            deadline_type="INTERNAL",
            is_extendable=True,
            is_jurisdictional=False,
            alert_days_before=3,
            computation_details=internal_details,
        ))

        return results
