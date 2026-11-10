"""Recurring birthday date helpers.

Kept free of font/panel imports so the web settings parser can validate a
date without initialising the display.
"""

from __future__ import annotations

import datetime

DATE_FORMATS = ("%Y-%m-%d", "%m-%d", "%m/%d", "%Y/%m/%d")


def parse_birthday_date(value) -> tuple[int, int] | None:
    """Return ``(month, day)`` from a saved birthday date.

    Accepts ``YYYY-MM-DD`` (an HTML date input), ``MM-DD``, ``MM/DD`` and
    ``YYYY/MM/DD``.  The year is deliberately discarded so the birthday
    recurs every year.  Invalid or empty values return ``None``.
    """
    text = str(value or "").strip()
    if not text:
        return None
    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime(text, date_format)
        except ValueError:
            continue
        return parsed.month, parsed.day
    return None


def is_birthday(value, today: datetime.date | None = None) -> bool:
    """True when *value* falls on today's month and day (year ignored)."""
    month_day = parse_birthday_date(value)
    if month_day is None:
        return False
    today = today or datetime.date.today()
    return month_day == (today.month, today.day)
