"""Helpers for resolving an approximate location from the server's IP."""

import json
import math
import urllib.request

from utilities.timezones import is_valid_zone


def ip_details(timeout: float = 5) -> tuple[float, float, str]:
    """Return ``(latitude, longitude, time_zone)`` estimated by ipwho.is.

    The provider answers with the coordinates and the IANA zone in the same
    response, so the zone costs no extra request.  The zone is ``""`` when
    it is missing or names something this system cannot resolve; callers
    treat that as "follow the OS time zone".
    """
    request = urllib.request.Request(
        "https://ipwho.is/",
        headers={
            "User-Agent": "HobbyTicker/1.0 (+https://github.com/gvalles9/Hobby_Ticker_Wall)"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read(65536))

    if not isinstance(data, dict) or not data.get("success", False):
        raise ValueError("IP location provider reported failure")
    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
    except (KeyError, TypeError) as exc:
        raise ValueError("IP location provider returned invalid coordinates") from exc
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("IP location provider returned out-of-range coordinates")

    zone = ""
    timezone = data.get("timezone")
    if isinstance(timezone, dict):
        # ``id`` is the IANA name and survives DST; ``offset``/``utc`` are a
        # snapshot and would be an hour wrong after a clock change.
        candidate = str(timezone.get("id") or "").strip()
        if is_valid_zone(candidate):
            zone = candidate
    return latitude, longitude, zone


def ip_location(timeout: float = 5) -> tuple[float, float]:
    """Return latitude and longitude estimated by ipwho.is."""
    latitude, longitude, _zone = ip_details(timeout)
    return latitude, longitude


def ip_timezone(timeout: float = 5) -> str:
    """Return the IANA zone ipwho.is reports for this network, or ``""``."""
    return ip_details(timeout)[2]


def location_search_box(latitude: float, longitude: float) -> dict[str, float]:
    """Build a roughly 20 km search box around a point."""
    latitude_offset = 10 / 111
    longitude_offset = 10 / (111 * max(abs(math.cos(math.radians(latitude))), 0.01))

    def wrap(value: float) -> float:
        return (value + 180) % 360 - 180

    return {
        "flight_zone_tl_y": min(90, latitude + latitude_offset),
        "flight_zone_tl_x": wrap(longitude - longitude_offset),
        "flight_zone_br_y": max(-90, latitude - latitude_offset),
        "flight_zone_br_x": wrap(longitude + longitude_offset),
    }


def resolve_auto_location(config) -> bool:
    """Resolve and persist an unset automatic location using the server IP.

    The zone that arrives with the same response seeds the display's time
    zone while the owner has not chosen one.  It is only ever a starting
    point: a manual pick - or a cleared field - always wins.
    """
    if config.get("location_source") != "auto":
        return False

    latitude, longitude, zone = ip_details()
    updates = {
        "flight_lat": latitude,
        "flight_lng": longitude,
        "flight_observer_lat": latitude,
        "flight_observer_lng": longitude,
        "location_source": "ip",
        **location_search_box(latitude, longitude),
    }
    if (
        zone
        and config.get("timezone_source", "auto") == "auto"
        and not config.get("timezone")
    ):
        updates["timezone"] = zone
    config.update(updates)
    config.save()
    return True
