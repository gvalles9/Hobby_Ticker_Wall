from __future__ import annotations

from types import SimpleNamespace

from scenes.idle.themes import classic_idle_theme


def _theme():
    theme = classic_idle_theme.ClassicIdleTheme.__new__(
        classic_idle_theme.ClassicIdleTheme
    )
    theme.panel = object()
    theme.canvas = object()
    theme.weather_icon_drawn = False
    theme.last_weather_icon_key = None
    return theme


def test_classic_idle_draws_and_caches_current_condition_icon(monkeypatch):
    drawn = []
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(weather_mode=1, observer_lat=40.0, observer_lng=-75.0),
    )
    monkeypatch.setattr(classic_idle_theme, "is_daytime", lambda lat, lng: True)
    monkeypatch.setattr(
        classic_idle_theme,
        "draw_icon",
        lambda panel, canvas, x, y, icon: drawn.append((x, y, icon)),
    )

    theme = _theme()
    weather = {"condition_code": 1000}
    theme.draw_weather_icon(weather)
    theme.draw_weather_icon(weather)

    assert drawn == [
        (*classic_idle_theme.WEATHER_ICON_POSITION, "sun"),
    ]
    assert theme.weather_icon_drawn is True


def test_classic_idle_weather_icon_has_balanced_spacing_at_right_edge():
    icon_x, _ = classic_idle_theme.WEATHER_ICON_POSITION

    assert (
        classic_idle_theme.SCREEN_WIDTH - (icon_x + 15)
        == classic_idle_theme.WEATHER_ICON_TEXT_GAP
    )
    assert (
        icon_x - classic_idle_theme.WEATHER_DETAIL_RIGHT_EDGE
        == classic_idle_theme.WEATHER_ICON_TEXT_GAP
    )


def test_classic_idle_clears_previous_icon_when_condition_changes(monkeypatch):
    cleared = []
    drawn = []
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(weather_mode=1, observer_lat=40.0, observer_lng=-75.0),
    )
    monkeypatch.setattr(classic_idle_theme, "is_daytime", lambda lat, lng: True)
    monkeypatch.setattr(
        classic_idle_theme,
        "blank_area",
        lambda panel, canvas, x, y: cleared.append((x, y)),
    )
    monkeypatch.setattr(
        classic_idle_theme,
        "draw_icon",
        lambda panel, canvas, x, y, icon: drawn.append(icon),
    )

    theme = _theme()
    theme.draw_weather_icon({"condition_code": 1000})
    theme.draw_weather_icon({"condition_code": 1006})

    assert cleared == [classic_idle_theme.WEATHER_ICON_POSITION]
    assert drawn == ["sun", "cloud"]


def test_classic_idle_removes_icon_when_weather_display_is_off(monkeypatch):
    cleared = []
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(weather_mode=0, observer_lat=40.0, observer_lng=-75.0),
    )
    monkeypatch.setattr(
        classic_idle_theme,
        "blank_area",
        lambda panel, canvas, x, y: cleared.append((x, y)),
    )

    theme = _theme()
    theme.weather_icon_drawn = True
    theme.draw_weather_icon({"condition_code": 1000})

    assert cleared == [classic_idle_theme.WEATHER_ICON_POSITION]
    assert theme.weather_icon_drawn is False


def test_classic_idle_draws_labeled_temperature_humidity_rain_and_wind(monkeypatch):
    class Panel:
        def __init__(self):
            self.text = []

        def draw_text(self, canvas, font, x, y, colour, text):
            self.text.append((x, y, text))

    panel = Panel()
    theme = _theme()
    theme.panel = panel
    theme.last_weather_details = None
    theme.last_temp_c = None
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(
            weather_mode=1,
            temperature_unit="c",
            precipitation_unit="mm",
            speed_unit="kmh",
        ),
    )
    monkeypatch.setattr(classic_idle_theme, "TC", lambda colour: colour)
    monkeypatch.setattr(
        classic_idle_theme, "font_text_width", lambda font, text: len(text) * 4
    )
    monkeypatch.setattr(
        classic_idle_theme, "temperature_to_colour", lambda temp: "temp"
    )

    theme.draw_weather_details(
        {
            "temp_c": 18.4,
            "humidity": 62,
            "precip_mm": 1.2,
            "wind_kph": 14,
            "wind_degree": 45,
        }
    )

    assert [entry[2] for entry in panel.text] == [
        "Temp 18C",
        "Hum 62%",
        "Rain 1.2mm",
        "Wind 14kmh NE",
    ]
    expected_positions = [
        (
            classic_idle_theme.WEATHER_DETAIL_RIGHT_EDGE - len(text) * 4,
            y,
        )
        for text, y in zip(
            ("Temp 18C", "Hum 62%", "Rain 1.2mm", "Wind 14kmh NE"),
            classic_idle_theme.WEATHER_DETAIL_Y_POSITIONS,
        )
    ]
    assert [entry[:2] for entry in panel.text] == expected_positions
    assert all(
        x + len(text) * 4 == classic_idle_theme.WEATHER_DETAIL_RIGHT_EDGE
        for (x, _), text in zip(
            expected_positions,
            ("Temp 18C", "Hum 62%", "Rain 1.2mm", "Wind 14kmh NE"),
        )
    )


def test_classic_idle_formats_precipitation_in_inches(monkeypatch):
    class Panel:
        def __init__(self):
            self.text = []

        def draw_text(self, canvas, font, x, y, colour, text):
            self.text.append(text)

    panel = Panel()
    theme = _theme()
    theme.panel = panel
    theme.last_weather_details = None
    theme.last_temp_c = None
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(
            weather_mode=1,
            temperature_unit="f",
            precipitation_unit="in",
            speed_unit="mph",
        ),
    )
    monkeypatch.setattr(classic_idle_theme, "TC", lambda colour: colour)
    monkeypatch.setattr(
        classic_idle_theme, "font_text_width", lambda font, text: len(text) * 4
    )
    monkeypatch.setattr(
        classic_idle_theme, "temperature_to_colour", lambda temp: "temp"
    )

    theme.draw_weather_details(
        {
            "temp_c": 18.4,
            "humidity": 62,
            "precip_mm": 1.27,
            "wind_kph": 14,
            "wind_degree": 45,
        }
    )

    assert "Rain 0.05in" in panel.text


def test_classic_idle_clears_weather_details_when_weather_is_unavailable(monkeypatch):
    class Panel:
        def __init__(self):
            self.text = []

        def draw_text(self, canvas, font, x, y, colour, text):
            self.text.append((x, y, text))

    panel = Panel()
    theme = _theme()
    theme.panel = panel
    theme.last_weather_details = (
        "Temp 18C",
        "Hum 62%",
        "Rain 1.2mm",
        "Wind 14kmh NE",
    )
    theme.last_temp_c = 18.4
    monkeypatch.setattr(
        classic_idle_theme.Config,
        "instance",
        lambda: SimpleNamespace(weather_mode=1),
    )
    monkeypatch.setattr(classic_idle_theme, "TC", lambda colour: colour)

    theme.draw_weather_details(None)

    assert [entry[2] for entry in panel.text] == [
        "Temp 18C",
        "Hum 62%",
        "Rain 1.2mm",
        "Wind 14kmh NE",
    ]
    assert theme.last_weather_details is None
