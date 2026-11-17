"""The classic idle date and weekday rows share one visible left edge.

The two rows are drawn at fixed baselines on the left of the panel, but
5x8 glyphs have different left bearings - a date starting with "N" used
to start a pixel or two left of a weekday starting with "T".
"""

import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

from display.bdf_font import BDFFont
from display.spans import font_ink_offset
from scenes.idle.themes import classic_idle_theme

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "5x8.bdf"

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
DATES = (
    "November 17th 2026",
    "December 1st 2026",
    "1-11-2026",
    "11-1-2026",
    "1/5/2027",
)


def _first_ink_x(font, text: str, pen_x: int) -> int | None:
    """Leftmost pixel column *text* paints when drawn at *pen_x*."""
    advance = 0
    leftmost = None
    for char in text:
        glyph = font.get_glyph(ord(char))
        if glyph is None:
            advance += 1
            continue
        total_bits = ((glyph.bbx_w + 7) // 8) * 8
        for bit in range(glyph.bbx_w):
            mask = 1 << (total_bits - 1 - bit)
            if any(row & mask for row in glyph.rows):
                ink_x = pen_x + advance + glyph.bbx_xoff + bit
                leftmost = ink_x if leftmost is None else min(leftmost, ink_x)
                break
        advance += glyph.dwidth
    return leftmost


class _FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 17, 12, 0)


def _capture_theme():
    theme = classic_idle_theme.ClassicIdleTheme.__new__(
        classic_idle_theme.ClassicIdleTheme
    )
    theme.canvas = object()
    theme.last_date = None
    theme.last_day = None
    theme.drawn = []
    theme.panel = SimpleNamespace(
        draw_text=lambda canvas, font, x, y, colour, text: theme.drawn.append(
            (x, y, text)
        )
    )
    return theme


def test_ink_offset_skips_leading_glyphs_without_pixels():
    font = classic_idle_theme.DATE_FONT

    assert font_ink_offset(font, " TUESDAY") == font_ink_offset(font, "TUESDAY")


def test_every_weekday_and_date_lands_on_the_shared_ink_column():
    font = classic_idle_theme.DATE_FONT

    for text in WEEKDAYS + DATES:
        pen_x = classic_idle_theme.ClassicIdleTheme._left_x(font, text)
        assert _first_ink_x(font, text, pen_x) == classic_idle_theme.TEXT_INK_X, text


def test_drawn_date_lines_up_with_the_weekday_above_it(monkeypatch):
    monkeypatch.setattr(classic_idle_theme.datetime, "datetime", _FixedDatetime)
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(date_format=0),
    )
    theme = _capture_theme()

    theme.draw_day()
    theme.draw_date()

    day_x, day_y, day_text = theme.drawn[0]
    date_x, date_y, date_text = theme.drawn[1]

    assert day_text == "Tuesday"
    assert date_text == "November 17th 2026"
    assert date_y > day_y

    font = classic_idle_theme.DATE_FONT
    assert _first_ink_x(font, day_text, day_x) == _first_ink_x(font, date_text, date_x)


class _MetricsOnlyFont:
    """Stand-in for ``rgbmatrix.graphics.Font``: metrics, no glyph bitmaps.

    The Pi 3/4 driver font exposes ``CharacterWidth`` but no ``get_glyph``;
    the glyph data has to come from the BDF file the panel loaded.
    """

    def __init__(self, reference: BDFFont):
        self._reference = reference

    def CharacterWidth(self, codepoint: int) -> int:
        return self._reference.CharacterWidth(codepoint)


def _stub_rgbmatrix_panel(monkeypatch, font, path):
    """Make ``bdf_path_for_font`` report *path* for *font* only."""
    resolved = None if path is None else str(path)
    monkeypatch.setitem(
        sys.modules,
        "display.rgbpanel_rgbmatrix",
        SimpleNamespace(bdf_path_for_font=lambda f: resolved if f is font else None),
    )


def test_ink_offset_falls_back_to_registered_bdf_for_driver_font(monkeypatch):
    reference = BDFFont(str(FONT_PATH))
    font = _MetricsOnlyFont(reference)
    _stub_rgbmatrix_panel(monkeypatch, font, FONT_PATH)

    for text in WEEKDAYS + DATES:
        assert font_ink_offset(font, text) == font_ink_offset(reference, text), text


def test_ink_offset_is_zero_when_no_glyph_data_is_available(monkeypatch):
    reference = BDFFont(str(FONT_PATH))
    font = _MetricsOnlyFont(reference)
    _stub_rgbmatrix_panel(monkeypatch, font, None)

    assert font_ink_offset(font, "Tuesday") == 0
