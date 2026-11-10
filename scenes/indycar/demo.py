"""Bundled snapshots for offline scene previews.

The INDYCAR feeds are quiet for most of the year, so the settings page can
inject one of these snapshots when the INDYCAR test mode is enabled.  They
are also what the scene tests exercise, keeping the suite network-free.
"""

from __future__ import annotations

from datetime import date

from utilities.indycar.models import (
    ActivitySession,
    Championship,
    DriverTiming,
    NextRace,
    RaceEvent,
    SessionState,
    Snapshot,
    Standing,
)

ST_PETE = RaceEvent(
    event_id="5559",
    name="Firestone Grand Prix of St. Petersburg",
    track="Streets of St. Petersburg",
    city="St. Petersburg",
    state="Florida",
    country="USA",
    date=date(2027, 3, 7),
    green_flag="2027-03-07 12:30:00",
    green_flag_tbd=False,
    laps="100",
    track_length="1.8",
    tv="Fox",
)


def _race_driver(
    position: int,
    number: str,
    first: str,
    last: str,
    team: str,
    gap: str,
    laps: int = 45,
    **kwargs,
) -> DriverTiming:
    return DriverTiming(
        position=position,
        car_number=number,
        first_name=first,
        last_name=last,
        team=team,
        laps=laps,
        gap=gap,
        best_lap=kwargs.pop("best_lap", "1:14.505"),
        last_lap=kwargs.pop("last_lap", "1:15.120"),
        qual_time=kwargs.pop("qual_time", "1:14.505"),
        qual_speed=kwargs.pop("qual_speed", "117.850"),
        **kwargs,
    )


def _race_session() -> SessionState:
    drivers = (
        _race_driver(1, "11", "Alex", "Palou", "Chip Ganassi Racing", "0.0000"),
        _race_driver(2, "71", "Tymek", "Kucharczyk", "HMD Motorsports", "1.8420"),
        _race_driver(3, "28", "Max", "Taylor", "Andretti Global", "4.1190"),
        _race_driver(4, "6", "Max", "Garcia", "Chip Ganassi Racing", "6.5030"),
    )
    return SessionState(
        live=True,
        event_id="5559",
        event_name="Firestone Grand Prix of St. Petersburg",
        track_name="Streets of St. Petersburg",
        session_name="Race",
        session_type="R",
        session_label="Race",
        flag="GREEN",
        status="GREEN",
        time_to_go="01:23:45",
        total_laps=100,
        series="L",
        drivers=drivers,
        fetched_at=1_800_000_000.0,
    )


def _qualifying_session() -> SessionState:
    drivers = (
        _race_driver(
            1,
            "71",
            "Tymek",
            "Kucharczyk",
            "HMD Motorsports",
            "0.0000",
            laps=0,
            best_lap="1:13.991",
            last_lap="1:14.220",
            qual_time="1:13.991",
            qual_speed="118.920",
        ),
        _race_driver(
            2,
            "11",
            "Alex",
            "Palou",
            "Chip Ganassi Racing",
            "0.1840",
            laps=0,
            best_lap="1:14.175",
            last_lap="1:14.405",
            qual_time="1:14.175",
            qual_speed="118.610",
            second_qual_time="1:14.020",
            second_qual_speed="118.720",
        ),
        _race_driver(
            3,
            "28",
            "Max",
            "Taylor",
            "Andretti Global",
            "0.4020",
            laps=0,
            best_lap="1:14.393",
            last_lap="1:14.610",
            qual_time="1:14.393",
            qual_speed="118.220",
        ),
    )
    return SessionState(
        live=True,
        event_id="5559",
        event_name="Firestone Grand Prix of St. Petersburg",
        track_name="Streets of St. Petersburg",
        session_name="Qualifying",
        session_type="Q",
        session_label="Qualifying",
        flag="GREEN",
        status="GREEN",
        time_to_go="00:08:42",
        series="L",
        drivers=drivers,
        fetched_at=1_800_000_000.0,
    )


def _next_race() -> NextRace:
    session = ActivitySession(
        event_id=ST_PETE.event_id,
        event_name=ST_PETE.name,
        session_id="6965",
        label="Race",
        session_type="R",
        start=ST_PETE.green_flag,
        end=ST_PETE.green_flag,
        status="ACTIVE",
        estimated_green_flag=ST_PETE.green_flag,
        broadcast="Fox",
        networks=("Fox", "INDYCAR LIVE"),
    )
    return NextRace(event=ST_PETE, days_until=120, session=session)


def _standings() -> tuple[Standing, ...]:
    return (
        Standing(1, "Alex Palou", "Chip Ganassi Racing", "11", 631, 6, 4, 12, 15, 17),
        Standing(2, "Tymek Kucharczyk", "HMD Motorsports", "71", 512, 2, 1, 8, 13, 17),
        Standing(3, "Max Taylor", "Andretti Global", "28", 498, 1, 1, 7, 12, 17),
    )


def demo_race_snapshot() -> Snapshot:
    """A live race with Palou leading and three cars on the lead lap."""
    return Snapshot(
        session=_race_session(),
        next_race=_next_race(),
        standings=_standings(),
        events=(ST_PETE,),
        activity=(_next_race().session,),
        championship=Championship(
            leader=_standings()[0],
            runner_up=_standings()[1],
            races_total=17,
            races_complete=0,
            races_remaining=17,
            points_available=918,
            margin=119,
            clinched=False,
        ),
        fetched_at=1_800_000_000.0,
    )


def demo_qualifying_snapshot() -> Snapshot:
    """A live qualifying session so the qualification layout can be previewed."""
    snapshot = demo_race_snapshot()
    return Snapshot(
        session=_qualifying_session(),
        next_race=snapshot.next_race,
        standings=snapshot.standings,
        events=snapshot.events,
        activity=snapshot.activity,
        championship=snapshot.championship,
        fetched_at=snapshot.fetched_at,
    )


def demo_champion_snapshot() -> Snapshot:
    """An off-season clinched championship for the flashing celebration."""
    standings = _standings()
    return Snapshot(
        session=None,
        next_race=_next_race(),
        standings=standings,
        events=(ST_PETE,),
        activity=(_next_race().session,),
        championship=Championship(
            leader=standings[0],
            runner_up=standings[1],
            races_total=17,
            races_complete=17,
            races_remaining=0,
            points_available=0,
            margin=119,
            clinched=True,
        ),
        fetched_at=1_800_000_000.0,
    )
