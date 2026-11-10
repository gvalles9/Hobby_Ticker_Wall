"""Offline parser tests for the INDYCAR feed layer."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from utilities.indycar.parsing import (
    boolean,
    integer,
    next_race,
    parse_activity,
    parse_drivers,
    parse_feed_date,
    parse_schedule,
    parse_timing,
    parse_tsconfig,
    session_is_live,
    text,
)

FIXTURES = Path(__file__).parent / "fixtures" / "indycar"


def fixture(name: str):
    """Load one recorded feed payload."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("", ""),
        ("  Palou  ", "Palou"),
        ("None", ""),
        ("null", ""),
        (11, "11"),
    ],
)
def test_text_normalizes_feed_scalars(value, expected):
    assert text(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0),
        ("", 0),
        ("--", 0),
        ("-", 0),
        ("1,234", 1234),
        ("3.9", 3),
        (7, 7),
        (True, 1),
        ("not a number", 0),
    ],
)
def test_integer_handles_blank_and_formatted_values(value, expected):
    assert integer(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("0", False),
        ("", False),
        (None, False),
    ],
)
def test_boolean_accepts_feed_spellings(value, expected):
    assert boolean(value) is expected


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def test_parse_timing_reads_heartbeat_and_driver_rows():
    session = parse_timing(fixture("timing_race_live.json"))

    assert session.event_name == "Firestone Grand Prix of St. Petersburg"
    assert session.track_name == "Streets of St. Petersburg"
    assert session.session_name == "Race"
    assert session.session_type == "R"
    assert session.flag == "GREEN"
    assert session.status == "GREEN"
    assert session.time_to_go == "01:23:45"
    assert session.series == "L"
    assert session.live is False
    assert len(session.drivers) == 22

    leader = session.leader
    assert leader is not None
    assert leader.position == 1
    assert leader.car_number == "11"
    assert leader.name == "Alex Palou"
    assert leader.short_name == "Palou"
    assert leader.team == "Chip Ganassi Racing"
    assert leader.gap == "0.0000"
    assert leader.laps == 45
    assert leader.tire == "P"
    assert leader.on_track is True
    assert leader.raw is not None


def test_parse_timing_sorts_unranked_drivers_last():
    payload = {
        "timing_results": {
            "heartbeat": {"eventName": "Test"},
            "Item": [
                {"rank": 2, "lastName": "Bravo"},
                {"lastName": "NoRank"},
                {"rank": 1, "lastName": "Alpha"},
            ],
        }
    }

    session = parse_timing(payload)

    assert [driver.short_name for driver in session.drivers] == [
        "Alpha",
        "Bravo",
        "NoRank",
    ]


def test_parse_timing_tolerates_missing_payload():
    session = parse_timing({})

    assert session.event_name == ""
    assert session.drivers == ()
    assert session.leader is None


def test_session_is_live_requires_fresh_activity():
    session = parse_timing(fixture("timing_race_live.json"))

    assert session_is_live(
        session, no_track_activity=False, fetched_at=1000.0, now=1010.0
    )
    assert not session_is_live(
        session, no_track_activity=True, fetched_at=1000.0, now=1010.0
    )
    assert not session_is_live(
        session, no_track_activity=False, fetched_at=0.0, now=1010.0
    )
    assert not session_is_live(
        session, no_track_activity=False, fetched_at=1000.0, now=1201.0
    )
    assert not session_is_live(
        None, no_track_activity=False, fetched_at=1000.0, now=1010.0
    )


def test_session_is_live_rejects_cold_and_unknown_states():
    session = parse_timing(fixture("timing_race_live.json"))
    cold = replace(session, flag="COLD", status="COLD")
    unknown = replace(session, flag="", status="")

    assert not session_is_live(
        cold, no_track_activity=False, fetched_at=1000.0, now=1010.0
    )
    assert not session_is_live(
        unknown, no_track_activity=False, fetched_at=1000.0, now=1010.0
    )


# ---------------------------------------------------------------------------
# Track config
# ---------------------------------------------------------------------------


