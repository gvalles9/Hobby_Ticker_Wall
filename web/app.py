"""
FlightTracker web configuration interface.

Runs as a Flask daemon thread on port 8584.
GET  /               -> redirect to /settings (or /first-setup on first run)
GET  /login          -> login form
POST /login          -> check password, set session
GET  /logout         -> clear session, redirect to /login
GET  /settings       -> settings form (requires login)
POST /settings       -> save config.json, return restarting page, exec after 1 s
GET  /first-setup    -> guided first-use wizard (requires login)
POST /first-setup    -> save wizard answers + new web password, then restart
POST /settings/reset -> restore application defaults (keeps Wi-Fi + password)
POST /password/reset -> restore the default web password, reopen the wizard
POST /wifi-setup/reset -> reopen the setup hotspot (keeps saved credentials)
POST /wifi-setup/forget -> delete saved Wi-Fi networks and open the hotspot
POST /handoff/reset  -> full handoff reset: defaults + password + Wi-Fi
GET  /ping           -> health-check used by the restarting page
GET  /update         -> update status page (requires login)
POST /update/check   -> check for updates, return JSON (requires login)
POST /update/apply   -> apply update via git + pip, then restart (requires login)
GET  /debug-config   -> download config JSON with secrets redacted
GET  /logs           -> view in-memory log buffer
GET  /logs/download  -> download full log buffer as .txt
"""

from __future__ import annotations

import contextlib
import copy
import functools
import hashlib
import json
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from display.rgbpanel import PANEL_COLOUR_ORDERS
from setup.configuration import (
    BONNET_TYPES,
    CONFIG_PATH,
    DEFAULT_BONNET_TYPE,
    DEFAULTS,
    PLATFORM_DATA_DIR,
    Config,
    _migrate_provider_lists,
)
from setup.logging import get_buffer
from utilities import ssh_access
from utilities.flight import Flight
from utilities.lookups import cache as routes_cache
from utilities.lookups import usage as usage_tally
from utilities.tle_manager import TLE_CACHE_PATH, TLE_CACHE_TTL
from utilities.updater import (
    GITHUB_REPOSITORY_URL,
    compare_versions,
    get_update_info,
    perform_update,
    version_string,
)
from version import APP_VERSION, VERSION

# Port is read from config.json via Config.web_port (default 8584).
FLASK_PORT = Config.instance().web_port

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app_ready = threading.Event()

logger = logging.getLogger("web")


@app.context_processor
def _inject_version():
    """Make the app version available to every template (footer, etc.)."""
    return {"app_version": f"Hobby Ticker {version_string(APP_VERSION)}"}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(password: str) -> bool:
    return hash_password(password) == Config.instance().web_password_hash


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def validate_csrf(form) -> bool:
    return str(form.get("csrf_token", "")) == session.get("csrf_token")


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# Coerce helpers
# ---------------------------------------------------------------------------


def str_val(v, default="") -> str:
    return str(v) if v is not None else default


