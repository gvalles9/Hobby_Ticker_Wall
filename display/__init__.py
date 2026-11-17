from __future__ import annotations

import sys
from time import perf_counter, sleep

# How long the panel shows a scene failure before returning to the idle
# screen.  The failing scene is retried after the SceneManager quarantine.
SCENE_ERROR_SECONDS = 10

# ---------------------------------------------------------------------------
# Lazy class construction - defers panel, font, and overhead imports
# until first access so the boot screen and web interface start cheaply.
# ---------------------------------------------------------------------------

DisplayClass = None
_overhead_instance = None


def _get_overhead_class():
    """The single Overhead facade over all configured lookup providers."""
    from utilities.overhead import Overhead

    return Overhead


def get_overhead_instance():
    global _overhead_instance
    if _overhead_instance is None:
        _overhead_instance = _get_overhead_class()()
    return _overhead_instance


def get_overhead_last_updated():
    overhead = get_overhead_instance()
    if hasattr(overhead, "last_updated"):
        return overhead.last_updated
    return None


def draw_scene_error(
    panel,
    canvas,
    label: str,
    *,
    width: int | None = None,
    height: int | None = None,
    title_font=None,
    body_font=None,
) -> None:
    """Draw "<label> FAILED / SEE LOG VIEWER" on the panel.

    This deliberately uses only the panel driver's own drawing calls.  It
    does not touch the scene that failed and avoids the glyph-bitmap helpers
    that caused the 1.2.1 crash-loop, so it still works when a scene's
    rendering code is broken.
    """
    from display.spans import font_text_width
    from setup import fonts, screen
    from setup.colours import RED, WHITE

    width = screen.WIDTH if width is None else width
    height = screen.HEIGHT if height is None else height
    if title_font is None:
        title_font = fonts.medium_bold
    if body_font is None:
        body_font = fonts.small

    suffix = " FAILED"
    name = str(label).upper()
    title = name + suffix

    # Long scene names drop to the smaller font, then lose characters, so
    # the message always fits and "FAILED" stays visible.
    if font_text_width(title_font, title) > width - 4:
        title_font = body_font
    while name and font_text_width(title_font, name + suffix) > width - 4:
        name = name[:-1]
    title = (name + suffix) if name else suffix.strip()

    body = "SEE LOG VIEWER"

    panel.clear(canvas)
    panel.draw_text(
        canvas,
        title_font,
        max(1, (width - font_text_width(title_font, title)) // 2),
        height // 2 - 2,
        RED,
        title,
    )
    panel.draw_text(
        canvas,
        body_font,
        max(1, (width - font_text_width(body_font, body)) // 2),
        height // 2 + 11,
        WHITE,
        body,
    )


def build_display_class():
    import logging
    from datetime import date

    from display.panel_factory import get_panel
    from scenes.flight.flight_scene import FlightScene
    from scenes.idle.idle_scene import IdleScene
    from scenes.image.image_scene import ImageScene
    from scenes.satellite.satellite_scene import SatelliteScene
    from setup import frames, screen
    from setup.configuration import Config
    from setup.themes import theme_set
    from utilities.scene_manager import SceneManager
    from utilities.tle_manager import TLEManager

    cfg = Config.instance()
    theme_set(cfg.colour_theme)
    logger = logging.getLogger("display")

    from utilities.lookups.flights import refresh_interval, top_flight_provider

    REFRESH_INTERVAL = refresh_interval()
    _pid, source_name = top_flight_provider()
    logger.info(
        "Flight provider: %s, refresh every %ds",
        source_name or "<none configured>",
        REFRESH_INTERVAL,
    )

    if cfg.loading_indicator == "gpio":
        from scenes.loadingled import LoadingLEDIndicator as IndicatorClass
    elif cfg.loading_indicator == "none":
        from scenes.loadingnull import NullLoadingIndicator as IndicatorClass
    else:
        from scenes.loadingpulse import LoadingPulseIndicator as IndicatorClass

    class Display:
        def __init__(self, matrix=None, canvas=None):
            cfg = Config.instance()

            # Scene failure state.  _error_frames is filled in by
            # _init_timing once the loop period is known.
            self._frame = 0
            self._error_label = None
            self._error_until_frame = 0
            self._error_frames = 1
            self._error_draw_failed = False
            self._pending_scene_error = None

            self._init_panel(matrix, canvas, cfg)

            overhead = get_overhead_instance()
            self._init_scenes(overhead, cfg)
            # Date-triggered scenes (birthday and custom messages) are built
            # from today's date.  Remember it so a unit left on across
            # midnight can rebuild the rotation without a restart.
            self._idle_date = date.today()

            self.loading = IndicatorClass(self.canvas, self.panel, overhead)
            self._init_timing(cfg)

        def _init_panel(self, matrix, canvas, cfg):
            self.panel_height = 64 if cfg.display_scan_rate == 32 else screen.HEIGHT
            if matrix is not None:
                # Came from splash screen - reuse the already-initialised panel
                self.panel = get_panel()
                self.canvas = canvas
                self.pre_initialised = True
            else:
                self.panel = get_panel()
                self.panel.init_matrix(
                    width=screen.WIDTH,
                    height=self.panel_height,
                    brightness=cfg.brightness_percent,
                    rotation=180 if cfg.screen_rotate else 0,
                    hat_pwm=cfg.hat_pwm_enabled,
                    gpio_slowdown=cfg.gpio_slowdown,
                    bonnet_type=cfg.bonnet_type,
                )
                self.canvas = self.panel.create_canvas()
                self.panel.clear(self.canvas)
                self.pre_initialised = False

        def _init_scenes(self, overhead, cfg):
            self.scene_manager = SceneManager(on_scene_error=self._on_scene_error)
            # The idle scene is the fallback: if it cannot be built there is
            # nothing left to show, so let that failure reach startup.
            self.scene_manager.register(IdleScene(self.canvas, self.panel))
            flight_ok = self._register_scene(
                lambda: FlightScene(
                    self.canvas, self.panel, overhead, REFRESH_INTERVAL
                ),
                "flight",
            )
            image_ok = self._register_scene(
                lambda: ImageScene(self.canvas, self.panel), "image"
            )
            if flight_ok and image_ok:
                logger.info("Registered scenes: Idle, Flight, Image")
            else:
                logger.info("Registered scenes: Idle (optional scenes skipped)")

            satellite_debug_preview = (
                cfg.debug_scene == "satellite" and cfg.satellite_test_mode
            )
            if cfg.satellite_tracking_enabled or satellite_debug_preview:
                try:
                    tle_manager = TLEManager()
                    if cfg.satellite_tracking_enabled and not satellite_debug_preview:
                        tle_manager.start()
                    registered = self._register_scene(
                        lambda: SatelliteScene(self.canvas, self.panel, tle_manager),
                        "satellite",
                    )
                    if registered:
                        if (
                            cfg.satellite_tracking_enabled
                            and not satellite_debug_preview
                        ):
                            logger.info(
                                "Satellite tracking enabled - registered Satellite "
                                "scene (NORAD ids: %s)",
                                cfg.satellite_norad_ids,
                            )
                        else:
                            logger.info(
                                "Satellite debug preview enabled - using a "
                                "simulated pass"
                            )
                except Exception:
                    logger.exception(
                        "Could not start satellite tracking; skipping the scene"
                    )
                    self._remember_scene_error("satellite")
            else:
                logger.info("Satellite tracking disabled")

            try:
                self._init_indycar(cfg)
            except Exception:
                logger.exception("Could not start the INDYCAR scenes; skipping them")
                self._remember_scene_error("indycar")

        def _register_scene(self, factory, label: str) -> bool:
            """Build and register a scene, skipping it if construction fails.

            A scene that cannot be built at startup used to stop the whole
            display from booting.  Now it is logged and the rest of the
            rotation starts, with the failure shown on the panel.
            """
            try:
                self.scene_manager.register(factory())
            except Exception:
                logger.exception("Could not build the %s scene; skipping it", label)
                self._remember_scene_error(label)
                return False
            return True

        def _remember_scene_error(self, label: str) -> None:
            """Queue a startup scene failure for the first display frame."""
            if self._pending_scene_error is None:
                self._pending_scene_error = label

        def _init_indycar(self, cfg):
            """Register the live INDYCAR scenes when enabled or previewing."""
            from scenes.indycar import ChampionScene, DriverScene, Top3Scene
            from utilities.indycar.monitor import IndyCarMonitor

            enabled = getattr(cfg, "indycar_enabled", False) is True
            test_mode = getattr(cfg, "indycar_test_mode", False) is True
            debug_scene = str(getattr(cfg, "debug_scene", "auto"))
            idle_theme = str(getattr(cfg, "idle_screen_theme", "classic"))
            include_in_cycle = getattr(cfg, "idle_cycle_include_indycar", False) is True
            idle_themes = getattr(cfg, "idle_screen_themes", None)
            if not isinstance(idle_themes, (list, tuple)):
                idle_themes = [idle_theme]

            # Selecting one of the INDYCAR debug scenes is an explicit
            # preview request.  Do not require test mode: the scene layer
            # supplies the bundled snapshot for the preview, so the forced
            # scene always has something to show.
            debug_preview = debug_scene in (
                "indy_top3",
                "indy_driver",
                "indy_champion",
            )
            idle_wants = (
                "indycar_next" in idle_themes
                or idle_theme == "indycar_next"
                or (idle_theme == "cycle" and include_in_cycle)
            )

            if not (enabled or debug_preview or idle_wants):
                logger.info("INDYCAR scenes disabled")
                return

            monitor = IndyCarMonitor.instance()
            if not (debug_preview or test_mode):
                monitor.start()

            if not (enabled or debug_preview):
                logger.info("INDYCAR live scenes disabled (idle screen only)")
                return

            # Register in this order: equal-priority scenes are sorted
            # stably, and the manager picks the last one, so a configured
            # tracked driver wins over the Top 3 scene.  The champion scene
            # has its own lower priority and a live-session guard.
            self.scene_manager.register(Top3Scene(self.canvas, self.panel, monitor))
            self.scene_manager.register(DriverScene(self.canvas, self.panel, monitor))
            self.scene_manager.register(ChampionScene(self.canvas, self.panel, monitor))
            if debug_preview:
                logger.info("INDYCAR debug preview enabled - using bundled snapshots")
            else:
                logger.info("Registered INDYCAR scenes: Top 3, Driver, Champion")

        def _init_timing(self, cfg):
            self.frames = frames
            self.frame_period = max(
                0.001, self.frames.PERIOD * cfg.display_speed_factor
            )
            self.brightness_update_interval = max(1, int(round(1 / self.frame_period)))
            self._error_frames = max(
                1, int(round(SCENE_ERROR_SECONDS / self.frame_period))
            )

        def _on_scene_error(self, label: str) -> None:
            """Show *label* on the panel for SCENE_ERROR_SECONDS."""
            self._error_label = label
            self._error_until_frame = self._frame + self._error_frames
            self._error_draw_failed = False

        def _draw_error_frame(self) -> None:
            try:
                draw_scene_error(
                    self.panel,
                    self.canvas,
                    self._error_label,
                    height=self.panel_height,
                )
            except Exception:
                if not self._error_draw_failed:
                    logger.exception("Could not draw the scene error message")
                    self._error_draw_failed = True
                # Give the normal rotation another go next frame.
                self._error_label = None
                self.scene_manager.current_scene = None

        def update_brightness(self):
            cfg = Config.instance()

            def brightness_schedule_simple():
                if cfg.is_in_brightness_schedule():
                    if self.panel.get_brightness() != cfg.schedule_brightness_percent:
                        self.panel.set_brightness(cfg.schedule_brightness_percent)
                        if cfg.schedule_brightness_percent == 0:
                            self.panel.clear(self.canvas)
                else:
                    if self.panel.get_brightness() != cfg.brightness_percent:
                        self.panel.set_brightness(cfg.brightness_percent)

            def brightness_schedule_advanced():
                percent = cfg.advanced_brightness_percent_at()
                if percent is None:
                    # No schedule entries - behave like "not in schedule".
                    if self.panel.get_brightness() != cfg.brightness_percent:
                        self.panel.set_brightness(cfg.brightness_percent)
                    return
                if self.panel.get_brightness() != percent:
                    self.panel.set_brightness(percent)
                    if percent == 0:
                        self.panel.clear(self.canvas)

            if cfg.brightness_mode == "advanced":
                brightness_schedule_advanced()
            else:
                brightness_schedule_simple()

        def _refresh_idle_rotation(self):
            """Rebuild the fallback idle scene after the date changes."""
            logger.info("Date changed - rebuilding the idle rotation")
            try:
                self.scene_manager.replace_fallback(IdleScene(self.canvas, self.panel))
            except Exception:
                # Keep the old rotation running and tell the owner.
                logger.exception("Could not rebuild the idle rotation")
                self._on_scene_error("idle")

        def run(self):
            print("Press CTRL-C to stop")

            if self.pre_initialised:
                self.panel.clear(self.canvas)
                self.panel.swap(self.canvas)

            self.panel.clear(self.canvas)

            if self._pending_scene_error is not None:
                self._on_scene_error(self._pending_scene_error)
                self._pending_scene_error = None

            frame = 0
            cfg = Config.instance()
            try:
                while True:
                    start = perf_counter()
                    self._frame = frame

                    today = date.today()
                    if today != self._idle_date:
                        self._idle_date = today
                        self._refresh_idle_rotation()

                    if not (frame % self.brightness_update_interval):
                        self.update_brightness()

                    if not cfg.is_in_device_standby():
                        if (
                            self._error_label is not None
                            and frame < self._error_until_frame
                        ):
                            self._draw_error_frame()
                        else:
                            if self._error_label is not None:
                                self._error_label = None
                                # Force a clean re-entry: scenes that only
                                # repaint changed pixels must redraw every
                                # pixel the error message covered.
                                self.scene_manager.current_scene = None
                            self.scene_manager.kick(cfg.debug_scene)
                            self.loading.tick(frame)

                    self.panel.swap(self.canvas)

                    frame += 1

                    elapsed = perf_counter() - start
                    sleep_time = self.frame_period - elapsed
                    if sleep_time < 0.001:
                        sleep_time = 0.001
                    sleep(sleep_time)

            except KeyboardInterrupt:
                print("Exiting\n")
                sys.exit(0)

    return Display


def get_display_class():
    global DisplayClass
    if DisplayClass is None:
        DisplayClass = build_display_class()
    return DisplayClass


def __getattr__(name):
    if name == "Display":
        return get_display_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
