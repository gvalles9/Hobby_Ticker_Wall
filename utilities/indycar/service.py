"""Polling and caching service for the INDYCAR feeds.

The service is deliberately independent of the display and configuration
layers.  A scene will eventually call :meth:`IndyCarService.snapshot` from
its ``poll()`` method; until then the same API can be exercised from the
CLI with ``python -m utilities.indycar``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable

from utilities.indycar.client import FEED_PATHS, IndyCarFeeds
from utilities.indycar.models import SessionState, Snapshot
from utilities.indycar.parsing import (
    championship,
    next_race,
    parse_activity,
    parse_drivers,
    parse_schedule,
    parse_timing,
    parse_tsconfig,
    select_next_session,
    session_is_live,
)

SCHEDULE_REFRESH = 6 * 60 * 60
DRIVERS_REFRESH = 6 * 60 * 60

# Keep the live scene on screen briefly when the timing feed flips to
# COLD/idle at the end of a session, so the display does not flicker back
# to idle while the final flag is still being shown.
LIVE_HOLD_SECONDS = 20.0


@dataclass
class _CachedFeed:
    data: Any = None
    fetched_at: float = 0.0
    etag: str = ""
    last_modified: str = ""
    error: str = ""
    failures: int = 0
    retry_at: float = 0.0


class IndyCarService:
    """Fetch feeds on a schedule and assemble a normalized snapshot."""

    def __init__(
        self,
        feeds: IndyCarFeeds | None = None,
        clock: Callable[[], float] = time.time,
        live_max_age: float = 120.0,
        backoff_min: float = 2.0,
        backoff_max: float = 60.0,
        live_hold: float = LIVE_HOLD_SECONDS,
    ) -> None:
        self.feeds = feeds or IndyCarFeeds(clock=clock)
        self.clock = clock
        self.live_max_age = live_max_age
        self.backoff_min = backoff_min
        self.backoff_max = backoff_max
        self.live_hold = live_hold
        self._cache = {name: _CachedFeed() for name in FEED_PATHS}
        self._last_live = False
        self._last_live_session: SessionState | None = None
        self._last_live_at = 0.0
        self._last_snapshot = Snapshot()

    def snapshot(self, *, force: bool = False, now: float | None = None) -> Snapshot:
        """Return the current snapshot, fetching only due feeds."""
        current = self.clock() if now is None else float(now)
        try:
            return self._build_snapshot(current, force)
        except Exception as exc:  # never let a feed surprise reach the display
            error = f"{type(exc).__name__}: {exc}"
            if self._last_snapshot.session or self._last_snapshot.next_race:
                self._last_snapshot = replace(self._last_snapshot, error=error)
                return self._last_snapshot
            return Snapshot(fetched_at=current, error=error)

    def reset(self) -> None:
        """Drop all cached feeds and the last snapshot."""
        self._cache = {name: _CachedFeed() for name in FEED_PATHS}
        self._last_live = False
        self._last_live_session = None
        self._last_live_at = 0.0
        self._last_snapshot = Snapshot()

    def _build_snapshot(self, now: float, force: bool) -> Snapshot:
        self._refresh("tsconfig", now, force)
        track = parse_tsconfig(self._cache["tsconfig"].data)
        self._last_live = bool(self._last_snapshot.is_live)

        if not track.no_track_activity or self._last_live:
            self._refresh("timing", now, force)

        self._refresh("activity", now, force)
        self._refresh("schedule", now, force)
        self._refresh("drivers", now, force)

        timing_data = self._cache["timing"].data
        session = parse_timing(timing_data) if timing_data is not None else None
        if session is not None:
            live = session_is_live(
                session,
                no_track_activity=track.no_track_activity,
                fetched_at=self._cache["timing"].fetched_at,
                now=now,
                max_age=self.live_max_age,
            )
            session = replace(
                session,
                live=live,
                fetched_at=self._cache["timing"].fetched_at,
            )
            if live:
                self._last_live_at = now
                self._last_live_session = session
            elif (
                self._last_live_session is not None
                and self._last_live_at
                and now - self._last_live_at <= self.live_hold
            ):
                # Hold the just-finished session on screen for a few
                # seconds instead of dropping straight back to idle.
                session = replace(session, live=True)
                self._last_live_session = session
        self._last_live = bool(session and session.live)

        events = parse_schedule(self._cache["schedule"].data)
        activity = parse_activity(self._cache["activity"].data)
        standings = parse_drivers(self._cache["drivers"].data)
        today = datetime.fromtimestamp(now, tz=timezone.utc).date()
        upcoming = next_race(events, today)
        if upcoming is not None:
            next_session = select_next_session(activity, upcoming.event.event_id)
            if next_session is not None:
                upcoming = replace(upcoming, session=next_session)

        # The schedule's laps column is the most reliable race distance
        # when it is numeric; the timing heartbeat rarely carries it.
        if session is not None and session.total_laps <= 0:
            for event in events:
                if event.event_id and event.event_id == session.event_id:
                    if event.total_laps:
                        session = replace(session, total_laps=event.total_laps)
                    break

        season = championship(events, standings)

        errors = [
            f"{name}: {cached.error}"
            for name, cached in self._cache.items()
            if cached.error
        ]
        snapshot = Snapshot(
            session=session,
            next_race=upcoming,
            standings=standings,
            events=events,
            activity=activity,
            championship=season,
            fetched_at=now,
            error="; ".join(errors),
        )
        self._last_snapshot = snapshot
        return snapshot

    def _cadence(self, name: str, now: float) -> float:
        if name == "timing":
            return 5.0
        if name == "tsconfig":
            return 15.0 if self._last_live else 60.0
        if name == "activity":
            if self._last_live:
                return 30.0
            return 60.0 if self._near_event(now) else 300.0
        if name == "schedule":
            return SCHEDULE_REFRESH
        if name == "drivers":
            return DRIVERS_REFRESH
        return 60.0

    def _near_event(self, now: float) -> bool:
        events = parse_schedule(self._cache["schedule"].data)
        today = datetime.fromtimestamp(now, tz=timezone.utc).date()
        upcoming = next_race(events, today)
        return bool(upcoming and upcoming.days_until <= 2)

    def _refresh(self, name: str, now: float, force: bool) -> None:
        cached = self._cache[name]
        if not force:
            if now < cached.retry_at:
                return
            if cached.fetched_at and (
                now - cached.fetched_at < self._cadence(name, now)
            ):
                return

        # The large, slow-moving feeds can use conditional requests; the
        # fast-moving feeds get a cache-buster like the official site uses.
        conditional = name in {"schedule", "drivers"}
        result = self.feeds.fetch(
            name,
            etag=cached.etag if conditional else "",
            last_modified=cached.last_modified if conditional else "",
            cache_bust=not conditional,
        )

        if result.not_modified:
            cached.fetched_at = now
            cached.error = ""
            cached.failures = 0
            cached.retry_at = 0.0
            return

        if result.error:
            cached.error = result.error
            cached.failures += 1
            delay = min(
                self.backoff_max,
                self.backoff_min * (2 ** (cached.failures - 1)),
            )
            cached.retry_at = now + delay
            return

        cached.data = result.data
        cached.fetched_at = result.fetched_at or now
        cached.etag = result.etag
        cached.last_modified = result.last_modified
        cached.error = ""
        cached.failures = 0
        cached.retry_at = 0.0
