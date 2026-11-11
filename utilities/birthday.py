"""Recurring birthday date helpers.

Kept free of font/panel imports so the web settings parser can validate a
date without initialising the display.  The generic implementation lives in
:mod:`utilities.recurring_date`; these wrappers preserve the birthday API.
"""

from __future__ import annotations

import datetime

from utilities.recurring_date import (
    DATE_FORMATS,
    is_recurring_date,
    parse_recurring_date,
)

__all__ = ["DATE_FORMATS", "is_birthday", "parse_birthday_date"]


def parse_birthday_date(value) -> tuple[int, int] | None:
    """Return ``(month, day)`` from a saved birthday date.

    Accepts ``YYYY-MM-DD`` (an HTML date input), ``MM-DD``, ``MM/DD`` and
    ``YYYY/MM/DD``.  The year is deliberately discarded so the birthday
    recurs every year.  Invalid or empty values return ``None``.
    """
    return parse_recurring_date(value)


def is_birthday(value, today: datetime.date | None = None) -> bool:
    """True when *value* falls on today's month and day (year ignored)."""
    return is_recurring_date(value, today)
