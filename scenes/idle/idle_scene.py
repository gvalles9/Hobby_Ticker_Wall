"""
IdleScene - priority-0 fallback scene with pluggable themes.

Reads cfg.idle_screen_themes and instantiates every selected theme
subclass, rotating through them when more than one is selected.
BaseIdleScene provides the shared scene-protocol boilerplate
(priority, has_data, active, on_enter, reset, frame-throttled draw);
each theme implements draw_content() with its own layout.

WeatherService (a singleton daemon thread in theme_utilities.py) is
started lazily and shared by all themes.
"""

from __future__ import annotations

from scenes.idle.themes.theme_utilities import WeatherService
from setup import frames
from setup.configuration import ALL_IDLE_THEMES, CUSTOM_IDLE_THEMES, Config

PRIORITY = 0
IDLE_THEME_CYCLE_SECONDS = 30


class BaseIdleScene:
    """
    Base class for all idle screen themes.

    Provides the scene protocol expected by SceneManager:
        priority, poll(), has_data(), active(), on_enter(), reset(), draw()

    Subclasses implement:
        theme_init()        - set up theme-specific state (called from __init__)
        theme_reset()       - clear theme-specific state (called from reset())
        draw_content(count) - render one second's worth of content
    """

    priority = PRIORITY
    debug_name = "idle"

    def __init__(self, canvas, panel):
        self.canvas = canvas
        self.panel = panel

        # Scene frame counter
        self.frame: int = 0

        # Shared weather service (singleton daemon thread)
        self.weather = WeatherService.instance()

        # Let the theme initialise its own state
        self.theme_init()

    # ------------------------------------------------------------------
    # Scene protocol
    # ------------------------------------------------------------------

    def poll(self) -> None:
        pass  # weather is handled by the background WeatherService thread

    def has_data(self) -> bool:
        return True  # always the guaranteed fallback

    def active(self) -> bool:
        return True  # never interrupted mid-draw

    def on_enter(self) -> None:
        """Called by SceneManager on scene transition. Clears canvas then resets."""
        self.panel.clear(self.canvas)
        self.reset()

    def reset(self) -> None:
        """Clear cached draw state so everything redraws on next tick."""
        self.frame = 0
        self.theme_reset()

    def draw(self) -> None:
        """Called every frame. Throttles to ~1 fps, then calls draw_content()."""
        self.frame += 1
        if self.frame % int(frames.PER_SECOND):
            return

        count = self.frame // int(frames.PER_SECOND)
        self.draw_content(count)

    # ------------------------------------------------------------------
    # Hooks for subclasses
    # ------------------------------------------------------------------

    def theme_init(self) -> None:
        """Override to set up theme-specific state."""
        pass

    def theme_reset(self) -> None:
        """Override to clear theme-specific state."""
        pass

    def draw_content(self, count: int) -> None:
        """Override to render content. Called once per second."""
        raise NotImplementedError


class CyclingIdleScene:
    """Rotate through two or more idle theme scenes every 30 seconds."""

    priority = PRIORITY
    debug_name = "idle"

    def __init__(self, classic_scene, forecast_scene, *extra_scenes):
        self.scenes = (classic_scene, forecast_scene, *extra_scenes)
        self.current_index = 0
        self.frames_on_current_scene = 0

    @property
    def current_scene(self):
        return self.scenes[self.current_index]

    def poll(self) -> None:
        for scene in self.scenes:
            scene.poll()

    def has_data(self) -> bool:
        return True

    def active(self) -> bool:
        return True

    def on_enter(self) -> None:
        self.current_index = 0
        self.frames_on_current_scene = 0
        self.current_scene.on_enter()

    def reset(self) -> None:
        self.frames_on_current_scene = 0
        self.current_scene.reset()

    def draw(self) -> None:
        self.current_scene.draw()
        self.frames_on_current_scene += 1
        cycle_frames = round(IDLE_THEME_CYCLE_SECONDS * frames.PER_SECOND)
        if self.frames_on_current_scene >= cycle_frames:
            self.current_index = (self.current_index + 1) % len(self.scenes)
            self.frames_on_current_scene = 0
            self.current_scene.on_enter()


# ---------------------------------------------------------------------------
# Theme registry - maps config string to theme class.
# Imports are deferred to avoid circular dependencies (themes import
# BaseIdleScene from this module).
# ---------------------------------------------------------------------------


def _load_themes() -> dict:
    """Lazy-load theme classes to avoid circular imports."""
    from scenes.idle.themes.birthday_idle_theme import BirthdayIdleTheme
    from scenes.idle.themes.classic_idle_theme import ClassicIdleTheme
    from scenes.idle.themes.conditions_idle_theme import ConditionsIdleTheme
    from scenes.idle.themes.custom_text_idle_theme import CustomTextIdleTheme
    from scenes.idle.themes.forecast_idle_theme import ForecastIdleTheme
    from scenes.idle.themes.indycar_next_theme import IndyCarNextTheme

    return {
        "classic": ClassicIdleTheme,
        "forecast": ForecastIdleTheme,
        "conditions": ConditionsIdleTheme,
        "indycar_next": IndyCarNextTheme,
        "birthday": BirthdayIdleTheme,
        "custom_1": lambda canvas, panel: CustomTextIdleTheme(canvas, panel, slot=1),
        "custom_2": lambda canvas, panel: CustomTextIdleTheme(canvas, panel, slot=2),
        "custom_3": lambda canvas, panel: CustomTextIdleTheme(canvas, panel, slot=3),
    }


