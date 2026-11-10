"""Blinker placement for the multi-select idle rotation."""

from __future__ import annotations

from scenes import loadingpulse
from setup import screen
from setup.configuration import Config


def _config(**values):
    cfg = Config.__new__(Config)
    cfg.data_store = dict(values)
    return cfg


def _position(monkeypatch, **values):
    monkeypatch.setattr(Config, "instance", lambda: _config(**values))
    return loadingpulse._blinker_position()


def test_forecast_only_uses_the_bottom_right_pixel(monkeypatch):
    assert _position(monkeypatch, idle_screen_themes=["forecast"]) == (
        screen.WIDTH - 1,
        screen.HEIGHT - 1,
    )


def test_classic_only_uses_the_default_pixel(monkeypatch):
    assert _position(monkeypatch, idle_screen_themes=["classic"]) == (
        loadingpulse.DEFAULT_BLINKER_POSITION
    )


def test_mixed_rotation_uses_the_default_pixel(monkeypatch):
    assert (
        _position(monkeypatch, idle_screen_themes=["classic", "forecast"])
        == loadingpulse.DEFAULT_BLINKER_POSITION
    )


def test_legacy_cycle_migration_uses_the_default_pixel(monkeypatch):
    assert _position(monkeypatch, idle_screen_theme="cycle") == (
        loadingpulse.DEFAULT_BLINKER_POSITION
    )
