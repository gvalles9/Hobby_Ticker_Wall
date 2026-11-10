"""Normalized data models for the INDYCAR feed layer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DriverTiming:
    """One car's live timing row."""

    position: int
    car_number: str
    first_name: str
    last_name: str
    team: str
    laps: int = 0
    gap: str = ""
    live_gap: str = ""
    last_lap: str = ""
    best_lap: str = ""
    tire: str = ""
    status: str = ""
    on_track: bool = False
    pit_stops: int = 0
    flag_status: str = ""
    start_position: int = 0
    qual_time: str = ""
    qual_speed: str = ""
    second_qual_time: str = ""
    second_qual_speed: str = ""
    total_time: str = ""
    laps_led: int = 0
    best_speed: str = ""
    last_speed: str = ""
    equipment: str = ""
    driver_id: str = ""
    team_id: str = ""
    raw: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)

    @property
    def name(self) -> str:
        """Full driver name, falling back gracefully when fields are blank."""
        parts = [part for part in (self.first_name, self.last_name) if part]
        return " ".join(parts).strip()

    @property
    def short_name(self) -> str:
        """Last name when available, otherwise first name or car number."""
        return self.last_name or self.first_name or self.car_number

    @property
    def initial_name(self) -> str:
        """Compact ``A. Palou`` form for the three-line Top 3 rows."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}. {self.last_name}"
        return self.name or self.car_number


@dataclass(frozen=True)
class SessionState:
    """A timing session snapshot.

    ``live`` is set by the service after checking feed freshness and the
    session flag state.  Parsing alone cannot know whether the data is
    still current.
    """

    live: bool = False
    event_id: str = ""
    event_name: str = ""
    track_name: str = ""
    session_name: str = ""
    session_type: str = ""
    session_label: str = ""
    flag: str = ""
    status: str = ""
    time_to_go: str = ""
    total_laps: int = 0
    series: str = ""
    drivers: tuple[DriverTiming, ...] = ()
    fetched_at: float = 0.0

    @property
    def leader(self) -> DriverTiming | None:
        """First classified driver, if any."""
        return self.drivers[0] if self.drivers else None

    @property
    def is_qualifying(self) -> bool:
        """True when the timing feed describes a qualifying session."""
        session_type = self.session_type.strip().upper()
        label = f"{self.session_name} {self.session_label}".lower()
        return session_type.startswith("Q") or "qualif" in label


@dataclass(frozen=True)
class TrackConfig:
    """Display flags published alongside the timing feed."""

    no_track_activity: bool = True
    rain_delay: bool = False
    track_map_url: str = ""
    show_static_track_map: bool = False
    overrides: Mapping[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )


@dataclass(frozen=True)
class RaceEvent:
    """A race weekend from the official schedule feed."""

    event_id: str
    name: str
    track: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    date: date | None = None
    green_flag: str = ""
    green_flag_tbd: bool = False
    laps: str = ""
    track_length: str = ""
    is_complete: bool = False
    winner: str = ""
    tv: str = ""
    past_winners: tuple[str, ...] = ()
    raw: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)

    @property
    def total_laps(self) -> int:
        """Published race distance when the schedule has a numeric value."""
        try:
            return int(str(self.laps).strip())
        except (TypeError, ValueError):
            return 0


@dataclass(frozen=True)
class NextRace:
    """The nearest upcoming race and its date-only countdown."""

    event: RaceEvent
    days_until: int
    session: ActivitySession | None = None


@dataclass(frozen=True)
class Standing:
    """A driver's season totals, ordered by points."""

    position: int
    driver: str
    team: str = ""
    car_number: str = ""
    points: int = 0
    wins: int = 0
    poles: int = 0
    top5: int = 0
    top10: int = 0
    starts: int = 0
    driver_id: str = ""
    team_id: str = ""
    engine: str = ""
    engine_logo: str = ""


@dataclass(frozen=True)
class ActivitySession:
    """A session window from the track-activity feed.

    Times are kept as the feed's raw strings because their timezone has
    not been validated against a live weekend yet.
    """

    event_id: str
    event_name: str
    session_id: str
    label: str
    session_type: str
    start: str
    end: str
    status: str = ""
    estimated_green_flag: str = ""
    broadcast: str = ""
    networks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Championship:
    """Cheap season-clinch calculation for the champion scene.

    The feeds publish no explicit champion or season field, so this is
    derived from the schedule completeness and the drivers' points.
    """

    leader: Standing | None = None
    runner_up: Standing | None = None
    races_total: int = 0
    races_complete: int = 0
    races_remaining: int = 0
    points_available: int = 0
    margin: int = 0
    clinched: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Everything the display layer needs in one object."""

    session: SessionState | None = None
    next_race: NextRace | None = None
    standings: tuple[Standing, ...] = ()
    events: tuple[RaceEvent, ...] = ()
    activity: tuple[ActivitySession, ...] = ()
    championship: Championship | None = None
    fetched_at: float = 0.0
    error: str = ""

    @property
    def is_live(self) -> bool:
        """True when a live session is available."""
        return bool(self.session and self.session.live)

    @property
    def next_event(self) -> NextRace | None:
        """Alias for the idle next-event screen."""
        return self.next_race
