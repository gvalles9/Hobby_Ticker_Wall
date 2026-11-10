"""Offline service tests for the INDYCAR polling layer."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from utilities.indycar.client import FeedResult
from utilities.indycar.service import IndyCarService

FIXTURES = Path(__file__).parent / "fixtures" / "indycar"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def feed_payloads(*, live: bool):
    """Recorded payloads, with the track-activity flag set as needed."""
    return {
        "tsconfig": {
            "no_track_activity": not live,
            "rain_delay": False,
            "track_map_url": "",
            "show_static_track_map": False,
        },
        "timing": fixture("timing_race_live.json"),
        "activity": fixture("activity.json"),
        "schedule": fixture("schedule.json"),
        "drivers": fixture("drivers.json"),
    }


class Clock:
    def __init__(self, now: float):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeFeeds:
    """In-memory feed source that records every request."""

    def __init__(self, payloads, clock, fetched_at=None):
        self.payloads = payloads
        self.clock = clock
        self.fetched_at = fetched_at
        self.calls = []
        self.errors = {}
        self.not_modified = set()
        self.etags = {}

    def fetch(self, name, **kwargs):
        self.calls.append((name, kwargs))

        if name in self.errors:
            return FeedResult(
                name=name,
                error=self.errors[name],
                fetched_at=self.clock(),
            )
        if name in self.not_modified:
            return FeedResult(
                name=name,
                status=304,
                not_modified=True,
                fetched_at=self.clock(),
            )
        return FeedResult(
            name=name,
            data=self.payloads[name],
            status=200,
            etag=self.etags.get(name, f'"{name}"'),
            last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
            fetched_at=(self.clock() if self.fetched_at is None else self.fetched_at),
        )

    def names(self):
        return [name for name, _ in self.calls]


# ---------------------------------------------------------------------------
# Snapshot assembly
# ---------------------------------------------------------------------------


def test_idle_snapshot_skips_timing_and_still_has_schedule():
    clock = Clock(1_700_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)

    snapshot = service.snapshot()

    assert snapshot.is_live is False
    assert snapshot.session is None
    assert "timing" not in feeds.names()
    assert feeds.names() == ["tsconfig", "activity", "schedule", "drivers"]

    assert snapshot.next_race is not None
    assert snapshot.next_race.event.name == "Streets of St. Petersburg"
    assert snapshot.next_race.event.date == date(2027, 3, 7)
    assert snapshot.next_race.days_until > 0

    assert snapshot.standings[0].driver == "Marcus Armstrong"
    assert snapshot.standings[0].position == 1
    assert snapshot.error == ""
    assert snapshot.fetched_at == clock.now


def test_live_snapshot_fetches_timing_and_marks_session_live():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=True), clock)
    service = IndyCarService(feeds=feeds, clock=clock)

    snapshot = service.snapshot()

    assert snapshot.is_live is True
    assert snapshot.session is not None
    assert snapshot.session.live is True
    assert snapshot.session.event_name == ("Firestone Grand Prix of St. Petersburg")
    assert snapshot.session.leader is not None
    assert snapshot.session.leader.name == "Alex Palou"
    assert feeds.names() == [
        "tsconfig",
        "timing",
        "activity",
        "schedule",
        "drivers",
    ]


def test_stale_timing_is_parsed_but_not_live():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=True), clock, fetched_at=clock.now - 500.0)
    service = IndyCarService(feeds=feeds, clock=clock)

    snapshot = service.snapshot()

    assert snapshot.session is not None
    assert snapshot.session.drivers
    assert snapshot.session.live is False
    assert snapshot.is_live is False


def test_activity_ending_clears_a_previously_live_session():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=True), clock)
    service = IndyCarService(feeds=feeds, clock=clock)

    assert service.snapshot().is_live is True

    feeds.payloads["tsconfig"]["no_track_activity"] = True
    clock.advance(61)
    feeds.calls.clear()

    snapshot = service.snapshot()

    assert "timing" in feeds.names()
    assert snapshot.is_live is False
    assert snapshot.session is not None
    assert snapshot.session.live is False


# ---------------------------------------------------------------------------
# Polling cadence and caching
# ---------------------------------------------------------------------------


def test_idle_snapshot_does_not_refetch_within_cadence():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    service.snapshot()

    feeds.calls.clear()
    snapshot = service.snapshot()

    assert feeds.names() == []
    assert snapshot.next_race is not None
    assert snapshot.standings


def test_live_timing_polls_faster_than_other_feeds():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=True), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    service.snapshot()

    feeds.calls.clear()
    clock.advance(6)
    snapshot = service.snapshot()

    assert feeds.names() == ["timing"]
    assert snapshot.is_live is True


def test_slow_feeds_use_conditional_requests():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    service.snapshot()

    feeds.calls.clear()
    clock.advance(6 * 60 * 60 + 1)
    service.snapshot()

    requests = dict(feeds.calls)
    assert requests["schedule"]["etag"] == '"schedule"'
    assert requests["schedule"]["last_modified"].startswith("Mon")
    assert requests["schedule"]["cache_bust"] is False
    assert requests["drivers"]["etag"] == '"drivers"'
    assert requests["drivers"]["cache_bust"] is False

    assert requests["tsconfig"]["etag"] == ""
    assert requests["tsconfig"]["cache_bust"] is True


def test_not_modified_keeps_cached_schedule_and_standings():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    first = service.snapshot()

    feeds.not_modified.update({"schedule", "drivers"})
    clock.advance(6 * 60 * 60 + 1)
    second = service.snapshot()

    assert second.next_race == first.next_race
    assert second.standings == first.standings
    assert second.error == ""


# ---------------------------------------------------------------------------
# Errors, backoff, and recovery
# ---------------------------------------------------------------------------


def test_feed_errors_are_reported_without_raising():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    feeds.errors["schedule"] = "HTTP 500: boom"
    feeds.errors["drivers"] = "TimeoutError: timed out"
    service = IndyCarService(feeds=feeds, clock=clock)

    snapshot = service.snapshot()

    assert "schedule: HTTP 500: boom" in snapshot.error
    assert "drivers: TimeoutError: timed out" in snapshot.error
    assert snapshot.next_race is None
    assert snapshot.standings == ()
    assert snapshot.session is None


def test_failed_feed_backs_off_before_retrying():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    feeds.errors["schedule"] = "HTTP 500: boom"
    service = IndyCarService(feeds=feeds, clock=clock)

    service.snapshot()
    assert feeds.names().count("schedule") == 1

    feeds.calls.clear()
    service.snapshot()
    assert feeds.names().count("schedule") == 0

    clock.advance(3)
    service.snapshot()
    assert feeds.names().count("schedule") == 1


def test_unexpected_feed_exception_keeps_last_snapshot():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    first = service.snapshot()

    def boom(now, force):
        raise RuntimeError("parser exploded")

    service._build_snapshot = boom
    second = service.snapshot()

    assert second.next_race == first.next_race
    assert second.standings == first.standings
    assert second.error == "RuntimeError: parser exploded"


def test_reset_forces_a_full_refresh():
    clock = Clock(1_800_000_000.0)
    feeds = FakeFeeds(feed_payloads(live=False), clock)
    service = IndyCarService(feeds=feeds, clock=clock)
    service.snapshot()

    feeds.calls.clear()
    service.reset()
    service.snapshot()

    assert feeds.names() == ["tsconfig", "activity", "schedule", "drivers"]
