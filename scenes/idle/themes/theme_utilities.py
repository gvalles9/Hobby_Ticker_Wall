"""
Shared utilities for idle screen themes.

Contains the WeatherService singleton (a daemon-thread weather fetcher
accessible by any theme or future scheduler), the temperature-to-colour
mapping, and assorted constants/helpers used across themes.
"""

from __future__ import annotations

import datetime
import json
import logging
import threading
import urllib.request

from display.rgbpanel import Colour
from display.spans import font_text_width
from setup import fonts
from setup.configuration import Config
from setup.screen import WIDTH as SCREEN_WIDTH
from setup.themes import (
    TC,
    THEME_BG,
    THEME_CURRENT_DATE,
    THEME_CURRENT_DAY,
    THEME_WEATHER_00C,
    THEME_WEATHER_01C,
    THEME_WEATHER_10C,
    THEME_WEATHER_15C,
    THEME_WEATHER_20C,
    THEME_WEATHER_25C,
    THEME_WEATHER_35C,
)

# ---------------------------------------------------------------------------
# Clock / Date / Day-of-week bar (shared by conditions + forecast themes)
# ---------------------------------------------------------------------------

_CLOCK_FONT = fonts.small
_CLOCK_POSITION = (0, 6)
_DATE_FONT = _CLOCK_FONT
_DATE_POSITION_Y = _CLOCK_POSITION[1]
# Date format: 0 = Month Dth YYYY, 1 = DD-MM-YYYY, 2 = MM-DD-YYYY.
_DATE_DAY_FIRST = {1: True, 2: False}
_DAY_ABBREVS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_display_date(date: datetime.datetime, date_format: int) -> str:
    """Format the configured calendar date consistently across idle themes."""
    if date_format == 0:
        day = date.day
        if 11 <= day % 100 <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{_MONTH_NAMES[date.month - 1]} {day}{suffix} {date.year}"

    fmt = "%d-%m-%Y" if date_format == 1 else "%m-%d-%Y"
    return date.strftime(fmt).replace("-0", "-").lstrip("0")


class ClockDateBar:
    """Renders the clock (top-left) + day-abbrev/date (top-right) row.

    Shared by ConditionsIdleTheme and ForecastIdleTheme, which use the
    exact same layout.  The only per-theme difference is the colour used
    for the clock digits, supplied via ``time_theme_key``.

    Usage::

        self.bar = ClockDateBar(panel, canvas, THEME_CONDITIONS_TIME)
        self.bar.draw()          # call once per second
        self.bar.reset()         # on scene reset / canvas clear
    """

    def __init__(self, panel, canvas, time_theme_key: str) -> None:
        self.panel = panel
        self.canvas = canvas
        self.time_theme_key = time_theme_key
        self.last_time: str | None = None
        self.last_date: str | None = None
        self._clock_width: int = 0

    def reset(self) -> None:
        """Clear cached state so the next draw() fully redraws."""
        self.last_time = None
        self.last_date = None
        self._clock_width = 0

    # -- clock ---------------------------------------------------------

    def _draw_clock(self) -> None:
        cfg = Config.instance()
        now = datetime.datetime.now()
        if cfg.clock_24hr:
            time_str = now.strftime("%H:%M")
        else:
            hour = int(now.strftime("%I"))
            time_str = f"{hour}:{now.strftime('%M')}"

        if self.last_time == time_str:
            return

        if self.last_time is not None:
            self.panel.draw_text(
                self.canvas,
                _CLOCK_FONT,
                _CLOCK_POSITION[0],
                _CLOCK_POSITION[1],
                TC(THEME_BG),
                self.last_time,
            )

        self.last_time = time_str
        self._clock_width = font_text_width(_CLOCK_FONT, time_str)
        self.panel.draw_text(
            self.canvas,
            _CLOCK_FONT,
            _CLOCK_POSITION[0],
            _CLOCK_POSITION[1],
            TC(self.time_theme_key),
            time_str,
        )

    # -- day + date ----------------------------------------------------

    def _draw_date(self) -> None:
        cfg = Config.instance()
        now = datetime.datetime.now()

        day_name = _DAY_ABBREVS[now.weekday()].upper()
        day = now.day
        month = now.month

        if cfg.date_format == 0:
            date_str = format_display_date(now, cfg.date_format)
        else:
            day_first = _DATE_DAY_FIRST.get(cfg.date_format, True)
            date_str = f"{day}/{month}" if day_first else f"{month}/{day}"

        current_date = day_name + " " + date_str
        if self.last_date == current_date:
            return

        date_width = font_text_width(_DATE_FONT, date_str)
        date_x = SCREEN_WIDTH + 1 - date_width
        day_width = font_text_width(_DATE_FONT, day_name)
        # Centre the day abbreviation in the gap between the clock and
        # the right-aligned date.
        gap_start = _CLOCK_POSITION[0] + self._clock_width
        gap_end = date_x
        day_x = gap_start + (gap_end - gap_start - day_width) // 2

        if self.last_date is not None:
            old_day_name = self.last_date[:3]
            old_date_str = self.last_date[4:]
            old_date_width = font_text_width(_DATE_FONT, old_date_str)
            old_date_x = SCREEN_WIDTH + 1 - old_date_width
            old_day_width = font_text_width(_DATE_FONT, old_day_name)
            old_gap_start = _CLOCK_POSITION[0] + self._clock_width
            old_gap_end = old_date_x
            old_day_x = (
                old_gap_start + (old_gap_end - old_gap_start - old_day_width) // 2
            )
            self.panel.draw_text(
                self.canvas,
                _DATE_FONT,
                old_day_x,
                _DATE_POSITION_Y,
                TC(THEME_BG),
                old_day_name,
            )
            self.panel.draw_text(
                self.canvas,
                _DATE_FONT,
                old_date_x,
                _DATE_POSITION_Y,
                TC(THEME_BG),
                old_date_str,
            )

        self.last_date = current_date
        self.panel.draw_text(
            self.canvas,
            _DATE_FONT,
            day_x,
            _DATE_POSITION_Y,
            TC(THEME_CURRENT_DAY),
            day_name,
        )
        self.panel.draw_text(
            self.canvas,
            _DATE_FONT,
            date_x,
            _DATE_POSITION_Y,
            TC(THEME_CURRENT_DATE),
            date_str,
        )

    # -- public --------------------------------------------------------

    def draw(self) -> None:
        """Redraw clock and date if either has changed. Call ~1/sec."""
        self._draw_clock()
        self._draw_date()


