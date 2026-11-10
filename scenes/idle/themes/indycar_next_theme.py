"""Idle theme for the next INDYCAR event.

The official INDYCAR schedule is published months ahead, so this theme is
useful for most of the year.  It is opt-in: the existing idle themes are
untouched, and it can either be selected on its own (``indycar_next``) or
appended to the classic/forecast rotation with
``idle_cycle_include_indycar``.
"""

from __future__ import annotations

from scenes.idle.idle_scene import BaseIdleScene
from scenes.indycar.base import current_snapshot
from scenes.indycar.formatting import (
    SESSION_TYPE_NAMES,
    countdown_text,
    draw_text_right,
    event_weekday,
    format_event_date,
    format_event_time,
    format_session_time,
    session_broadcast,
    truncate_to_width,
)
from setup import fonts
from setup.colours import CYAN, GOLD, GREY, LIGHT_STEEL_BLUE, WHITE
from setup.configuration import Config
from setup.screen import WIDTH as SCREEN_WIDTH
from utilities.indycar.models import NextRace, Snapshot

HEADER_FONT = fonts.small
NAME_FONT = fonts.small
DETAIL_FONT = fonts.extrasmall

RIGHT_EDGE = SCREEN_WIDTH - 1


def _session_label(next_race: NextRace) -> str:
    """Session name plus its short type code (``Race (R)``)."""
    session = next_race.session
    if session is None:
        return "Race"
    label = session.label.strip()
    code = session.session_type.strip().upper()
    if label:
        if code and code not in label.upper():
            return f"{label} ({code})"
        return label
    return SESSION_TYPE_NAMES.get(code, code or "Session")


def _published_time(next_race: NextRace, clock_24hr: bool) -> str:
    """Published event time, falling back to the activity session window."""
    event = next_race.event
    if event.green_flag_tbd and next_race.session is not None:
        session_time = format_session_time(next_race.session.start, clock_24hr)
        if session_time:
            return f"{session_time} TBD"
    return format_event_time(event, clock_24hr)


class IndyCarNextTheme(BaseIdleScene):
    """Show the event, track, session, date/time, and a day-level countdown."""

    debug_name = "indy_next"

    def draw_content(self, count: int) -> None:
        snapshot = current_snapshot(self.debug_name)
        next_race = snapshot.next_event
        if next_race is None:
            self._draw_empty(snapshot)
            return

        cfg = Config.instance()
        clock_24hr = bool(getattr(cfg, "clock_24hr", True))
        date_format = int(getattr(cfg, "date_format", 0))

        self.panel.clear(self.canvas)

        # Row 1: screen label and the day-level countdown.
        self.panel.draw_text(
            self.canvas,
            HEADER_FONT,
            1,
            7,
            GOLD,
            "NEXT RACE",
        )
        draw_text_right(
            self.panel,
            self.canvas,
            RIGHT_EDGE,
            7,
            HEADER_FONT,
            WHITE,
            countdown_text(next_race.days_until),
        )

        # Row 2: event name.
        event_name = truncate_to_width(
            NAME_FONT, next_race.event.name or "INDYCAR", RIGHT_EDGE
        )
        self.panel.draw_text(
            self.canvas,
            NAME_FONT,
            1,
            15,
            WHITE,
            event_name,
        )

        # Row 3: track name, with the session name/type on the right.
        track = next_race.event.track or next_race.event.name
        track_text = truncate_to_width(DETAIL_FONT, track, RIGHT_EDGE - 80)
        self.panel.draw_text(
            self.canvas,
            DETAIL_FONT,
            1,
            23,
            LIGHT_STEEL_BLUE,
            track_text,
        )
        draw_text_right(
            self.panel,
            self.canvas,
            RIGHT_EDGE,
            23,
            DETAIL_FONT,
            CYAN,
            _session_label(next_race),
        )

        # Row 4: weekday/date and the published time (no timezone guessing).
        date_text = format_event_date(next_race.event.date, date_format)
        weekday = event_weekday(next_race.event.date)
        left_text = f"{weekday} {date_text}".strip()
        time_text = _published_time(next_race, clock_24hr)
        self.panel.draw_text(
            self.canvas,
            DETAIL_FONT,
            1,
            31,
            GREY,
            truncate_to_width(DETAIL_FONT, left_text, 120),
        )
        self.panel.draw_text(
            self.canvas,
            DETAIL_FONT,
            125,
            31,
            WHITE,
            time_text,
        )
        broadcast = session_broadcast(
            next_race.session.networks if next_race.session else (),
            next_race.event.tv,
        )
        if broadcast:
            draw_text_right(
                self.panel,
                self.canvas,
                RIGHT_EDGE,
                31,
                DETAIL_FONT,
                GREY,
                truncate_to_width(DETAIL_FONT, broadcast, 40),
            )

    def _draw_empty(self, snapshot: Snapshot) -> None:
        """Placeholder for the off-season before a schedule is published."""
        self.panel.clear(self.canvas)
        header = "INDYCAR"
        self.panel.draw_text(self.canvas, HEADER_FONT, 1, 14, GOLD, header)
        message = "No upcoming race"
        if snapshot.error:
            message = "Schedule unavailable"
        self.panel.draw_text(
            self.canvas,
            DETAIL_FONT,
            1,
            24,
            GREY,
            truncate_to_width(DETAIL_FONT, message, RIGHT_EDGE),
        )
