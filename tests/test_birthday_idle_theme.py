"""Offline tests for the Happy Birthday idle theme, date matching, and config."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from scenes.idle.themes import birthday_idle_theme, theme_utilities
from scenes.idle.themes.birthday_idle_theme import BirthdayIdleTheme
from setup.colours import HOT_PINK
from setup.configuration import (
    DEFAULT_BIRTHDAY_DATE,
    DEFAULT_BIRTHDAY_ENABLED,
    DEFAULTS,
    Config,
)
from utilities.birthday import is_birthday, parse_birthday_date


def _config(**values):
    cfg = Config.__new__(Config)
    cfg.data_store = dict(values)
    return cfg


def _theme(monkeypatch):
    monkeypatch.setattr(
        theme_utilities.WeatherService,
        "instance",
        classmethod(lambda cls: MagicMock()),
    )
    monkeypatch.setattr(
        birthday_idle_theme, "font_text_width", lambda font, text: len(text) * 7
    )
    panel = MagicMock()
    return BirthdayIdleTheme(object(), panel), panel


def _texts(panel):
    return [call.args[5] for call in panel.draw_text.call_args_list]


class TestBirthdayDate:
    def test_accepts_iso_month_day_and_slash_formats(self):
        assert parse_birthday_date("2026-12-25") == (12, 25)
        assert parse_birthday_date("12-25") == (12, 25)
        assert parse_birthday_date("12/25") == (12, 25)
        assert parse_birthday_date("2026/12/25") == (12, 25)

    def test_rejects_empty_and_invalid_values(self):
        assert parse_birthday_date("") is None
        assert parse_birthday_date(None) is None
        assert parse_birthday_date("not-a-date") is None
        assert parse_birthday_date("2026-02-30") is None

    def test_matches_month_and_day_ignoring_the_year(self):
        assert is_birthday("2020-12-25", datetime.date(2026, 12, 25)) is True
        assert is_birthday("12-25", datetime.date(2026, 12, 25)) is True
        assert is_birthday("2026-12-25", datetime.date(2026, 12, 26)) is False
        assert is_birthday("", datetime.date(2026, 12, 25)) is False


class TestBirthdayTheme:
    def test_always_has_data(self, monkeypatch):
        theme, _panel = _theme(monkeypatch)

        assert theme.has_data() is True

    def test_draws_greeting_confetti_hat_and_cake(self, monkeypatch):
        theme, panel = _theme(monkeypatch)

        theme.draw_content(1)

        texts = _texts(panel)
        assert "Happy" in texts
        assert " Birthday" in texts
        assert panel.draw_line.called  # cone hat stripes / brim
        assert panel.draw_square.called
        assert panel.set_pixel.called  # confetti and candle flame
        assert any(
            call.args[5] == HOT_PINK for call in panel.draw_square.call_args_list
        )

    def test_confetti_animates_between_ticks(self, monkeypatch):
        theme, panel = _theme(monkeypatch)

        theme.draw_content(1)
        first = [call.args[1:3] for call in panel.set_pixel.call_args_list]
        panel.set_pixel.reset_mock()

        theme.draw_content(2)
        second = [call.args[1:3] for call in panel.set_pixel.call_args_list]

        assert first and second
        assert first != second


class TestBirthdayConfig:
    def test_defaults_are_off(self):
        assert DEFAULT_BIRTHDAY_ENABLED is False
        assert DEFAULT_BIRTHDAY_DATE == ""
        assert DEFAULTS["birthday_enabled"] is False
        assert DEFAULTS["birthday_date"] == ""

    def test_properties_read_the_data_store(self):
        cfg = _config(birthday_enabled=True, birthday_date=" 12-25 ")

        assert cfg.birthday_enabled is True
        assert cfg.birthday_date == "12-25"

    def test_a_saved_date_enables_the_scene_by_default(self):
        assert _config(birthday_date="2026-12-25").birthday_enabled is True
        assert _config(birthday_date="12-25").birthday_enabled is True

    def test_empty_or_invalid_dates_disable_the_scene(self):
        assert (
            _config(birthday_enabled=True, birthday_date="").birthday_enabled is False
        )
        assert (
            _config(birthday_enabled=True, birthday_date="not-a-date").birthday_enabled
            is False
        )

    def test_clearing_the_date_disables_a_previously_enabled_scene(self):
        cfg = _config(birthday_enabled=True, birthday_date="12-25")

        assert cfg.birthday_enabled is True

        cfg.data_store["birthday_date"] = ""
        assert cfg.birthday_enabled is False

    def test_idle_theme_allows_birthday(self):
        assert _config(idle_screen_theme="birthday").idle_screen_theme == "birthday"

    def test_debug_scene_allows_birthday(self):
        assert _config(debug_scene="birthday").debug_scene == "birthday"