def int_val(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def float_val(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def bool_val(v) -> bool:
    """HTML checkboxes send 'on' when checked, nothing when unchecked."""
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("on", "true", "1", "yes")


def wrap_lng(lng: float) -> float:
    """Wrap any longitude to the range [-180, 180).

    Guards against values > 180 or < -180 that the Leaflet map could
    produce when worldCopyJump was not enabled.
    """
    return ((lng + 180) % 360 + 360) % 360 - 180


# ---------------------------------------------------------------------------
# Live-data helpers
# ---------------------------------------------------------------------------


def _select_overhead_class():
    """Return the Overhead facade and the top flight provider's display name."""
    from utilities.lookups.flights import top_flight_provider
    from utilities.overhead import Overhead

    _pid, source_name = top_flight_provider()
    return Overhead, source_name or "No provider configured"


def _flatten_debug_rows(value, prefix="") -> list[dict[str, str]]:
    """Flatten nested dict values into dotted-key rows, skipping lists and blanks."""
    rows = []
    if isinstance(value, dict):
        for key, child in sorted(value.items()):
            new_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(child, dict):
                rows.extend(_flatten_debug_rows(child, new_prefix))
            elif isinstance(child, list) or child is None:
                continue
            else:
                rows.append({"key": new_prefix, "value": str(child)})
    return rows


def _build_weather_current_rows(weather_data: dict | None) -> list[dict[str, str]]:
    """Build a flat key/value table for the current weather payload."""
    if not isinstance(weather_data, dict):
        return []
    rows = []
    for row in _flatten_debug_rows(weather_data):
        if row["value"] not in ("", None):
            rows.append(row)
    return rows


def _build_forecast_rows(forecast_data: list | None) -> tuple[list[dict], list[str]]:
    """Build a row-per-day forecast table using the union of available fields."""
    if not isinstance(forecast_data, list):
        return [], []

    columns = sorted(
        {key for day in forecast_data if isinstance(day, dict) for key in day}
    )
    rows = []
    for index, day in enumerate(forecast_data, start=1):
        if not isinstance(day, dict):
            continue
        row = {"day": f"Day {index}"}
        for column in columns:
            value = day.get(column)
            row[column] = "" if value is None else str(value)
        rows.append(row)
    return rows, columns


def _build_flight_rows(flights: list) -> tuple[list[dict], list[str]]:
    """Build a flat debug table for all flight objects."""
    from dataclasses import fields

    excluded_fields = {
        "origin_name",
        "destination_name",
        "registration",
        "origin_municipality",
        "destination_municipality",
        "origin_country",
        "destination_country",
    }
    field_names = [
        field.name for field in fields(Flight) if field.name not in excluded_fields
    ]
    rows = []
    for flight in flights:
        row = {}
        for field_name in field_names:
            value = getattr(flight, field_name, None)
            row[field_name] = "" if value is None else str(value)
        rows.append(row)
    return rows, field_names


def _format_last_updated_value(timestamp) -> str:
    """Format an epoch timestamp into a human-readable string."""
    if timestamp is None:
        return ""
    try:
        import datetime as _dt

        return _dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return ""


def _get_live_data_overhead() -> tuple[object, str]:
    """Return the shared overhead instance already owned by the display flow."""
    from display import get_overhead_instance

    overhead = get_overhead_instance()
    _, data_source_name = _select_overhead_class()
    return overhead, data_source_name


# ---------------------------------------------------------------------------
# Restart helper
# ---------------------------------------------------------------------------


def restart_after(delay: float = 1.0):
    """Schedule os.execv after `delay` seconds on a daemon thread."""

    # os.execv bypasses atexit, so persist the usage tallies now - every
    # restart path funnels through here.
    from utilities.lookups import usage as usage_tally

    usage_tally.flush()

    def do_restart():
        import time

        time.sleep(delay)
        logger.info("Restarting process: %s %s", sys.executable, sys.argv)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=do_restart, daemon=True, name="restart").start()


# ---------------------------------------------------------------------------
# Backup import / export helpers
# ---------------------------------------------------------------------------

# Files used by the swap-on-boot import mechanism (see flight-tracker.py).
# The web layer only writes CONFIG_UPDATE_PATH; the boot logic handles the
# rest.  Kept here so both modules share a single source of truth.
CONFIG_UPDATE_PATH = PLATFORM_DATA_DIR / "config-update.json"
CONFIG_BACKUP_PATH = PLATFORM_DATA_DIR / "config-backup.json"
IMPORT_IN_PROGRESS_MARKER = PLATFORM_DATA_DIR / ".import-in-progress"
IMPORT_FAILED_MARKER = PLATFORM_DATA_DIR / ".import-failed"


def build_backup_dict(cfg: Config) -> dict:
    """Return a copy of the current config tagged with the running version.

    The ``_version`` key is forced to :data:`VERSION` so the export always
    reflects the software that produced it, even if the on-disk config
    carries a stale value from an older release.
    """
    data = dict(cfg.as_dict())
    data["_version"] = list(VERSION)
    return data


def parse_backup_json(raw: bytes) -> tuple[dict | None, list[int] | None, str | None]:
    """Parse an uploaded backup file.

    Returns ``(data, backup_version, error)``.  On success ``error`` is
    ``None`` and ``data`` is the parsed dict.  ``backup_version`` is the
    ``_version`` list from the file, or ``None`` when the key is absent
    (e.g. an export from before version tagging existed).

    Validation is intentionally minimal and permissive: only valid JSON
    and a top-level dict are required.  No key checks against ``DEFAULTS``
    are performed, so backups from newer or older FlightTracker versions
    are accepted - the version-mismatch warning is the user's informed
    consent, and ``Config.load()`` merges unknown/missing keys gracefully.
    An empty ``{}`` is accepted (it merges to ``DEFAULTS`` on load).
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, None, f"File is not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, None, "File is not a valid config (expected a JSON object)."
    version = data.get("_version")
    if version is not None and (
        not isinstance(version, list) or not all(isinstance(n, int) for n in version)
    ):
        version = None
    return data, version, None


def _consume_import_failed_marker() -> bool:
    """Return True if a failed-import marker was present, and delete it.

    Called by the settings route so the user sees a one-shot alert after
    a crashed import was auto-restored on boot.
    """
    try:
        IMPORT_FAILED_MARKER.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Settings form parsing
# ---------------------------------------------------------------------------


def _parse_provider_form(form, cfg) -> dict:
    """Parse the Lookup Priority page's two reorderable lists.

    The Vue app submits the ordered, enable-toggled provider lists as JSON
    strings under ``flight_providers_json`` / ``route_providers_json``.
    Missing keys leave the configured order untouched.
    """
    import json as _json

    out: dict = {}
    for key, capability, config_key in (
        ("flight_providers_json", "flights", "flight_providers"),
        ("route_providers_json", "routes", "route_providers"),
    ):
        raw = form.get(key)
        if not raw:
            continue
        try:
            order = _json.loads(raw)
        except ValueError:
            logger.warning("Ignoring malformed %s payload", key)
            continue
        if not isinstance(order, list):
            continue
        from utilities.lookups.registry import normalise_provider_list

        clean, warnings = normalise_provider_list(order, capability)
        if clean:
            out[config_key] = clean
        for w in warnings:
            logger.warning("[providers] %s", w)
    return out


def _parse_schedule_advanced_form(form) -> dict:
    """Parse the advanced brightness schedule submitted as JSON.

    The Vue app serialises the schedule rows into a hidden
    ``screen_schedule_advanced_json`` input.  Missing or malformed
    payloads leave the configured schedule untouched; valid payloads are
    validated, deduped (last occurrence wins) and sorted by time.
    """
    import json as _json

    from setup.configuration import _parse_schedule_time

    raw = form.get("screen_schedule_advanced_json")
    if not raw:
        return {}
    try:
        entries = _json.loads(raw)
    except ValueError:
        logger.warning("Ignoring malformed screen_schedule_advanced_json payload")
        return {}
    if not isinstance(entries, list):
        return {}

    cleaned: dict[int, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        t = _parse_schedule_time(entry.get("time"))
        if t is None:
            continue
        try:
            brightness = max(0, min(5, int(entry.get("brightness", 0))))
        except (TypeError, ValueError):
            continue
        cleaned[t.hour * 60 + t.minute] = {
            "time": t.strftime("%H:%M"),
            "brightness": brightness,
        }
    return {"screen_schedule_advanced": [cleaned[m] for m in sorted(cleaned)]}


def _parse_provider_settings(form, cfg) -> dict[str, dict]:
    """Collect ``providers.<pid>.<field>`` form keys into a settings subtree.

    Sensitive fields use mask-token semantics (via
    :func:`lookups.config.apply_submitted_settings`): the masked sentinel
    keeps the stored value, "" clears it, anything else replaces it.  Only
    providers actually present in the form are returned, so unrelated
    providers' settings are never touched by this form submission.
    """
    from utilities.lookups.config import apply_submitted_settings
    from utilities.lookups.registry import PROVIDERS

    collected: dict[str, dict[str, str]] = {}
    prefix = "providers."
    for key in form:
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].split(".")
        if len(parts) != 2:
            continue
        pid, field_key = parts
        if pid not in PROVIDERS:
            continue
        # HTML checkboxes only post when ticked, so the Vue bool fields
        # pair a hidden "false" input with the checkbox; the last posted
        # value wins (checked -> "on" after "false", unchecked -> just
        # "false").  Plain dicts (tests) have no getlist - a single
        # value is all they can hold anyway.
        getlist = getattr(form, "getlist", None)
        values = getlist(key) if getlist is not None else [form.get(key, "")]
        collected.setdefault(pid, {})[field_key] = str(values[-1]) if values else ""

    subtree: dict[str, dict] = {}
    for pid, fields in collected.items():
        spec = PROVIDERS[pid]
        stored = cfg.provider_settings(pid)
        clean, _changed = apply_submitted_settings(spec.config, stored, fields)
        subtree[pid] = clean
    return subtree


def _merge_provider_settings(cfg, partial: dict) -> dict:
    """Validate *partial* provider settings and merge them into the stored subtree."""
    from utilities.lookups.config import validate_provider_settings
    from utilities.lookups.registry import PROVIDERS

    merged = cfg.providers_subtree
    for pid, settings in partial.items():
        spec = PROVIDERS.get(pid)
        if spec is None:
            continue
        clean, warnings = validate_provider_settings(spec.config, settings)
        for warning in warnings:
            logger.warning("[providers] %s", warning)
        merged[pid] = clean
    return merged


# Human labels for the idle scenes, shared by the settings page and the
# first-setup wizard (kept in the same order as IDLE_SCREEN_THEMES).
IDLE_THEME_META = {
    "classic": ("Classic", "clock, date and current weather"),
    "forecast": ("Forecast", "upcoming weather icons"),
    "conditions": ("Current Conditions", "weather at a glance"),
    "indycar_next": ("INDYCAR next event", "next race countdown"),
    "birthday": ("Happy Birthday", "celebration scene on that date"),
}


def _form_values(form, key: str) -> list[str]:
    """Return every submitted value for *key* (``getlist``-aware)."""
    values = form.getlist(key) if hasattr(form, "getlist") else form.get(key, [])
    if isinstance(values, str):
        return [values]
    if values is None:
        return []
    return [str(value) for value in values]


def _parse_selected_idle_themes(form, cfg, allowed) -> list[str]:
    """Read the idle-scene checkboxes, falling back to the legacy field."""
    submitted = _form_values(form, "idle_screen_themes")
    list_submitted = bool(submitted) or bool(form.get("idle_screen_themes_submitted"))

    if not list_submitted:
        # Older browser pages (and API callers) only send the single-theme
        # field.  Expand ``cycle`` exactly like Config.idle_screen_themes.
        legacy = str_val(
            form.get("idle_screen_theme"),
            getattr(cfg, "idle_screen_theme", "cycle"),
        ).lower()
        if legacy == "cycle":
            themes = ["classic", "forecast"]
            if bool_val(form.get("idle_cycle_include_indycar")):
                themes.append("indycar_next")
            return themes
        return [legacy] if legacy in allowed else ["classic"]

    selected: list[str] = []
    for value in submitted:
        name = str(value).strip().lower()
        if name == "cycle":
            for expanded in ("classic", "forecast"):
                if expanded not in selected:
                    selected.append(expanded)
        elif name in allowed and name not in selected:
            selected.append(name)
    # Never save an empty selection - the idle screen must always draw.
    return selected or ["classic"]


def _idle_theme_fields(idle_themes: list[str]) -> dict:
    """Config keys derived from a validated idle-theme selection."""
    return {
        "idle_screen_themes": idle_themes,
        "idle_screen_theme": (
            "cycle" if idle_themes == ["classic", "forecast"] else idle_themes[0]
        ),
        "idle_cycle_include_indycar": "indycar_next" in idle_themes,
    }


def _parse_birthday_date_field(form, cfg) -> str:
    """Normalise the birthday-date input.

    An explicitly submitted field wins: a valid date is kept, anything
    invalid clears the date (which disables the scene).  A missing key
    (partial/API submissions) keeps the saved date.
    """
    from utilities.birthday import parse_birthday_date

    current = str(getattr(cfg, "birthday_date", "") or "").strip()
    submitted = form.get("birthday_date")
    if submitted is None:
        return current
    # An explicitly empty field clears the date and disables the scene.
    value = str(submitted).strip()[:10]
    if value and parse_birthday_date(value) is None:
        return ""
    return value


def _unit_profile_fields(form, cfg) -> dict:
    """Parse the independent metric/standard unit profiles.

    Blank or invalid submissions keep the current profile so partial
    forms (and the first-setup wizard) never reset units silently.
    """
    from setup.configuration import unit_profile_values

    current_flight_units = getattr(cfg, "flight_units", "")
    if current_flight_units not in ("metric", "standard"):
        current_flight_units = (
            "standard"
            if getattr(cfg, "height_unit", "m") == "ft"
            or getattr(cfg, "speed_unit", "kmh") in ("mph", "kts")
            else "metric"
        )
    current_idle_units = getattr(cfg, "idle_units", "")
    if current_idle_units not in ("metric", "standard"):
        current_idle_units = (
            "standard" if getattr(cfg, "temperature_unit", "f") == "f" else "metric"
        )
    flight_units = str_val(form.get("flight_units"), current_flight_units).lower()
    if flight_units not in ("metric", "standard"):
        flight_units = current_flight_units
    idle_units = str_val(form.get("idle_units"), current_idle_units).lower()
    if idle_units not in ("metric", "standard"):
        idle_units = current_idle_units
    return {
        "flight_units": flight_units,
        "idle_units": idle_units,
        **unit_profile_values(flight_units, idle_units),
    }


def parse_first_setup_form(form, cfg) -> dict:
    """Parse the first-setup wizard form.

    A subset of the settings form: the bonnet type is required, and every
    other value keeps its current (or default) state when the section is
    left untouched.  The web password is validated and stored by the
    route, not here.
    """
    from setup.configuration import IDLE_SCREEN_THEMES

    idle_themes = _parse_selected_idle_themes(form, cfg, IDLE_SCREEN_THEMES)
    birthday_date = _parse_birthday_date_field(form, cfg)
    return {
        # Required: LED matrix bonnet (invalid values fall back to default)
        "bonnet_type": (lambda v: v if v in BONNET_TYPES else DEFAULT_BONNET_TYPE)(
            str_val(form.get("bonnet_type"), DEFAULT_BONNET_TYPE).lower()
        ),
        # Optional: location - blank keeps the current (auto-detected) spot
        "flight_lat": float_val(form.get("flight_lat"), cfg.flight_lat),
        "flight_lng": wrap_lng(float_val(form.get("flight_lng"), cfg.flight_lng)),
        "flight_radius": float_val(form.get("flight_radius"), cfg.flight_radius),
        # Optional: units, brightness, clock and date
        **_unit_profile_fields(form, cfg),
        "screen_brightness": max(
            1, min(5, int_val(form.get("screen_brightness"), cfg.screen_brightness))
        ),
        "clock_24hr": bool_val(form.get("clock_24hr")),
        "date_format": int_val(form.get("date_format"), cfg.date_format),
        # Optional: idle scenes and the birthday scene
        **_idle_theme_fields(idle_themes),
        "birthday_enabled": bool(birthday_date),
        "birthday_date": birthday_date,
        # Optional: satellite tracking
        "satellite_tracking_enabled": bool_val(form.get("satellite_tracking_enabled")),
        "satellite_norad_ids": [
            int(n.strip())
            for n in form.get("satellite_norad_ids", "").splitlines()
            if n.strip().isdigit()
        ],
        # The wizard is complete once this form is saved
        "first_setup_complete": True,
    }


def parse_settings_form(form, cfg) -> dict:
    """Coerce the submitted HTML form into a config dict, applying clamps."""
    from scenes.flight.custom_details import AVAILABLE_FIELDS
    from setup.configuration import (
        DEFAULT_FLIGHT_DATA_POINTS,
        DEFAULT_SATELLITE_DATA_POINTS,
        IDLE_SCREEN_THEMES,
        SATELLITE_DATA_FIELDS,
    )

    idle_themes = _parse_selected_idle_themes(form, cfg, IDLE_SCREEN_THEMES)
    birthday_date = _parse_birthday_date_field(form, cfg)
    current_flight_data_points = getattr(
        cfg, "flight_data_points", DEFAULT_FLIGHT_DATA_POINTS
    )
    current_satellite_data_points = getattr(
        cfg, "satellite_data_points", DEFAULT_SATELLITE_DATA_POINTS
    )
    current_indycar_driver = str(
        getattr(cfg, "indycar_tracked_driver", "") or ""
    ).strip()
    current_indycar_champion_override = str(
        getattr(cfg, "indycar_champion_override", "") or ""
    ).strip()
    stored_location_source = (
        cfg.get("location_source", "manual")
        if hasattr(cfg, "get")
        else getattr(cfg, "location_source", "manual")
    )
    location_source = str(form.get("location_source", stored_location_source))
    if location_source not in ("auto", "browser", "ip", "manual"):
        location_source = "manual"
    return {
        # Location / flight zone
        "location_source": location_source,
        "flight_location_mode": (
            "advanced"
            if str_val(form.get("flight_location_mode"), "simple").lower() == "advanced"
            else "simple"
        ),
        "flight_lat": float_val(form.get("flight_lat"), cfg.flight_lat),
        "flight_lng": wrap_lng(float_val(form.get("flight_lng"), cfg.flight_lng)),
        "flight_radius": float_val(form.get("flight_radius"), cfg.flight_radius),
        "flight_min_altitude": float_val(
            form.get("flight_min_altitude"), cfg.flight_min_altitude
        ),
        "flight_max_altitude": float_val(
            form.get("flight_max_altitude"), cfg.flight_max_altitude
        ),
        # Advanced mode: bounding-box corners
        "flight_zone_tl_y": float_val(
            form.get("flight_zone_tl_y"), cfg.flight_zone_tl_y
        ),
        "flight_zone_tl_x": wrap_lng(
            float_val(form.get("flight_zone_tl_x"), cfg.flight_zone_tl_x)
        ),
        "flight_zone_br_y": float_val(
            form.get("flight_zone_br_y"), cfg.flight_zone_br_y
        ),
        "flight_zone_br_x": wrap_lng(
            float_val(form.get("flight_zone_br_x"), cfg.flight_zone_br_x)
        ),
        # Advanced mode: observer position
        "flight_observer_lat": float_val(
            form.get("flight_observer_lat"), cfg.flight_observer_lat
        ),
        "flight_observer_lng": wrap_lng(
            float_val(form.get("flight_observer_lng"), cfg.flight_observer_lng)
        ),
        # Airport display
        "home_airport_code": str_val(form.get("home_airport_code")).upper()[:6],
        "airport_display_style": max(
            0, min(4, int_val(form.get("airport_display_style"), 0))
        ),
        "airport_code_format": (
            "icao"
            if str_val(form.get("airport_code_format"), "iata").lower() == "icao"
            else "iata"
        ),
        "journey_blank_filler": str_val(form.get("journey_blank_filler"), " ? "),
        "show_airline_icon": bool_val(form.get("show_airline_icon")),
        "airport_lookup_full": bool_val(form.get("airport_lookup_full")),
        # Plane info row
        "details": int_val(form.get("details"), 0),
        "details_custom_template": str_val(
            form.get("details_custom_template"), cfg.details_custom_template
        ),
        **{
            f"flight_data_point_{index + 1}": (
                value
                if (
                    value := str_val(
                        form.get(f"flight_data_point_{index + 1}"),
                        current_flight_data_points[index],
                    )
                )
                in AVAILABLE_FIELDS
                else current_flight_data_points[index]
            )
            for index in range(4)
        },
        **{
            f"satellite_data_point_{index + 1}": (
                value
                if (
                    value := str_val(
                        form.get(f"satellite_data_point_{index + 1}"),
                        current_satellite_data_points[index],
                    )
                )
                in SATELLITE_DATA_FIELDS
                else current_satellite_data_points[index]
            )
            for index in range(4)
        },
        "show_emergency_squawk": bool_val(form.get("show_emergency_squawk")),
        # Units (independent screen profiles)
        **_unit_profile_fields(form, cfg),
        # Weather
        "weatherapi_key": str_val(form.get("weatherapi_key"), cfg.weatherapi_key),
        "weather_mode": int_val(form.get("weather_mode"), 0),
        "rain_sensitivity": max(0, min(2, int_val(form.get("rain_sensitivity"), 1))),
        "number_separator": (
            v
            if (v := str_val(form.get("number_separator"), "none").lower())
            in ("none", "comma", "period")
            else "none"
        ),
        "weather_refresh_minutes": max(
            1,
            min(
                120,
                int_val(
                    form.get("weather_refresh_minutes"), cfg.weather_refresh_minutes
                ),
            ),
        ),
        # Display
        "colour_theme": int_val(form.get("colour_theme"), 0),
        "theme": {
            "forecast": {
                "duration": (
                    "3day"
                    if str_val(form.get("theme_forecast_duration"), "3hour").lower()
                    == "3day"
                    else (
                        "12hour"
                        if str_val(form.get("theme_forecast_duration"), "3hour").lower()
                        == "12hour"
                        else "3hour"
                    )
                ),
            },
            "conditions": {
                "disable_description_scroll": bool_val(
                    form.get("theme_conditions_disable_scroll")
                ),
            },
        },
        "brightness_mode": (
            "advanced"
            if str_val(form.get("brightness_mode"), "simple").lower() == "advanced"
            else "simple"
        ),
        "screen_brightness": max(1, min(5, int_val(form.get("screen_brightness"), 3))),
        "screen_rotate": bool_val(form.get("screen_rotate")),
        "display_speed": (
            str_val(form.get("display_speed"), cfg.display_speed).lower()
            if str_val(form.get("display_speed"), cfg.display_speed).lower()
            in ("default", "slower", "faster")
            else cfg.display_speed
        ),
        "display_scan_rate": (
            32 if str_val(form.get("display_scan_rate"), "").lower() == "32" else 16
        ),
        # Brightness schedule
        "screen_schedule_enabled": bool_val(form.get("screen_schedule_enabled")),
        "screen_schedule_auto": bool_val(form.get("screen_schedule_auto")),
        "screen_schedule_start": str_val(form.get("screen_schedule_start"), "22:00"),
        "screen_schedule_end": str_val(form.get("screen_schedule_end"), "07:00"),
        "screen_schedule_brightness": max(
            0, min(5, int_val(form.get("screen_schedule_brightness"), 0))
        ),
        # Clock / date
        "clock_24hr": bool_val(form.get("clock_24hr")),
        "date_format": int_val(form.get("date_format"), 0),
        # Idle screen themes (ordered multi-select, plus the legacy field)
        **_idle_theme_fields(idle_themes),
        # Birthday scene (recurring yearly; only month/day are compared).
        # Entering a valid date enables the scene automatically.
        "birthday_enabled": bool(birthday_date),
        "birthday_date": birthday_date,
        # INDYCAR (opt-in)
        "indycar_enabled": bool_val(form.get("indycar_enabled")),
        "indycar_tracked_driver": str_val(
            form.get("indycar_tracked_driver"), current_indycar_driver
        ).strip()[:40],
        "indycar_champion_enabled": bool_val(form.get("indycar_champion_enabled")),
        "indycar_champion_override": str_val(
            form.get("indycar_champion_override"), current_indycar_champion_override
        ).strip()[:40],
        "indycar_champion_flash_seconds": max(
            10,
            min(
                600,
                int_val(form.get("indycar_champion_flash_seconds"), 60),
            ),
        ),
        "indycar_test_mode": bool_val(form.get("indycar_test_mode")),
        "indycar_test_qualifying": bool_val(form.get("indycar_test_qualifying")),
        # Web interface
        "web_interface_enabled": bool_val(form.get("web_interface_enabled")),
        "web_port": max(1024, min(65535, int_val(form.get("web_port"), cfg.web_port))),
        "log_level": (
            str_val(form.get("log_level"), cfg.log_level).upper()
            if str_val(form.get("log_level"), cfg.log_level).upper()
            in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
            else cfg.log_level
        ),
        # Provider usage tally (see lookups/usage.py + /api)
        "provider_usage_logging": bool_val(form.get("provider_usage_logging")),
        # Per-provider API call limiting (see lookups/ratelimit.py)
        "api_limit_mode": (
            v
            if (v := str_val(form.get("api_limit_mode"), "none").lower())
            in ("none", "daily", "monthly")
            else "none"
        ),
        # Hardware
        "gpio_slowdown": max(1, min(4, int_val(form.get("gpio_slowdown"), 1))),
        "hat_pwm_enabled": str_val(form.get("hat_pwm_enabled"), "").lower()
        == "quality",
        "bonnet_type": (lambda v: v if v in BONNET_TYPES else DEFAULT_BONNET_TYPE)(
            str_val(form.get("bonnet_type"), DEFAULT_BONNET_TYPE).lower()
        ),
        "loading_indicator": (
            lambda v: v if v in ("none", "pixel", "gpio") else "pixel"
        )(str_val(form.get("loading_indicator"), "pixel").lower()),
        "loading_led_gpio_pin": int_val(form.get("loading_led_gpio_pin"), 25),
        "panel_colour_order": (lambda v: v if v in PANEL_COLOUR_ORDERS else "RGB")(
            str_val(form.get("panel_colour_order"), "RGB").upper()
        ),
        # Lookup provider priority lists (reorderable, submitted as JSON)
        **_parse_provider_form(form, cfg),
        # Advanced brightness schedule (submitted as JSON)
        **_parse_schedule_advanced_form(form),
        # Per-provider settings (providers.<pid>.<field> form keys, with
        # mask-token semantics for sensitive fields)
        "providers": _parse_provider_settings(form, cfg),
        "max_flight_lookup": max(1, int_val(form.get("max_flight_lookup"), 5)),
        # Max minutes to keep a sighted flight in the rotation (0 = no
        # timeout; decimals allowed, 0.5 = 30 seconds); clamped here and
        # in Config
        "max_flight_track_minutes": max(
            0,
            min(
                1440,
                round(
                    float_val(form.get("max_flight_track_minutes"), 0.0),
                    2,
                ),
            ),
        ),
        # Lookup cache durations (route in hours, aircraft in days; clamped
        # here and in Config)
        "cache_route_hours": max(1, min(48, int_val(form.get("cache_route_hours"), 2))),
        "cache_aircraft_days": max(
            1, min(30, int_val(form.get("cache_aircraft_days"), 7))
        ),
        "callsign_format": (
            "iata"
            if str_val(form.get("callsign_format"), "icao").lower() == "iata"
            else "icao"
        ),
        "info_bar_mode": (
            value
            if (value := str_val(form.get("info_bar_mode"), "callsign").lower())
            in {"airline", "callsign", "callsign_airline"}
            else "callsign"
        ),
        # Satellite tracking
        "satellite_tracking_enabled": bool_val(form.get("satellite_tracking_enabled")),
        "satellite_norad_ids": [
            int(n.strip())
            for n in form.get("satellite_norad_ids", "").splitlines()
            if n.strip().isdigit()
        ],
        "satellite_min_elevation": max(
            0, min(90, int_val(form.get("satellite_min_elevation"), 20))
        ),
        "satellite_max_count": max(
            1, min(10, int_val(form.get("satellite_max_count"), 5))
        ),
        "satellite_timeout_enabled": bool_val(form.get("satellite_timeout_enabled")),
        "satellite_test_mode": bool_val(form.get("satellite_test_mode")),
        "satellite_timeout_seconds": max(
            5, min(3600, int_val(form.get("satellite_timeout_seconds"), 30))
        ),
        "debug_scene": (
            value
            if (value := str_val(form.get("debug_scene"), "auto").lower())
            in {
                "auto",
                "flight",
                "satellite",
                "idle",
                "indy_top3",
                "indy_driver",
                "indy_champion",
                "birthday",
            }
            else "auto"
        ),
        "_version": VERSION,
    }


def handle_password_change(form, cfg) -> str:
    """Return the web_password_hash to store, raising on mismatch."""
    new_password = form.get("new_password", "").strip()
    confirm_password = form.get("confirm_password", "").strip()
    if new_password:
        if new_password != confirm_password:
            raise ValueError("New passwords do not match.")
        logger.info("Web password updated")
        return hash_password(new_password)
    # Preserve existing hash
    return cfg.web_password_hash


# ---------------------------------------------------------------------------
# First-setup wizard
# ---------------------------------------------------------------------------


def _first_setup_pending(cfg) -> bool:
    """True while the first-setup wizard should be offered.

    The wizard is done once its flag is set, or as soon as any web password
    exists (e.g. it was changed through the regular settings page).
    """
    return not (cfg.first_setup_complete or cfg.get("web_password_hash"))


def _default_landing() -> str:
    """Where to send a freshly authenticated user."""
    if _first_setup_pending(Config.instance()):
        return url_for("first_setup")
    return url_for("settings")


def _first_setup_page_data(cfg, form=None) -> dict:
    """Template data for the wizard page.

    When *form* is given (a rejected POST), the submitted values
    re-populate the inputs so nothing typed is lost.
    """
    from setup.configuration import IDLE_SCREEN_THEMES

    def val(key, current):
        if form is not None and key in form:
            return form.get(key)
        return current

    def flag(key, current: bool) -> bool:
        # Checkboxes are absent when unchecked, so a submitted form is
        # authoritative even for missing keys.
        if form is not None:
            return bool_val(form.get(key))
        return current

    selected = (
        _form_values(form, "idle_screen_themes")
        if form is not None
        else list(cfg.idle_screen_themes)
    )
    return {
        "csrf_token": csrf_token(),
        "bonnet_type": val("bonnet_type", cfg.bonnet_type),
        # Location (blank keeps the current, possibly auto-detected, spot)
        "flight_lat": val("flight_lat", cfg.flight_lat),
        "flight_lng": val("flight_lng", cfg.flight_lng),
        "flight_radius": val("flight_radius", cfg.flight_radius),
        # Units / brightness / clock
        "flight_units": val("flight_units", cfg.flight_units),
        "idle_units": val("idle_units", cfg.idle_units),
        "screen_brightness": int_val(
            val("screen_brightness", cfg.screen_brightness), cfg.screen_brightness
        ),
        "clock_24hr": flag("clock_24hr", cfg.clock_24hr),
        "date_format": int_val(val("date_format", cfg.date_format), cfg.date_format),
        # Idle scenes / birthday / satellites
        "themes": [
            {
                "value": theme,
                "label": IDLE_THEME_META[theme][0],
                "description": IDLE_THEME_META[theme][1],
                "checked": theme in selected,
            }
            for theme in IDLE_SCREEN_THEMES
        ],
        "birthday_date": val("birthday_date", cfg.birthday_date),
        "satellite_tracking_enabled": flag(
            "satellite_tracking_enabled", cfg.satellite_tracking_enabled
        ),
        "satellite_norad_ids_text": val(
            "satellite_norad_ids",
            "\n".join(str(n) for n in cfg.satellite_norad_ids),
        ),
    }


@app.route("/first-setup", methods=["GET", "POST"])
@login_required
def first_setup():
    """Guided first-use wizard.

    Required: the LED matrix bonnet type and a new web-interface
    password.  Everything else is clearly labelled optional and keeps its
    current or default value when left untouched.
    """
    cfg = Config.instance()
    if not _first_setup_pending(cfg):
        return redirect(url_for("settings"))

    if request.method == "POST":
        form = request.form
        logger.info("POST /first-setup received")

        try:
            if not validate_csrf(form):
                raise ValueError("Invalid CSRF token.")

            if form.get("action") == "skip":
                # Skipping only records that the wizard was seen; no
                # display-affecting value changes, so no restart.
                cfg.set("first_setup_complete", True)
                cfg.save()
                logger.info("First-setup wizard skipped")
                return redirect(url_for("settings"))

            bonnet = str_val(form.get("bonnet_type"), "").lower()
            if bonnet not in BONNET_TYPES:
                raise ValueError("Choose which bonnet your display uses.")

            new_password = form.get("new_password", "").strip()
            confirm_password = form.get("confirm_password", "").strip()
            if not new_password:
                raise ValueError("Choose a new password for the web interface.")
            if new_password != confirm_password:
                raise ValueError("New passwords do not match.")

            new_data = parse_first_setup_form(form, cfg)
            new_data["web_password_hash"] = hash_password(new_password)

            logger.debug("Parsed first-setup settings: %s", new_data)
            cfg.update(new_data)
            cfg.save()
            logger.info("First setup saved to %s", CONFIG_PATH)
        except Exception as exc:
            logger.error("Error processing first-setup form: %s", exc)
            import traceback

            traceback.print_exc()
            return (
                render_template(
                    "first_setup.html",
                    error=str(exc),
                    **_first_setup_page_data(cfg, form),
                ),
                400,
            )

        restart_after(delay=1.0)
        return render_template("restarting.html")

    return render_template("first_setup.html", **_first_setup_page_data(cfg))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    if _first_setup_pending(Config.instance()):
        return redirect(url_for("first_setup"))
    return redirect(url_for("settings"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(_default_landing())

    error = None
    if request.method == "POST":
        if not validate_csrf(request.form):
            error = "Invalid request."
        else:
            password = request.form.get("password", "")
            logger.info("Login attempt")
            if check_password(password):
                session["authenticated"] = True
                logger.info("Login successful")
                next_url = request.args.get("next") or _default_landing()
                return redirect(next_url)
            else:
                logger.warning("Login failed - wrong password")
                error = "Incorrect password."

    using_default_password = not bool(Config.instance().get("web_password_hash"))
    return render_template(
        "login.html",
        error=error,
        csrf_token=csrf_token(),
        using_default_password=using_default_password,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def _humanise_uptime(seconds: int) -> str:
    """Compact uptime for the status card: "6d 3h", "6h 12m", "4m"."""
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _system_telemetry() -> dict:
    """Host telemetry for the status page (all values optional).

    Everything is stdlib - /proc + /sys + shutil - so the card simply
    omits whatever the host can't report (temperature on a laptop, memory
    on macOS, and so on).
    """
    from utilities import system_info

    throughput = system_info.network_throughput()
    if throughput is not None:
        # Report in megabits per second - friendlier than bytes for the
        # kind of connection a Pi sits behind.
        throughput["down_mbps"] = round(throughput["down_bps"] / 125_000, 2)
        throughput["up_mbps"] = round(throughput["up_bps"] / 125_000, 2)

    uptime = system_info.uptime_seconds()
    return {
        "hostname": system_info.hostname(),
        "model": system_info.hardware_model(),
        "cpu_temp_c": system_info.cpu_temperature(),
        "uptime_seconds": system_info.uptime_seconds(),
        "uptime_human": _humanise_uptime(uptime) if uptime is not None else None,
        "load": system_info.load_average(),
        "memory": system_info.memory_usage(),
        "storage": system_info.storage_usage("/"),
        "ip": system_info.ip_address(),
        "throughput": throughput,
    }


def _status_page_data() -> dict:
    """Assemble the runtime status view for the status page.

    The web app shares its process with the tracker, so everything here is
    a direct read of live state: the provider registry, the quarantine
    (provider hold-offs), and the display facade's last-fetch record.
    """

    from display import get_overhead_instance
    from utilities.lookups import ratelimit
    from utilities.lookups.flights import refresh_interval
    from utilities.lookups.quarantine import QUARANTINE
    from utilities.lookups.registry import PROVIDERS, load_config

    cfg = load_config()
    hold_offs = QUARANTINE.snapshot()
    quota = ratelimit.status()
    flight_ids = {e["provider"] for e in cfg.flight_providers if e.get("enabled")}
    route_ids = {e["provider"] for e in cfg.route_providers if e.get("enabled")}

    providers = []
    for spec in PROVIDERS.values():
        settings = cfg.provider_settings(spec.id)
        providers.append(
            {
                "id": spec.id,
                "name": spec.name,
                "capabilities": sorted(spec.capabilities),
                "flight_capable": "flights" in spec.capabilities,
                "route_capable": bool(spec.capabilities & {"routes", "aircraft"}),
                "flight_enabled": spec.id in flight_ids
                and "flights" in spec.capabilities,
                "route_enabled": spec.id in route_ids
                and bool(spec.capabilities & {"routes", "aircraft"}),
                "configured": spec.config.is_configured(settings),
                "missing_required": spec.config.missing_required(settings),
                "hold_off_s": hold_offs.get(spec.id),
                "quota": quota["providers"].get(spec.id, {}),
            }
        )

    # The shared Overhead instance belongs to the display loop; reading it
    # is safe (facade reads are lock-guarded).  Only non-clearing state is
    # touched here - the data property would steal the scene's new_data
    # flag, so the flight count comes from the last-fetch record instead.
    overhead = get_overhead_instance()
    last_fetch = overhead.last_fetch
    if last_fetch is not None:
        last_fetch = {
            **last_fetch,
            "at_fmt": _format_last_updated_value(last_fetch["at"]),
        }
    return {
        "providers": providers,
        "api_limit_mode": quota["mode"],
        "api_limit_period": quota["period"],
        "fetch": {
            "last_updated_fmt": _format_last_updated_value(overhead.last_updated),
            "error": overhead.error,
            "empty": overhead.data_is_empty,
            "refresh_interval": refresh_interval(),
            "last_fetch": last_fetch,
        },
        "system": _system_telemetry(),
        "active_page": "status",
    }


@app.route("/status")
@login_required
def status():
    """Runtime status: providers, hold-offs and the last fetch attempt."""
    return render_template("status.html", **_status_page_data())


def _provider_ui_data(cfg) -> dict:
    """Build the provider-facing data for the settings page.

    The browser never sees a sensitive value: secrets are masked in the
    config snapshot (the web password hash and image API key are
    excluded entirely), and the
    per-provider descriptor metadata drives the Data Source page's
    provider settings cards.
    """
    from utilities.lookups.config import MASK, provider_settings_view
    from utilities.lookups.registry import PROVIDERS

    cfg_masked = {
        key: value
        for key, value in cfg.as_dict().items()
        if key not in ("web_password_hash", "image_api_key")
    }
    # The stored list may be empty on installs that still use the legacy
    # single-theme setting; expose the effective selection to the UI.
    cfg_masked["idle_screen_themes"] = cfg.idle_screen_themes

    providers_meta = []
    for pid, spec in PROVIDERS.items():
        settings = cfg.provider_settings(pid)
        providers_meta.append(
            {
                "id": spec.id,
                "name": spec.name,
                "description": spec.description,
                "capabilities": sorted(spec.capabilities),
                "live_fields": sorted(spec.config.live_fields),
                "configured": spec.config.is_configured(settings),
                "missing_required": spec.config.missing_required(settings),
                "fields": [field.as_dict_view() for field in spec.config.fields],
            }
        )
    cfg_masked["providers"] = {
        pid: provider_settings_view(spec.config, cfg.provider_settings(pid))
        for pid, spec in PROVIDERS.items()
    }

    def order(capability):
        entries = getattr(cfg, f"{capability}_providers")
        return [
            {"provider": e["provider"], "enabled": bool(e.get("enabled"))}
            for e in entries
        ]

    return {
        "cfg": cfg_masked,
        "providers_meta": providers_meta,
        "flight_order": order("flight"),
        "route_order": order("route"),
        "mask_token": MASK,
    }


def _settings_page_data(
    cfg,
    template_errors=None,
    error=None,
    import_failed=False,
):
    """Build the context dict passed to settings.html.

    The Vue app reads ``window.FT_CONFIG`` (the raw config dict) and
    ``window.FT_PAGE_DATA`` (everything else: airports, version, URLs,
    template errors, etc.).  This helper keeps both in sync so every
    render_template call produces the same shape.
    """
    from flask import url_for as _url_for

    schedule_window = cfg.brightness_schedule_window
    # Serialise datetime.time objects to {hour, minute} dicts for JSON.
    sw_json = [None, None]
    if schedule_window and len(schedule_window) == 2:
        sw_json = [
            {"hour": t.hour, "minute": t.minute} if t else None for t in schedule_window
        ]

    provider_ui = _provider_ui_data(cfg)

    return {
        "cfg": provider_ui["cfg"],
        "airports_json": airports_json(),
        "template_errors": template_errors or [],
        "error": error,
        "import_failed": import_failed,
        "location_detection_enabled": cfg.get("location_source") in ("auto", "ip"),
        "csrf_token": csrf_token(),
        "in_schedule": cfg.is_in_brightness_schedule(),
        "schedule_window": schedule_window,
        "schedule_window_json": sw_json,
        "schedule_advanced_active": cfg.active_advanced_entry(),
        "current_version": version_string(APP_VERSION),
        "active_page": "settings",
        "providers_meta": provider_ui["providers_meta"],
        "flight_providers_order": provider_ui["flight_order"],
        "route_providers_order": provider_ui["route_order"],
        "mask_token": provider_ui["mask_token"],
        "static_urls": {
            "weatherExplained": _url_for(
                "static", filename="images/weather_explained.png"
            ),
            "scaleExplained": _url_for("static", filename="images/scale_explained.png"),
        },
        "symbol_images": {
            "{symbol:altitude}": _url_for(
                "static", filename="images/symbols_altitude.png"
            ),
            "{symbol:speed}": _url_for("static", filename="images/symbols_speed.png"),
            "{symbol:heading}": _url_for(
                "static", filename="images/symbols_heading.png"
            ),
            "{symbol:degree}": _url_for(
                "static", filename="images/symbols_degrees.png"
            ),
            "{symbol:origin_arrow}": _url_for(
                "static", filename="images/symbols_origin.png"
            ),
            "{symbol:dest_arrow}": _url_for(
                "static", filename="images/symbols_destination.png"
            ),
        },
        "urls": {
            "ipLocation": _url_for("ip_location"),
            "logs": _url_for("logs"),
            "update": _url_for("update"),
            "cacheClear": "/cache-clear",
            "backupExport": "/backup/export",
            "backupRestore": "/backup/restore",
            "debugConfig": "/debug-config",
            "statusApi": "/api",
            "sshAccess": _url_for("remote_access_ssh"),
        },
    }


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    cfg = Config.instance()
    using_default_password = not bool(cfg.get("web_password_hash"))

    if request.method == "POST":
        form = request.form
        logger.info("POST /settings received")
        logger.debug("Raw form keys: %s", list(form.keys()))

        try:
            if not validate_csrf(form):
                raise ValueError("Invalid CSRF token.")

            new_data = parse_settings_form(form, cfg)

            # Provider settings arrive as a partial subtree (only the
            # providers whose cards were shown) - merge it through
            # descriptor validation so no junk is ever persisted.
            providers_partial = new_data.pop("providers", None)
            if providers_partial:
                new_data["providers"] = _merge_provider_settings(cfg, providers_partial)

            new_password = form.get("new_password", "").strip()

            # Validate custom plane-info template when custom mode is selected.
            template_errors = []
            if new_data.get("details") == 2:
                from scenes.flight.custom_details import validate_template

                template_errors = validate_template(
                    new_data.get("details_custom_template", "")
                )
                if template_errors:
                    # Don't raise - pass errors to the template for inline
                    # display next to the textarea.
                    merged_cfg = Config.__new__(Config)
                    merged_cfg.data_store = {**cfg.as_dict(), **new_data}
                    return (
                        render_template(
                            "settings.html",
                            **_settings_page_data(
                                merged_cfg,
                                template_errors=template_errors,
                            ),
                        ),
                        400,
                    )

            if using_default_password and not new_password:
                merged_cfg = Config.__new__(Config)
                merged_cfg.data_store = {**cfg.as_dict(), **new_data}
                return (
                    render_template(
                        "settings.html",
                        **_settings_page_data(
                            merged_cfg,
                            error="To change any setting you must update the default web-interface password, even if you plan on disabling the web-interface.",
                        ),
                    ),
                    400,
                )

            new_data["web_password_hash"] = handle_password_change(form, cfg)

            logger.debug("Parsed settings: %s", new_data)

            cfg.update(new_data)
            cfg.save()
            logger.info("Config saved to %s", CONFIG_PATH)

        except Exception as exc:
            logger.error("Error processing settings form: %s", exc)
            import traceback

            traceback.print_exc()
            merged_cfg = Config.__new__(Config)
            merged_cfg.data_store = (
                {**cfg.as_dict(), **new_data}
                if "new_data" in locals()
                else cfg.as_dict()
            )
            return (
                render_template(
                    "settings.html",
                    **_settings_page_data(merged_cfg, error=str(exc)),
                ),
                400,
            )

        restart_after(delay=1.0)
        return render_template("restarting.html")

    import_failed = _consume_import_failed_marker()
    return render_template(
        "settings.html",
        **_settings_page_data(cfg, import_failed=import_failed),
    )


@app.route("/wifi-setup", methods=["GET", "POST"])
def wifi_setup():
    """Configure the Pi's home Wi-Fi while its temporary setup AP is active."""
    setup_marker = Path("/run/flighttracker-wifi-setup")
    if not setup_marker.exists():
        abort(404)

    error = None
    if request.method == "POST":
        if not validate_csrf(request.form):
            error = "Invalid request. Reload the setup page and try again."
        else:
            payload = {
                "ssid": request.form.get("ssid", "").strip(),
                "password": request.form.get("password", ""),
            }
            if not payload["ssid"] or not payload["password"]:
                error = "Enter your Wi-Fi network name and password."
            else:
                try:
                    result = subprocess.run(
                        ["sudo", "-n", "/usr/local/sbin/flighttracker-configure-wifi"],
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        timeout=90,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    logger.error("Wi-Fi setup helper failed: %s", exc)
                    error = (
                        "Wi-Fi setup could not be started. Check the Pi installation."
                    )
                else:
                    if result.returncode:
                        error = result.stderr.strip() or (
                            "Could not connect. Check the network name and password."
                        )
                    else:
                        logger.info("Home Wi-Fi connection configured.")
                        from utilities.system_info import hostname

                        return render_template(
                            "wifi_setup_complete.html",
                            hostname=hostname(),
                            web_port=FLASK_PORT,
                        )

    return render_template(
        "wifi_setup.html",
        csrf_token=csrf_token(),
        error=error,
    )


@app.route("/settings/reset", methods=["POST"])
@login_required
def reset_settings():
    """Restore application defaults without changing Wi-Fi or web access."""
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    cfg = Config.instance()
    password_hash = cfg.get("web_password_hash", "")
    cfg.data_store = copy.deepcopy(DEFAULTS)
    cfg.data_store["web_password_hash"] = password_hash
    _migrate_provider_lists(cfg.data_store, {})
    cfg.save()
    logger.info("Application settings reset to defaults.")
    restart_after(delay=1.0)
    return jsonify(message="FlightTracker settings were reset to defaults.")


def _run_wifi_helper(payload: dict) -> bool:
    """Run the privileged Wi-Fi helper with *payload* on stdin.

    Returns True on success; failures are logged (the caller decides how
    to report them).
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", "/usr/local/sbin/flighttracker-configure-wifi"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("Wi-Fi helper failed: %s", exc)
        return False
    if result.returncode:
        logger.error("Wi-Fi helper failed: %s", result.stderr.strip())
        return False
    return True


@app.route("/wifi-setup/reset", methods=["POST"])
@login_required
def reset_wifi():
    """Reopen the protected Wi-Fi setup hotspot without forgetting credentials."""
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    if not _run_wifi_helper({"action": "start_setup"}):
        return jsonify(error="Could not start the Wi-Fi setup hotspot."), 500

    logger.info("Wi-Fi setup hotspot reopened from the settings page.")
    restart_after(delay=1.0)
    return jsonify(
        message="The setup hotspot is starting. Use the QR code on the display."
    )


@app.route("/wifi-setup/forget", methods=["POST"])
@login_required
def forget_wifi():
    """Delete every saved Wi-Fi network and open the first-boot setup hotspot.

    With no saved profile, the next boot starts the setup hotspot exactly
    like a fresh install - used for testing the setup flow and for handing
    the device to someone else.
    """
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    if not _run_wifi_helper({"action": "forget_wifi"}):
        return jsonify(error="Could not delete the saved Wi-Fi networks."), 500

    logger.info("Saved Wi-Fi networks deleted; setup hotspot opened.")
    restart_after(delay=1.0)
    return jsonify(
        message=(
            "Saved Wi-Fi networks deleted. Join the setup hotspot with the "
            "QR code on the display to connect to a new network."
        )
    )


@app.route("/password/reset", methods=["POST"])
@login_required
def reset_password():
    """Restore the default web password and re-open the first-setup wizard.

    The recipient (or a returning owner) signs in with the default
    password and walks through the wizard again.
    """
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    cfg = Config.instance()
    # Empty hash = default password; clearing the flag re-opens the wizard.
    cfg.data_store["web_password_hash"] = ""
    cfg.data_store["first_setup_complete"] = False
    cfg.save()
    logger.info("Web password reset to the default; first-setup wizard re-opened.")
    restart_after(delay=1.0)
    return jsonify(
        message=(
            "The web password is back to the default (flighttracker). "
            "The first-setup wizard opens on the next sign-in."
        )
    )


@app.route("/handoff/reset", methods=["POST"])
@login_required
def prepare_handoff():
    """Reset everything personal before handing the device to someone else.

    Restores application defaults - which clears the web password back to
    the default and re-opens the first-setup wizard - then deletes every
    saved Wi-Fi network and opens the first-boot setup hotspot.  Unlike
    ``/settings/reset`` this does not keep the web password.
    """
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    cfg = Config.instance()
    cfg.data_store = copy.deepcopy(DEFAULTS)
    _migrate_provider_lists(cfg.data_store, {})
    cfg.save()
    logger.info("Settings restored to defaults for handoff.")

    if not _run_wifi_helper({"action": "forget_wifi"}):
        return (
            jsonify(
                error=(
                    "Settings were reset, but the saved Wi-Fi networks could "
                    "not be deleted. Try Forget Wi-Fi again."
                )
            ),
            500,
        )

    logger.info("Handoff reset complete; setup hotspot opened.")
    restart_after(delay=1.0)
    return jsonify(
        message=(
            "Hobby Ticker is reset for handoff. Join the setup hotspot with "
            "the QR code on the display; the next owner sets everything up "
            "from there."
        )
    )


@app.route("/remote-access/ssh", methods=["GET", "POST"])
@login_required
def remote_access_ssh():
    """Read or change SSH availability from the Admin page."""
    if request.method == "GET":
        return jsonify(ssh_access.status())

    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")

    action = request.form.get("action", "").strip().lower()
    if action not in ("on", "off"):
        return jsonify(error="Invalid SSH action."), 400

    try:
        result = subprocess.run(
            ["sudo", "-n", "/usr/local/sbin/flighttracker-set-ssh", action],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("Could not change SSH state: %s", exc)
        return jsonify(error="SSH control is not installed on this system."), 500

    if result.returncode:
        logger.error("SSH helper failed: %s", result.stderr.strip())
        return (
            jsonify(error=result.stderr.strip() or "Could not change SSH state."),
            500,
        )

    try:
        state = json.loads(result.stdout)
    except json.JSONDecodeError:
        state = ssh_access.status()

    logger.info(
        "SSH %s from the settings page.", "enabled" if action == "on" else "disabled"
    )
    message = (
        "SSH is now enabled. It stays on until you turn it off."
        if action == "on"
        else "SSH is now disabled."
    )
    return jsonify(message=message, state=state)


@app.route("/api/location/ip")
@login_required
def ip_location():
    """Return an approximate location based on the server's public IP."""
    try:
        from utilities.location import ip_location as lookup_ip_location

        lat, lng = lookup_ip_location()
    except (OSError, TimeoutError, ValueError, KeyError) as exc:
        logger.warning("IP location lookup failed: %s", exc)
        return jsonify(error="IP-based location lookup failed."), 502

    return jsonify(latitude=lat, longitude=lng)


@app.route("/ping")
def ping():
    """Health-check endpoint used by the restarting page to detect a successful reboot."""
    if app_ready.is_set():
        return "ok", 200
    return "starting", 503


AIRPORTS_JSON: str | None = None


def load_airports_json() -> str:
    global AIRPORTS_JSON
    if AIRPORTS_JSON is None:
        filename = (
            "airports-full.json"
            if Config.instance().airport_lookup_full
            else "airports.json"
        )
        airports_path = Path(__file__).parent.parent / "assets" / filename
        try:
            with open(airports_path, encoding="utf-8") as fh:
                AIRPORTS_JSON = fh.read()
        except Exception:
            AIRPORTS_JSON = "{}"
    return AIRPORTS_JSON


def airports_json() -> str:
    return load_airports_json()


# Top-level config keys that may contain sensitive information (provider
# settings are redacted schema-driven via their descriptors).
SENSITIVE_KEYS = {
    "weatherapi_key",
    "image_api_key",
    "web_password_hash",
}


def _redact_for_debug(data: dict) -> dict:
    """Return *data* with every sensitive value redacted.

    Top-level sensitive keys use :data:`SENSITIVE_KEYS`; the nested
    ``providers`` subtree is redacted from the provider descriptors so new
    sensitive fields are covered automatically.
    """
    from utilities.lookups.config import REDACTED
    from utilities.lookups.registry import PROVIDERS

    safe: dict = {}
    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            safe[key] = REDACTED if value else ""
        else:
            safe[key] = value

    providers = data.get("providers")
    if isinstance(providers, dict):
        # Schema-driven: a provider descriptor field marked sensitive=True
        # is redacted here automatically.
        sensitive_by_pid = {
            pid: {f.key for f in spec.config.sensitive_fields()}
            for pid, spec in PROVIDERS.items()
        }
        redacted_providers: dict = {}
        for pid, settings in providers.items():
            if not isinstance(settings, dict):
                redacted_providers[pid] = settings
                continue
            sensitive = sensitive_by_pid.get(pid, frozenset())
            redacted_providers[pid] = {
                key: (REDACTED if value and key in sensitive else value)
                for key, value in settings.items()
            }
        safe["providers"] = redacted_providers
    return safe


@app.route("/debug-config")
@login_required
def debug_config():
    """Return the current config as JSON with all API keys / passwords removed.

    Intended for users to safely share their configuration when requesting
    help via GitHub issues.
    """
    import json

    cfg = Config.instance()
    safe = _redact_for_debug(cfg.as_dict())
    payload = json.dumps(safe, indent=2, sort_keys=True)
    return Response(
        payload,
        mimetype="application/json",
        headers={
            "Content-Disposition": "attachment; filename=flighttracker-debug-config.json"
        },
    )


@app.route("/backup/export")
@login_required
def backup_export():
    """Download a full, unredacted copy of the current config as a backup.

    The filename includes a timestamp so successive exports don't collide.
    The ``_version`` key is set to the running version so imports can
    detect version mismatches.
    """
    import datetime as _dt

    cfg = Config.instance()
    payload = json.dumps(build_backup_dict(cfg), indent=2, sort_keys=True)
    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"config-{timestamp}.json"
    logger.info("Exporting config backup: %s", filename)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/backup/restore", methods=["GET", "POST"])
@login_required
def backup_restore():
    """Upload a backup file and confirm before overwriting settings.

    GET  - show the upload form with the overwrite warning.
    POST - parse the uploaded file, check the version, and either show an
           error or render the confirm view.  The parsed config is stashed
           to ``config-update.json`` only when the user confirms via the
           separate ``/backup/restore/apply`` endpoint, so this step never
           touches the live config.
    """
    if request.method == "GET":
        return render_template(
            "restore.html",
            csrf_token=csrf_token(),
            active_page="backup",
        )

    # POST - parse upload
    if not validate_csrf(request.form):
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="backup",
            ),
            403,
        )

    uploaded = request.files.get("backup_file")
    if uploaded is None or not uploaded.filename:
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error="No file selected. Please choose a backup file to import.",
                active_page="backup",
            ),
            400,
        )

    raw = uploaded.read()
    data, backup_version, error = parse_backup_json(raw)
    if error is not None:
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error=error,
                active_page="backup",
            ),
            400,
        )

    # Version comparison for the confirm view.
    current_version = list(VERSION)
    if backup_version is None:
        version_warning = (
            "This backup does not contain a version tag. It may be from an "
            "older release of Flight Tracker; some settings may not apply."
        )
        comparison = None
    else:
        comparison = compare_versions(backup_version, current_version)
        if comparison < 0:
            version_warning = (
                f"This backup is from an older version of Flight Tracker "
                f"({version_string(backup_version)}). You are running "
                f"{version_string(current_version)}. Some settings may not "
                f"apply."
            )
        elif comparison > 0:
            version_warning = (
                f"This backup is from a newer version of Flight Tracker "
                f"({version_string(backup_version)}). You are running "
                f"{version_string(current_version)}. Some settings may not "
                f"be recognised by your version."
            )
        else:
            version_warning = None

    # Stash the parsed config server-side so the apply step doesn't need the
    # file re-uploaded.  A nonce in the session ties the confirm POST to this
    # specific upload.
    nonce = secrets.token_hex(16)
    stash_path = PLATFORM_DATA_DIR / f".pending-backup-{nonce}.json"
    tmp_path = stash_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, stash_path)
    except OSError as exc:
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error=f"Failed to stage backup for import: {exc}",
                active_page="backup",
            ),
            500,
        )

    session["pending_backup_nonce"] = nonce
    logger.info("Backup staged for import (nonce %s)", nonce)

    return render_template(
        "restore.html",
        csrf_token=csrf_token(),
        confirm=True,
        backup_version=(
            version_string(backup_version) if backup_version is not None else "unknown"
        ),
        current_version=version_string(current_version),
        version_warning=version_warning,
        active_page="backup",
    )


