"""
SceneManager - pure scene dispatch engine.

Each scene must implement:
    priority    int     Higher value = higher priority.
    has_data()  bool    Scene has something to show right now.
    active()    bool    Scene is mid-presentation; prevent preemption.
    draw()      None    Render one frame. Scene owns its own frame counter.
    reset()     None    Internal state reset (e.g. carousel advance). No canvas clear.
    on_enter()  None    Called by SceneManager on scene transition. Clears canvas + resets.

Scene failures are contained here instead of reaching the display loop: a
scene that raises is logged, reported to an optional callback (so the display
can tell the owner), and left out of the rotation for ``quarantine_seconds``
before it is tried again.  The idle scene cannot be skipped - it is the last
resort - so a failure there is reported but the loop keeps running.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# A scene that raises is left out of the rotation for this long before it is
# tried again.  Long enough that a persistent bug does not flash an error on
# the display every few seconds.
DEFAULT_QUARANTINE_SECONDS = 300.0

# Repeats of the same failure are logged at most this often.
ERROR_LOG_INTERVAL_SECONDS = 300.0


def scene_label(scene) -> str:
    """Return a short, human-readable name for *scene*.

    Used in log messages and on the panel, so it is kept lowercase and free
    of underscores ("indy_top3" becomes "indy top3").
    """
    name = getattr(scene, "debug_name", None)
    if not name:
        name = type(scene).__name__
        if name.endswith("Scene"):
            name = name[:-5]
    text = str(name).replace("_", " ").strip()
    return text or "scene"


class SceneManager:
    """
    Priority-based scene dispatcher.

    Scenes are sorted by priority ascending so that index 0 is always the
    lowest-priority fallback (matching the C++ layout where scenes[0] is
    the always-on weather/idle scene).

    kick() logic (mirrors scene_manager.cpp):
      1. Search all non-fallback scenes for the highest-priority one that
         has_data() and the highest-priority one that is active().
      2. If the has_data scene outranks the active scene -> reset + draw it.
      3. Else if something is active -> keep drawing it.
      4. Else -> fall back to scenes[0], resetting if we just arrived here.
    """

    def __init__(
        self,
        on_scene_error: Callable[[str], None] | None = None,
        quarantine_seconds: float = DEFAULT_QUARANTINE_SECONDS,
    ):
        self.scenes: list = []
        self.current_scene = None
        self._on_scene_error = on_scene_error
        self._quarantine_seconds = quarantine_seconds
        self._quarantined_until: dict[int, float] = {}
        self._last_error_logged: dict[int, float] = {}

    def register(self, scene) -> None:
        """Register a scene. Kept sorted lowest->highest priority so index 0
        is the fallback, matching the C++ array layout."""
        self.scenes.append(scene)
        self.scenes.sort(key=lambda s: s.priority)

    def replace_fallback(self, scene) -> None:
        """Swap the lowest-priority fallback scene for *scene*.

        Used when the idle rotation is rebuilt (for example at midnight, so
        date-triggered scenes appear without a restart).  The list stays
        sorted, and if the old fallback was on screen the replacement takes
        over immediately.
        """
        if not self.scenes:
            self.register(scene)
            return

        old_fallback = self.scenes[0]
        if old_fallback is scene:
            return

        was_current = self.current_scene is old_fallback
        self.scenes[0] = scene
        self.scenes.sort(key=lambda s: s.priority)

        if was_current:
            # A failure here is contained like any other scene call; the
            # next kick tries again.
            self.current_scene = None
            if self._call(scene, "on_enter"):
                self.current_scene = scene

    def kick(self, debug_scene: str = "auto") -> None:
        if not self.scenes:
            return

        now = time.monotonic()

        for scene in self.scenes:
            if self._is_quarantined(scene, now):
                continue
            self._call(scene, "poll")

        fallback = self.scenes[0]
        available = [
            scene for scene in self.scenes[1:] if not self._is_quarantined(scene, now)
        ]

        if debug_scene != "auto":
            forced = next(
                (
                    scene
                    for scene in self.scenes
                    if getattr(scene, "debug_name", None) == debug_scene
                ),
                None,
            )
            if forced is not None and not self._is_quarantined(forced, now):
                if forced is fallback:
                    if self._enter(forced):
                        self._call(forced, "draw")
                    return
                ok, has_data = self._call(forced, "has_data")
                if ok and has_data and self._enter(forced):
                    ok, _ = self._call(forced, "draw")
                    if ok:
                        return

        highest_with_data = None
        highest_active = None

        # highest priority first
        for scene in reversed(available):
            if highest_with_data is None:
                ok, has_data = self._call(scene, "has_data")
                if ok and has_data:
                    highest_with_data = scene

            if highest_active is None:
                ok, active = self._call(scene, "active")
                if ok and active:
                    highest_active = scene

            if highest_with_data and highest_active:
                break

        # Determine winner
        winner = None
        if highest_with_data and (
            highest_active is None
            or highest_with_data.priority > highest_active.priority
        ):
            winner = highest_with_data
        elif highest_active:
            winner = highest_active

        if winner is not None:
            if self._enter(winner):
                ok, _ = self._call(winner, "draw")
                if ok:
                    return
            if winner is fallback:
                # The fallback was already tried this frame; do not repeat it.
                return

        if self.current_scene is not fallback and not self._enter(fallback):
            return
        self._call(fallback, "draw")

    # ------------------------------------------------------------------
    # Failure containment
    # ------------------------------------------------------------------

    def _call(self, scene, method: str, *args):
        """Call a scene method, containing any exception it raises."""
        try:
            return True, getattr(scene, method)(*args)
        except Exception as exc:
            self._handle_failure(scene, method, exc)
            return False, None

    def _enter(self, scene) -> bool:
        """Make *scene* current, entering it if it is not already."""
        if scene is self.current_scene:
            return True
        ok, _ = self._call(scene, "on_enter")
        if not ok:
            return False
        self.current_scene = scene
        return True

    def _handle_failure(self, scene, method: str, exc: Exception) -> None:
        label = scene_label(scene)
        now = time.monotonic()
        key = id(scene)

        last_logged = self._last_error_logged.get(key)
        if last_logged is None or now - last_logged >= ERROR_LOG_INTERVAL_SECONDS:
            if last_logged is None:
                logger.error("Scene %s failed in %s()", label, method, exc_info=exc)
            else:
                logger.warning(
                    "Scene %s is still failing in %s(): %s", label, method, exc
                )
            self._last_error_logged[key] = now

        is_fallback = bool(self.scenes) and scene is self.scenes[0]
        if not is_fallback:
            self._quarantined_until[key] = now + self._quarantine_seconds
            if self.current_scene is scene:
                self.current_scene = None

        self._notify_error(label)

    def _is_quarantined(self, scene, now: float) -> bool:
        key = id(scene)
        until = self._quarantined_until.get(key)
        if until is None:
            return False
        if now >= until:
            self._quarantined_until.pop(key, None)
            # Forget the old log time too, so a fresh failure shows a full
            # traceback rather than a one-line repeat.
            self._last_error_logged.pop(key, None)
            return False
        return True

    def _notify_error(self, label: str) -> None:
        if self._on_scene_error is None:
            return
        try:
            self._on_scene_error(label)
        except Exception:
            logger.exception("The scene error callback failed")
