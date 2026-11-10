"""Happy Birthday idle theme.

A celebratory screen for the idle rotation: a cone hat on the left, a
layered birthday cake on the right, festive confetti falling around the
display, and "Happy Birthday" centred in the middle.

The date is recurring - only the month and day are compared, so a date
saved for any year comes back every year.  The theme can be selected
directly (``birthday``) to preview it at any time, or added to the idle
rotation automatically when a ``birthday_date`` is saved and today
matches it.
"""

from __future__ import annotations

from scenes.idle.idle_scene import BaseIdleScene
from scenes.idle.themes.theme_utilities import font_text_width
from setup import fonts
from setup.colours import (
    CYAN,
    GOLD,
    GREY,
    HOT_PINK,
    LIGHT_PINK,
    LIME_GREEN,
    ORANGE,
    VIOLET,
    WHITE,
    YELLOW,
)
from setup.screen import HEIGHT as SCREEN_HEIGHT
from setup.screen import WIDTH as SCREEN_WIDTH

TEXT_FONT = fonts.medium
TEXT_HAPPY = "Happy"
TEXT_BIRTHDAY = " Birthday"
TEXT_BASELINE = 21

# A small, deterministic confetti field.  Each piece slowly falls and
# wraps back to the top, so the scene animates once per second without
# keeping any random state.
CONFETTI_COLOURS = (YELLOW, HOT_PINK, CYAN, LIME_GREEN, ORANGE, LIGHT_PINK, VIOLET)
CONFETTI_COUNT = 34


class BirthdayIdleTheme(BaseIdleScene):
    """Birthday scene: hat, cake, confetti, and centred greeting."""

    debug_name = "birthday"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw_content(self, count: int) -> None:
        self.panel.clear(self.canvas)
        self._draw_confetti(count)
        self._draw_hat()
        self._draw_cake()
        self._draw_greeting()

    # -- confetti ------------------------------------------------------

    def _draw_confetti(self, count: int) -> None:
        for index in range(CONFETTI_COUNT):
            x = (index * 47 + 11) % SCREEN_WIDTH
            speed = 1 + index % 3
            base_y = (index * 5) % (SCREEN_HEIGHT // 2)
            y = (base_y + count * speed) % SCREEN_HEIGHT
            colour = CONFETTI_COLOURS[index % len(CONFETTI_COLOURS)]
            self.panel.set_pixel(
                self.canvas, x, y, colour.red, colour.green, colour.blue
            )
            if index % 4 == 0:
                self.panel.set_pixel(
                    self.canvas,
                    (x + 1) % SCREEN_WIDTH,
                    y,
                    colour.red,
                    colour.green,
                    colour.blue,
                )

    # -- left: party hat ----------------------------------------------

    def _draw_hat(self) -> None:
        centre_x = 20
        tip_y = 4
        base_y = 28
        stripe_colours = (HOT_PINK, YELLOW, CYAN, VIOLET)

        for y in range(tip_y + 1, base_y + 1):
            half_width = max(1, int((y - tip_y) * 0.7))
            colour = stripe_colours[(y - tip_y) // 4 % len(stripe_colours)]
            self.panel.draw_line(
                self.canvas,
                centre_x - half_width,
                y,
                centre_x + half_width,
                y,
                colour,
            )

        # Pom-pom on the point and a brim across the bottom.
        self.panel.draw_square(
            self.canvas, centre_x - 1, tip_y - 1, centre_x + 2, tip_y + 2, WHITE
        )
        self.panel.draw_line(self.canvas, 3, base_y + 1, 37, base_y + 1, GOLD)
        # A few spots on the cone.
        for x, y in ((16, 14), (24, 18), (19, 23)):
            self.panel.set_pixel(self.canvas, x, y, 255, 255, 255)

    # -- right: birthday cake -----------------------------------------

    def _draw_cake(self) -> None:
        # Plate.
        self.panel.draw_square(self.canvas, 151, 28, 190, 29, GREY)

        # Bottom tier.
        self.panel.draw_square(self.canvas, 153, 20, 189, 27, LIGHT_PINK)
        # Frosting along the top of the bottom tier.
        self.panel.draw_square(self.canvas, 153, 20, 189, 21, WHITE)
        for x in range(155, 189, 6):
            self.panel.draw_square(self.canvas, x, 22, x + 2, 23, WHITE)

        # Top tier.
        self.panel.draw_square(self.canvas, 160, 14, 182, 19, HOT_PINK)
        self.panel.draw_square(self.canvas, 160, 14, 182, 15, WHITE)
        for x in range(162, 182, 6):
            self.panel.draw_square(self.canvas, x, 16, x + 2, 17, WHITE)

        # Candle with a glowing flame.
        self.panel.draw_square(self.canvas, 170, 8, 171, 13, CYAN)
        self.panel.set_pixel(self.canvas, 170, 6, 255, 180, 0)
        self.panel.set_pixel(self.canvas, 171, 5, 255, 80, 0)

    # -- middle: greeting ---------------------------------------------

    def _draw_greeting(self) -> None:
        happy_width = font_text_width(TEXT_FONT, TEXT_HAPPY)
        birthday_width = font_text_width(TEXT_FONT, TEXT_BIRTHDAY)
        x = (SCREEN_WIDTH - happy_width - birthday_width) // 2
        self.panel.draw_text(
            self.canvas, TEXT_FONT, x, TEXT_BASELINE, YELLOW, TEXT_HAPPY
        )
        self.panel.draw_text(
            self.canvas,
            TEXT_FONT,
            x + happy_width,
            TEXT_BASELINE,
            HOT_PINK,
            TEXT_BIRTHDAY,
        )
