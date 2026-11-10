"""Optional INDYCAR team logos with a coloured initials-tile fallback.

The official feeds publish driver headshots, car illustrations, and engine
logos, but no team logos.  A logo can be dropped into
``assets/indycar/teams/<slug>.png`` where ``<slug>`` is the lower-case,
hyphenated team name (for example ``chip-ganassi-racing.png``).  When the
file is absent the display draws a compact coloured tile using the team's
initials so every row still has a visual team marker.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PIL import Image

from display.rgbpanel import Colour
from display.spans import font_text_width
from setup import fonts

logger = logging.getLogger(__name__)

TEAM_DIR = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "indycar" / "teams"
)

DEFAULT_SIZE = 16
_BORDER = Colour(210, 210, 210)
_INITIAL_COLOUR = Colour(255, 255, 255)

# A small, deliberately dark palette so many teams remain distinguishable
# on an LED matrix without relying on any single brand colour.
_PALETTE = (
    Colour(18, 62, 112),
    Colour(112, 28, 34),
    Colour(30, 92, 58),
    Colour(86, 58, 12),
    Colour(72, 34, 100),
    Colour(20, 78, 84),
    Colour(100, 54, 72),
    Colour(52, 52, 96),
)

_image_cache: dict[tuple[str, int], Image.Image | None] = {}


def team_slug(team: str) -> str:
    """Map a feed team name to its PNG filename stem."""
    slug = re.sub(r"[^a-z0-9]+", "-", (team or "").strip().lower()).strip("-")
    return slug or "unknown"


def team_initials(team: str) -> str:
    """Two-character initials for the placeholder tile."""
    words = [word for word in re.split(r"\s+", (team or "").strip()) if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _load_logo(team: str, size: int) -> Image.Image | None:
    """Load and resize a team PNG once, returning ``None`` when absent."""
    key = (team_slug(team), size)
    if key in _image_cache:
        return _image_cache[key]

    path = TEAM_DIR / f"{key[0]}.png"
    image: Image.Image | None = None
    try:
        with Image.open(path) as source:
            image = source.convert("RGBA").resize((size, size), Image.NEAREST)
    except (OSError, ValueError):
        image = None
    _image_cache[key] = image
    return image


def draw_team_logo(
    panel,
    canvas,
    x: int,
    y: int,
    team: str,
    size: int = DEFAULT_SIZE,
) -> None:
    """Draw a team logo, or a coloured initials tile when none exists."""
    image = _load_logo(team, size)
    if image is not None:
        panel.draw_image(canvas, x, y, image)
        return

    slug = team_slug(team)
    colour = _PALETTE[sum(ord(char) for char in slug) % len(_PALETTE)]
    last = size - 1
    panel.draw_square(canvas, x, y, x + last, y + last, colour)
    panel.draw_line(canvas, x, y, x + last, y, _BORDER)
    panel.draw_line(canvas, x, y + last, x + last, y + last, _BORDER)
    panel.draw_line(canvas, x, y, x, y + last, _BORDER)
    panel.draw_line(canvas, x + last, y, x + last, y + last, _BORDER)

    if size < 12:
        return
    initials = team_initials(team)
    font = fonts.extrasmall
    width = font_text_width(font, initials)
    baseline = y + (size + font.ascent - font.descent) // 2 - 1
    panel.draw_text(
        canvas,
        font,
        x + max(0, (size - width) // 2),
        baseline,
        _INITIAL_COLOUR,
        initials,
    )


def clear_logo_cache() -> None:
    """Drop cached images after the asset folder changes."""
    _image_cache.clear()
