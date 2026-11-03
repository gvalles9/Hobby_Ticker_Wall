import datetime

from scenes.idle.themes.theme_utilities import format_display_date


def test_default_date_format_uses_month_name_ordinal_and_year():
    assert format_display_date(datetime.datetime(2026, 11, 1), 0) == (
        "November 1st 2026"
    )


def test_default_date_format_handles_ordinal_suffix_exceptions():
    assert format_display_date(datetime.datetime(2026, 11, 2), 0) == (
        "November 2nd 2026"
    )
    assert format_display_date(datetime.datetime(2026, 11, 3), 0) == (
        "November 3rd 2026"
    )
    for day in (11, 12, 13):
        assert format_display_date(datetime.datetime(2026, 11, day), 0) == (
            f"November {day}th 2026"
        )


def test_numeric_date_formats_remain_available():
    date = datetime.datetime(2026, 11, 1)

    assert format_display_date(date, 1) == "1-11-2026"
    assert format_display_date(date, 2) == "11-1-2026"