# ---------------------------------------------------------------------------
# Weather API constants
# ---------------------------------------------------------------------------

WEATHERAPI_URL = (
    "http://api.weatherapi.com/v1/forecast.json"
    "?key={key}&q={lat},{lng}&days=3&aqi=no&alerts=no"
)
NOAA_POINTS_URL = "https://api.weather.gov/points/{lat},{lng}"
NOAA_USER_AGENT = "FlightTracker/1.0 (https://github.com/ColinWaddell/FlightTracker)"
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rainfall graph constants (shared by classic + forecast themes)
# ---------------------------------------------------------------------------

RAINFALL_HOURS = 24
RAINFALL_12HR_MARKERS = True
RAINFALL_GRAPH_ORIGIN = (SCREEN_WIDTH - 24, 15)
RAINFALL_COLUMN_WIDTH = 1
RAINFALL_GRAPH_HEIGHT = 8
_RAINFALL_SENSITIVITY_LEVELS = (
    1,
    3,
    9,
)  # mm full-scale per sensitivity level (Egypt/UK/Singapore)
RAINFALL_OVERSPILL_FLASH_ENABLED = True

# ---------------------------------------------------------------------------
# Temperature thresholds -> theme colour keys
# ---------------------------------------------------------------------------

TEMPERATURE_THRESHOLDS = [
    (0, THEME_WEATHER_00C),
    (1, THEME_WEATHER_01C),
    (10, THEME_WEATHER_10C),
    (15, THEME_WEATHER_15C),
    (20, THEME_WEATHER_20C),
    (25, THEME_WEATHER_25C),
    (35, THEME_WEATHER_35C),
]


# ---------------------------------------------------------------------------
# Temperature -> colour
# ---------------------------------------------------------------------------


def temperature_to_colour(temp_c: float) -> Colour:
    """Map a temperature in C to an interpolated theme colour."""
    lo_temp, lo_key = TEMPERATURE_THRESHOLDS[0]
    hi_temp, hi_key = TEMPERATURE_THRESHOLDS[1]

    for i in range(1, len(TEMPERATURE_THRESHOLDS) - 1):
        if temp_c > TEMPERATURE_THRESHOLDS[i][0]:
            lo_temp, lo_key = TEMPERATURE_THRESHOLDS[i]
            hi_temp, hi_key = TEMPERATURE_THRESHOLDS[i + 1]

    c_lo = TC(lo_key)
    c_hi = TC(hi_key)

    if temp_c >= hi_temp:
        ratio = 1.0
    elif temp_c > lo_temp:
        ratio = (temp_c - lo_temp) / (hi_temp - lo_temp)
    else:
        ratio = 0.0

    return Colour(
        int(c_lo.red + (c_hi.red - c_lo.red) * ratio),
        int(c_lo.green + (c_hi.green - c_lo.green) * ratio),
        int(c_lo.blue + (c_hi.blue - c_lo.blue) * ratio),
    )