@app.route("/backup/restore/apply", methods=["POST"])
@login_required
def backup_restore_apply():
    """Write the staged backup to ``config-update.json`` and reboot.

    The actual overwrite of ``config.json`` happens on the next boot via
    the swap-on-boot logic in ``flight-tracker.py`` - this endpoint never
    touches the live config directly.
    """
    if not validate_csrf(request.form):
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="backup",
            ),
            403,
        )

    nonce = session.pop("pending_backup_nonce", None)
    if not nonce:
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error="No pending backup found. Please upload a file again.",
                active_page="backup",
            ),
            400,
        )

    stash_path = PLATFORM_DATA_DIR / f".pending-backup-{nonce}.json"
    try:
        with open(stash_path) as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        # Clean up the stash if it's unreadable.
        with contextlib.suppress(OSError):
            stash_path.unlink()
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error=f"Staged backup is unreadable: {exc}. Please upload again.",
                active_page="backup",
            ),
            500,
        )

    # Write the confirmed config to config-update.json atomically.
    try:
        tmp_path = CONFIG_UPDATE_PATH.with_suffix(CONFIG_UPDATE_PATH.suffix + ".tmp")
        with open(tmp_path, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, CONFIG_UPDATE_PATH)
    except OSError as exc:
        with contextlib.suppress(OSError):
            stash_path.unlink()
        return (
            render_template(
                "restore.html",
                csrf_token=csrf_token(),
                error=f"Failed to write config update file: {exc}",
                active_page="backup",
            ),
            500,
        )

    # Clean up the stash - config-update.json is now the source of truth.
    with contextlib.suppress(OSError):
        stash_path.unlink()

    logger.info(
        "Config import confirmed - wrote %s, restarting to apply",
        CONFIG_UPDATE_PATH,
    )
    restart_after(delay=1.0)
    return render_template("restarting.html")


