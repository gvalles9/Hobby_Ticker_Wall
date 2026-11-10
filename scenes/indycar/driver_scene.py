"""Tracked-driver INDYCAR scene, including a qualifying layout.

The driver is chosen by car number or surname in the settings
(``indycar_tracked_driver``).  In a race the scene shows position, gap to
the car ahead, gap to the leader, and lap distance.  In qualifying those
race-only fields are replaced with the driver's qualifying time, gap to
provisional pole, and qualifying speed.
"""

from __future__ import annotations

from display.spans import font_text_width
from scenes.indycar.base import IndyCarSceneBase
from scenes.indycar.formatting import (
    draw_text_right,
    find_driver,
    flag_colour,
    format_session_name,
    format_time_to_go,
    gap_to_leader,
    gap_to_next,
    qualifying_gap,
    qualifying_speed,
    qualifying_time,
    truncate_to_width,
)
from scenes.indycar.team_logo import draw_team_logo
from setup import fonts
from setup.colours import CYAN, GOLD, GREY, LIGHT_STEEL_BLUE, WHITE
from setup.configuration import Config
from utilities.indycar.models import SessionState, Snapshot

PRIORITY = 3
HEADER_FONT = fonts.small
NAME_FONT = fonts.regular
METRIC_FONT = fonts.extrasmall
LOGO_SIZE = 16

METRIC_X = 124
METRIC_BASELINES = (13, 19, 25, 31)


def _draw_header(panel, canvas, session: SessionState) -> None:
    label = (format_session_name(session) or "INDYCAR").upper()
    panel.draw_text(canvas, HEADER_FONT, 1, 7, flag_colour(session.flag), label)

    time_text = format_time_to_go(session.time_to_go)
    draw_text_right(panel, canvas, 191, 7, HEADER_FONT, WHITE, time_text)


def _draw_metric(panel, canvas, baseline: int, label: str, value: str, colour) -> None:
    panel.draw_text(canvas, METRIC_FONT, METRIC_X, baseline, GREY, label)
    value_x = METRIC_X + font_text_width(METRIC_FONT, label) + 3
    panel.draw_text(canvas, METRIC_FONT, value_x, baseline, colour, value)


class DriverScene(IndyCarSceneBase):
    """Show a single tracked driver's race or qualifying telemetry."""

    priority = PRIORITY
    debug_name = "indy_driver"

    @staticmethod
    def _selector() -> str:
        cfg = Config.instance()
        value = getattr(cfg, "indycar_tracked_driver", "")
        selector = value.strip() if isinstance(value, str) else ""
        if not selector and str(getattr(cfg, "debug_scene", "auto")) == "indy_driver":
            # Preview the layout offline without first saving a driver.
            return "Palou"
        return selector

    def _driver(self, session: SessionState):
        """Resolve the configured driver, falling back to the demo driver.

        During a preview the bundled snapshot may not contain the driver
        saved in the settings (for example a 2026 driver), so fall back to
        the demo leader to keep the layout visible.
        """
        driver, index = find_driver(session.drivers, self._selector())
        if driver is None and self.preview_active():
            driver, index = find_driver(session.drivers, "Palou")
        return driver, index

    def has_data(self) -> bool:
        selector = self._selector()
        session = self.snapshot().session
        if not selector or session is None or not session.live or not session.drivers:
            return False
        driver, _index = self._driver(session)
        return driver is not None

    def draw_content(self, snapshot: Snapshot) -> None:
        session = snapshot.session
        if session is None or not session.drivers:
            return

        driver, index = self._driver(session)
        if driver is None:
            return

        _draw_header(self.panel, self.canvas, session)

        draw_team_logo(
            self.panel,
            self.canvas,
            0,
            8,
            driver.team,
            LOGO_SIZE,
        )

        name = truncate_to_width(NAME_FONT, driver.name, 101)
        self.panel.draw_text(
            self.canvas,
            NAME_FONT,
            20,
            19,
            WHITE,
            name,
        )

        team_text = (
            f"#{driver.car_number} {driver.team}" if driver.car_number else driver.team
        )
        team_text = truncate_to_width(METRIC_FONT, team_text, 101)
        self.panel.draw_text(
            self.canvas,
            METRIC_FONT,
            20,
            30,
            LIGHT_STEEL_BLUE,
            team_text,
        )

        if session.is_qualifying:
            metrics = (
                ("POS", str(driver.position), GOLD),
                ("TIME", qualifying_time(driver), WHITE),
                ("GAP", qualifying_gap(driver), CYAN),
                ("SPD", qualifying_speed(driver), WHITE),
            )
        else:
            lap_value = (
                f"{driver.laps}/{session.total_laps}"
                if session.total_laps > 0
                else str(driver.laps)
            )
            metrics = (
                ("POS", str(driver.position), GOLD),
                ("AHEAD", gap_to_next(session.drivers, index), CYAN),
                ("LEAD", gap_to_leader(driver), CYAN),
                ("LAP", lap_value, WHITE),
            )

        for baseline, (label, value, colour) in zip(METRIC_BASELINES, metrics):
            _draw_metric(self.panel, self.canvas, baseline, label, value, colour)
