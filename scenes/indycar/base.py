"""Shared scene-protocol boilerplate for the INDYCAR display scenes."""

from __future__ import annotations

from setup import frames
from setup.configuration import Config
from utilities.indycar.models import Snapshot
from utilities.indycar.monitor import IndyCarMonitor

LIVE_SCENE_NAMES = ("indy_top3", "indy_driver", "indy_champion")


def current_snapshot(scene_name: str = "") -> Snapshot:
    """Latest monitor snapshot, or a bundled demo while previewing a scene.

    The INDYCAR feeds are quiet outside a race weekend, so the settings
    page can switch on test mode or force a scene from the debug selector.
    Forcing one of the live scenes is itself a preview request, so it uses
    the bundled snapshots even when test mode is off; that keeps previews
    (and the scene tests) completely offline.
    """
    cfg = Config.instance()
    test_mode = getattr(cfg, "indycar_test_mode", False) is True
    debug_scene = str(getattr(cfg, "debug_scene", "auto"))

    if scene_name in LIVE_SCENE_NAMES:
        use_demo = test_mode or debug_scene == scene_name
    elif scene_name == "indy_next":
        use_demo = test_mode and debug_scene in ("auto", "idle")
    else:
        use_demo = False

    if use_demo:
        from scenes.indycar.demo import (
            demo_champion_snapshot,
            demo_qualifying_snapshot,
            demo_race_snapshot,
        )

        if scene_name == "indy_champion":
            return demo_champion_snapshot()
        if scene_name == "indy_driver" and (
            getattr(cfg, "indycar_test_qualifying", False) is True
        ):
            return demo_qualifying_snapshot()
        return demo_race_snapshot()

    return IndyCarMonitor.instance().snapshot()


class IndyCarSceneBase:
    """Throttled 1 fps redraw plus test-mode snapshot selection."""

    priority = 3
    debug_name = "indy"

    def __init__(self, canvas, panel, monitor: IndyCarMonitor | None = None):
        self.canvas = canvas
        self.panel = panel
        self.monitor = monitor or IndyCarMonitor.instance()
        self.frame = 0

    # -- scene protocol ----------------------------------------------------

    def poll(self) -> None:
        """The monitor thread owns all network access."""
        pass

    def has_data(self) -> bool:
        raise NotImplementedError

    def active(self) -> bool:
        return self.has_data()

    def on_enter(self) -> None:
        self.panel.clear(self.canvas)
        self.frame = 0
        self.scene_enter()

    def reset(self) -> None:
        self.frame = 0

    def draw(self) -> None:
        self.frame += 1
        if self.frame % int(frames.PER_SECOND):
            return
        self.panel.clear(self.canvas)
        self.draw_content(self.snapshot())

    # -- hooks / helpers ---------------------------------------------------

    def scene_enter(self) -> None:
        """Override for scene-specific enter behaviour."""

    def draw_content(self, snapshot: Snapshot) -> None:
        raise NotImplementedError

    def snapshot(self) -> Snapshot:
        """Latest snapshot, or a bundled demo when previewing this scene."""
        return current_snapshot(self.debug_name)

    def preview_active(self) -> bool:
        """True when test mode or a forced scene is previewing this scene."""
        cfg = Config.instance()
        debug_scene = str(getattr(cfg, "debug_scene", "auto"))
        if self.debug_name in LIVE_SCENE_NAMES:
            return (
                getattr(cfg, "indycar_test_mode", False) is True
                or debug_scene == self.debug_name
            )
        return (
            getattr(cfg, "indycar_test_mode", False) is True
            and self.debug_name == "indy_next"
            and debug_scene in ("auto", "idle")
        )
