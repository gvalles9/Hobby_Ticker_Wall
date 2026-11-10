"""Formatting helpers shared by the INDYCAR scenes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime

from display.spans import font_text_width
from setup.colours import GOLD, LIME_GREEN, RED, WHITE, YELLOW
from utilities.indycar.models import (
    DriverTiming,
    RaceEvent,
    SessionState,
    Standing,
)
from utilities.indycar.parsing import parse_feed_datetime

SESSION_TYPE_NAMES = {
    "R": "Race",
    "Q": "Qualifying",
    "Q1": "Qualifying",
    "Q2": "Qualifying",
    "Q3": "Qualifying",
    "P": "Practice",
    "W": "Warmup",
    "T": "Test",
}


def flag_colour(flag: str):
    """Colour for a session label, driven by the track flag."""
    flag = (flag or "").strip().upper()
    if flag in ("GREEN", "WARMUP"):
        return LIME_GREEN
    if flag in ("YELLOW", "CAUTION"):
        return YELLOW
    if flag == "RED":
        return RED
    if flag in ("WHITE", "CHECKERED", "CHEQUERED"):
        return WHITE
    return GOLD


def format_gap(value: str, *, leader: bool = False) -> str:
    """Render a timing-feed gap compactly."""
    if leader:
        return "LEADER"
    raw = (value or "").strip()
    if not raw:
        return "--"
    try:
        number = float(raw.replace("+", ""))
    except ValueError:
        return raw
    if number <= 0:
        return "LEADER"
    text = f"{number:.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"+{text}"


def numeric_gap(value: str) -> float | None:
    """Return the gap as seconds when it is numeric, else ``None``."""
    raw = (value or "").strip().replace("+", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def gap_to_leader(driver: DriverTiming) -> str:
    """Gap from the tracked driver to the leader."""
    return format_gap(driver.gap, leader=driver.position <= 1)


def gap_to_next(drivers: Sequence[DriverTiming], index: int) -> str:
    """Gap to the car immediately ahead, derived from the leader gaps.

    The feed publishes a gap-to-leader column (``diff``/``gap``) but not a
    reliable gap-to-the-car-ahead value, so subtract the two adjacent
    leader gaps.  Lapped/non-numeric gaps fall back to the raw feed text.
    """
    if index <= 0:
        return "LEADER"
    current = drivers[index]
    ahead = drivers[index - 1]
    current_gap = numeric_gap(current.gap)
    ahead_gap = numeric_gap(ahead.gap)
    if current_gap is not None and ahead_gap is not None:
        difference = max(0.0, current_gap - ahead_gap)
        text = f"{difference:.3f}".rstrip("0").rstrip(".")
        return "LEADER" if difference <= 0 else f"+{text}"
    return format_gap(current.gap)


def qualifying_gap(driver: DriverTiming) -> str:
    """Gap to provisional pole, using ``POLE`` for the fastest car."""
    if driver.position <= 1:
        return "POLE"
    return format_gap(driver.gap)


def qualifying_time(driver: DriverTiming) -> str:
    """Best published qualifying time, with sensible fallbacks."""
    return driver.qual_time or driver.second_qual_time or driver.best_lap or "--"


def qualifying_speed(driver: DriverTiming) -> str:
    """Best published qualifying speed, with a best-lap fallback."""
    return driver.qual_speed or driver.second_qual_speed or driver.best_speed or "--"


def format_time_to_go(value: str) -> str:
    """Normalize the heartbeat clock for the header row."""
    raw = (value or "").strip()
    if not raw:
        return "--:--"
    if raw.startswith("0") and len(raw) > 5 and raw[1] == ":":
        return raw[1:]
    return raw


def format_lap(driver: DriverTiming | None, total_laps: int = 0) -> str:
    """Race-distance label, omitting the total when the feed has none."""
    laps = driver.laps if driver else 0
    if laps <= 0 and total_laps <= 0:
        return "LAP --"
    if total_laps > 0:
        return f"LAP {laps}/{total_laps}"
    return f"LAP {laps}"


def format_session_name(session: SessionState | None) -> str:
    """Human-readable session name (``Race``, ``Qualifying``, ...)."""
    if session is None:
        return ""
    name = session.session_name or session.session_label
    if name:
        return name
    code = session.session_type.strip().upper()
    return SESSION_TYPE_NAMES.get(code, code or "Session")


def format_session_type(session: SessionState | None) -> str:
    """Short type label used next to the session name."""
    if session is None:
        return ""
    code = session.session_type.strip().upper()
    return SESSION_TYPE_NAMES.get(code, code)


def find_driver(
    drivers: Sequence[DriverTiming], selector: str
) -> tuple[DriverTiming | None, int]:
    """Find a driver by car number or surname.

    Returns the driver and its index in the position-sorted sequence so
    the caller can compute the gap to the car ahead.
    """
    needle = (selector or "").strip().lstrip("#").lower()
    if not needle:
        return None, -1

    for index, driver in enumerate(drivers):
        if driver.car_number.strip().lower() == needle:
            return driver, index

    for index, driver in enumerate(drivers):
        last = driver.last_name.strip().lower()
        full = driver.name.strip().lower()
        if last == needle or full == needle:
            return driver, index

    for index, driver in enumerate(drivers):
        if needle in driver.name.strip().lower():
            return driver, index

    return None, -1


def find_standing(standings: Sequence[Standing], selector: str) -> Standing | None:
    """Find a season standing by driver name or car number."""
    needle = (selector or "").strip().lstrip("#").lower()
    if not needle:
        return None

    for standing in standings:
        if standing.car_number.strip().lower() == needle:
            return standing

    for standing in standings:
        name = standing.driver.strip().lower()
        if name == needle:
            return standing

    for standing in standings:
        if needle in standing.driver.strip().lower():
            return standing

    return None


def truncate_to_width(font, text: str, max_width: int) -> str:
    """Trim text to fit ``max_width`` pixels, appending a dot marker."""
    if max_width <= 0:
        return ""
    if font_text_width(font, text) <= max_width:
        return text
    trimmed = text
    while trimmed and font_text_width(font, trimmed + "..") > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "..") if trimmed else ""


def draw_text_right(
    panel,
    canvas,
    x_right: int,
    y: int,
    font,
    colour,
    text: str,
) -> int:
    """Draw text with its right edge at ``x_right``; return its width."""
    width = font_text_width(font, text)
    x = max(0, x_right - width)
    panel.draw_text(canvas, font, x, y, colour, text)
    return width


def format_event_date(value: date | None, date_format: int = 0) -> str:
    """Calendar date using the same formats as the idle clock."""
    if value is None:
        return "Date TBD"
    if date_format == 0:
        day = value.day
        if 11 <= day % 100 <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return value.strftime("%b ") + f"{day}{suffix} {value.year}"
    fmt = "%d-%m-%Y" if date_format == 1 else "%m-%d-%Y"
    return value.strftime(fmt).replace("-0", "-").lstrip("0")


def format_event_time(event: RaceEvent, clock_24hr: bool = True) -> str:
    """Published time marker (never converted between timezones)."""
    published = event.green_flag
    parsed = parse_feed_datetime(published)
    if parsed is None:
        if event.green_flag_tbd:
            return "TBD"
        return "--:--"
    if clock_24hr:
        result = parsed.strftime("%H:%M")
    else:
        result = parsed.strftime("%I:%M %p").lstrip("0")
    return f"{result} TBD" if event.green_flag_tbd else result


def format_session_time(start: str, clock_24hr: bool = True) -> str:
    """Published activity-session start time, used when the schedule is TBD."""
    parsed = parse_feed_datetime(start)
    if parsed is None:
        return ""
    if clock_24hr:
        return parsed.strftime("%H:%M")
    return parsed.strftime("%I:%M %p").lstrip("0")


def countdown_text(days_until: int) -> str:
    """Day-level countdown; the feed's clock times are not reliable."""
    if days_until <= 0:
        return "TODAY"
    if days_until == 1:
        return "TOMORROW"
    return f"IN {days_until} DAYS"


def session_broadcast(networks: Iterable[str], fallback: str = "") -> str:
    """Pick a short broadcast label for the next-event screen."""
    for network in networks:
        if network:
            return network
    return fallback


def event_weekday(value: date | None) -> str:
    """Three-letter weekday abbreviation, empty when the date is unknown."""
    if value is None:
        return ""
    return datetime(value.year, value.month, value.day).strftime("%a")