@app.route("/logs")
@login_required
def logs():
    """Show the most recent in-memory log entries (newest-first).

    Refresh the page to see new entries.  The buffer is capped at
    BUFFER_SIZE records and cleared on restart.
    """
    import datetime as _dt

    records = get_buffer().records()
    # Format the epoch timestamp into something readable once, server-side.
    rows = [
        {
            "time": _dt.datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M:%S"),
            "level": r["level"],
            "source": r["source"],
            "message": r["message"],
        }
        for r in records
    ]
    return render_template("logs.html", rows=rows, active_page="logs")


@app.route("/logs/download")
@login_required
def logs_download():
    """Return the full in-memory log buffer as a plain-text download.

    Intended for users to easily share their logs when requesting help.
    """
    import datetime as _dt

    records = get_buffer().records()
    lines = [
        f"{_dt.datetime.fromtimestamp(r['time']).strftime('%Y-%m-%d %H:%M:%S')} "
        f"{r['level']:<8} {r['source']:<20} {r['message']}"
        for r in records
    ]
    payload = "\n".join(lines)
    return Response(
        payload,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=flighttracker-logs.txt"},
    )


# ---------------------------------------------------------------------------
# Update routes
# ---------------------------------------------------------------------------


@app.route("/update")
@login_required
def update():
    """Show the update status page."""
    info = get_update_info()
    info["current_version"] = version_string(APP_VERSION)
    return render_template(
        "update.html",
        info=info,
        csrf_token=csrf_token(),
        active_page="update",
        repository_url=GITHUB_REPOSITORY_URL,
    )


