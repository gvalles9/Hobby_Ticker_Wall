from unittest.mock import MagicMock

from scenes.idle import idle_scene
from setup.configuration import Config


def test_idle_scene_factory_builds_classic_and_three_day_forecast(monkeypatch):
    from scenes.idle.themes import classic_idle_theme, forecast_idle_theme

    classic = MagicMock()
    forecast = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(idle_screen_theme="cycle"),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )

    def make_forecast(canvas, panel, duration_override):
        assert duration_override == "3day"
        return forecast

    monkeypatch.setattr(forecast_idle_theme, "ForecastIdleTheme", make_forecast)

    scene = idle_scene.IdleScene(object(), object())

    assert isinstance(scene, idle_scene.CyclingIdleScene)
    assert scene.scenes == (classic, forecast)


def test_idle_theme_cycle_switches_every_configured_interval(monkeypatch):
    monkeypatch.setattr(idle_scene, "IDLE_THEME_CYCLE_SECONDS", 1)
    monkeypatch.setattr(idle_scene.frames, "PER_SECOND", 2)

    classic = MagicMock()
    forecast = MagicMock()
    scene = idle_scene.CyclingIdleScene(classic, forecast)
    scene.on_enter()

    scene.draw()
    assert scene.current_scene is classic
    scene.draw()
    assert scene.current_scene is forecast
    forecast.on_enter.assert_called_once()

    scene.draw()
    assert scene.current_scene is forecast
    scene.draw()
    assert scene.current_scene is classic
    assert classic.on_enter.call_count == 2
