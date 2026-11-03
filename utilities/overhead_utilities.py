"""
Shared helpers for the overhead data-source libraries (fr24, tar1090, osn).

Consolidates:
  - Constants (EARTH_RADIUS_KM, BLANK_FIELDS)
  - Unit conversions (metres->feet, m/s->knots, m/s->fpm)
  - Geometry (in_zone, distance_from_home)
  - Field cleaning (clean_field)
  - Airport info lookup (bundled airports.json)
"""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371
EARTH_RADIUS_M = EARTH_RADIUS_KM * 1000.0
BLANK_FIELDS = {"", "N/A", "NONE"}

# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------


def metres_to_feet(m) -> float:
    """Convert metres to feet, returning 0.0 on invalid input."""
    try:
        return float(m) * 3.28084
    except (TypeError, ValueError):
        return 0.0


def ms_to_knots(ms) -> int:
    """Convert metres/second to knots, returning 0 on invalid input."""
    try:
        return int(float(ms) * 1.94384)
    except (TypeError, ValueError):
        return 0


def ms_to_fpm(ms) -> int:
    """Convert metres/second to feet/minute, returning 0 on invalid input."""
    try:
        return int(float(ms) * 196.85)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def in_zone(lat, lon, zone) -> bool:
    """Return True if (lat, lon) falls inside the bounding box *zone*.

    *zone* is a dict with keys ``tl_y``, ``tl_x`` (top-left) and
    ``br_y``, ``br_x`` (bottom-right).
    """
    return zone["br_y"] <= lat <= zone["tl_y"] and zone["tl_x"] <= lon <= zone["br_x"]


# Returned for invalid input so distance-based sorting still works: bad
# entries sort last instead of the sort raising or the order going random.
# Public: display-side callers (Overhead._to_flight) use it to recognise
# "unknown" results rather than rendering a million-kilometre aircraft.
DISTANCE_SENTINEL_KM = 1e6


