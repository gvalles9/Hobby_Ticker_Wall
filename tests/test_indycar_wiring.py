"""Display wiring tests for the INDYCAR debug scene selector.

Selecting one of the INDYCAR debug scenes must register and force that
scene even when the INDYCAR test mode is off; the scene layer supplies
the bundled demo snapshot for the preview.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import display
from setup.configuration import Config
from utilities.indycar.models import Snapshot


def _build_display(monkeypatch, **overrides):
    cfg = MagicMock()
    cfg.colour_theme = 0
    cfg.loading_indicator = "none"
    cfg.satellite_tracking_enabled = False
    cfg.display_scan_rate = 16
    cfg.screen_rotate = False
    cfg.hat_pwm_enabled = False
    cfg.gpio_slowdown = 1
    cfg.panel_colour_order = "RGB"
    cfg.bonnet_type = "single"
    cfg.display_speed_factor = 1.0
    cfg.brightness_percent = 60
    cfg.indycar_enabled = False
    cfg.indycar_test_mode = False
    cfg.indycar_tracked_driver = ""
    cfg.indycar_test_qualifying = False
    cfg.indycar_champion_enabled = True
    cfg.indycar_champion_override = ""
    cfg.indycar_champion_flash_seconds = 60
    cfg.idle_screen_theme = "classic"
    cfg.idle_cycle_include_indycar = False
    for key, value in overrides.items():
        setattr(cfg, key, value)

    panel = MagicMock()
    panel.create_canvas.return_value = MagicMock(name="canvas")
    monitor = MagicMock()
    monitor.snapshot.return_value = Snapshot()

    monkeypatch.setattr(Config, "instance", classmethod(lambda cls: cfg))
    monkeypatch.setattr("display.panel_factory.get_panel", lambda: panel)
    monkeypatch.setattr("display.get_overhead_instance", lambda: MagicMock())
    monkeypatch.setattr(
        "scenes.idle.idle_scene.IdleScene",
        lambda canvas, panel: MagicMock(priority=0, debug_name="idle"),
    )
    monkeypatch.setattr(
        "scenes.flight.flight_scene.FlightScene",
        lambda *args, **kwargs: MagicMock(priority=1, debug_name="flight"),
    )
    monkeypatch.setattr(
        "scenes.image.image_scene.ImageScene",
        lambda canvas, panel: MagicMock(priority=10, debug_name="image"),
    )
    monkeypatch.setattr(
        "utilities.indycar.monitor.IndyCarMonitor.instance",
        classmethod(lambda cls: monitor),
    )

    return display.build_display_class()(), monitor, cfg


def _scene_names(disp):
    return [getattr(scene, "debug_name", None) for scene in disp.scene_manager.scenes]


def test_forced_top3_registers_and_renders_without_test_mode(monkeypatch):
    disp, _monitor, _cfg = _build_display(
        monkeypatch, debug_scene="indy_top3", indycar_test_mode=False
    )

    assert "indy_top3" in _scene_names(disp)
    disp.scene_manager.kick("indy_top3")

    assert type(disp.scene_manager.current_scene).__name__ == "Top3Scene"


def test_forced_driver_previews_without_a_saved_driver(monkeypatch):
    disp, _monitor, _cfg = _build_display(
        monkeypatch, debug_scene="indy_driver", indycar_test_mode=False
    )

    assert "indy_driver" in _scene_names(disp)
    disp.scene_manager.kick("indy_driver")

    assert type(disp.scene_manager.current_scene).__name__ == "DriverScene"


def test_forced_champion_previews_without_test_mode(monkeypatch):
    disp, _monitor, _cfg = _build_display(
        monkeypatch, debug_scene="indy_champion", indycar_test_mode=False
    )

    assert "indy_champion" in _scene_names(disp)
    disp.scene_manager.kick("indy_champion")

    assert type(disp.scene_manager.current_scene).__name__ == "ChampionScene"


def test_indycar_scenes_stay_unregistered_when_disabled(monkeypatch):
    disp, _monitor, _cfg = _build_display(monkeypatch, debug_scene="auto")

    assert "indy_top3" not in _scene_names(disp)
    assert "indy_driver" not in _scene_names(disp)
    assert "indy_champion" not in _scene_names(disp)


def test_idle_theme_list_including_indycar_starts_the_monitor(monkeypatch):
    _disp, monitor, _cfg = _build_display(
        monkeypatch,
        idle_screen_theme="classic",
        idle_screen_themes=["classic", "indycar_next"],
        debug_scene="auto",
    )

    monitor.start.assert_called_once()


def test_test_mode_does_not_start_the_live_monitor(monkeypatch):
    _disp, monitor, _cfg = _build_display(
        monkeypatch,
        indycar_enabled=True,
        indycar_test_mode=True,
        debug_scene="auto",
    )

    monitor.start.assert_not_called()


def test_live_mode_starts_the_monitor(monkeypatch):
    _disp, monitor, _cfg = _build_display(
        monkeypatch,
        indycar_enabled=True,
        debug_scene="auto",
    )

    monitor.start.assert_called_once()
