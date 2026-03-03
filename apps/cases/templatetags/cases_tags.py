from __future__ import annotations

from datetime import date

from django import template

register = template.Library()


@register.simple_tag
def days_until(target_date: date) -> int:
    """Return the number of days from today until the target date."""
    if target_date is None:
        return 0
    return (target_date - date.today()).days


@register.filter
def abs_val(value: int) -> int:
    """Return the absolute value of an integer."""
    try:
        return abs(int(value))
    except (TypeError, ValueError):
        return 0