def _is_finite_number(value) -> bool:
    """True for real ints/floats - bools, NaN/inf and overflow excluded."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def distance_from_home(lat, lon, alt_ft, home) -> float:
    """Distance from an aircraft to the observer, in km.

    Haversine ground track plus the altitude difference as the vertical
    leg - the slant-range approximation used by ADS-B tooling.

    Parameters
    ----------
    lat, lon : float
        Position of the aircraft in decimal degrees.
    alt_ft : float
        Aircraft altitude in feet.
    home : sequence of [lat, lon, radius_km]
        Observer location.  ``radius_km`` is the observer's distance from
        the Earth's centre, so the legacy ``EARTH_RADIUS_KM`` value means
        the observer sits at sea level.

    Returns
    -------
    float
        Distance in km.  Invalid input (malformed *home*, non-numeric or
        non-finite coordinates) is logged and returns
        ``DISTANCE_SENTINEL_KM`` so sorting always works and bad entries
        sort last rather than failing silently.
    """
    try:
        home_lat, home_lon, home_radius_km = home
    except (TypeError, ValueError):
        logger.warning("distance_from_home: malformed home %r", home)
        return DISTANCE_SENTINEL_KM

    values = (lat, lon, alt_ft, home_lat, home_lon, home_radius_km)
    if not all(_is_finite_number(v) for v in values):
        logger.warning(
            "distance_from_home: non-numeric position "
            "(lat=%r, lon=%r, alt_ft=%r, home=%r)",
            lat,
            lon,
            alt_ft,
            home,
        )
        return DISTANCE_SENTINEL_KM

    # home carries the distance from the Earth's centre, so sea level is
    # EARTH_RADIUS_KM and the observer's altitude is the difference.
    observer_alt_m = (home_radius_km - EARTH_RADIUS_KM) * 1000.0
    aircraft_alt_m = alt_ft * 0.3048

    lat1 = math.radians(lat)
    lat2 = math.radians(home_lat)
    dlat = lat2 - lat1
    dlon = math.radians(home_lon - lon)

    # Haversine central angle.  h is clamped to [0, 1] - floating-point
    # rounding can nudge it just past 1 for near-antipodal points, which
    # would turn sqrt(1 - h) into a domain error.
    sin_dlat = math.sin(dlat / 2) ** 2
    sin_dlon = math.sin(dlon / 2) ** 2
    h = sin_dlat + math.cos(lat1) * math.cos(lat2) * sin_dlon
    h = min(1.0, max(0.0, h))
    horizontal_m = 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(h), math.sqrt(1.0 - h))

    vertical_m = aircraft_alt_m - observer_alt_m
    # hypot is the overflow-safe form of sqrt(horizontal**2 + vertical**2).
    return math.hypot(horizontal_m, vertical_m) / 1000.0


# ---------------------------------------------------------------------------
# Field cleaning
# ---------------------------------------------------------------------------


def clean_field(value) -> str:
    """Strip whitespace and return '' for blank/None/sentinel values."""
    if value is None:
        return ""
    try:
        value = value.strip()
    except AttributeError:
        value = str(value).strip()
    return "" if value.upper() in BLANK_FIELDS else value


# ---------------------------------------------------------------------------
# Airport info lookup (bundled airports.json)
# ---------------------------------------------------------------------------

_airports_cache: dict[str, dict] = {}
_airports_loaded = False
_airport_coordinates_cache: dict[str, dict[str, float]] = {}
_airport_coordinates_loaded = False


def _selected_airports_filename() -> str:
    """Pick the lookup table file from config.

    Lazily imported: setup.configuration resolves its data paths at
    import time and this module must stay import-light.
    """
    from setup.configuration import Config

    full = bool(Config.instance().airport_lookup_full)
    return "airports-full.json" if full else "airports.json"


def _load_airports():
    global _airports_cache, _airports_loaded
    if _airports_loaded:
        return
    _airports_loaded = True
    path = Path(__file__).parent.parent / "assets" / _selected_airports_filename()
    try:
        with open(path, encoding="utf-8") as file:
            _airports_cache = json.load(file)
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        _airports_cache = {}


def reset_airports_cache() -> None:
    """Reset the airports.json cache (used by tests)."""
    global _airports_cache, _airports_loaded
    _airports_cache = {}
    _airports_loaded = False


def airport_info(iata: str) -> dict:
    """Return the full airport dict {name, municipality, country_name} or {}."""
    _load_airports()
    return _airports_cache.get(iata.upper(), {})


def airport_coordinates(code: str) -> dict[str, float]:
    """Return coordinates for an airport code, or {} when unavailable."""
    global _airport_coordinates_cache, _airport_coordinates_loaded
    if not _airport_coordinates_loaded:
        _airport_coordinates_loaded = True
        path = Path(__file__).parent.parent / "assets" / "airport_coordinates.json"
        try:
            with open(path, encoding="utf-8") as file:
                _airport_coordinates_cache = json.load(file)
        except Exception as e:
            logger.warning("Failed to load %s: %s", path, e)
            _airport_coordinates_cache = {}
    return _airport_coordinates_cache.get((code or "").upper(), {})


def route_progress_fraction(
    origin: str, destination: str, latitude: float | None, longitude: float | None
) -> float | None:
    """Estimate route progress as direct distance travelled from origin."""
    if latitude is None or longitude is None:
        return None
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    ):
        return None

    start = airport_coordinates(origin)
    end = airport_coordinates(destination)
    if not start or not end:
        return None

    def distance_km(point: dict[str, float]) -> float:
        return distance_from_home(
            lat,
            lon,
            0,
            [point["latitude"], point["longitude"], EARTH_RADIUS_KM],
        )

    total_distance = distance_from_home(
        end["latitude"],
        end["longitude"],
        0,
        [start["latitude"], start["longitude"], EARTH_RADIUS_KM],
    )
    if (
        not math.isfinite(total_distance)
        or total_distance <= 0
        or total_distance >= DISTANCE_SENTINEL_KM
    ):
        return None
    travelled = distance_km(start)
    if not math.isfinite(travelled) or travelled >= DISTANCE_SENTINEL_KM:
        return None
    return min(1.0, max(0.0, travelled / total_distance))


def airport_name(iata: str) -> str:
    """Return the airport name for *iata*, or '' if unknown."""
    return airport_info(iata).get("name", "")
