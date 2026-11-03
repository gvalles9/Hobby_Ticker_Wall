"""
ClassicIdleTheme - clock, date, day-of-week, and weather bar.

The original idle screen layout.  Inherits scene-protocol boilerplate
from BaseIdleScene and implements draw_content() with the classic
clock/date/weather layout.
"""

from __future__ import annotations

import datetime
from math import ceil

from scenes.idle.idle_scene import BaseIdleScene
from scenes.idle.themes.icons.weather.codes import code_to_weather
from scenes.idle.themes.icons.weather.forecast_sprite import (
    blank_area,
    draw_icon,
)
from scenes.idle.themes.theme_utilities import (
    _RAINFALL_SENSITIVITY_LEVELS,
    RAINFALL_12HR_MARKERS,
    RAINFALL_COLUMN_WIDTH,
    RAINFALL_GRAPH_HEIGHT,
    RAINFALL_GRAPH_ORIGIN,
    RAINFALL_HOURS,
    RAINFALL_OVERSPILL_FLASH_ENABLED,
    font_text_width,
    format_display_date,
    temperature_to_colour,
)
from setup import fonts
from setup.configuration import Config
from setup.screen import WIDTH as SCREEN_WIDTH
from setup.themes import (
    TC,
    THEME_BG,
    THEME_CURRENT_DATE,
    THEME_CURRENT_DAY,
    THEME_TIME,
    THEME_TIME_AMPM,
)
from utilities.sun_times import is_daytime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Clock
CLOCK_FONT = fonts.regular
CLOCK_AMPM_FONT = fonts.extrasmall
CLOCK_POSITION = (1, 8)
AMPM_POSITION_Y = 6

# Date
DATE_FONT = fonts.small
DATE_POSITION = (1, 31)
# Day of week
DAY_FONT = fonts.small
DAY_POSITION = (2, 23)

# Temperature display
TEMPERATURE_FONT = fonts.extrasmall
WEATHER_ICON_RIGHT_MARGIN = 4
WEATHER_ICON_TEXT_GAP = 4
WEATHER_ICON_POSITION = (SCREEN_WIDTH - 15 - WEATHER_ICON_RIGHT_MARGIN, 8)
WEATHER_DETAIL_RIGHT_EDGE = WEATHER_ICON_POSITION[0] - WEATHER_ICON_TEXT_GAP
WEATHER_DETAIL_Y_POSITIONS = (6, 12, 18, 24)