# ---------------------------------------------------------------------------
# Weather data parsing
# ---------------------------------------------------------------------------

# Fields copied verbatim from raw["current"] into the parsed dict.
_CURRENT_FLOAT_FIELDS = (
    "temp_c",
    "wind_kph",
    "pressure_mb",
    "precip_mm",
    "feelslike_c",
    "windchill_c",
    "heatindex_c",
    "dewpoint_c",
    "vis_km",
    "uv",
    "gust_kph",
)
_CURRENT_INT_FIELDS = (
    "wind_degree",
    "humidity",
    "cloud",
    "will_it_rain",
    "chance_of_rain",
    "will_it_snow",
    "chance_of_snow",
)
_CURRENT_STR_FIELDS = ("wind_dir",)

# Fields copied verbatim from raw["forecast"]["forecastday"][n]["day"].
_DAY_FLOAT_FIELDS = (
    "maxtemp_c",
    "mintemp_c",
    "avgtemp_c",
    "maxwind_kph",
    "totalprecip_mm",
    "totalsnow_cm",
)
_DAY_INT_FIELDS = (
    "avghumidity",
    "daily_will_it_rain",
    "daily_chance_of_rain",
    "daily_will_it_snow",
    "daily_chance_of_snow",
)


def _coerce(value, caster, default):
    """Safely cast *value* with *caster*, returning *default* on failure."""
    try:
        return caster(value)
    except (TypeError, ValueError):
        return default


def _parse_current(raw_current: dict) -> dict:
    """Extract and type-coerce the fields we care about from the API current block."""
    out = {}
    for key in _CURRENT_FLOAT_FIELDS:
        out[key] = _coerce(raw_current.get(key), float, 0.0)
    for key in _CURRENT_INT_FIELDS:
        out[key] = _coerce(raw_current.get(key), int, 0)
    for key in _CURRENT_STR_FIELDS:
        out[key] = str(raw_current.get(key, ""))
    # condition is a nested object
    out["condition_code"] = _coerce(
        raw_current.get("condition", {}).get("code"), int, 0
    )
    out["description"] = raw_current.get("condition", {}).get("text")
    return out


def _parse_day(raw_day: dict) -> dict:
    """Extract and type-coerce the fields we care about from a forecast day block."""
    out = {}
    for key in _DAY_FLOAT_FIELDS:
        out[key] = _coerce(raw_day.get(key), float, 0.0)
    for key in _DAY_INT_FIELDS:
        out[key] = _coerce(raw_day.get(key), int, 0)
    out["condition_code"] = _coerce(raw_day.get("condition", {}).get("code"), int, 0)
    return out


def _parse_astro(raw_astro: dict) -> dict:
    """Extract sunrise/sunset (and moon) strings from a forecast astro block.

    WeatherAPI returns these as strings like "06:30 AM" / "07:45 PM".
    We keep them as raw strings; callers parse them to ``datetime.time``
    via ``utilities.sun_times.parse_time`` (which handles the HH:MM part).
    Missing values default to empty strings.
    """
    out = {}
    for key in ("sunrise", "sunset", "moonrise", "moonset", "moon_phase"):
        out[key] = str(raw_astro.get(key, "")) if raw_astro else ""
    out["moon_illumination"] = _coerce(
        raw_astro.get("moon_illumination") if raw_astro else None, int, 0
    )
    return out


def _parse_hourly(raw_forecast_days: list) -> list[dict]:
    """Flatten all forecast hours into dicts with temp, precip, and condition code.

    The API returns 24 hours per day starting at 0:00 local time.  We
    only need the forecast from the current hour onwards, so the first
    ``current_hour`` entries (hours already elapsed today) are dropped.
    All time information in the API is in local time.
    """
    import datetime

    current_hour = datetime.datetime.now().hour

    out = []
    for day in raw_forecast_days:
        for h in day.get("hour", []):
            out.append(
                {
                    "temp_c": _coerce(h.get("temp_c"), float, 0.0),
                    "precip_mm": _coerce(h.get("precip_mm"), float, 0.0),
                    "condition_code": _coerce(
                        h.get("condition", {}).get("code"), int, 0
                    ),
                }
            )

    # Drop hours that have already elapsed today (e.g. if it's 2 AM,
    # discard elements 0 and 1 so the list starts at the current hour).
    return out[current_hour:]


