"""Live Top 3 INDYCAR scene.

The scene is deliberately separate from the tracked-driver scene: this one
shows the leading three cars at a glance, while :class:`DriverScene`
drills into one configured driver.  Both share the same priority so a
tracked driver can take over only when one is configured.
"""

from __future__ import annotations

from display.spans import font_text_width
from scenes.indycar.base import IndyCarSceneBase
from scenes.indycar.formatting import (
    draw_text_right,
    flag_colour,
    format_lap,
    format_session_name,
    format_time_to_go,
    gap_to_next,
    truncate_to_width,
)
from scenes.indycar.team_logo import draw_team_logo
from setup import fonts
from setup.colours import CYAN, GOLD, GREY, LIGHT_STEEL_BLUE, WHITE
from utilities.indycar.models import SessionState, Snapshot

PRIORITY = 3
HEADER_FONT = fonts.small
ROW_FONT = fonts.extrasmall
LOGO_SIZE = 7


def _draw_header(panel, canvas, session: SessionState) -> None:
    label = (format_session_name(session) or "INDYCAR").upper()
    label_colour = flag_colour(session.flag)
    panel.draw_text(canvas, HEADER_FONT, 1, 7, label_colour, label)

    time_text = format_time_to_go(session.time_to_go)
    time_x = 1 + font_text_width(HEADER_FONT, label) + 8
    panel.draw_text(canvas, HEADER_FONT, time_x, 7, WHITE, time_text)

    lap_text = format_lap(session.leader, session.total_laps)
    draw_text_right(panel, canvas, 191, 7, HEADER_FONT, CYAN, lap_text)


class Top3Scene(IndyCarSceneBase):
    """Show the top three cars, their gaps, teams, and team markers."""

    priority = PRIORITY
    debug_name = "indy_top3"

    def has_data(self) -> bool:
        session = self.snapshot().session
        return bool(session and session.live and session.drivers)

    def draw_content(self, snapshot: Snapshot) -> None:
        session = snapshot.session
        if session is None or not session.drivers:
            return

        _draw_header(self.panel, self.canvas, session)
        drivers = session.drivers

        for index, driver in enumerate(drivers[:3]):
            top = 8 + index * 8
            baseline = top + 5

            draw_team_logo(
                self.panel,
                self.canvas,
                0,
                top,
                driver.team,
                LOGO_SIZE,
            )

            position = str(driver.position or index + 1)
            self.panel.draw_text(
                self.canvas,
                ROW_FONT,
                9,
                baseline,
                GOLD if index == 0 else WHITE,
                position,
            )

            name = truncate_to_width(ROW_FONT, driver.name, 66)
            self.panel.draw_text(
                self.canvas,
                ROW_FONT,
                18,
                baseline,
                WHITE,
                name,
            )

            gap = gap_to_next(drivers, index)
            draw_text_right(
                self.panel,
                self.canvas,
                110,
                baseline,
                ROW_FONT,
                GREY,
                gap,
            )

            team = truncate_to_width(ROW_FONT, driver.team, 77)
            self.panel.draw_text(
                self.canvas,
                ROW_FONT,
                114,
                baseline,
                LIGHT_STEEL_BLUE,
                team,
            )