@app.route("/update/check", methods=["POST"])
@login_required
def update_check():
    """Check for updates and return JSON status."""
    if not validate_csrf(request.form):
        return {"error": "Invalid CSRF token."}, 403
    info = get_update_info()
    info["current_version"] = version_string(APP_VERSION)
    return info, 200


@app.route("/update/apply", methods=["POST"])
@login_required
def update_apply():
    """Apply a fast-forward update from the Hobby Ticker repository."""
    if not validate_csrf(request.form):
        return (
            render_template(
                "update.html",
                info=get_update_info(),
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="update",
                repository_url=GITHUB_REPOSITORY_URL,
            ),
            403,
        )

    logger.info("Applying update from the Hobby Ticker main branch")
    success, message = perform_update()

    if not success:
        logger.error("Update failed: %s", message)
        return (
            render_template(
                "update.html",
                info=get_update_info(),
                csrf_token=csrf_token(),
                error=message,
                active_page="update",
                repository_url=GITHUB_REPOSITORY_URL,
            ),
            500,
        )

    logger.info("Update succeeded, restarting...")
    restart_after(delay=2.0)
    return render_template("restarting.html")


@app.route("/cache-clear")
@login_required
def cache_clear():
    """Show the clear-cache status page."""
    return render_template(
        "clear_cache.html", csrf_token=csrf_token(), active_page="clear_cache"
    )


