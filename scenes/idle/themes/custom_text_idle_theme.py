"""Date-triggered custom text idle theme.

Up to three of these scenes can be configured from the Default Screen
settings page.  Each slot has a message and a recurring month/day; on the
matching day the scene joins the idle rotation automatically (exactly like
the birthday scene), and ticking the slot previews it at any time.

Short messages slide left-to-right so they stay in reading order.  Messages
wider than the display use the bounce scroller, which reveals the whole
string and then retracts it.
"""

from __future__ import annotations

from display.scroller import Scroller, spans_width
from display.spans import Span
from scenes.idle.idle_scene import BaseIdleScene
from setup import fonts
from setup.colours import WHITE
from setup.configuration import Config
from setup.screen import WIDTH as SCREEN_WIDTH
from utilities.custom_scene import cfg_colour, cfg_text, colour_for

TEXT_FONT = fonts.medium
TEXT_BASELINE = 21


class CustomTextIdleTheme(BaseIdleScene):
    """Scrolling user message for a configured date-triggered slot."""

    debug_name = "custom"

    def __init__(self, canvas, panel, slot: int = 1, preview_text: str | None = None):
        self.slot = int(slot)
        self.preview_text = preview_text
        self.debug_name = f"custom_{self.slot}"
        super().__init__(canvas, panel)

    # ------------------------------------------------------------------
    # Scene setup
    # ------------------------------------------------------------------

    def theme_init(self) -> None:
        self.text = ""
        self.colour = WHITE
        self.scroller = None
        self._built = False

    def theme_reset(self) -> None:
        self.scroller = None
        self._built = False

    def _build_scroller(self) -> None:
        cfg = Config.instance()
        text = self.preview_text
        if text is None:
            text = cfg_text(cfg, self.slot)
        text = str(text or "")
        if not text:
            self.scroller = None
            return

        self.text = text
        self.colour = colour_for(cfg_colour(cfg, self.slot))
        span = Span(self.colour, TEXT_FONT, text)
        fits = spans_width([span]) <= SCREEN_WIDTH
        self.scroller = Scroller(
            self.panel,
            self.canvas,
            0,
            TEXT_BASELINE,
            SCREEN_WIDTH,
            [span],
            slide=fits,
            bounce=not fits,
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self) -> None:
        """Tick the scroller every frame (not the base 1 fps throttle)."""
        self.frame += 1
        if not self._built:
            self._build_scroller()
            self._built = True
        if self.scroller is not None:
            self.scroller.draw()
