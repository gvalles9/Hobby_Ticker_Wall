from unittest.mock import MagicMock

from scenes.idle import idle_scene
from setup.configuration import Config
from utilities import birthday as birthday_utils


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


def test_idle_scene_factory_appends_birthday_when_scheduled(monkeypatch):
    from scenes.idle.themes import (
        birthday_idle_theme,
        classic_idle_theme,
        forecast_idle_theme,
    )

    classic = MagicMock()
    forecast = MagicMock()
    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_theme="cycle",
            idle_cycle_include_indycar=False,
            birthday_enabled=True,
            birthday_date="12-25",
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: True)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        forecast_idle_theme,
        "ForecastIdleTheme",
        lambda canvas, panel, duration_override: forecast,
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, forecast, birthday)


def test_idle_scene_factory_wraps_a_single_theme_with_birthday(monkeypatch):
    from scenes.idle.themes import birthday_idle_theme, classic_idle_theme

    classic = MagicMock()
    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_theme="classic",
            birthday_enabled=True,
            birthday_date="12-25",
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: True)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert isinstance(scene, idle_scene.CyclingIdleScene)
    assert scene.scenes == (classic, birthday)


def test_idle_scene_factory_skips_birthday_off_date(monkeypatch):
    from scenes.idle.themes import classic_idle_theme

    classic = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_theme="classic",
            birthday_enabled=True,
            birthday_date="12-25",
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: False)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene is classic


def test_idle_scene_factory_selects_birthday_directly(monkeypatch):
    from scenes.idle.themes import birthday_idle_theme

    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(idle_screen_theme="birthday", birthday_enabled=False),
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene is birthday


def test_idle_scene_factory_forces_birthday_from_debug_scene(monkeypatch):
    from scenes.idle.themes import birthday_idle_theme

    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_theme="classic",
            debug_scene="birthday",
            birthday_enabled=False,
        ),
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene is birthday


def test_idle_scene_factory_appends_indycar_only_when_opted_in(monkeypatch):
    from scenes.idle.themes import (
        classic_idle_theme,
        forecast_idle_theme,
        indycar_next_theme,
    )

    classic = MagicMock()
    forecast = MagicMock()
    indycar = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_theme="cycle",
            idle_cycle_include_indycar=True,
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        forecast_idle_theme,
        "ForecastIdleTheme",
        lambda canvas, panel, duration_override: forecast,
    )
    monkeypatch.setattr(
        indycar_next_theme, "IndyCarNextTheme", lambda canvas, panel: indycar
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, forecast, indycar)


def test_idle_scene_factory_builds_every_selected_theme(monkeypatch):
    from scenes.idle.themes import classic_idle_theme, conditions_idle_theme

    classic = MagicMock()
    conditions = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "conditions"],
            birthday_enabled=False,
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        conditions_idle_theme,
        "ConditionsIdleTheme",
        lambda canvas, panel: conditions,
    )

    scene = idle_scene.IdleScene(object(), object())

    assert isinstance(scene, idle_scene.CyclingIdleScene)
    assert scene.scenes == (classic, conditions)


def test_idle_scene_factory_uses_three_day_forecast_in_a_rotation(monkeypatch):
    from scenes.idle.themes import classic_idle_theme, forecast_idle_theme

    classic = MagicMock()
    forecast = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "forecast"],
            birthday_enabled=False,
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )

    def make_forecast(canvas, panel, duration_override):
        assert duration_override == "3day"
        return forecast

    monkeypatch.setattr(forecast_idle_theme, "ForecastIdleTheme", make_forecast)

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, forecast)


def test_idle_scene_factory_honours_forecast_duration_when_alone(monkeypatch):
    from scenes.idle.themes import forecast_idle_theme

    forecast = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(idle_screen_themes=["forecast"], birthday_enabled=False),
    )
    monkeypatch.setattr(
        forecast_idle_theme,
        "ForecastIdleTheme",
        lambda canvas, panel: forecast,
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene is forecast


def test_idle_scene_factory_does_not_duplicate_an_explicit_birthday(monkeypatch):
    from scenes.idle.themes import birthday_idle_theme, classic_idle_theme

    classic = MagicMock()
    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "birthday"],
            birthday_enabled=True,
            birthday_date="12-25",
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: True)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, birthday)


def test_idle_scene_factory_appends_birthday_to_a_multi_theme_selection(monkeypatch):
    from scenes.idle.themes import (
        birthday_idle_theme,
        classic_idle_theme,
        conditions_idle_theme,
    )

    classic = MagicMock()
    conditions = MagicMock()
    birthday = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "conditions"],
            birthday_enabled=True,
            birthday_date="12-25",
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: True)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        conditions_idle_theme,
        "ConditionsIdleTheme",
        lambda canvas, panel: conditions,
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, conditions, birthday)


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