@app.route("/cache-clear/apply", methods=["POST"])
@login_required
def cache_clear_apply():
    """Clear route/TLE cache files then restart."""
    if not validate_csrf(request.form):
        return (
            render_template(
                "clear_cache.html",
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="clear_cache",
            ),
            403,
        )

    logger.info("Clearing cache files")
    try:
        routes_cache.clear()
        if TLE_CACHE_PATH.exists():
            TLE_CACHE_PATH.unlink()
    except OSError as exc:
        logger.error("Cache clear failed: %s", exc)
        return (
            render_template(
                "clear_cache.html",
                csrf_token=csrf_token(),
                error=f"Failed to clear cache: {exc}",
                active_page="clear_cache",
            ),
            500,
        )

    logger.info("Cache cleared, restarting...")
    restart_after(delay=2.0)
    return render_template("restarting.html")


# ---------------------------------------------------------------------------
# Data routes
# ---------------------------------------------------------------------------


@app.route("/live-data")
@login_required
def live_data():
    """Show current weather and overhead flight data for debugging."""
    from scenes.idle.themes.theme_utilities import WeatherService

    overhead, data_source_name = _get_live_data_overhead()

    weather_service = WeatherService.instance()
    weather_service.do_fetch()
    weather_data = weather_service.get() or {}

    weather_current_rows = _build_weather_current_rows(weather_data)
    forecast_rows, forecast_columns = _build_forecast_rows(weather_data.get("daily"))
    flight_rows, flight_columns = _build_flight_rows(overhead.data)
    last_updated = _format_last_updated_value(getattr(overhead, "last_updated", None))

    return render_template(
        "live_data.html",
        active_page="live_data",
        weather_current_rows=weather_current_rows,
        forecast_rows=forecast_rows,
        forecast_columns=forecast_columns,
        flight_rows=flight_rows,
        flight_columns=flight_columns,
        data_source_name=data_source_name,
        flight_count=len(flight_rows),
        last_updated=last_updated,
    )


