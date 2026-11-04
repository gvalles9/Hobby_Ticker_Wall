"""Tests for scenes/satellite/satellite_scene.py - pass recompute holdoff.

A CelesTrak outage used to re-run - and re-log - the skipped pass
computation on every poll tick.  These tests pin the holdoff behaviour:
recompute is gated by a cooldown and the skip warning is rate-limited.
"""

from __future__ import annotations

import logging
import types

import scenes.satellite.satellite_scene as satellite_scene
from scenes.satellite.satellite_scene import SatelliteScene, format_satellite_data

_LOGGER = "scenes.satellite.satellite_scene"


class _FakeTLEManager:
    def __init__(self, tles):
        self._tles = tles
        self.try_get_calls = 0

    def try_get(self):
        self.try_get_calls += 1
        return self._tles


class _StubConfig:
    satellite_max_count = 3
    observer_lat = 55.9
    observer_lng = -4.3
    satellite_min_elevation = 10
    satellite_test_mode = False
    debug_scene = "auto"
    satellite_timeout_enabled = False
    satellite_timeout_seconds = 30
    satellite_data_points = ("azimuth", "elevation", "speed", "altitude")

    @classmethod
    def instance(cls):
        return cls()


def _cfg():
    return types.SimpleNamespace(
        observer_lat=55.9,
        observer_lng=-4.3,
        satellite_min_elevation=10,
        satellite_max_count=3,
        satellite_test_mode=False,
        debug_scene="auto",
    )


def _scene(tles=None):
    manager = _FakeTLEManager(tles)
    return SatelliteScene(canvas=None, panel=None, tle_manager=manager), manager


class TestNoTleHoldoff:
    """recompute_passes with no TLE data: warn once, retry on cooldown."""

    def test_warns_once_then_goes_quiet(self, caplog):
        scene, manager = _scene(tles=None)

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            scene.recompute_passes(_cfg())  # first skip warns
            scene.recompute_passes(_cfg())  # identical repeat stays silent

        assert manager.try_get_calls == 2
        assert caplog.text.count("no TLE data available") == 1

    def test_poll_gates_recompute_behind_cooldown(self, monkeypatch, caplog):
        monkeypatch.setattr(satellite_scene, "Config", _StubConfig)
        scene, manager = _scene(tles=None)

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            scene.poll()  # first tick: warns + arms the cooldown
            scene.poll()  # within cooldown: no recompute attempt at all
            assert manager.try_get_calls == 1
            assert caplog.text.count("no TLE data available") == 1

            scene.next_recompute_at = 0.0
            scene.poll()  # cooldown expired: retries, but the log stays quiet
            assert manager.try_get_calls == 2
            assert caplog.text.count("no TLE data available") == 1

            scene.last_no_tle_logged_at = 0.0
            scene.next_recompute_at = 0.0
            scene.poll()  # log interval expired: warns once more
            assert manager.try_get_calls == 3
            assert caplog.text.count("no TLE data available") == 2

    def test_poll_skips_recompute_while_cooled_down(self, monkeypatch):
        monkeypatch.setattr(satellite_scene, "Config", _StubConfig)
        scene, manager = _scene(tles=None)

        scene.next_recompute_at = float("inf")  # far future
        scene.poll()

        assert manager.try_get_calls == 0  # cooldown blocks the attempt


class TestRecoveryFromOutage:
    def test_success_resets_suppression_and_computes(self, monkeypatch):
        tle = ("ISS (ZARYA)", "1 25544U 98067A   ...", "2 25544  51.6 ...")
        scene, manager = _scene(tles=[tle])
        scene.last_no_tle_logged_at = 12345.0  # as if an outage had been warned
        monkeypatch.setattr(
            satellite_scene.passes_mod, "compute_passes", lambda *args, **kw: []
        )

        scene.recompute_passes(_cfg())

        assert manager.try_get_calls == 1
        assert scene.last_no_tle_logged_at == 0.0
        assert scene.next_recompute_at > scene.windows_computed_at


class TestHealthyPathCooldown:
    def test_success_arms_cooldown_again(self, monkeypatch):
        """Success also arms the cooldown: empty SGP4 results used to
        recompute every tick, hammering the Pi's CPU for no benefit."""
        monkeypatch.setattr(satellite_scene, "Config", _StubConfig)
        tle = ("ISS (ZARYA)", "1 25544U ...", "2 25544 ...")
        scene, manager = _scene(tles=[tle])
        monkeypatch.setattr(
            satellite_scene.passes_mod, "compute_passes", lambda *a, **k: []
        )

        scene.poll()

        assert scene.pass_windows == []
        assert scene.windows_computed_at > 0
        assert scene.next_recompute_at >= scene.windows_computed_at

        scene.poll()  # next tick: gated, try_get not called again
        assert manager.try_get_calls == 1


