"""Configuration defaults and validation for the INDYCAR settings."""

from __future__ import annotations

from setup.configuration import (
    DEFAULT_IDLE_CYCLE_INCLUDE_INDYCAR,
    DEFAULT_INDYCAR_CHAMPION_FLASH_SECONDS,
    DEFAULT_INDYCAR_ENABLED,
    DEFAULT_INDYCAR_TEST_MODE,
    DEFAULTS,
    Config,
)


def _config(**values):
    cfg = Config.__new__(Config)
    cfg.data_store = dict(values)
    return cfg


def test_defaults_are_opt_in_and_documented():
    assert DEFAULT_INDYCAR_ENABLED is False
    assert DEFAULT_INDYCAR_TEST_MODE is False
    assert DEFAULT_IDLE_CYCLE_INCLUDE_INDYCAR is False
    assert DEFAULT_INDYCAR_CHAMPION_FLASH_SECONDS == 60
    assert DEFAULTS["indycar_enabled"] is False
    assert DEFAULTS["indycar_champion_enabled"] is True
    assert DEFAULTS["idle_cycle_include_indycar"] is False


def test_properties_read_the_data_store():
    cfg = _config(
        indycar_enabled=True,
        indycar_tracked_driver="  Palou  ",
        indycar_champion_enabled=False,
        indycar_champion_override=" #11 ",
        indycar_test_mode=True,
        indycar_test_qualifying=True,
        idle_cycle_include_indycar=True,
    )

    assert cfg.indycar_enabled is True
    assert cfg.indycar_tracked_driver == "Palou"
    assert cfg.indycar_champion_enabled is False
    assert cfg.indycar_champion_override == "#11"
    assert cfg.indycar_test_mode is True
    assert cfg.indycar_test_qualifying is True
    assert cfg.idle_cycle_include_indycar is True


def test_champion_flash_seconds_is_clamped():
    assert _config().indycar_champion_flash_seconds == 60
    assert (
        _config(indycar_champion_flash_seconds=1).indycar_champion_flash_seconds == 10
    )
    assert (
        _config(indycar_champion_flash_seconds=9999).indycar_champion_flash_seconds
        == 600
    )
    assert (
        _config(
            indycar_champion_flash_seconds="nonsense"
        ).indycar_champion_flash_seconds
        == 60
    )


def test_debug_scene_allows_indycar_previews():
    for name in ("indy_top3", "indy_driver", "indy_champion"):
        assert _config(debug_scene=name).debug_scene == name
    assert _config(debug_scene="indy_unknown").debug_scene == "auto"


def test_idle_screen_theme_allows_indycar_next():
    assert _config(idle_screen_theme="indycar_next").idle_screen_theme == "indycar_next"