@app.route("/cached-data")
@login_required
def cached_data():
    """Show cached route and TLE data in tables."""
    import datetime as _dt
    import json as _json

    # --- Route cache ---
    route_entries = []
    try:
        now = time.time()
        for row in routes_cache.debug_entries(routes_cache.KIND_ROUTE):
            ts = row["ts"]
            cached_at = (
                _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            )
            route_entries.append(
                {
                    "callsign": row["key"],
                    "plane": row["entry"].get("plane", ""),
                    "origin": row["entry"].get("origin", ""),
                    "destination": row["entry"].get("destination", ""),
                    "origin_name": row["entry"].get("origin_name", ""),
                    "destination_name": row["entry"].get("destination_name", ""),
                    "cached_at": cached_at,
                    "expired": ts > 0 and (now - ts) > row["ttl"],
                }
            )
        route_entries.sort(key=lambda e: e["callsign"])
    except Exception as exc:
        logger.warning("Failed to read route cache: %s", exc)

    # --- TLE cache ---
    tle_entries = []
    tle_fetched_at = ""
    tle_expired = False
    try:
        if TLE_CACHE_PATH.exists():
            with open(TLE_CACHE_PATH) as f:
                raw = _json.load(f)
            ts = raw.get("timestamp", 0)
            if ts:
                tle_fetched_at = _dt.datetime.fromtimestamp(ts).strftime(
                    "%Y-%m-%d %H:%M"
                )
                tle_expired = (time.time() - ts) > TLE_CACHE_TTL
            cached_at = tle_fetched_at
            for tle in raw.get("tles", []):
                tle_entries.append(
                    {
                        "name": tle[0] if len(tle) > 0 else "",
                        "line1": tle[1] if len(tle) > 1 else "",
                        "line2": tle[2] if len(tle) > 2 else "",
                        "cached_at": cached_at,
                        "expired": tle_expired,
                    }
                )
    except Exception as exc:
        logger.warning("Failed to read TLE cache: %s", exc)

    return render_template(
        "cached_data.html",
        route_entries=route_entries,
        tle_entries=tle_entries,
        tle_fetched_at=tle_fetched_at,
        tle_expired=tle_expired,
        csrf_token=csrf_token(),
        active_page="cached_data",
    )