def _parse_weather(raw: dict) -> dict:
    """Filter the full WeatherAPI response down to the fields we use.

    Returns a dict with current-condition fields at the root level,
    plus ``hourly`` and ``daily`` lists.  Missing or malformed values
    are coerced to safe defaults rather than raising.

    ``astro`` holds today's sunrise/sunset (and moon) strings parsed
    from the first forecast day's ``astro`` block, used by the
    Current Conditions idle theme.
    """
    current = raw.get("current", {})
    forecast = raw.get("forecast", {}).get("forecastday", [])

    parsed = _parse_current(current)
    parsed["hourly"] = _parse_hourly(forecast)
    parsed["daily"] = [_parse_day(d.get("day", {})) for d in forecast]

    # Today's astro block (sunrise/sunset) for the conditions theme.
    astro_raw = forecast[0].get("astro", {}) if forecast else {}
    parsed["astro"] = _parse_astro(astro_raw)

    return parsed


def _noaa_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": NOAA_USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


def _noaa_observation_value(observation: dict, key: str) -> float | None:
    value = observation.get(key, {}).get("value")
    return _coerce(value, float, None)


def _noaa_condition_code(description: str | None) -> int:
    """Map NWS forecast/observation descriptions to existing weather icons."""
    text = (description or "").lower()
    if any(word in text for word in ("partly sunny", "mostly sunny", "mostly clear")):
        return 1003
    if "thunder" in text:
        return 1087
    if "snow" in text or "blizzard" in text:
        return 1213
    if "sleet" in text or "freezing rain" in text or "ice" in text:
        return 1204
    if "rain" in text or "shower" in text or "drizzle" in text:
        return 1183
    if "fog" in text or "mist" in text or "haze" in text:
        return 1135
    if "overcast" in text:
        return 1009
    if "cloud" in text:
        if "partly" in text:
            return 1003
        return 1006
    if any(word in text for word in ("sunny", "clear", "fair")):
        return 1000
    return 1003


def _noaa_wind_kph(speed: str | None) -> float | None:
    """Parse NWS wind speeds such as '10 mph' or '5 to 10 mph'."""
    if not speed:
        return None
    parts = speed.split()
    values = [_coerce(part, float, None) for part in parts]
    values = [value for value in values if value is not None]
    if not values:
        return None
    multiplier = 1.609344 if "mph" in speed.lower() else 1.0
    return sum(values) / len(values) * multiplier


def _noaa_temp_c(value, unit: str | None) -> float | None:
    if value is None:
        return None
    temperature = _coerce(value, float, None)
    if temperature is None:
        return None
    return (temperature - 32) * 5 / 9 if unit == "F" else temperature


def _noaa_qpf_by_hour(grid_data: dict) -> dict[datetime.datetime, float]:
    """Return quantitative precipitation keyed by its UTC start time in mm."""
    result = {}
    values = (
        grid_data.get("properties", {})
        .get("quantitativePrecipitation", {})
        .get("values", [])
    )
    for entry in values:
        try:
            start_text, _duration = entry["validTime"].split("/", 1)
            start = datetime.datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            amount = float(entry["value"])
        except (KeyError, TypeError, ValueError):
            continue
        unit = entry.get("unitCode", "")
        if "m" in unit and "mm" not in unit and "kg_m-2" not in unit:
            amount *= 1000
        result[start] = amount
    return result


