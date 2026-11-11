"""Date-triggered custom text scenes.

Up to three idle scenes can show a user-supplied message on a recurring
month/day (an anniversary, a pet's birthday, and so on).  The helpers here
are shared by the config layer, the web settings parser, and the idle scene
factory; they stay free of font/panel imports so the web process can use
them without initialising the display.
"""

from __future__ import annotations

from setup.colours import (
    BLUE_LIGHT,
    CYAN,
    GOLD,
    HOT_PINK,
    LIME_GREEN,
    ORANGE,
    RED,
    VIOLET,
    WHITE,
    YELLOW,
)
from utilities.recurring_date import is_recurring_date

CUSTOM_SCENE_SLOTS = (1, 2, 3)
CUSTOM_SCENE_TEXT_MAX = 40
DEFAULT_CUSTOM_SCENE_COLOUR = "white"

# Palette offered by the settings page.  Keys are stored in config.json;
# values are the panel colours used by the theme.
CUSTOM_SCENE_COLOURS = {
    "white": WHITE,
    "yellow": YELLOW,
    "gold": GOLD,
    "orange": ORANGE,
    "red": RED,
    "hot_pink": HOT_PINK,
    "violet": VIOLET,
    "cyan": CYAN,
    "lime_green": LIME_GREEN,
    "blue_light": BLUE_LIGHT,
}
CUSTOM_SCENE_COLOUR_NAMES = tuple(CUSTOM_SCENE_COLOURS)


def scene_name(slot: int) -> str:
    """Return the idle-theme registry name for *slot* (``custom_1`` ...)."""
    return f"custom_{int(slot)}"


def slot_from_name(name: str) -> int:
    """Return the slot number from a ``custom_N`` name (defaults to 1)."""
    try:
        slot = int(str(name).rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 1
    return slot if slot in CUSTOM_SCENE_SLOTS else 1


def scene_keys(slot: int) -> tuple[str, str, str]:
    """Return ``(text_key, date_key, colour_key)`` for *slot*."""
    prefix = f"custom_scene_{int(slot)}"
    return f"{prefix}_text", f"{prefix}_date", f"{prefix}_colour"


def _cfg_str(cfg, key: str) -> str:
    """Read a string config value, tolerating simple test doubles.

    A real string attribute wins (that covers plain objects and mocks with
    configured values); otherwise the config's ``get`` lookup is used.  The
    attribute check uses ``hasattr`` so a real :class:`Config`, which stores
    these keys only in its data store, still reads the saved value.  Only
    real strings are accepted: ``MagicMock`` returns another mock for any
    attribute and has a callable ``get``, so without the type check every
    existing idle-scene test would accidentally schedule scenes.
    """
    if hasattr(cfg, key):
        value = getattr(cfg, key)
        if isinstance(value, str):
            return value.strip()
    getter = getattr(cfg, "get", None)
    value = getter(key, "") if callable(getter) else ""
    return value.strip() if isinstance(value, str) else ""


def cfg_text(cfg, slot: int) -> str:
    """Return the saved message for *slot* (empty when unset)."""
    text_key, _date_key, _colour_key = scene_keys(slot)
    return _cfg_str(cfg, text_key)


def cfg_date(cfg, slot: int) -> str:
    """Return the saved recurring date for *slot* (empty when unset)."""
    _text_key, date_key, _colour_key = scene_keys(slot)
    return _cfg_str(cfg, date_key)


def cfg_colour(cfg, slot: int) -> str:
    """Return the saved palette name for *slot* (``white`` when invalid)."""
    _text_key, _date_key, colour_key = scene_keys(slot)
    value = _cfg_str(cfg, colour_key).lower()
    return value if value in CUSTOM_SCENE_COLOURS else DEFAULT_CUSTOM_SCENE_COLOUR


def colour_for(value) -> object:
    """Map a stored palette name to a panel colour (white when invalid)."""
    return CUSTOM_SCENE_COLOURS.get(
        str(value or "").strip().lower(), CUSTOM_SCENE_COLOURS["white"]
    )


def sanitise_text(value) -> str:
    """Normalise user-entered message text.

    Collapses whitespace, drops control characters and characters outside
    Latin-1 (the BDF fonts have no glyphs for them, so they would render as
    blank gaps), and caps the length at :data:`CUSTOM_SCENE_TEXT_MAX`.
    """
    text = str(value or "")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    kept = []
    for char in text:
        if not char.isprintable():
            continue
        try:
            char.encode("latin-1")
        except UnicodeEncodeError:
            continue
        kept.append(char)
    return " ".join("".join(kept).split())[:CUSTOM_SCENE_TEXT_MAX].strip()


def scheduled_scene_names(cfg, today=None) -> list[str]:
    """Return the custom scene names that should join today's rotation.

    A slot is scheduled only when it has both a message and a valid
    recurring date matching *today*.
    """
    names: list[str] = []
    for slot in CUSTOM_SCENE_SLOTS:
        if not cfg_text(cfg, slot):
            continue
        if is_recurring_date(cfg_date(cfg, slot), today):
            names.append(scene_name(slot))
    return names