@app.route("/cached-data/routes/delete", methods=["POST"])
@login_required
def cached_data_routes_delete():
    """Delete selected entries from the route cache."""
    if not validate_csrf(request.form):
        return (
            render_template(
                "cached_data.html",
                route_entries=[],
                tle_entries=[],
                tle_fetched_at="",
                tle_expired=False,
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="cached_data",
            ),
            403,
        )

    keys = request.form.getlist("keys")
    if not keys:
        return redirect(url_for("cached_data"))

    removed = routes_cache.delete(keys, routes_cache.KIND_ROUTE)
    logger.info("Deleted %d route cache entries (requested %d)", removed, len(keys))
    return redirect(url_for("cached_data"))


@app.route("/cached-data/tles/delete", methods=["POST"])
@login_required
def cached_data_tles_delete():
    """Delete selected TLE entries from the TLE cache file."""

    if not validate_csrf(request.form):
        return (
            render_template(
                "cached_data.html",
                route_entries=[],
                tle_entries=[],
                tle_fetched_at="",
                tle_expired=False,
                csrf_token=csrf_token(),
                error="Invalid CSRF token.",
                active_page="cached_data",
            ),
            403,
        )

    names = request.form.getlist("keys")
    if not names:
        return redirect(url_for("cached_data"))

    try:
        from utilities.tle_manager import load_cache, save_cache

        cached = load_cache()
        if cached:
            tles = [tuple(t) for t in cached["tles"]]
            original = len(tles)
            tles = [t for t in tles if t[0] not in names]
            removed = original - len(tles)
            if removed:
                save_cache(tles)
                logger.info(
                    "Deleted %d TLE cache entries (requested %d)",
                    removed,
                    len(names),
                )
    except Exception as exc:
        logger.error("TLE cache delete failed: %s", exc)

    return redirect(url_for("cached_data"))


# ---------------------------------------------------------------------------
# Provider API usage (/api) - totals over a date range or all history
# ---------------------------------------------------------------------------


def _usage_summary_for(start=None, end=None) -> dict:
    """Validate the optional date range and return aggregated usage tallies."""
    for name, value in (("start", start), ("end", end)):
        if value is not None:
            try:
                time.strptime(value, "%Y-%m-%d")
            except ValueError:
                abort(
                    400,
                    description=f"invalid {name} date (expected YYYY-MM-DD): {value!r}",
                )
    if start is not None and end is not None and start > end:
        start, end = end, start  # friendlier than an error
    return usage_tally.summary(start=start, end=end)


@app.route("/api")
@login_required
def api_usage():
    """Provider API usage totals over the whole logging history."""
    return render_template(
        "api_usage.html",
        summary=_usage_summary_for(),
        csrf_token=csrf_token(),
        active_page="api_usage",
    )


@app.route("/api/<start>/<end>")
@login_required
def api_usage_range(start, end):
    """Provider API usage totals between two dates (inclusive)."""
    return render_template(
        "api_usage.html",
        summary=_usage_summary_for(start, end),
        csrf_token=csrf_token(),
        active_page="api_usage",
    )


@app.route("/api/json")
@login_required
def api_usage_json():
    """Provider API usage totals (all history) as JSON."""
    return jsonify(_usage_summary_for())


@app.route("/api/<start>/<end>/json")
@login_required
def api_usage_range_json(start, end):
    """Provider API usage totals between two dates (inclusive) as JSON."""
    return jsonify(_usage_summary_for(start, end))


@app.route("/api/clear", methods=["POST"])
@login_required
def api_usage_clear():
    """Erase all recorded provider usage tallies."""
    if not validate_csrf(request.form):
        abort(403, description="Invalid CSRF token.")
    usage_tally.clear()
    logger.info("Provider usage tallies cleared")
    return redirect(url_for("api_usage"))
