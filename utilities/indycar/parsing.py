"""Pure parsers for the INDYCAR feed payloads.

Keeping these functions side-effect free makes the feed contract easy to
test against recorded fixtures without any network access.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any

from utilities.indycar.models import (
    ActivitySession,
    Championship,
    DriverTiming,
    NextRace,
    RaceEvent,
    SessionState,
    Standing,
    TrackConfig,
)

# 2026 points: 50 for a win, 1 pole, 1 lap led, 2 most laps led.
MAX_RACE_POINTS = 54

LIVE_FLAGS = frozenset(
    {"GREEN", "YELLOW", "RED", "WHITE", "WARMUP", "CHECKERED", "CHEQUERED"}
)
LIVE_STATUSES = frozenset(
    {
        "GREEN",
        "YELLOW",
        "RED",
        "ACTIVE",
        "RUNNING",
        "WARMUP",
        "CHECKERED",
        "CHEQUERED",
    }
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def text(value: Any, default: str = "") -> str:
    """Normalize a feed scalar to stripped text."""
    if value is None:
        return default
    result = str(value).strip()
    if result in {"", "None", "null"}:
        return default
    return result


def integer(value: Any, default: int = 0) -> int:
    """Parse a feed scalar that may be numeric, blank, or '--'."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = text(value).replace(",", "")
    if cleaned in {"", "--", "-"}:
        return default
    try:
        return int(float(cleaned))
    except ValueError:
        return default


def boolean(value: Any) -> bool:
    """Parse the feed's various boolean spellings."""
    if isinstance(value, bool):
        return value
    return text(value).lower() in {"1", "true", "yes", "y", "on"}


def _first_text(*values: Any) -> str:
    for value in values:
        result = text(value)
        if result:
            return result
    return ""


def _first_int(*values: Any) -> int:
    for value in values:
        result = integer(value)
        if result:
            return result
    return 0


def parse_timing(payload: Any) -> SessionState:
    """Parse ``timingscoring-ris.json`` into a session snapshot."""
    timing = _mapping(_mapping(payload).get("timing_results"))
    heartbeat = _mapping(timing.get("heartbeat"))
    items = _sequence(timing.get("Item") or timing.get("item"))

    drivers: list[DriverTiming] = []
    for raw in items:
        row = _mapping(raw)
        drivers.append(
            DriverTiming(
                position=_first_int(
                    row.get("rank"),
                    row.get("overallRank"),
                    row.get("liveRank"),
                ),
                car_number=text(row.get("no")),
                first_name=text(row.get("firstName")),
                last_name=text(row.get("lastName")),
                team=text(row.get("team")),
                laps=integer(row.get("laps")),
                gap=_first_text(row.get("gap"), row.get("diff"), row.get("liveGap")),
                live_gap=text(row.get("liveGap")),
                last_lap=text(row.get("lastLapTime")),
                best_lap=text(row.get("bestLapTime")),
                tire=text(row.get("Tire")),
                status=text(row.get("status")),
                on_track=boolean(row.get("onTrack")),
                pit_stops=integer(row.get("pitStops")),
                flag_status=text(row.get("flagStatus")),
                start_position=_first_int(
                    row.get("startPosition"),
                    row.get("startRank"),
                ),
                qual_time=text(row.get("qualTime")),
                qual_speed=text(row.get("qualSpeed")),
                second_qual_time=text(row.get("secondQualTime")),
                second_qual_speed=text(row.get("secondQualSpeed")),
                total_time=text(row.get("totalTime")),
                laps_led=integer(row.get("lapsLed")),
                best_speed=text(row.get("BestSpeed")),
                last_speed=text(row.get("LastSpeed")),
                equipment=text(row.get("equipment")),
                driver_id=text(row.get("DriverID")),
                team_id=text(row.get("TeamID")),
                raw=row,
            )
        )

    drivers.sort(
        key=lambda driver: (
            driver.position <= 0,
            driver.position,
            driver.short_name.lower(),
        )
    )

    return SessionState(
        live=False,
        event_id=text(heartbeat.get("EventID")),
        event_name=text(heartbeat.get("eventName")),
        track_name=text(heartbeat.get("trackName")),
        session_name=text(heartbeat.get("SessionName")),
        session_type=text(heartbeat.get("SessionType")),
        session_label=text(heartbeat.get("EventSessionLabel")),
        flag=text(heartbeat.get("currentFlag")),
        status=text(heartbeat.get("SessionStatus")),
        time_to_go=text(heartbeat.get("overallTimeToGo")),
        total_laps=_first_int(
            heartbeat.get("totalLaps"),
            heartbeat.get("TotalLaps"),
            heartbeat.get("raceLaps"),
            heartbeat.get("laps"),
        ),
        series=text(heartbeat.get("Series")),
        drivers=tuple(drivers),
    )


