import datetime
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


def test_idle_scene_factory_puts_scheduled_birthday_first(monkeypatch):
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

    assert scene.scenes == (birthday, classic, forecast)


def test_idle_scene_factory_puts_scheduled_birthday_first_in_pair(monkeypatch):
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
    assert scene.scenes == (birthday, classic)


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


def test_idle_scene_factory_puts_scheduled_birthday_first_in_multi_theme(monkeypatch):
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

    assert scene.scenes == (birthday, classic, conditions)


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


def _mmdd(day: datetime.date) -> str:
    return f"{day.month:02d}-{day.day:02d}"


def test_idle_scene_factory_puts_scheduled_custom_scene_first(monkeypatch):
    from scenes.idle.themes import classic_idle_theme, custom_text_idle_theme

    classic = MagicMock()
    custom = MagicMock()
    today = datetime.date.today()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic"],
            birthday_enabled=False,
            custom_scene_1_text="Happy Anniversary",
            custom_scene_1_date=_mmdd(today),
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        custom_text_idle_theme,
        "CustomTextIdleTheme",
        lambda canvas, panel, slot=1: custom,
    )

    scene = idle_scene.IdleScene(object(), object())

    assert isinstance(scene, idle_scene.CyclingIdleScene)
    assert scene.scenes == (custom, classic)


def test_idle_scene_factory_puts_all_scheduled_dated_scenes_first(monkeypatch):
    from scenes.idle.themes import (
        birthday_idle_theme,
        classic_idle_theme,
        custom_text_idle_theme,
    )

    classic = MagicMock()
    birthday = MagicMock()
    custom_by_slot = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    dated_date = _mmdd(datetime.date.today())
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic"],
            birthday_enabled=True,
            birthday_date=dated_date,
            custom_scene_1_text="First",
            custom_scene_1_date=dated_date,
            custom_scene_2_text="Second",
            custom_scene_2_date=dated_date,
            custom_scene_3_text="Third",
            custom_scene_3_date=dated_date,
        ),
    )
    monkeypatch.setattr(birthday_utils, "is_birthday", lambda value: True)
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        birthday_idle_theme, "BirthdayIdleTheme", lambda canvas, panel: birthday
    )
    monkeypatch.setattr(
        custom_text_idle_theme,
        "CustomTextIdleTheme",
        lambda canvas, panel, slot=1: custom_by_slot[slot],
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (
        birthday,
        custom_by_slot[1],
        custom_by_slot[2],
        custom_by_slot[3],
        classic,
    )


def test_idle_scene_factory_drops_an_empty_custom_slot(monkeypatch):
    from scenes.idle.themes import classic_idle_theme

    classic = MagicMock()
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "custom_1"],
            birthday_enabled=False,
            custom_scene_1_text="",
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene is classic


def test_idle_scene_factory_previews_a_selected_custom_scene_off_date(monkeypatch):
    from scenes.idle.themes import classic_idle_theme, custom_text_idle_theme

    classic = MagicMock()
    custom = MagicMock()
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            idle_screen_themes=["classic", "custom_1"],
            birthday_enabled=False,
            custom_scene_1_text="Preview only",
            custom_scene_1_date=_mmdd(tomorrow),
        ),
    )
    monkeypatch.setattr(
        classic_idle_theme, "ClassicIdleTheme", lambda canvas, panel: classic
    )
    monkeypatch.setattr(
        custom_text_idle_theme,
        "CustomTextIdleTheme",
        lambda canvas, panel, slot=1: custom,
    )

    scene = idle_scene.IdleScene(object(), object())

    assert scene.scenes == (classic, custom)


def test_idle_scene_factory_debug_previews_an_empty_custom_slot(monkeypatch):
    from scenes.idle.themes import custom_text_idle_theme

    sentinel = MagicMock()
    captured = {}

    def make_custom(canvas, panel, slot=1, preview_text=None):
        captured["slot"] = slot
        captured["preview_text"] = preview_text
        return sentinel

    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(debug_scene="custom_2", idle_screen_theme="classic"),
    )
    monkeypatch.setattr(custom_text_idle_theme, "CustomTextIdleTheme", make_custom)

    scene = idle_scene.IdleScene(object(), object())

    assert scene is sentinel
    assert captured == {"slot": 2, "preview_text": "Custom message 2"}


def test_idle_scene_factory_debug_previews_saved_custom_text(monkeypatch):
    from scenes.idle.themes import custom_text_idle_theme

    sentinel = MagicMock()
    captured = {}

    def make_custom(canvas, panel, slot=1, preview_text=None):
        captured["slot"] = slot
        captured["preview_text"] = preview_text
        return sentinel

    monkeypatch.setattr(
        Config,
        "instance",
        lambda: MagicMock(
            debug_scene="custom_3",
            idle_screen_theme="classic",
            custom_scene_3_text="Happy Birthday",
        ),
    )
    monkeypatch.setattr(custom_text_idle_theme, "CustomTextIdleTheme", make_custom)

    scene = idle_scene.IdleScene(object(), object())

    assert scene is sentinel
    assert captured == {"slot": 3, "preview_text": None}