def test_test_mode_generates_a_pass_without_fetching_tles(monkeypatch):
    class TestConfig(_StubConfig):
        satellite_test_mode = True
        debug_scene = "satellite"

    monkeypatch.setattr(satellite_scene, "Config", TestConfig)
    scene, manager = _scene(tles=None)
    computed = []

    def fake_compute_passes(tles, *args, **kwargs):
        computed.append((tles, kwargs.get("test_mode")))
        return [satellite_scene.passes_mod.fake_pass_window()]

    monkeypatch.setattr(
        satellite_scene.passes_mod, "compute_passes", fake_compute_passes
    )

    scene.poll()

    assert manager.try_get_calls == 0
    assert computed == [([], True)]
    assert scene.pass_windows
    assert scene.has_data()


def test_test_mode_change_recomputes_without_waiting_for_poll_timeout(monkeypatch):
    class TestConfig(_StubConfig):
        satellite_test_mode = True
        debug_scene = "satellite"

    monkeypatch.setattr(satellite_scene, "Config", TestConfig)
    scene, manager = _scene(tles=None)
    scene.pass_windows = [satellite_scene.passes_mod.fake_pass_window()]
    scene.windows_computed_at = satellite_scene.datetime.datetime.utcnow().timestamp()
    scene.last_test_mode = False
    scene.next_recompute_at = (
        satellite_scene.datetime.datetime.utcnow().timestamp() + 60
    )
    computed = []
    monkeypatch.setattr(
        satellite_scene.passes_mod,
        "compute_passes",
        lambda tles, *args, **kwargs: computed.append(kwargs["test_mode"])
        or [satellite_scene.passes_mod.fake_pass_window()],
    )

    scene.poll()

    assert manager.try_get_calls == 0
    assert computed == [True]


def test_satellite_name_is_shifted_left_to_keep_closing_parenthesis_visible(
    monkeypatch,
):
    class Panel:
        def __init__(self):
            self.drawn = []

        def draw_text(self, canvas, font, x, y, colour, text):
            self.drawn.append((x, y, text))

    scene, _manager = _scene()
    scene.panel = Panel()
    scene.last_cycle_second = satellite_scene.datetime.datetime.utcnow().timestamp()
    monkeypatch.setattr(
        satellite_scene, "fonts", types.SimpleNamespace(extrasmall=object())
    )
    monkeypatch.setattr(
        satellite_scene,
        "font_text_width",
        lambda font, text: len(text) * 4,
    )
    monkeypatch.setattr(
        satellite_scene.passes_mod,
        "current_position",
        lambda window: None,
    )

    now = satellite_scene.datetime.datetime.utcnow()
    window = types.SimpleNamespace(
        name="ISS (ZARYA)",
        trajectory=[],
        aos=now - satellite_scene.datetime.timedelta(minutes=1),
        los=now + satellite_scene.datetime.timedelta(minutes=5),
        max_el=45.0,
    )
    scene.update_text_panel([window])

    name_x, _name_y, name = next(
        item for item in scene.panel.drawn if item[2] == "ISS (ZARYA)"
    )
    assert name.endswith(")")
    assert name_x + len(name) * 4 <= satellite_scene.screen.WIDTH - 4


def test_satellite_data_defaults_are_drawn_on_both_sides_of_globe(monkeypatch):
    class Panel:
        def __init__(self):
            self.drawn = []

        def draw_text(self, canvas, font, x, y, colour, text):
            self.drawn.append((x, y, text))

    scene, _manager = _scene()
    scene.panel = Panel()
    scene.last_cycle_second = satellite_scene.datetime.datetime.utcnow().timestamp()
    monkeypatch.setattr(satellite_scene, "Config", _StubConfig)
    monkeypatch.setattr(
        satellite_scene, "fonts", types.SimpleNamespace(extrasmall=object())
    )
    monkeypatch.setattr(
        satellite_scene, "font_text_width", lambda font, text: len(text) * 4
    )
    monkeypatch.setattr(
        satellite_scene.passes_mod, "current_position", lambda window: (90, 45)
    )
    monkeypatch.setattr(satellite_scene, "compute_telemetry", lambda *args: None)

    now = satellite_scene.datetime.datetime.utcnow()
    window = types.SimpleNamespace(
        name="ISS",
        trajectory=[],
        aos=now - satellite_scene.datetime.timedelta(minutes=1),
        los=now + satellite_scene.datetime.timedelta(minutes=5),
        max_el=45.0,
    )
    scene.update_text_panel([window])

    labels = {text: (x, y) for x, y, text in scene.panel.drawn}
    assert labels["Azimuth"][0] < satellite_scene.azel_plot.PLOT_CX
    assert labels["Elevation"][0] < satellite_scene.azel_plot.PLOT_CX
    assert labels["Speed"][0] > satellite_scene.azel_plot.PLOT_CX
    assert labels["Altitude"][0] > satellite_scene.azel_plot.PLOT_CX