def session_is_live(
    session: SessionState | None,
    *,
    no_track_activity: bool,
    fetched_at: float,
    now: float,
    max_age: float = 120.0,
) -> bool:
    """Decide whether a parsed timing snapshot is current and live.

    The timing feed keeps serving the last session's data after a weekend,
    so presence of drivers is not enough.  ``tsconfig.no_track_activity``
    and feed freshness are part of the contract.
    """
    if session is None or no_track_activity:
        return False
    if fetched_at <= 0:
        return False

    elapsed = max(0.0, now - fetched_at)
    if elapsed > max_age:
        return False

    flag = session.flag.upper()
    status = session.status.upper()
    if flag == "COLD" or status == "COLD":
        return False

    return flag in LIVE_FLAGS or status in LIVE_STATUSES


def parse_tsconfig(payload: Any) -> TrackConfig:
    """Parse ``tsconfig.json``; missing data is treated as no activity."""
    data = _mapping(payload)
    return TrackConfig(
        no_track_activity=boolean(data.get("no_track_activity", True)),
        rain_delay=boolean(data.get("rain_delay")),
        track_map_url=text(data.get("track_map_url")),
        show_static_track_map=boolean(data.get("show_static_track_map")),
        overrides=_mapping(data.get("overrides")),
    )


def parse_feed_date(value: Any) -> date | None:
    """Parse the schedule's SQL-style date marker.

    The feed publishes times like ``2027-03-07 05:00:00`` and sets
    ``green_flag_tbd_time`` for most events.  Those values are date
    markers, not reliable green-flag clock times, so only the date is
    exposed here until a live weekend can validate the timezone.
    """
    raw = text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_feed_datetime(value: Any) -> datetime | None:
    """Parse a feed timestamp while keeping its published (naive) clock time.

    The schedule/activity feeds publish date-marker timestamps whose
    timezone has not been validated against a live weekend.  Returning a
    naive datetime keeps the display honest: it shows what the feed
    published rather than inventing a timezone conversion.
    """
    raw = text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def parse_schedule(payload: Any) -> tuple[RaceEvent, ...]:
    """Parse ``schedulefeed.json`` into race events sorted by date."""
    schedule = _mapping(_mapping(payload).get("schedule"))
    races = _sequence(schedule.get("race"))

    events: list[RaceEvent] = []
    for raw in races:
        row = _mapping(raw)
        tv = _mapping(row.get("tv"))
        listing = _mapping(tv.get("listing"))

        winner = row.get("racewinner")
        if isinstance(winner, Mapping):
            winner_name = text(winner.get("name"))
        else:
            winner_name = text(winner)

        past_winners: list[str] = []
        for entry in _sequence(_mapping(row.get("past_winners")).get("past_winner")):
            past = _mapping(entry)
            name = text(past.get("name"))
            year = text(past.get("year"))
            if name:
                past_winners.append(f"{name} ({year})" if year else name)

        events.append(
            RaceEvent(
                event_id=text(row.get("eventid")),
                name=text(row.get("name")),
                track=text(row.get("trackname")),
                city=text(row.get("city")),
                state=text(row.get("state")),
                country=text(row.get("country")),
                date=parse_feed_date(row.get("green_flag")),
                green_flag=text(row.get("green_flag")),
                green_flag_tbd=boolean(row.get("green_flag_tbd_time")),
                laps=text(row.get("laps")),
                track_length=text(row.get("track_length")),
                is_complete=boolean(row.get("is_complete")),
                winner=winner_name,
                tv=text(listing.get("channel")),
                past_winners=tuple(past_winners),
                raw=row,
            )
        )

    events.sort(
        key=lambda event: (
            event.date is None,
            event.date or date.max,
            event.event_id,
        )
    )
    return tuple(events)


def next_race(
    events: Sequence[RaceEvent], today: date | None = None
) -> NextRace | None:
    """Return the nearest incomplete race on or after ``today``."""
    current = today or datetime.now(timezone.utc).date()
    for event in events:
        if event.date is None or event.is_complete:
            continue
        if event.date >= current:
            return NextRace(
                event=event,
                days_until=(event.date - current).days,
            )
    return None