def _parse_noaa_weather(
    hourly_forecast: dict,
    daily_forecast: dict,
    observations: dict | None,
    grid_data: dict | None,
    lat: float,
    lng: float,
) -> dict:
    """Normalize NWS forecast/observation data for the existing idle themes."""
    hourly_periods = hourly_forecast.get("properties", {}).get("periods", [])
    daily_periods = daily_forecast.get("properties", {}).get("periods", [])
    qpf = _noaa_qpf_by_hour(grid_data or {})
    now = datetime.datetime.now(datetime.timezone.utc)

    observation = None
    if observations:
        observation_properties = observations.get("properties", {})
        observation = (
            observation_properties.get("periods", [None])[0]
            if "periods" in observation_properties
            else observation_properties
        )
    if observation is None and hourly_periods:
        period = hourly_periods[0]
        temp_c = _noaa_temp_c(period.get("temperature"), period.get("temperatureUnit"))
        current_description = period.get("shortForecast", "")
        current = {
            "temp_c": _coerce(temp_c, float, None),
            "humidity": _coerce(
                period.get("relativeHumidity", {}).get("value"), float, None
            ),
            "wind_kph": _noaa_wind_kph(period.get("windSpeed")),
            "wind_degree": None,
            "pressure_mb": None,
            "precip_mm": 0.0,
            "condition_code": _noaa_condition_code(current_description),
            "description": current_description,
            "uv": None,
        }
    elif observation is not None:
        current_description = observation.get("textDescription", "")
        temp_c = _noaa_observation_value(observation, "temperature")
        wind_speed = _noaa_observation_value(observation, "windSpeed")
        pressure = _noaa_observation_value(observation, "barometricPressure")
        precipitation = _noaa_observation_value(observation, "precipitationLastHour")
        current = {
            "temp_c": temp_c,
            "humidity": _noaa_observation_value(observation, "relativeHumidity"),
            "wind_kph": wind_speed * 3.6 if wind_speed is not None else None,
            "wind_degree": _noaa_observation_value(observation, "windDirection"),
            "pressure_mb": pressure / 100 if pressure is not None else None,
            "precip_mm": precipitation or 0.0,
            "condition_code": _noaa_condition_code(current_description),
            "description": current_description,
            "uv": None,
        }
    else:
        current = {
            "temp_c": None,
            "humidity": None,
            "wind_kph": None,
            "wind_degree": None,
            "pressure_mb": None,
            "precip_mm": 0.0,
            "condition_code": 1003,
            "description": "",
            "uv": None,
        }

    hourly = []
    for period in hourly_periods:
        try:
            start = datetime.datetime.fromisoformat(
                period["startTime"].replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError):
            continue
        if start.astimezone(datetime.timezone.utc) < now.replace(
            minute=0, second=0, microsecond=0
        ):
            continue
        temp_c = _noaa_temp_c(period.get("temperature"), period.get("temperatureUnit"))
        hourly.append(
            {
                "temp_c": _coerce(temp_c, float, 0.0),
                "precip_mm": qpf.get(start.astimezone(datetime.timezone.utc), 0.0),
                "condition_code": _noaa_condition_code(period.get("shortForecast")),
            }
        )

    daily_by_date = {}
    daily_tz_by_date = {}
    for period in daily_periods:
        try:
            daily_start = datetime.datetime.fromisoformat(
                period["startTime"].replace("Z", "+00:00")
            )
            day = daily_start.date()
        except (KeyError, TypeError, ValueError):
            continue
        daily_tz_by_date[day] = daily_start.tzinfo or datetime.timezone.utc
        entry = daily_by_date.setdefault(
            day,
            {
                "maxtemp_c": None,
                "mintemp_c": None,
                "avgtemp_c": None,
                "maxwind_kph": 0.0,
                "totalprecip_mm": 0.0,
                "totalsnow_cm": 0.0,
                "avghumidity": 0,
                "daily_will_it_rain": 0,
                "daily_chance_of_rain": 0,
                "daily_will_it_snow": 0,
                "daily_chance_of_snow": 0,
                "condition_code": 1003,
            },
        )
        temp_c = _noaa_temp_c(period.get("temperature"), period.get("temperatureUnit"))
        if period.get("isDaytime"):
            entry["maxtemp_c"] = _coerce(temp_c, float, None)
            entry["condition_code"] = _noaa_condition_code(period.get("shortForecast"))
        else:
            entry["mintemp_c"] = _coerce(temp_c, float, None)
        entry["avgtemp_c"] = (
            (entry["maxtemp_c"] + entry["mintemp_c"]) / 2
            if entry["maxtemp_c"] is not None and entry["mintemp_c"] is not None
            else entry["maxtemp_c"] or entry["mintemp_c"]
        )
        entry["maxwind_kph"] = max(
            entry["maxwind_kph"], _noaa_wind_kph(period.get("windSpeed")) or 0.0
        )
        precip_chance = _coerce(
            period.get("probabilityOfPrecipitation", {}).get("value"), int, 0
        )
        entry["daily_chance_of_rain"] = max(
            entry["daily_chance_of_rain"], precip_chance
        )
        entry["daily_will_it_rain"] = int(entry["daily_chance_of_rain"] > 0)
    for day, entry in daily_by_date.items():
        entry["totalprecip_mm"] = sum(
            amount
            for start, amount in qpf.items()
            if start.astimezone(daily_tz_by_date[day]).date() == day
        )

    from utilities.sun_times import approx_sunrise_sunset

    sunrise, sunset = approx_sunrise_sunset(lat, lng)
    return {
        **current,
        "hourly": hourly,
        "daily": list(daily_by_date.values()),
        "astro": {
            "sunrise": sunrise.strftime("%I:%M %p"),
            "sunset": sunset.strftime("%I:%M %p"),
            "moonrise": "",
            "moonset": "",
            "moon_phase": "",
            "moon_illumination": 0,
        },
    }


