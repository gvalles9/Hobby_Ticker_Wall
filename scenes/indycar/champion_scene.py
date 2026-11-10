"""Flashing INDYCAR Drivers Champion celebration scene.

The scene is intentionally lower priority than a live INDYCAR session and
refuses to show whenever a session is live, so it can never preempt race
coverage.  It is bounded: after ``indycar_champion_flash_seconds`` it
gives the screen back to the normal rotation.

Champion detection uses the feed layer's clinch calculation, plus a
manual override for the off-season when the feeds carry no season or
champion field.
"""

from __future__ import annotations

import time

from display.spans import font_text_width
from scenes.indycar.base import IndyCarSceneBase
from scenes.indycar.formatting import find_standing, truncate_to_width
from scenes.indycar.team_logo import draw_team_logo
from setup import fonts
from setup.colours import GOLD, LIGHT_STEEL_BLUE, WHITE
from setup.configuration import Config
from setup.screen import WIDTH as SCREEN_WIDTH
from utilities.indycar.models import Snapshot

PRIORITY = 2.5
HEADER_FONT = fonts.large_bold
NAME_FONT = fonts.small
TEAM_FONT = fonts.extrasmall
LOGO_SIZE = 16
DEFAULT_FLASH_SECONDS = 60


class ChampionScene(IndyCarSceneBase):
    """Flash the season champion, then yield automatically."""

    priority = PRIORITY
    debug_name = "indy_champion"

    def __init__(self, canvas, panel, monitor=None):
        super().__init__(canvas, panel, monitor)
        self.started_at: float | None = None
        self.champion_key: tuple[str, str] | None = None

    # -- detection ---------------------------------------------------------

    @staticmethod
    def _duration() -> int:
        cfg = Config.instance()
        value = getattr(cfg, "indycar_champion_flash_seconds", DEFAULT_FLASH_SECONDS)
        try:
            return max(5, min(600, int(value)))
        except (TypeError, ValueError):
            return DEFAULT_FLASH_SECONDS

    @staticmethod
    def _champion(snapshot: Snapshot) -> tuple[str, str] | None:
        """Resolve the champion name/team, honouring the manual override."""
        cfg = Config.instance()
        override = getattr(cfg, "indycar_champion_override", "")
        override = override.strip() if isinstance(override, str) else ""
        if override:
            standing = find_standing(snapshot.standings, override)
            if standing is not None:
                return standing.driver, standing.team
            return override, ""

        championship = snapshot.championship
        if championship is not None and championship.clinched:
            leader = championship.leader
            if leader is not None:
                return leader.driver, leader.team
        return None

    def _timer_expired(self) -> bool:
        return (
            self.started_at is not None
            and (time.monotonic() - self.started_at) >= self._duration()
        )

    def has_data(self) -> bool:
        cfg = Config.instance()
        if getattr(cfg, "indycar_champion_enabled", True) is False:
            return False

        snapshot = self.snapshot()
        if snapshot.is_live:
            return False

        champion = self._champion(snapshot)
        if champion is None:
            self.champion_key = None
            return False

        key = champion
        if key != self.champion_key:
            # A new champion (or a changed override) starts a fresh window.
            self.champion_key = key
            self.started_at = None

        if self.started_at is None:
            return True
        return not self._timer_expired()

    # -- scene protocol ----------------------------------------------------

    def scene_enter(self) -> None:
        self.started_at = time.monotonic()

    def draw_content(self, snapshot: Snapshot) -> None:
        champion = self._champion(snapshot)
        if champion is None:
            return

        name, team = champion
        tick = max(0, self.frame // max(1, int(1 / 0.08)))
        if tick % 2 == 0:
            header = "DRIVERS CHAMPION"
            width = font_text_width(HEADER_FONT, header)
            self.panel.draw_text(
                self.canvas,
                HEADER_FONT,
                max(0, (SCREEN_WIDTH - width) // 2),
                11,
                GOLD,
                header,
            )

        draw_team_logo(
            self.panel,
            self.canvas,
            20,
            14,
            team,
            LOGO_SIZE,
        )

        name_x = 42
        display_name = truncate_to_width(NAME_FONT, name, SCREEN_WIDTH - name_x - 2)
        self.panel.draw_text(
            self.canvas,
            NAME_FONT,
            name_x,
            23,
            WHITE,
            display_name,
        )
        display_team = truncate_to_width(TEAM_FONT, team, SCREEN_WIDTH - name_x - 2)
        self.panel.draw_text(
            self.canvas,
            TEAM_FONT,
            name_x,
            30,
            LIGHT_STEEL_BLUE,
            display_team,
        )
