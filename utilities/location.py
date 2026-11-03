"""Helpers for resolving an approximate location from the server's IP."""

import json
import math
import urllib.request


def ip_location(timeout: float = 5) -> tuple[float, float]:
    """Return latitude and longitude estimated by ipwho.is."""
    request = urllib.request.Request(
        "https://ipwho.is/",
        headers={"User-Agent": "FlightTracker location setup"},
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
    return latitude, longitude


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
    """Resolve and persist an unset automatic location using the server IP."""
    if config.get("location_source") != "auto":
        return False

    latitude, longitude = ip_location()
    config.update(
        {
            "flight_lat": latitude,
            "flight_lng": longitude,
            "flight_observer_lat": latitude,
            "flight_observer_lng": longitude,
            "location_source": "ip",
            **location_search_box(latitude, longitude),
        }
    )
    config.save()
    return True
