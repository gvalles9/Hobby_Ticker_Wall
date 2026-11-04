"""
SatelliteScene - Az-El polar plot for overhead satellite passes.

Shown when one or more tracked satellites are currently above the configured
minimum elevation.  Priority 2 (beats FlightScene at 1 and IdleScene at 0).

Display layout:
    Centre Az-El circular plot (horizon ring, north notch, trajectory arcs,
          bright current-position dots).
    Right  Cycling name + telemetry (speed / altitude), each satellite
          rendered in its matching palette colour.

Data flow:
    TLEManager  ->  passes.compute_passes()  ->  list[PassWindow]
    poll() checks whether any PassWindow is active right now.
    draw() reads pre-baked trajectory data - no orbital math per frame.
"""

from __future__ import annotations

import datetime
import logging

from display.rgbpanel import Colour
from display.spans import PlacedSpan, Span, font_text_width
from scenes.satellite import azel_plot
from scenes.satellite import passes as passes_mod
from setup import fonts, frames, screen
from setup.colours import PEACH, PINK, WHITE, YELLOW
from setup.configuration import Config

logger = logging.getLogger(__name__)

PRIORITY = 2

# How long (in seconds) to display each satellite's telemetry before cycling
CYCLE_INTERVAL_S = 4

# When TLE data is unavailable, back off instead of recomputing every poll
# tick: the TLE manager runs its own fetch/backoff schedule, so the scene
# only needs to re-check for data periodically.  Without this, a CelesTrak
# outage re-logs the skip warning every frame.  The skip warning itself is
# rate-limited to once per NO_TLE_LOG_INTERVAL seconds.
NO_TLE_RETRY_SECONDS = 60
NO_TLE_LOG_INTERVAL = 600

# Satellite data column positions (extrasmall 4x6 font)
DATA_COL_X = (4, screen.WIDTH - 40)
NAME_RIGHT_MARGIN = 4
NAME_Y = 5  # satellite name (yellow)
# blank line at y=6
ROW_LAYOUT = ((13, 19), (25, 31))