def test_format_satellite_data_supports_azimuth_and_elevation():
    cfg = types.SimpleNamespace(speed_unit="kmh", height_unit="m")

    assert format_satellite_data("azimuth", 359.6, 25.2, None, cfg, None) == (
        "Azimuth",
        "000",
        "deg",
    )
    assert format_satellite_data("elevation", 359.6, 25.2, None, cfg, None) == (
        "Elevation",
        "25",
        "deg",
    )


def test_format_satellite_data_applies_configured_speed_and_altitude_units():
    cfg = types.SimpleNamespace(speed_unit="mph", height_unit="ft")

    assert format_satellite_data("speed", 0, 0, (100, 2), cfg, None) == (
        "Speed",
        "62",
        "mph",
    )
    assert format_satellite_data("altitude", 0, 0, (100, 2), cfg, None) == (
        "Altitude",
        "6561",
        "ft",
    )


def test_format_satellite_data_supports_new_fields():
    cfg = types.SimpleNamespace(speed_unit="kmh", height_unit="m")
    now = satellite_scene.datetime.datetime.utcnow()

    # Test range with a window containing trajectory
    window = satellite_scene.passes_mod.PassWindow(
        name="TEST",
        tle_index=0,
        aos=now - satellite_scene.datetime.timedelta(minutes=1),
        los=now + satellite_scene.datetime.timedelta(minutes=5),
        max_el=45.0,
        trajectory=[(90, 45, 500.0, now)],
    )
    assert format_satellite_data("range", 0, 0, None, cfg, window) == (
        "Range",
        "500",
        "km",
    )

    # Test time_to_aos
    future_aos = now + satellite_scene.datetime.timedelta(seconds=120)
    window_future = satellite_scene.passes_mod.PassWindow(
        name="TEST",
        tle_index=0,
        aos=future_aos,
        los=now + satellite_scene.datetime.timedelta(minutes=10),
        max_el=45.0,
        trajectory=[],
    )
    assert format_satellite_data("time_to_aos", 0, 0, None, cfg, window_future) == (
        "To AOS",
        "120",
        "s",
    )

    # Test time_to_los
    future_los = now + satellite_scene.datetime.timedelta(seconds=300)
    window_los = satellite_scene.passes_mod.PassWindow(
        name="TEST",
        tle_index=0,
        aos=now - satellite_scene.datetime.timedelta(minutes=1),
        los=future_los,
        max_el=45.0,
        trajectory=[],
    )
    assert format_satellite_data("time_to_los", 0, 0, None, cfg, window_los) == (
        "To LOS",
        "300",
        "s",
    )

    # Test pass_duration
    window_dur = satellite_scene.passes_mod.PassWindow(
        name="TEST",
        tle_index=0,
        aos=now - satellite_scene.datetime.timedelta(minutes=2),
        los=now + satellite_scene.datetime.timedelta(minutes=3),
        max_el=45.0,
        trajectory=[],
    )
    assert format_satellite_data("pass_duration", 0, 0, None, cfg, window_dur) == (
        "Duration",
        "300",
        "s",
    )

    # Test max_elevation
    window_max = satellite_scene.passes_mod.PassWindow(
        name="TEST",
        tle_index=0,
        aos=now - satellite_scene.datetime.timedelta(minutes=1),
        los=now + satellite_scene.datetime.timedelta(minutes=5),
        max_el=67.3,
        trajectory=[],
    )
    assert format_satellite_data("max_elevation", 0, 0, None, cfg, window_max) == (
        "Max El",
        "67",
        "deg",
    )

    # Test None window returns placeholder
    assert format_satellite_data("range", 0, 0, None, cfg, None) == ("Range", "--", "")
    assert format_satellite_data("time_to_aos", 0, 0, None, cfg, None) == ("To AOS", "--", "")
    assert format_satellite_data("time_to_los", 0, 0, None, cfg, None) == ("To LOS", "--", "")
    assert format_satellite_data("pass_duration", 0, 0, None, cfg, None) == ("Duration", "--", "")
    assert format_satellite_data("max_elevation", 0, 0, None, cfg, None) == ("Max El", "--", "")