# ---------------------------------------------------------------------------
# WeatherService - singleton daemon-thread weather fetcher
# ---------------------------------------------------------------------------


class WeatherService(threading.Thread):
    """
    Singleton daemon thread that fetches weather on startup and then every
    ``weather_refresh_minutes`` minutes (configurable). A WeatherAPI key
    selects WeatherAPI.com; without one, the U.S.-only NOAA/NWS API is used.
    Thread-safe via a lock.

    Any consumer (idle theme, future scheduler, etc.) can call
    WeatherService.instance().get() to read the latest cached data.
    """

    _instance: WeatherService | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> WeatherService:
        """Return the singleton, starting it if necessary."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.start()
            return cls._instance

    def __init__(self):
        super().__init__(daemon=True, name="weather-service")
        self.lock = threading.Lock()
        self.weather_data: dict | None = None
        self.stop_event = threading.Event()

    def run(self) -> None:
        import logging

        from setup.configuration import Config

        logger = logging.getLogger(__name__)
        # Re-read the interval each iteration so a config change takes
        # effect on the next refresh cycle without restarting the thread.
        while True:
            cfg = Config.instance()
            try:
                from utilities.location import resolve_auto_location

                resolve_auto_location(cfg)
            except (OSError, TimeoutError, ValueError, KeyError) as exc:
                logger.warning("Automatic location lookup failed: %s", exc)
            else:
                self.do_fetch()
            if self.stop_event.wait(cfg.weather_refresh_seconds):
                break

    def do_fetch(self) -> None:
        from setup.configuration import Config

        cfg = Config.instance()

        for _ in range(3):
            try:
                if cfg.weatherapi_key:
                    url = WEATHERAPI_URL.format(
                        key=cfg.weatherapi_key,
                        lat=cfg.observer_lat,
                        lng=cfg.observer_lng,
                    )
                    with urllib.request.urlopen(url, timeout=10) as response:
                        raw = json.loads(response.read().decode())
                    parsed = _parse_weather(raw)
                else:
                    point = _noaa_json(
                        NOAA_POINTS_URL.format(
                            lat=cfg.observer_lat,
                            lng=cfg.observer_lng,
                        )
                    )
                    point_properties = point["properties"]
                    hourly_forecast = _noaa_json(point_properties["forecastHourly"])
                    daily_forecast = _noaa_json(point_properties["forecast"])
                    observations = None
                    try:
                        stations = _noaa_json(point_properties["observationStations"])
                        station_list = stations.get("features", [])
                        if station_list:
                            observations = _noaa_json(
                                station_list[0]["id"].rstrip("/")
                                + "/observations/latest"
                            )
                    except Exception:
                        _logger.warning(
                            "NOAA observation fetch failed; using hourly forecast "
                            "for current conditions",
                            exc_info=True,
                        )
                    grid_data = None
                    try:
                        grid_data = _noaa_json(point_properties["forecastGridData"])
                    except Exception:
                        _logger.warning(
                            "NOAA precipitation forecast fetch failed; rainfall "
                            "amounts will be unavailable",
                            exc_info=True,
                        )
                    parsed = _parse_noaa_weather(
                        hourly_forecast,
                        daily_forecast,
                        observations,
                        grid_data,
                        cfg.observer_lat,
                        cfg.observer_lng,
                    )

                with self.lock:
                    self.weather_data = parsed

                return

            except Exception:
                _logger.warning("Weather fetch failed; retrying", exc_info=True)
        _logger.error(
            "Weather fetch failed after retries; NOAA/NWS only supports U.S. "
            "forecast locations when no WeatherAPI key is configured"
        )

    def get(self) -> dict | None:
        with self.lock:
            return self.weather_data

    def stop(self) -> None:
        self.stop_event.set()
