"""Alabama court calendar with county-aware holiday support.

Extends workalendar's Alabama calendar with:
- Juneteenth (June 19) — federal/state holiday not in workalendar
- Mardi Gras — court holiday ONLY in Mobile and Baldwin counties
"""
from __future__ import annotations

from datetime import date, timedelta

from dateutil.easter import easter
from workalendar.usa import Alabama

# Counties where Mardi Gras is a court holiday
MARDI_GRAS_COUNTIES: frozenset[str] = frozenset({"MOBILE", "BALDWIN"})


class AlabamaCourtCalendar(Alabama):
    """Alabama court calendar with county-specific holidays.

    Subclasses workalendar's Alabama to add Juneteenth and
    county-aware Mardi Gras. Used by the deadline calculator
    to determine business days for ARCP Rule 6 computations.
    """

    def __init__(self, county: str = "Jefferson") -> None:
        super().__init__()
        self.county: str = county.upper()

    def get_variable_days(self, year: int) -> list[tuple[date, str]]:
        """Return variable holidays for the given year.

        Adds Juneteenth (with observed-date handling) and
        Mardi Gras for Mobile/Baldwin counties to the base
        Alabama holiday list.
        """
        days = super().get_variable_days(year)

        # Juneteenth — June 19
        juneteenth = date(year, 6, 19)
        if not any(d == juneteenth for d, _ in days):
            days.append((juneteenth, "Juneteenth National Independence Day"))
            # Observed date when Juneteenth falls on a weekend
            if juneteenth.weekday() == 5:  # Saturday → observe Friday
                days.append((
                    juneteenth - timedelta(days=1),
                    "Juneteenth National Independence Day (Observed)",
                ))
            elif juneteenth.weekday() == 6:  # Sunday → observe Monday
                days.append((
                    juneteenth + timedelta(days=1),
                    "Juneteenth National Independence Day (Observed)",
                ))

        # Mardi Gras — 47 days before Easter (Mobile & Baldwin only)
        if self.county in MARDI_GRAS_COUNTIES:
            easter_date = easter(year)
            mardi_gras = easter_date - timedelta(days=47)
            days.append((mardi_gras, "Mardi Gras"))

        return days

    def is_court_holiday(self, check_date: date) -> bool:
        """Return True if the date is a non-business day for the court.

        A court holiday is any weekend or state/county holiday.
        """
        return not self.is_working_day(check_date)

    def next_business_day(self, check_date: date) -> date:
        """Return the earliest business day on or after check_date.

        If check_date is already a business day, returns it unchanged.
        Otherwise rolls forward to the next working day.
        """
        current = check_date
        while not self.is_working_day(current):
            current += timedelta(days=1)
        return current