def test_parse_tsconfig_reads_idle_flags():
    config = parse_tsconfig(fixture("tsconfig_idle.json"))

    assert config.no_track_activity is True
    assert config.rain_delay is False
    assert config.show_static_track_map is True
    assert config.track_map_url.endswith(".jpg")
    assert "leaderboardHeartbeat" in config.overrides


def test_parse_tsconfig_defaults_to_no_activity():
    config = parse_tsconfig({})
    assert config.no_track_activity is True
    assert config.rain_delay is False
    assert config.track_map_url == ""

    active = parse_tsconfig({"no_track_activity": "0"})
    assert active.no_track_activity is False


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def test_parse_schedule_reads_events_in_date_order():
    events = parse_schedule(fixture("schedule.json"))

    assert len(events) == 3
    assert [event.name for event in events] == [
        "Streets of St. Petersburg",
        "Phoenix Raceway",
        "Streets of Arlington",
    ]
    assert [event.date for event in events] == [
        date(2027, 3, 7),
        date(2027, 3, 13),
        date(2027, 3, 21),
    ]

    first = events[0]
    assert first.event_id == "5559"
    assert first.track == "Streets of St. Petersburg"
    assert first.city == "St. Petersburg"
    assert first.state == "Florida"
    assert first.country == "USA"
    assert first.green_flag == "2027-03-07 05:00:00"
    assert first.tv == "Fox"
    assert first.is_complete is False
    assert first.winner == ""
    assert first.past_winners[0] == "Alex Palou (2026)"


def test_parse_schedule_tolerates_missing_payload():
    assert parse_schedule({}) == ()
    assert parse_schedule(None) == ()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2027-03-07 05:00:00", date(2027, 3, 7)),
        ("2027-03-07", date(2027, 3, 7)),
        ("2027-03-07T05:00:00Z", date(2027, 3, 7)),
        ("", None),
        ("TBD", None),
        (None, None),
    ],
)
def test_parse_feed_date(value, expected):
    assert parse_feed_date(value) == expected


def test_next_race_uses_date_markers_only():
    events = parse_schedule(fixture("schedule.json"))

    upcoming = next_race(events, today=date(2027, 3, 8))
    assert upcoming is not None
    assert upcoming.event.name == "Phoenix Raceway"
    assert upcoming.days_until == 5


def test_next_race_skips_completed_and_dateless_events():
    events = parse_schedule(fixture("schedule.json"))
    first = replace(events[0], is_complete=True)
    dateless = replace(events[1], date=None)

    upcoming = next_race((first, dateless), today=date(2027, 1, 1))
    assert upcoming is None

    upcoming = next_race((first, events[1]), today=date(2027, 1, 1))
    assert upcoming is not None
    assert upcoming.event.name == "Phoenix Raceway"


def test_next_race_returns_none_before_or_after_the_season():
    assert next_race((), today=date(2027, 1, 1)) is None


# ---------------------------------------------------------------------------
# Drivers and activity
# ---------------------------------------------------------------------------


def test_parse_drivers_orders_by_points_and_numbers_positions():
    standings = parse_drivers(fixture("drivers.json"))

    assert len(standings) == 6
    assert [standing.position for standing in standings] == [1, 2, 3, 4, 5, 6]

    top = standings[0]
    assert top.driver == "Marcus Armstrong"
    assert top.points == 320
    assert top.car_number != ""

    points = [standing.points for standing in standings]
    assert points == sorted(points, reverse=True)


def test_parse_drivers_tolerates_missing_payload():
    assert parse_drivers({}) == ()


def test_parse_activity_reads_session_windows():
    sessions = parse_activity(fixture("activity.json"))

    assert len(sessions) == 2
    first = sessions[0]
    assert first.event_id == "5559"
    assert first.event_name == "Streets of St. Petersburg"
    assert first.session_id == "6965"
    assert first.label == "Race"
    assert first.session_type == "R"
    assert first.start == "2027-03-07 05:00:00"
    assert first.end == "2027-03-07 05:00:00"
    assert first.status == "ACTIVE"


def test_parse_activity_tolerates_missing_payload():
    assert parse_activity({}) == ()
