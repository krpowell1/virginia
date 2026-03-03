"""Tests for the ARCP Rule 6 deadline calculator.

All 14 test cases must pass before any deployment. These cover:
- Calendar vs. business day counting
- Service method additions (Rule 6(e))
- Weekend and holiday roll-forward
- County-specific holidays (Mardi Gras)
- Non-extendable / jurisdictional deadlines
- Bulk deadline generation from service
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from apps.cases.alabama_calendar import AlabamaCourtCalendar
from apps.cases.deadlines import DeadlineCalculator


@pytest.fixture
def jefferson_calc() -> DeadlineCalculator:
    """Calculator for Jefferson County (no Mardi Gras)."""
    return DeadlineCalculator(county="Jefferson")


@pytest.fixture
def baldwin_calc() -> DeadlineCalculator:
    """Calculator for Baldwin County (Mardi Gras IS a holiday)."""
    return DeadlineCalculator(county="Baldwin")


# ------------------------------------------------------------------
# Test 1: Answer, personal service, weekday result
# ------------------------------------------------------------------
def test_answer_personal_service_weekday(jefferson_calc: DeadlineCalculator) -> None:
    """30 calendar days from March 16 (Mon) = April 15 (Wed). No roll needed."""
    result = jefferson_calc.answer_deadline(date(2026, 3, 16), "PERSONAL")
    assert result.due_date == date(2026, 4, 15)
    assert result.deadline_type == "ANSWER"
    assert result.is_extendable is True


# ------------------------------------------------------------------
# Test 2: Answer, mail service (+3 days, weekend roll)
# ------------------------------------------------------------------
def test_answer_mail_service_weekend_roll(jefferson_calc: DeadlineCalculator) -> None:
    """30 + 3 = 33 calendar days from March 16 = April 18 (Sat) → April 20 (Mon)."""
    result = jefferson_calc.answer_deadline(date(2026, 3, 16), "CERTIFIED_MAIL")
    assert result.due_date == date(2026, 4, 20)


# ------------------------------------------------------------------
# Test 3: Answer landing on Memorial Day
# ------------------------------------------------------------------
def test_answer_landing_on_memorial_day(jefferson_calc: DeadlineCalculator) -> None:
    """30 days from April 25 = May 25 (Memorial Day) → May 26 (Tue)."""
    result = jefferson_calc.answer_deadline(date(2026, 4, 25), "PERSONAL")
    assert result.due_date == date(2026, 5, 26)


# ------------------------------------------------------------------
# Test 4: Answer landing on Confederate Memorial Day
# ------------------------------------------------------------------
def test_answer_landing_on_confederate_memorial_day(
    jefferson_calc: DeadlineCalculator,
) -> None:
    """30 days from March 28 = April 27 (Confederate Memorial Day) → April 28 (Tue)."""
    result = jefferson_calc.answer_deadline(date(2026, 3, 28), "PERSONAL")
    assert result.due_date == date(2026, 4, 28)


# ------------------------------------------------------------------
# Test 5: Mardi Gras in Baldwin County (holiday)
# ------------------------------------------------------------------
def test_mardi_gras_baldwin_county(baldwin_calc: DeadlineCalculator) -> None:
    """10-day short period from Feb 6 in Baldwin County.

    Mardi Gras (Feb 17) is a court holiday in Baldwin, plus
    Washington/Jefferson Birthday (Feb 16). Both skipped.

    Business days: Feb 9-13 (5), Feb 18-20 (3), Feb 23-24 (2) = 10.
    """
    due, _ = baldwin_calc.compute_deadline(date(2026, 2, 6), 10)
    assert due == date(2026, 2, 24)


# ------------------------------------------------------------------
# Test 6: Mardi Gras NOT a holiday in Jefferson County
# ------------------------------------------------------------------
def test_mardi_gras_not_holiday_jefferson(jefferson_calc: DeadlineCalculator) -> None:
    """Same 10-day period from Feb 6 but in Jefferson County.

    Mardi Gras (Feb 17) is NOT a holiday here, so Feb 17 counts.
    Washington/Jefferson Birthday (Feb 16) still skipped.

    Business days: Feb 9-13 (5), Feb 17-20 (4), Feb 23 (1) = 10.
    """
    due, _ = jefferson_calc.compute_deadline(date(2026, 2, 6), 10)
    assert due == date(2026, 2, 23)


# ------------------------------------------------------------------
# Test 7: Short period (<11 days), 5 business days
# ------------------------------------------------------------------
def test_short_period_5_business_days(jefferson_calc: DeadlineCalculator) -> None:
    """5 business days from March 4 (Wed).

    Mar 5 (Thu), Mar 6 (Fri), Mar 9 (Mon), Mar 10 (Tue), Mar 11 (Wed).
    """
    due, _ = jefferson_calc.compute_deadline(date(2026, 3, 4), 5)
    assert due == date(2026, 3, 11)


# ------------------------------------------------------------------
# Test 8: Short period spanning Memorial Day + Jefferson Davis Birthday
# ------------------------------------------------------------------
def test_short_period_spanning_holidays(jefferson_calc: DeadlineCalculator) -> None:
    """7 business days from May 22 (Fri).

    Skips: May 23-24 (weekend), May 25 (Memorial Day),
    May 30-31 (weekend), Jun 1 (Jefferson Davis Birthday).

    Business days: May 26-29 (4), Jun 2-4 (3) = 7.
    """
    due, _ = jefferson_calc.compute_deadline(date(2026, 5, 22), 7)
    assert due == date(2026, 6, 4)


# ------------------------------------------------------------------
# Test 9: RFA response, standard 30 days, CRITICAL flag
# ------------------------------------------------------------------
def test_rfa_standard_30_days(jefferson_calc: DeadlineCalculator) -> None:
    """30 calendar days from March 10 = April 9 (Thu). Title includes CRITICAL."""
    result = jefferson_calc.rfa_response(date(2026, 3, 10))
    assert result.due_date == date(2026, 4, 9)
    assert "CRITICAL" in result.title


# ------------------------------------------------------------------
# Test 10: RFA early discovery, 45 days
# ------------------------------------------------------------------
def test_rfa_early_discovery_45_days(jefferson_calc: DeadlineCalculator) -> None:
    """45 calendar days from March 10 = April 24 (Fri)."""
    result = jefferson_calc.rfa_response(date(2026, 3, 10), early_discovery=True)
    assert result.due_date == date(2026, 4, 24)


# ------------------------------------------------------------------
# Test 11: Post-judgment motion, non-extendable
# ------------------------------------------------------------------
def test_post_judgment_motion_non_extendable(
    jefferson_calc: DeadlineCalculator,
) -> None:
    """30 calendar days from March 2 = April 1 (Wed). Not extendable."""
    result = jefferson_calc.post_judgment_motion(date(2026, 3, 2))
    assert result.due_date == date(2026, 4, 1)
    assert result.is_extendable is False


# ------------------------------------------------------------------
# Test 12: Rule 59.1 auto-denial, 90 days
# ------------------------------------------------------------------
def test_rule_59_1_auto_denial(jefferson_calc: DeadlineCalculator) -> None:
    """90 calendar days from March 5 = June 3 (Wed). Not extendable."""
    result = jefferson_calc.rule_59_1_auto_denial(date(2026, 3, 5))
    assert result.due_date == date(2026, 6, 3)
    assert result.is_extendable is False
    assert result.rule_reference == "Rule 59.1"


# ------------------------------------------------------------------
# Test 13: Appeal from auto-denial, 42 days, jurisdictional
# ------------------------------------------------------------------
def test_appeal_from_auto_denial(jefferson_calc: DeadlineCalculator) -> None:
    """42 calendar days from June 3 = July 15 (Wed). Jurisdictional."""
    result = jefferson_calc.appeal_deadline(date(2026, 6, 3))
    assert result.due_date == date(2026, 7, 15)
    assert result.is_extendable is False
    assert result.is_jurisdictional is True
    assert result.rule_reference == "ARAP 4(a)(1)"


# ------------------------------------------------------------------
# Test 14: Service generates multiple deadlines
# ------------------------------------------------------------------
def test_service_generates_three_deadlines(
    jefferson_calc: DeadlineCalculator,
) -> None:
    """generate_service_deadlines should produce answer + removal + internal."""
    mock_case = SimpleNamespace(
        date_served=date(2026, 3, 16),
        service_method="PERSONAL",
        county="Jefferson",
        jurisdiction="STATE",
    )
    results = jefferson_calc.generate_service_deadlines(mock_case)
    assert len(results) == 3

    types = {r.deadline_type for r in results}
    assert types == {"ANSWER", "REMOVAL", "INTERNAL"}

    # Answer and removal should share the same due date for personal service
    answer = next(r for r in results if r.deadline_type == "ANSWER")
    removal = next(r for r in results if r.deadline_type == "REMOVAL")
    assert answer.due_date == date(2026, 4, 15)
    assert removal.due_date == date(2026, 4, 15)
    assert removal.is_jurisdictional is True
    assert answer.is_extendable is True
    assert removal.is_extendable is False
