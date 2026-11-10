"""Offline tests for the INDYCAR display scenes and next-event idle theme."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from scenes.idle.themes import indycar_next_theme
from scenes.indycar import ChampionScene, DriverScene, Top3Scene
from scenes.indycar.demo import (
    demo_champion_snapshot,
    demo_qualifying_snapshot,
    demo_race_snapshot,
)
from setup.configuration import Config
from utilities.indycar.models import Snapshot


def _config(**overrides):
    values = {
        "indycar_tracked_driver": "",
        "indycar_champion_enabled": True,
        "indycar_champion_override": "",
        "indycar_champion_flash_seconds": 60,
        "indycar_test_mode": False,
        "indycar_test_qualifying": False,
        "debug_scene": "auto",
        "clock_24hr": True,
        "date_format": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _use_config(monkeypatch, **overrides):
    cfg = _config(**overrides)
    monkeypatch.setattr(Config, "instance", classmethod(lambda cls: cfg))
    return cfg


def _use_snapshot(monkeypatch, snapshot):
    monkeypatch.setattr(
        "scenes.indycar.base.current_snapshot", lambda scene_name="": snapshot
    )
    return snapshot


def _scene(cls, monkeypatch, snapshot, **config):
    _use_config(monkeypatch, **config)
    _use_snapshot(monkeypatch, snapshot)
    panel = MagicMock()
    return cls(object(), panel, monitor=MagicMock()), panel


def _texts(panel):
    return [call.args[5] for call in panel.draw_text.call_args_list]


class TestTop3Scene:
    def test_has_data_for_a_live_session(self, monkeypatch):
        scene, _panel = _scene(Top3Scene, monkeypatch, demo_race_snapshot())

        assert scene.has_data() is True

    def test_draws_positions_names_gaps_and_teams(self, monkeypatch):
        snapshot = demo_race_snapshot()
        scene, panel = _scene(Top3Scene, monkeypatch, snapshot)

        scene.draw_content(snapshot)
        texts = _texts(panel)

        assert "RACE" in texts
        assert "Alex Palou" in texts
        assert "Tymek Kucharczyk" in texts
        assert "Max Taylor" in texts
        assert "+1.842" in texts  # gap between P1 and P2
        assert "Chip Ganassi Racing" in texts
        # The team placeholders are drawn when no PNG is installed.
        assert panel.draw_square.called or panel.draw_image.called


class TestDriverScene:
    def test_requires_a_configured_driver(self, monkeypatch):
        scene, _panel = _scene(DriverScene, monkeypatch, demo_race_snapshot())

        assert scene.has_data() is False

    def test_race_layout_shows_gaps_and_lap(self, monkeypatch):
        snapshot = demo_race_snapshot()
        scene, panel = _scene(
            DriverScene,
            monkeypatch,
            snapshot,
            indycar_tracked_driver="Palou",
        )

        assert scene.has_data() is True
        scene.draw_content(snapshot)
        texts = _texts(panel)

        assert "Alex Palou" in texts
        assert "POS" in texts
        assert "AHEAD" in texts
        assert "LEAD" in texts
        assert "LAP" in texts
        assert "TIME" not in texts
        assert "45/100" in texts

    def test_qualifying_layout_swaps_race_fields(self, monkeypatch):
        snapshot = demo_qualifying_snapshot()
        scene, panel = _scene(
            DriverScene,
            monkeypatch,
            snapshot,
            indycar_tracked_driver="Palou",
        )

        scene.draw_content(snapshot)
        texts = _texts(panel)

        assert "POS" in texts
        assert "TIME" in texts
        assert "GAP" in texts
        assert "SPD" in texts
        assert "AHEAD" not in texts
        assert "1:14.175" in texts
        assert "+0.184" in texts

    def test_test_mode_previews_without_a_saved_driver(self, monkeypatch):
        _use_config(
            monkeypatch,
            indycar_test_mode=True,
            debug_scene="indy_driver",
        )
        _use_snapshot(monkeypatch, demo_race_snapshot())
        scene = DriverScene(object(), MagicMock(), monitor=MagicMock())

        assert scene._selector() == "Palou"
        assert scene.has_data() is True

    def test_debug_preview_works_without_test_mode(self, monkeypatch):
        _use_config(
            monkeypatch,
            indycar_test_mode=False,
            debug_scene="indy_driver",
        )
        _use_snapshot(monkeypatch, demo_race_snapshot())
        scene = DriverScene(object(), MagicMock(), monitor=MagicMock())

        assert scene._selector() == "Palou"
        assert scene.has_data() is True

    def test_preview_falls_back_when_saved_driver_is_not_in_demo(self, monkeypatch):
        scene, panel = _scene(
            DriverScene,
            monkeypatch,
            demo_race_snapshot(),
            indycar_tracked_driver="Newgarden",
            indycar_test_mode=False,
            debug_scene="indy_driver",
        )

        assert scene.has_data() is True
        scene.draw_content(demo_race_snapshot())

        assert "Alex Palou" in _texts(panel)


class TestDebugPreviewSnapshots:
    """The debug selector previews offline without needing test mode."""

    def test_forced_live_scene_uses_demo_without_test_mode(self, monkeypatch):
        from scenes.indycar import base

        _use_config(monkeypatch, indycar_test_mode=False, debug_scene="indy_top3")
        snapshot = base.current_snapshot("indy_top3")

        assert snapshot.is_live is True
        assert snapshot.session.drivers[0].name == "Alex Palou"

    def test_unforced_scene_without_test_mode_uses_the_monitor(self, monkeypatch):
        from scenes.indycar import base

        _use_config(monkeypatch, indycar_test_mode=False, debug_scene="auto")
        sentinel = Snapshot(error="live")
        monkeypatch.setattr(
            base.IndyCarMonitor,
            "instance",
            classmethod(lambda cls: SimpleNamespace(snapshot=lambda: sentinel)),
        )

        assert base.current_snapshot("indy_top3") is sentinel

    def test_forced_driver_uses_qualifying_demo_when_selected(self, monkeypatch):
        from scenes.indycar import base

        _use_config(
            monkeypatch,
            indycar_test_mode=False,
            debug_scene="indy_driver",
            indycar_test_qualifying=True,
        )

        assert base.current_snapshot("indy_driver").session.is_qualifying is True

    def test_test_mode_makes_the_next_event_use_demo(self, monkeypatch):
        from scenes.indycar import base

        _use_config(monkeypatch, indycar_test_mode=True, debug_scene="auto")

        assert base.current_snapshot("indy_next").next_event is not None


class TestChampionScene:
    def test_has_no_data_during_a_live_session(self, monkeypatch):
        scene, _panel = _scene(ChampionScene, monkeypatch, demo_race_snapshot())

        assert scene.has_data() is False

    def test_flashes_the_clinched_champion(self, monkeypatch):
        snapshot = demo_champion_snapshot()
        scene, panel = _scene(ChampionScene, monkeypatch, snapshot)

        assert scene.has_data() is True
        scene.on_enter()
        scene.draw_content(snapshot)
        texts = _texts(panel)

        assert "DRIVERS CHAMPION" in texts
        assert "Alex Palou" in texts
        assert "Chip Ganassi Racing" in texts

    def test_honours_the_manual_override(self, monkeypatch):
        snapshot = demo_champion_snapshot()
        scene, panel = _scene(
            ChampionScene,
            monkeypatch,
            snapshot,
            indycar_champion_override="Tymek Kucharczyk",
        )

        assert scene.has_data() is True
        scene.draw_content(snapshot)
        assert "Tymek Kucharczyk" in _texts(panel)

    def test_disabled_scene_has_no_data(self, monkeypatch):
        scene, _panel = _scene(
            ChampionScene,
            monkeypatch,
            demo_champion_snapshot(),
            indycar_champion_enabled=False,
        )

        assert scene.has_data() is False

    def test_stops_after_the_flash_window(self, monkeypatch):
        scene, _panel = _scene(ChampionScene, monkeypatch, demo_champion_snapshot())

        assert scene.has_data() is True
        scene.started_at = 0.0  # far in the past

        assert scene.has_data() is False


class TestNextEventIdleTheme:
    def _theme(self, monkeypatch, snapshot):
        from scenes.idle.themes import theme_utilities

        monkeypatch.setattr(
            theme_utilities.WeatherService,
            "instance",
            classmethod(lambda cls: MagicMock()),
        )
        monkeypatch.setattr(
            indycar_next_theme, "current_snapshot", lambda scene_name="": snapshot
        )
        _use_config(monkeypatch)
        panel = MagicMock()
        theme = indycar_next_theme.IndyCarNextTheme(object(), panel)
        return theme, panel

    def test_draws_event_track_session_date_time_and_countdown(self, monkeypatch):
        theme, panel = self._theme(monkeypatch, demo_race_snapshot())

        theme.draw_content(1)
        texts = _texts(panel)

        assert "NEXT RACE" in texts
        assert "IN 120 DAYS" in texts
        assert any(text.startswith("Firestone Grand Prix") for text in texts)
        assert any("Streets of St." in text for text in texts)
        assert "Race" in texts
        assert "12:30" in texts
        assert "Fox" in texts

    def test_empty_state_before_a_schedule_is_published(self, monkeypatch):
        theme, panel = self._theme(monkeypatch, Snapshot())

        theme.draw_content(1)
        texts = _texts(panel)

        assert "INDYCAR" in texts
        assert "No upcoming race" in texts