class ClassicIdleTheme(BaseIdleScene):
    """
    Classic idle layout: clock, date, day-of-week, weather temperature +
    rainfall graph.
    """

    # ------------------------------------------------------------------
    # Theme-specific state
    # ------------------------------------------------------------------

    def theme_init(self) -> None:
        """Called by BaseIdleScene.__init__ to let the theme set up state."""
        self.last_time: str | None = None
        self.last_date: str | None = None
        self.last_day: str | None = None
        self.last_temp_c: float | None = None
        self.last_weather_details: tuple[str, str, str, str] | None = None
        self.last_weather_icon_key: tuple[int, bool] | None = None
        self.weather_icon_drawn = False
        self.last_rain_data: list | None = None

    def theme_reset(self) -> None:
        """Called by BaseIdleScene.reset() to clear theme-specific state."""
        self.last_time = None
        self.last_date = None
        self.last_day = None
        self.last_temp_c = None
        self.last_weather_details = None
        self.last_weather_icon_key = None
        self.weather_icon_drawn = False
        self.last_rain_data = None

    # ------------------------------------------------------------------
    # draw_content - called once per second by BaseIdleScene.draw()
    # ------------------------------------------------------------------

    def draw_content(self, count: int) -> None:
        self.draw_clock()
        self.draw_date()
        self.draw_day()
        self.draw_weather(count)

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def draw_clock(self) -> None:
        cfg = Config.instance()
        now = datetime.datetime.now()
        if cfg.clock_24hr:
            time_str = now.strftime("%H:%M")
            ampm_str = None
        else:
            # Strip leading zero from 12-hour format (cross-platform:
            # %-I is Linux-only, %#I is Windows-only).
            hour = int(now.strftime("%I"))
            time_str = f"{hour}:{now.strftime('%M')}"
            ampm_str = now.strftime("%p")

        current_time = time_str + (ampm_str or "")
        if self.last_time == current_time:
            return

        # Undraw old value
        if self.last_time is not None:
            self.panel.draw_text(
                self.canvas,
                CLOCK_FONT,
                CLOCK_POSITION[0],
                CLOCK_POSITION[1],
                TC(THEME_BG),
                self.last_time[:5],
            )
            if ampm_str:
                old_ampm = "AM" if "AM" in self.last_time else "PM"
                ampm_position_x = CLOCK_POSITION[0] + font_text_width(
                    CLOCK_FONT, self.last_time[:5]
                )
                self.panel.draw_text(
                    self.canvas,
                    CLOCK_AMPM_FONT,
                    ampm_position_x + 1,
                    AMPM_POSITION_Y,
                    TC(THEME_BG),
                    old_ampm,
                )

        self.last_time = current_time

        self.panel.draw_text(
            self.canvas,
            CLOCK_FONT,
            CLOCK_POSITION[0],
            CLOCK_POSITION[1],
            TC(THEME_TIME),
            time_str,
        )
        if ampm_str:
            ampm_position_x = CLOCK_POSITION[0] + font_text_width(CLOCK_FONT, time_str)
            self.panel.draw_text(
                self.canvas,
                CLOCK_AMPM_FONT,
                ampm_position_x + 1,
                AMPM_POSITION_Y,
                TC(THEME_TIME_AMPM),
                ampm_str,
            )

    # ------------------------------------------------------------------
    # Date
    # ------------------------------------------------------------------

    def draw_date(self) -> None:
        cfg = Config.instance()
        current_date = format_display_date(
            datetime.datetime.now(),
            cfg.date_format if cfg.date_format in (0, 1, 2) else 0,
        )
        if self.last_date == current_date:
            return

        if self.last_date is not None:
            self.panel.draw_text(
                self.canvas,
                DATE_FONT,
                DATE_POSITION[0],
                DATE_POSITION[1],
                TC(THEME_BG),
                self.last_date,
            )
        self.last_date = current_date
        self.panel.draw_text(
            self.canvas,
            DATE_FONT,
            DATE_POSITION[0],
            DATE_POSITION[1],
            TC(THEME_CURRENT_DATE),
            current_date,
        )

    # ------------------------------------------------------------------
    # Day of week
    # ------------------------------------------------------------------

    def draw_day(self) -> None:
        current_day = datetime.datetime.now().strftime("%A")
        if self.last_day == current_day:
            return

        if self.last_day is not None:
            self.panel.draw_text(
                self.canvas,
                DAY_FONT,
                DAY_POSITION[0],
                DAY_POSITION[1],
                TC(THEME_BG),
                self.last_day,
            )
        self.last_day = current_day
        self.panel.draw_text(
            self.canvas,
            DAY_FONT,
            DAY_POSITION[0],
            DAY_POSITION[1],
            TC(THEME_CURRENT_DAY),
            current_day,
        )

    # ------------------------------------------------------------------
    # Weather
    # ------------------------------------------------------------------

    def draw_weather_icon(self, weather: dict | None) -> None:
        cfg = Config.instance()
        if cfg.weather_mode < 1 or weather is None:
            if self.weather_icon_drawn:
                blank_area(
                    self.panel,
                    self.canvas,
                    *WEATHER_ICON_POSITION,
                )
                self.weather_icon_drawn = False
            self.last_weather_icon_key = None
            return

        condition_code = int(weather.get("condition_code", 0))
        night = not is_daytime(cfg.observer_lat, cfg.observer_lng)
        icon_key = (condition_code, night)
        if icon_key == self.last_weather_icon_key:
            return

        if self.weather_icon_drawn:
            blank_area(self.panel, self.canvas, *WEATHER_ICON_POSITION)
            self.weather_icon_drawn = False

        icon_name, _animation_name, _intensity = code_to_weather(condition_code, night)
        if icon_name is not None:
            draw_icon(self.panel, self.canvas, *WEATHER_ICON_POSITION, icon_name)
            self.weather_icon_drawn = True
        else:
            blank_area(self.panel, self.canvas, *WEATHER_ICON_POSITION)
        self.last_weather_icon_key = icon_key

    def weather_detail_strings(
        self, weather: dict
    ) -> tuple[tuple[str, str, str, str], float | None]:
        """Format labeled current weather values for the classic idle layout."""
        cfg = Config.instance()
        temp_c = weather.get("temp_c")
        if temp_c is None:
            temp_text = "Temp --"
        else:
            if cfg.temperature_unit == "f":
                temp = temp_c * 9.0 / 5.0 + 32
                unit = "F"
            elif cfg.temperature_unit == "k":
                temp = temp_c + 273.15
                unit = "K"
            else:
                temp = temp_c
                unit = "C"
            temp_text = f"Temp {round(temp)}{unit}"

        humidity = weather.get("humidity")
        humidity_text = f"Hum {round(humidity)}%" if humidity is not None else "Hum --"

        precip_mm = weather.get("precip_mm")
        if precip_mm is None:
            precip_text = "Rain --"
        elif cfg.precipitation_unit == "in":
            precip_text = f"Rain {precip_mm / 25.4:.2f}in"
        else:
            precip_text = f"Rain {round(precip_mm, 1):g}mm"

        wind_kph = weather.get("wind_kph")
        direction = weather.get("wind_dir")
        degrees = weather.get("wind_degree")
        if not direction and degrees is not None:
            direction = self.degrees_to_cardinal(degrees)
        if wind_kph is None:
            wind_text = "Wind --"
        elif getattr(cfg, "idle_speed_unit", cfg.speed_unit) == "mph":
            wind_text = f"Wind {round(wind_kph * 0.621371)}mph"
        else:
            wind_text = f"Wind {round(wind_kph)}kmh"
        if direction:
            wind_text = f"{wind_text} {direction}"

        return (temp_text, humidity_text, precip_text, wind_text), temp_c

    @staticmethod
    def degrees_to_cardinal(degrees: float) -> str:
        """Convert a wind bearing to one of eight cardinal directions."""
        directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        return directions[int((float(degrees) + 22.5) // 45) % 8]

    def draw_weather_details(self, weather: dict | None) -> None:
        """Draw or clear the labeled current-weather rows."""
        if weather is None or Config.instance().weather_mode < 1:
            details = None
            temp_c = None
        else:
            details, temp_c = self.weather_detail_strings(weather)

        if details == self.last_weather_details and temp_c == self.last_temp_c:
            return

        if self.last_weather_details is not None:
            for text, (x, y) in zip(
                self.last_weather_details,
                self.weather_detail_positions(self.last_weather_details),
            ):
                self.panel.draw_text(
                    self.canvas, TEMPERATURE_FONT, x, y, TC(THEME_BG), text
                )

        self.last_weather_details = details
        self.last_temp_c = temp_c
        if details is None:
            return

        for index, (text, (x, y)) in enumerate(
            zip(details, self.weather_detail_positions(details))
        ):
            colour = (
                temperature_to_colour(temp_c)
                if index == 0 and temp_c is not None
                else TC(THEME_CURRENT_DATE)
            )
            self.panel.draw_text(self.canvas, TEMPERATURE_FONT, x, y, colour, text)

    @staticmethod
    def weather_detail_positions(
        details: tuple[str, str, str, str],
    ) -> tuple:
        """Return right-aligned positions for the weather labels."""
        return tuple(
            (
                WEATHER_DETAIL_RIGHT_EDGE - font_text_width(TEMPERATURE_FONT, text),
                y,
            )
            for text, y in zip(details, WEATHER_DETAIL_Y_POSITIONS)
        )

    def erase_rainfall(self) -> None:
        """Erase the previously-drawn rainfall graph, if any."""
        if self.last_rain_data is not None:
            self.draw_rainfall_graph(self.last_rain_data, TC(THEME_BG))
            self.last_rain_data = None

    def draw_weather(self, count: int) -> None:
        cfg = Config.instance()
        weather = self.weather.get()
        self.draw_weather_icon(weather)
        self.draw_weather_details(weather)

        # --- Rainfall graph ---
        if cfg.weather_mode < 2:
            self.erase_rainfall()
            return

        rain_data = self.rainfall_data(weather)

        # Erase stale graph when data changes
        if self.last_rain_data is not None and self.last_rain_data != rain_data:
            self.draw_rainfall_graph(self.last_rain_data, TC(THEME_BG))

        if rain_data:
            flash_enabled = RAINFALL_OVERSPILL_FLASH_ENABLED and bool(count % 2)
            self.draw_rainfall_graph(rain_data, flash_enabled=flash_enabled)
            self.last_rain_data = list(rain_data)

    def rainfall_data(self, weather: dict | None) -> list | None:
        if weather is None:
            return None
        forecast = weather["hourly"]
        start = datetime.datetime.now().hour
        slice = forecast[:RAINFALL_HOURS]
        return [
            {
                "precip_mm": h["precip_mm"],
                "temp_c": h["temp_c"],
                "hour": (start + i) % 24,
            }
            for i, h in enumerate(slice)
        ]

    def draw_rainfall_graph(
        self, rain_data: list, graph_colour=None, flash_enabled: bool = False
    ) -> None:
        columns = range(
            0, RAINFALL_HOURS * RAINFALL_COLUMN_WIDTH, RAINFALL_COLUMN_WIDTH
        )
        for data, column_x in zip(rain_data, columns):
            rainfall_max = _RAINFALL_SENSITIVITY_LEVELS[
                Config.instance().rain_sensitivity
            ]
            rain_height = int(
                ceil(data["precip_mm"] * (RAINFALL_GRAPH_HEIGHT / rainfall_max))
            )
            if rain_height > RAINFALL_GRAPH_HEIGHT:
                flash_height = min(
                    rain_height - RAINFALL_GRAPH_HEIGHT, RAINFALL_GRAPH_HEIGHT + 1
                )
                rain_height = RAINFALL_GRAPH_HEIGHT
            else:
                flash_height = 0

            hourly_marker = RAINFALL_12HR_MARKERS and data["hour"] in (0, 12)
            x1 = RAINFALL_GRAPH_ORIGIN[0] + column_x
            x2 = x1 + RAINFALL_COLUMN_WIDTH
            y1 = RAINFALL_GRAPH_ORIGIN[1] + (1 if hourly_marker else 0)
            y2 = RAINFALL_GRAPH_ORIGIN[1] - rain_height

            colour = (
                graph_colour
                if graph_colour is not None
                else temperature_to_colour(data["temp_c"])
            )
            self.panel.draw_square(self.canvas, x1, y1, x2, y2, colour)

            if flash_height and flash_enabled and graph_colour is None:
                self.panel.draw_square(
                    self.canvas,
                    x1,
                    RAINFALL_GRAPH_ORIGIN[1] - RAINFALL_GRAPH_HEIGHT,
                    x2,
                    RAINFALL_GRAPH_ORIGIN[1] - RAINFALL_GRAPH_HEIGHT + flash_height - 1,
                    TC(THEME_BG),
                )