def _birthday_scheduled(cfg) -> bool:
    """True when the birthday scene should join today's idle rotation."""
    if getattr(cfg, "birthday_enabled", False) is not True:
        return False
    from utilities.birthday import is_birthday

    return is_birthday(getattr(cfg, "birthday_date", ""))


def _custom_slot_has_text(cfg, name: str) -> bool:
    """True for non-custom themes, or a custom slot with a saved message."""
    if name not in CUSTOM_IDLE_THEMES:
        return True
    from utilities.custom_scene import cfg_text, slot_from_name

    return bool(cfg_text(cfg, slot_from_name(name)))


def _scheduled_custom_scenes(cfg) -> list[str]:
    """Custom scene names whose recurring date matches today."""
    from utilities.custom_scene import scheduled_scene_names

    return scheduled_scene_names(cfg)


def dated_theme_names(cfg) -> list[str]:
    """Date-triggered themes scheduled for today, in display order.

    Shared with the flight scene so the idle rotation and the flight
    rotation agree on which dated scenes are due.
    """
    names: list[str] = []
    if _birthday_scheduled(cfg):
        names.append("birthday")
    names.extend(_scheduled_custom_scenes(cfg))
    return names


def _selected_theme_names(cfg) -> list[str]:
    """Return the validated, de-duplicated idle theme selection."""
    names = getattr(cfg, "idle_screen_themes", None)
    if isinstance(names, (list, tuple)):
        selected: list[str] = []
        for item in names:
            name = str(item).strip().lower()
            if name in ALL_IDLE_THEMES and name not in selected:
                selected.append(name)
        if selected:
            return selected

    # Backwards compatibility for callers that only expose the old
    # single-theme attribute (and for tests using a simple mock).
    legacy = str(getattr(cfg, "idle_screen_theme", "classic")).lower()
    if legacy == "cycle":
        selected = ["classic", "forecast"]
        if getattr(cfg, "idle_cycle_include_indycar", False) is True:
            selected.append("indycar_next")
        return selected
    return [legacy if legacy in ALL_IDLE_THEMES else "classic"]


def IdleScene(canvas, panel):
    """
    Factory that returns the idle scene (or rotation) selected by config.

    Every name in ``cfg.idle_screen_themes`` is instantiated in order; two
    or more selected scenes are wrapped in a :class:`CyclingIdleScene`.
    Unknown names fall back to ``classic``.  A multi-scene rotation shows
    the forecast in its three-day form (matching the legacy ``cycle``
    behaviour), while a forecast-only selection honours the configured
    forecast duration.

    Selecting the birthday theme previews it regardless of the saved date.
    When the birthday or a custom slot has a saved recurring date matching
    today, those scenes join the rotation at the front, even if they were
    not selected.
    """
    cfg = Config.instance()
    debug_scene = str(getattr(cfg, "debug_scene", "auto"))

    # The Debug selector forces the birthday scene even when it is not
    # selected and today is not the saved date.
    if debug_scene == "birthday":
        from scenes.idle.themes.birthday_idle_theme import BirthdayIdleTheme

        return BirthdayIdleTheme(canvas, panel)

    # The Debug selector also previews any custom message slot, even when
    # it has no saved text (a placeholder makes the layout visible).
    if debug_scene in CUSTOM_IDLE_THEMES:
        from scenes.idle.themes.custom_text_idle_theme import CustomTextIdleTheme
        from utilities.custom_scene import cfg_text, slot_from_name

        slot = slot_from_name(debug_scene)
        preview_text = None if cfg_text(cfg, slot) else f"Custom message {slot}"
        return CustomTextIdleTheme(canvas, panel, slot=slot, preview_text=preview_text)

    selected = [
        name for name in _selected_theme_names(cfg) if _custom_slot_has_text(cfg, name)
    ]
    if not selected:
        selected = ["classic"]
    rotating = len(selected) > 1

    # Date-triggered scenes lead the rotation so they appear in the first
    # slot whenever idle is on screen. Keep birthday ahead of custom slots.
    dated = [name for name in dated_theme_names(cfg) if name not in selected]
    selected = dated + selected

    themes = _load_themes()
    scenes = []
    for name in selected:
        theme_class = themes.get(name)
        if theme_class is None:
            continue
        if name == "forecast" and rotating:
            scenes.append(theme_class(canvas, panel, duration_override="3day"))
        else:
            scenes.append(theme_class(canvas, panel))

    if not scenes:
        scenes.append(themes["classic"](canvas, panel))

    return CyclingIdleScene(*scenes) if len(scenes) > 1 else scenes[0]