def parse_drivers(payload: Any) -> tuple[Standing, ...]:
    """Build championship standings from the driver directory feed."""
    data = _mapping(_mapping(payload).get("drivers"))
    drivers = _sequence(data.get("driver"))

    rows: list[Standing] = []
    for raw in drivers:
        row = _mapping(raw)
        stats = _mapping(row.get("stats"))
        name = text(row.get("name")) or " ".join(
            part
            for part in (
                text(row.get("firstname")),
                text(row.get("lastname")),
            )
            if part
        )
        if not name:
            continue
        rows.append(
            Standing(
                position=0,
                driver=name,
                team=text(row.get("team")),
                car_number=text(row.get("number")),
                points=integer(stats.get("points")),
                wins=integer(stats.get("wins")),
                poles=integer(stats.get("poles")),
                top5=integer(stats.get("top5")),
                top10=integer(stats.get("top10")),
                starts=integer(stats.get("starts")),
                driver_id=text(row.get("driverid")),
                team_id=text(row.get("teamid")),
                engine=text(row.get("engine")),
                engine_logo=text(row.get("engine_logo")),
            )
        )

    rows.sort(key=lambda standing: (-standing.points, -standing.wins, standing.driver))
    return tuple(
        replace(standing, position=index + 1) for index, standing in enumerate(rows)
    )


def parse_activity(payload: Any) -> tuple[ActivitySession, ...]:
    """Parse ``trackactivityleaderboardfeed.json`` into session windows."""
    data = _mapping(_mapping(payload).get("trackactivity"))
    events = _sequence(data.get("event"))

    sessions: list[ActivitySession] = []
    for raw in events:
        event = _mapping(raw)
        for raw_session in _sequence(_mapping(event.get("sessions")).get("session")):
            session = _mapping(raw_session)
            networks = tuple(
                name
                for raw_network in _sequence(
                    _mapping(session.get("networks")).get("network")
                )
                if (name := text(_mapping(raw_network).get("name")))
            )
            sessions.append(
                ActivitySession(
                    event_id=text(event.get("eventid")),
                    event_name=text(event.get("eventname")),
                    session_id=text(session.get("sessionid")),
                    label=text(session.get("sessionlabel")),
                    session_type=text(session.get("sessiontype")),
                    start=text(session.get("startdatetime")),
                    end=text(session.get("enddatetime")),
                    status=text(session.get("status")),
                    estimated_green_flag=text(session.get("estimatedgreenflag")),
                    broadcast=_first_text(
                        session.get("broadcastnetworkname"),
                        networks[0] if networks else "",
                    ),
                    networks=networks,
                )
            )
    return tuple(sessions)


def select_next_session(
    sessions: Sequence[ActivitySession], event_id: str
) -> ActivitySession | None:
    """Return the session to show on the idle next-event screen.

    The race session is preferred; if the activity feed only has practice
    or qualifying windows for the event, the first published session is
    used instead.
    """
    event_id = text(event_id)
    candidates = [session for session in sessions if session.event_id == event_id]
    if not candidates:
        return None
    for session in candidates:
        if (
            session.session_type.strip().upper() == "R"
            or "race" in session.label.lower()
        ):
            return session
    return candidates[0]


def championship(
    events: Sequence[RaceEvent], standings: Sequence[Standing]
) -> Championship | None:
    """Compute a lightweight championship clinch from schedule + points.

    The calculation is intentionally cheap: the points leader has clinched
    when their margin over second place is larger than every point still
    available.  With 2026's system that is 54 points per remaining race
    (50 win + 1 pole + 1 lap led + 2 most laps led); there are no
    double-points races.  This is not a substitute for the official
    classification during the off-season rollover - the champion scene
    therefore also supports a manual override.
    """
    if not events or not standings:
        return None

    races_total = len(events)
    races_complete = sum(1 for event in events if event.is_complete)
    races_remaining = max(0, races_total - races_complete)
    points_available = races_remaining * MAX_RACE_POINTS

    leader = standings[0]
    runner_up = standings[1] if len(standings) > 1 else None
    margin = leader.points - (runner_up.points if runner_up else 0)
    clinched = bool(leader.points) and (
        races_remaining == 0 or margin > points_available
    )

    return Championship(
        leader=leader,
        runner_up=runner_up,
        races_total=races_total,
        races_complete=races_complete,
        races_remaining=races_remaining,
        points_available=points_available,
        margin=margin,
        clinched=clinched,
    )
