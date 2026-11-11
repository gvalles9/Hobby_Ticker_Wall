"""Tests for date-triggered custom text scenes.

Covers the shared recurring-date helpers, the slot config readers and text
sanitiser, the scrolling theme, and the config whitelists.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scenes.idle.themes import custom_text_idle_theme, theme_utilities
from scenes.idle.themes.custom_text_idle_theme import CustomTextIdleTheme
from setup.colours import HOT_PINK, WHITE
from setup.configuration import (
    ALL_IDLE_THEMES,
    CUSTOM_IDLE_THEMES,
    DEFAULTS,
    Config,
)
from utilities.custom_scene import (
    CUSTOM_SCENE_TEXT_MAX,
    cfg_colour,
    cfg_date,
    cfg_text,
    colour_for,
    sanitise_text,
    scene_keys,
    scene_name,
    scheduled_scene_names,
    slot_from_name,
)
from utilities.recurring_date import is_recurring_date, parse_recurring_date


def _config(**values):
    cfg = Config.__new__(Config)
    cfg.data_store = dict(values)
    return cfg


class TestRecurringDate:
    def test_accepts_the_supported_formats(self):
        assert parse_recurring_date("2026-12-25") == (12, 25)
        assert parse_recurring_date("12-25") == (12, 25)
        assert parse_recurring_date("12/25") == (12, 25)
        assert parse_recurring_date("2026/12/25") == (12, 25)

    def test_rejects_empty_and_invalid_values(self):
        assert parse_recurring_date("") is None
        assert parse_recurring_date(None) is None
        assert parse_recurring_date("not-a-date") is None
        assert parse_recurring_date("2026-02-30") is None

    def test_matches_month_and_day_ignoring_the_year(self):
        today = datetime.date(2026, 12, 25)
        assert is_recurring_date("2020-12-25", today) is True
        assert is_recurring_date("12-25", today) is True
        assert is_recurring_date("2026-12-26", today) is False
        assert is_recurring_date("", today) is False


class TestSlotHelpers:
    def test_scene_names_round_trip(self):
        for slot in (1, 2, 3):
            assert scene_name(slot) == f"custom_{slot}"
            assert slot_from_name(scene_name(slot)) == slot

    def test_slot_from_name_defaults_to_one_for_unknown_names(self):
        assert slot_from_name("custom_9") == 1
        assert slot_from_name("nonsense") == 1

    def test_scene_keys_are_per_slot(self):
        assert scene_keys(2) == (
            "custom_scene_2_text",
            "custom_scene_2_date",
            "custom_scene_2_colour",
        )

    def test_config_readers_accept_plain_objects(self):
        cfg = SimpleNamespace(
            custom_scene_1_text="  Hello  ",
            custom_scene_1_date=" 12-25 ",
            custom_scene_1_colour="GOLD",
        )
        assert cfg_text(cfg, 1) == "Hello"
        assert cfg_date(cfg, 1) == "12-25"
        assert cfg_colour(cfg, 1) == "gold"

    def test_config_readers_read_the_real_config_data_store(self):
        cfg = _config(
            custom_scene_1_text="  Happy  ",
            custom_scene_1_date=" 12-25 ",
            custom_scene_1_colour="GOLD",
        )
        assert cfg_text(cfg, 1) == "Happy"
        assert cfg_date(cfg, 1) == "12-25"
        assert cfg_colour(cfg, 1) == "gold"

    def test_config_readers_are_magicmock_safe(self):
        cfg = MagicMock()
        assert cfg_text(cfg, 1) == ""
        assert cfg_date(cfg, 1) == ""
        assert cfg_colour(cfg, 1) == "white"

    def test_unknown_colour_falls_back_to_white(self):
        cfg = SimpleNamespace(custom_scene_2_colour="chartreuse")
        assert cfg_colour(cfg, 2) == "white"
        assert colour_for("chartreuse") == WHITE
        assert colour_for("hot_pink") == HOT_PINK


class TestSanitiseText:
    def test_collapses_whitespace_and_strips(self):
        assert sanitise_text("  Happy   Anniversary \n ") == "Happy Anniversary"

    def test_drops_control_and_non_latin1_characters(self):
        assert sanitise_text("Hi\x00 \u2603 there") == "Hi there"

    def test_caps_at_the_character_limit(self):
        result = sanitise_text("A" * 60)
        assert len(result) == CUSTOM_SCENE_TEXT_MAX
        assert result == "A" * CUSTOM_SCENE_TEXT_MAX

    def test_empty_values_become_empty_strings(self):
        assert sanitise_text("") == ""
        assert sanitise_text(None) == ""


class TestScheduledScenes:
    def test_schedules_only_slots_with_text_matching_today(self):
        today = datetime.date(2026, 11, 11)
        cfg = SimpleNamespace(
            custom_scene_1_text="Happy Anniversary",
            custom_scene_1_date="11-11",
            custom_scene_2_text="Daisy",
            custom_scene_2_date="12-25",
            custom_scene_3_text="",
            custom_scene_3_date="11-11",
        )

        assert scheduled_scene_names(cfg, today) == ["custom_1"]

    def test_two_matching_slots_keep_slot_order(self):
        today = datetime.date(2026, 11, 11)
        cfg = SimpleNamespace(
            custom_scene_1_text="One",
            custom_scene_1_date="11-11",
            custom_scene_2_text="Two",
            custom_scene_2_date="11-11",
        )

        assert scheduled_scene_names(cfg, today) == ["custom_1", "custom_2"]

    def test_text_without_a_date_is_never_scheduled(self):
        cfg = SimpleNamespace(custom_scene_1_text="Preview only")
        assert scheduled_scene_names(cfg, datetime.date(2026, 11, 11)) == []


def _theme(monkeypatch, *, text="", colour="white", preview_text=None, width=100):
    """Build a custom theme with the scroller and width calculation mocked."""
    monkeypatch.setattr(
        theme_utilities.WeatherService,
        "instance",
        classmethod(lambda cls: MagicMock()),
    )
    cfg = SimpleNamespace(
        custom_scene_1_text=text,
        custom_scene_1_colour=colour,
    )
    monkeypatch.setattr(custom_text_idle_theme.Config, "instance", lambda: cfg)

    scroller = MagicMock()
    captured = {}

    def make_scroller(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return scroller

    monkeypatch.setattr(custom_text_idle_theme, "Scroller", make_scroller)
    monkeypatch.setattr(custom_text_idle_theme, "spans_width", lambda spans: width)

    theme = CustomTextIdleTheme(
        object(), MagicMock(), slot=1, preview_text=preview_text
    )
    return theme, scroller, captured


class TestCustomTextIdleTheme:
    def test_short_messages_slide_right_in_reading_order(self, monkeypatch):
        theme, _scroller, captured = _theme(
            monkeypatch, text="Happy Anniversary", colour="hot_pink"
        )

        theme.draw()

        assert captured["kwargs"]["slide"] is True
        assert captured["kwargs"]["bounce"] is False
        span = captured["args"][5][0]
        assert span.text == "Happy Anniversary"
        assert span.colour == HOT_PINK

    def test_wide_messages_use_bounce_mode(self, monkeypatch):
        theme, _scroller, captured = _theme(
            monkeypatch, text="A" * CUSTOM_SCENE_TEXT_MAX, width=400
        )

        theme.draw()

        assert captured["kwargs"]["slide"] is False
        assert captured["kwargs"]["bounce"] is True

    def test_empty_slots_draw_nothing(self, monkeypatch):
        theme, scroller, captured = _theme(monkeypatch, text="")

        theme.draw()

        assert captured == {}
        assert theme.scroller is None
        scroller.draw.assert_not_called()

    def test_debug_preview_uses_the_placeholder_text(self, monkeypatch):
        theme, _scroller, captured = _theme(
            monkeypatch, text="", preview_text="Custom message 1"
        )

        theme.draw()

        span = captured["args"][5][0]
        assert span.text == "Custom message 1"

    def test_draw_ticks_the_scroller_every_frame(self, monkeypatch):
        theme, scroller, _captured = _theme(monkeypatch, text="Hello")

        theme.draw()
        theme.draw()

        assert scroller.draw.call_count == 2
        assert theme.frame == 2

    def test_reset_rebuilds_the_scroller(self, monkeypatch):
        theme, _scroller, captured = _theme(monkeypatch, text="Hello")
        theme.draw()
        assert captured

        theme.reset()
        assert theme.scroller is None

        theme.draw()
        assert theme.scroller is not None


class TestCustomSceneConfig:
    def test_defaults_are_blank_and_off(self):
        for slot in (1, 2, 3):
            text_key, date_key, colour_key = scene_keys(slot)
            assert DEFAULTS[text_key] == ""
            assert DEFAULTS[date_key] == ""
            assert DEFAULTS[colour_key] == "white"

    def test_custom_themes_are_registered_but_not_in_the_wizard_list(self):
        from setup.configuration import IDLE_SCREEN_THEMES

        assert CUSTOM_IDLE_THEMES == ("custom_1", "custom_2", "custom_3")
        assert "custom_1" in ALL_IDLE_THEMES
        assert "custom_1" not in IDLE_SCREEN_THEMES

    def test_custom_themes_are_valid_saved_selections(self):
        cfg = _config(idle_screen_theme="custom_2")
        assert cfg.idle_screen_theme == "custom_2"
        assert _config(idle_screen_themes=["custom_1"]).idle_screen_themes == [
            "custom_1"
        ]

    def test_custom_scenes_are_valid_debug_targets(self):
        assert _config(debug_scene="custom_3").debug_scene == "custom_3"


@pytest.mark.parametrize("slot", (1, 2, 3))
def test_scene_keys_cover_every_slot(slot):
    assert scene_name(slot) in CUSTOM_IDLE_THEMES