class SatelliteScene:
    """
    Priority-2 scene.  Shows overhead satellite passes on an Az-El polar plot
    with cycling name and telemetry in the left panel.
    """

    priority = PRIORITY
    debug_name = "satellite"

    def __init__(self, canvas, panel, tle_manager):
        self.canvas = canvas
        self.panel = panel
        self.tle_manager = tle_manager

        self.frame: int = 0
        self.pass_windows: list[passes_mod.PassWindow] = []
        self.windows_computed_at: float = 0.0
        self.last_test_mode: bool | None = None

        # Which satellite's telemetry is currently shown in the right panel
        self.cycle_index: int = 0
        self.last_cycle_second: float = 0.0

        # Track drawn positions so we can update only when the pixel changes.
        # name -> (px, py, tle_index)
        self.last_positions: dict[str, tuple[int, int, int]] = {}

        # Blink state for the position dot (toggles every 0.5 s)
        self.blink_on: bool = True
        self.last_blink_on: bool = True

        # Stash previous text draws so we can erase only what changed
        self.last_text: dict[str, PlacedSpan] = {}

        # Whether the ring has been drawn yet (drawn once on enter, redrawn on reset)
        self.ring_drawn: bool = False

        # TLE-unavailability holdoff: recompute happens at most once per
        # NO_TLE_RETRY_SECONDS while pass data is unavailable (the TLE
        # manager fetches on its own schedule), and the skip warning is
        # logged at most once per NO_TLE_LOG_INTERVAL seconds.
        self.next_recompute_at: float = 0.0
        self.last_no_tle_logged_at: float = 0.0

    # ------------------------------------------------------------------
    # Scene protocol
    # ------------------------------------------------------------------

    def poll(self) -> None:
        """Refresh pass windows when stale; no-op otherwise."""
        cfg = Config.instance()
        now_ts = datetime.datetime.utcnow().timestamp()

        self.prune_expired_passes()

        # Recompute if windows haven't been built yet, are all expired,
        # or are older than 1 hour (to catch new passes that overlap
        # with currently active ones).
        test_mode_enabled = cfg.satellite_test_mode and cfg.debug_scene == "satellite"
        test_mode_changed = (
            self.last_test_mode is not None and test_mode_enabled != self.last_test_mode
        )
        needs_refresh = (
            not self.pass_windows
            or all(w.los.timestamp() < now_ts for w in self.pass_windows)
            or (now_ts - self.windows_computed_at) > 3600
            or test_mode_changed
        )

        if needs_refresh and (now_ts >= self.next_recompute_at or test_mode_changed):
            self.recompute_passes(cfg)

    def has_data(self) -> bool:
        cfg = Config.instance()
        return bool(
            passes_mod.visible_passes(
                self.pass_windows,
                cfg.satellite_timeout_enabled,
                cfg.satellite_timeout_seconds,
            )
        )

    def active(self) -> bool:
        return self.has_data()

    def on_enter(self) -> None:
        """Called by SceneManager on scene transition."""
        self.panel.clear(self.canvas)
        self.reset()

    def reset(self) -> None:
        self.frame = 0
        self.cycle_index = 0
        self.last_cycle_second = 0.0
        self.last_positions = {}
        self.last_text = {}
        self.blink_on = True
        self.last_blink_on = True
        self.ring_drawn = False

    def draw(self) -> None:
        self.frame += 1

        active = passes_mod.current_passes(self.pass_windows)
        if not active:
            return

        cfg = Config.instance()
        max_count = min(cfg.satellite_max_count, len(active))
        active = active[:max_count]

        # Draw ring once (persists across frames)
        if not self.ring_drawn:
            # Clear plot area before redrawing ring + trajectories
            self.panel.draw_square(
                self.canvas,
                azel_plot.PLOT_CX - azel_plot.PLOT_RADIUS - 1,
                0,
                azel_plot.PLOT_CX + azel_plot.PLOT_RADIUS + 1,
                screen.HEIGHT,
                Colour(0, 0, 0),
            )
            azel_plot.draw_horizon_ring(self.panel, self.canvas)
            self.draw_trajectories(active)
            self.ring_drawn = True

        # Update current-position dots
        self.draw_positions(active)

        # Update right-panel text at ~1 fps
        if self.frame % int(frames.PER_SECOND) == 0:
            self.update_text_panel(active)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def recompute_passes(self, cfg) -> None:
        now_ts = datetime.datetime.utcnow().timestamp()
        # Every path leaves a short cooldown so a failing or empty
        # computation does not re-run on every poll tick (pass geometry
        # barely moves in a minute; recomputing SGP4 per frame was the
        # spam source during CelesTrak outages).
        self.next_recompute_at = now_ts + NO_TLE_RETRY_SECONDS
        self._recompute_passes(cfg, now_ts)

    def _recompute_passes(self, cfg, now_ts: float) -> None:
        test_mode = cfg.satellite_test_mode and cfg.debug_scene == "satellite"
        self.last_test_mode = test_mode
        tles = [] if test_mode else self.tle_manager.try_get()
        if not test_mode and not tles:
            # Hold off: the TLE manager is fetching (or backing off) in its
            # own loop.  Warn only once per log interval - a prolonged
            # CelesTrak outage must not spam the log.
            if now_ts - self.last_no_tle_logged_at >= NO_TLE_LOG_INTERVAL:
                logger.warning(
                    "Satellite pass computation skipped - no TLE data available"
                    " (retry in %ds)",
                    NO_TLE_RETRY_SECONDS,
                )
                self.last_no_tle_logged_at = now_ts
            return
        try:
            self.pass_windows = passes_mod.compute_passes(
                tles,
                cfg.observer_lat,
                cfg.observer_lng,
                cfg.satellite_min_elevation,
                cfg.satellite_max_count,
                test_mode=test_mode,
            )
            self.windows_computed_at = datetime.datetime.utcnow().timestamp()
            # Force redraw of ring + trajectories on next draw()
            self.ring_drawn = False
            self.last_positions = {}
            # Allow the next unavailability to warn immediately again.
            self.last_no_tle_logged_at = 0.0
            logger.debug(
                "Pass computation complete - %d pass window(s) for %d satellite(s) "
                "(min elevation %d°)",
                len(self.pass_windows),
                len(tles),
                cfg.satellite_min_elevation,
            )
        except Exception as exc:
            logger.error("Satellite pass computation failed: %s", exc)

    def prune_expired_passes(self) -> None:
        """Remove pass windows that have already finished."""
        now = datetime.datetime.utcnow()
        self.pass_windows = [w for w in self.pass_windows if w.los >= now]

    def draw_trajectories(self, active: list[passes_mod.PassWindow]) -> None:
        """Paint dim trajectory arcs for all currently active passes."""
        for window in active:
            traj_2d = [(az, el) for az, el, _, _ in window.trajectory]
            azel_plot.draw_trajectory(
                self.panel, self.canvas, traj_2d, window.tle_index
            )

    def draw_positions(self, active: list[passes_mod.PassWindow]) -> None:
        """
        Update satellite position dots using a pixel-change-only strategy.

        The dot blinks at a 0.5 s cadence: bright when "on", dim when "off".
        On each frame the current Az/El is converted to a pixel.  If the
        pixel is the same as last frame *and* the blink state hasn't changed,
        nothing happens.  When either changes:
          - the old pixel is repainted in the DIM (trail) colour
          - the new pixel is painted in BRIGHT (blink on) or DIM (blink off)

        This avoids redrawing the entire trajectory every frame and
        eliminates flicker.
        """
        # Blink toggle: flip every 0.5 s
        blink_frames = int(frames.PER_SECOND * 0.5)
        self.blink_on = (self.frame // blink_frames) % 2 == 0

        new_positions: dict[str, tuple[int, int, int]] = {}

        for window in active:
            pos = passes_mod.current_position(window)
            if pos is None:
                continue
            az, el = pos
            px, py = azel_plot.azel_to_xy(az, el)
            new_positions[window.name] = (px, py, window.tle_index)

            old = self.last_positions.get(window.name)
            if old is None or self.blink_on != self.last_blink_on:
                # First frame or blink toggled - redraw
                if old is not None:
                    old_px, old_py, old_idx = old
                    azel_plot.draw_trail_pixel(
                        self.panel, self.canvas, old_px, old_py, old_idx
                    )
                if self.blink_on:
                    azel_plot.draw_position(
                        self.panel, self.canvas, az, el, window.tle_index
                    )
                else:
                    azel_plot.draw_trail_pixel(
                        self.panel, self.canvas, px, py, window.tle_index
                    )
            else:
                old_px, old_py, old_idx = old
                if (px, py) != (old_px, old_py):
                    # Pixel changed: dim the old, draw the new (respecting blink)
                    azel_plot.draw_trail_pixel(
                        self.panel, self.canvas, old_px, old_py, old_idx
                    )
                    if self.blink_on:
                        azel_plot.draw_position(
                            self.panel, self.canvas, az, el, window.tle_index
                        )
                    else:
                        azel_plot.draw_trail_pixel(
                            self.panel, self.canvas, px, py, window.tle_index
                        )

        # Dim any satellites that were active last frame but aren't now
        for name, (old_px, old_py, old_idx) in self.last_positions.items():
            if name not in new_positions:
                azel_plot.draw_trail_pixel(
                    self.panel, self.canvas, old_px, old_py, old_idx
                )

        self.last_positions = new_positions
        self.last_blink_on = self.blink_on

    def update_text_panel(self, active: list[passes_mod.PassWindow]) -> None:
        """
        Render the currently cycled satellite's name and telemetry.

        Layout (extrasmall 4x6 font):
            Top: satellite name
            Two rows: configured fields, each with a label and value/unit

        Uses a stash-and-erase strategy: old text is redrawn in black
        before new text is drawn on top, so only changed pixels are touched.
        """
        now_s = datetime.datetime.utcnow().timestamp()

        # Advance the cycle counter once per CYCLE_INTERVAL_S
        if now_s - self.last_cycle_second >= CYCLE_INTERVAL_S:
            self.cycle_index = (self.cycle_index + 1) % len(active)
            self.last_cycle_second = now_s

        window = active[self.cycle_index % len(active)]

        # Current position and derived telemetry feed the configurable rows.
        pos = passes_mod.current_position(window)
        az = el = None
        if pos is not None:
            az, el = pos
            telemetry = compute_telemetry(window, az, el)
        else:
            telemetry = None
        cfg = Config.instance()
        fields = cfg.satellite_data_points

        # Build the set of text elements for this frame.
        # Each entry is a PlacedSpan (a Span positioned at an x, y baseline).
        f = fonts.extrasmall
        name_width = font_text_width(f, window.name)
        name_x = max(
            0,
            min(DATA_COL_X[1], screen.WIDTH - name_width - NAME_RIGHT_MARGIN),
        )
        new_texts: dict[str, PlacedSpan] = {
            "name": PlacedSpan(Span(YELLOW, f, window.name), name_x, NAME_Y),
        }

        for index, field in enumerate(fields):
            label, value, unit = format_satellite_data(field, az, el, telemetry, cfg, window)
            column_x = DATA_COL_X[index // 2]
            label_y, value_y = ROW_LAYOUT[index % 2]
            row = index + 1
            new_texts[f"row{row}_label"] = PlacedSpan(
                Span(PEACH, f, label), column_x, label_y
            )
            value_key = f"row{row}_value"
            unit_key = f"row{row}_unit"
            new_texts[value_key] = PlacedSpan(
                Span(WHITE, f, value), column_x, value_y
            )
            new_texts[unit_key] = PlacedSpan(Span(PINK, f, unit), column_x, value_y)
            value_width = font_text_width(f, value)
            new_texts[unit_key] = new_texts[unit_key]._replace(
                x=column_x + value_width
            )

        black = Colour(0, 0, 0)

        for key, ps in new_texts.items():
            old = self.last_text.get(key)
            if old is not None and old != ps:
                # Erase the old text if anything changed (text, position, font, or colour)
                self.panel.draw_text(
                    self.canvas, old.span.font, old.x, old.y, black, old.span.text
                )
            self.panel.draw_text(
                self.canvas, ps.span.font, ps.x, ps.y, ps.span.colour, ps.span.text
            )

        self.last_text = new_texts


def format_satellite_data(
    field: str,
    azimuth: float | None,
    elevation: float | None,
    telemetry: tuple[float, float] | None,
    cfg,
    window: passes_mod.PassWindow | None = None,
) -> tuple[str, str, str]:
    """Return a satellite data field's label, display value, and unit."""
    if field == "azimuth":
        if azimuth is None:
            return "Azimuth", "--", ""
        return "Azimuth", f"{round(azimuth) % 360:03d}", "deg"
    if field == "elevation":
        if elevation is None:
            return "Elevation", "--", ""
        return "Elevation", f"{round(elevation):02d}", "deg"

    # New window-based fields (don't depend on telemetry)
    if field == "range":
        range_km = get_current_range(window)
        if range_km is None:
            return "Range", "--", ""
        return "Range", str(int(range_km)), "km"
    if field == "time_to_aos":
        if window is None:
            return "To AOS", "--", ""
        now = datetime.datetime.utcnow()
        if window.aos <= now:
            return "To AOS", "0", "s"
        seconds = int((window.aos - now).total_seconds())
        return "To AOS", str(seconds), "s"
    if field == "time_to_los":
        if window is None:
            return "To LOS", "--", ""
        now = datetime.datetime.utcnow()
        if window.los <= now:
            return "To LOS", "0", "s"
        seconds = int((window.los - now).total_seconds())
        return "To LOS", str(seconds), "s"
    if field == "pass_duration":
        if window is None:
            return "Duration", "--", ""
        seconds = int((window.los - window.aos).total_seconds())
        return "Duration", str(seconds), "s"
    if field == "max_elevation":
        if window is None:
            return "Max El", "--", ""
        return "Max El", f"{round(window.max_el):02d}", "deg"

    # Telemetry-dependent fields
    if telemetry is None:
        return ("Speed" if field == "speed" else "Altitude"), "--", ""

    speed_kmh, altitude_km = telemetry
    if field == "speed":
        if cfg.speed_unit == "mph":
            return "Speed", str(int(speed_kmh * 0.621371)), "mph"
        if cfg.speed_unit == "kts":
            return "Speed", str(int(speed_kmh * 0.539957)), "kts"
        return "Speed", str(int(speed_kmh)), "km/h"
    if field == "altitude":
        if cfg.height_unit == "ft":
            return "Altitude", str(int(altitude_km * 3280.84)), "ft"
        return "Altitude", str(int(altitude_km * 1000)), "m"

    return field, "--", ""


# ---------------------------------------------------------------------------
# Telemetry helpers
# ---------------------------------------------------------------------------


def get_current_range(window: passes_mod.PassWindow | None) -> float | None:
    """
    Get the current slant range to the satellite from the trajectory.
    Returns range in km, or None if unavailable.
    """
    if window is None or not window.trajectory:
        return None

    now = datetime.datetime.utcnow()

    # Find the trajectory segment containing the current time
    for i in range(len(window.trajectory) - 1):
        _, _, rng0, t0 = window.trajectory[i]
        _, _, rng1, t1 = window.trajectory[i + 1]
        if t0 <= now <= t1:
            span = (t1 - t0).total_seconds()
            if span <= 0:
                return rng0
            frac = (now - t0).total_seconds() / span
            return rng0 + (rng1 - rng0) * frac

    # If current time is outside the trajectory range, return the closest endpoint
    if now < window.trajectory[0][3]:
        _, _, rng, _ = window.trajectory[0]
        return rng
    _, _, rng, _ = window.trajectory[-1]
    return rng


def compute_telemetry(
    window: passes_mod.PassWindow,
    az_deg: float,
    el_deg: float,
) -> tuple[float, float] | None:
    """
    Estimate orbital speed and altitude from the pass trajectory.

    Uses consecutive trajectory samples to derive instantaneous speed,
    and reads altitude directly from pre-baked trajectory range data.

    Returns (speed_kmh, altitude_km), or None if unavailable.
    """
    import math

    # Find the two trajectory samples that bracket the current time
    now = datetime.datetime.utcnow()
    traj = window.trajectory

    for i in range(len(traj) - 1):
        _, _, _, t0 = traj[i]
        _, _, _, t1 = traj[i + 1]
        if t0 <= now <= t1:
            az0, el0, rng0, _ = traj[i]
            az1, el1, rng1, _ = traj[i + 1]

            dt = (t1 - t0).total_seconds()
            if dt > 0:
                # Azimuth delta with wrap-around handling
                daz = math.radians(((az1 - az0 + 180) % 360) - 180)
                del_ = math.radians(el1 - el0)
                # Approximate angular speed (small-angle approx, fine for 10 s steps)
                ang_speed_deg_s = math.sqrt(daz**2 + del_**2) * (180 / math.pi) / dt

                # Interpolate altitude at current time
                frac = (now - t0).total_seconds() / dt
                alt_km = rng0 + (rng1 - rng0) * frac

                # Slant range from observer: solve triangle Earth-observer-satellite
                EARTH_R = 6371.0
                el_rad = math.radians(max(1.0, (el0 + el1) / 2))
                slant_km = -EARTH_R * math.sin(el_rad) + math.sqrt(
                    (EARTH_R * math.sin(el_rad)) ** 2 + 2 * EARTH_R * alt_km + alt_km**2
                )

                speed_kmh = math.radians(ang_speed_deg_s) * slant_km * 3600
                return speed_kmh, alt_km

            break

    return None
