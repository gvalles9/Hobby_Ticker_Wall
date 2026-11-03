from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from scenes.idle.themes import theme_utilities


def test_noaa_weather_parser_normalizes_observations_and_forecasts():
    now = datetime.datetime.now(datetime.timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    start = now.isoformat()
    day = now.date().isoformat()
    hourly_forecast = {
        "properties": {
            "periods": [
                {
                    "startTime": start,
                    "temperature": 68,
                    "temperatureUnit": "F",
                    "shortForecast": "Partly Cloudy",
                }
            ]
        }
    }
    daily_forecast = {
        "properties": {
            "periods": [
                {
                    "startTime": f"{day}T06:00:00+00:00",
                    "temperature": 50,
                    "temperatureUnit": "F",
                    "isDaytime": False,
                    "shortForecast": "Mostly Cloudy",
                },
                {
                    "startTime": f"{day}T12:00:00+00:00",
                    "temperature": 70,
                    "temperatureUnit": "F",
                    "isDaytime": True,
                    "shortForecast": "Sunny",
                },
            ]
        }
    }
    observations = {
        "properties": {
            "temperature": {"value": 20},
            "relativeHumidity": {"value": 70},
            "windSpeed": {"value": 2},
            "windDirection": {"value": 180},
            "barometricPressure": {"value": 101325},
            "precipitationLastHour": {"value": 1.2},
            "textDescription": "Clear",
        }
    }
    grid_data = {
        "properties": {
            "quantitativePrecipitation": {
                "values": [
                    {
                        "validTime": f"{start}/PT1H",
                        "value": 1.5,
                        "unitCode": "wmoUnit:kg_m-2",
                    }
                ]
            }
        }
    }

    parsed = theme_utilities._parse_noaa_weather(
        hourly_forecast,
        daily_forecast,
        observations,
        grid_data,
        39.7,
        -97.1,
    )

    assert parsed["temp_c"] == 20
    assert parsed["humidity"] == 70
    assert parsed["wind_kph"] == 7.2
    assert parsed["pressure_mb"] == 1013.25
    assert parsed["precip_mm"] == 1.2
    assert parsed["condition_code"] == 1000
    assert theme_utilities._noaa_condition_code("Partly Sunny") == 1003
    assert parsed["hourly"][0] == {
        "temp_c": 20,
        "precip_mm": 1.5,
        "condition_code": 1003,
    }
    assert parsed["daily"][0]["mintemp_c"] == 10
    assert parsed["daily"][0]["maxtemp_c"] == pytest.approx(21.11111111111111)
    assert parsed["daily"][0]["totalprecip_mm"] == 1.5
    assert parsed["astro"]["sunrise"]


def test_weather_service_uses_noaa_without_weatherapi_key(monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    point_url = theme_utilities.NOAA_POINTS_URL.format(lat=39.7, lng=-97.1)
    responses = {
        point_url: {
            "properties": {
                "forecastHourly": "hourly",
                "forecast": "daily",
                "forecastGridData": "grid",
                "observationStations": "stations",
            }
        },
        "hourly": {
            "properties": {
                "periods": [
                    {
                        "startTime": now.isoformat(),
                        "temperature": 68,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    }
                ]
            }
        },
        "daily": {"properties": {"periods": []}},
        "stations": {"features": [{"id": "station"}]},
        "station/observations/latest": {"properties": {"temperature": {"value": 20}}},
        "grid": {"properties": {"quantitativePrecipitation": {"values": []}}},
    }
    requested = []
    monkeypatch.setattr(
        theme_utilities,
        "_noaa_json",
        lambda url: requested.append(url) or responses[url],
    )
    monkeypatch.setattr(
        "setup.configuration.Config.instance",
        lambda: SimpleNamespace(
            weatherapi_key="",
            observer_lat=39.7,
            observer_lng=-97.1,
        ),
    )

    service = theme_utilities.WeatherService()
    service.do_fetch()

    assert requested[0] == point_url
    assert service.get()["temp_c"] == 20


def test_weather_service_uses_weatherapi_when_key_is_configured(monkeypatch):
    requested = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    monkeypatch.setattr(
        theme_utilities.urllib.request,
        "urlopen",
        lambda url, timeout: requested.append((url, timeout)) or Response(),
    )
    monkeypatch.setattr(
        "setup.configuration.Config.instance",
        lambda: SimpleNamespace(
            weatherapi_key="test-key",
            observer_lat=39.7,
            observer_lng=-97.1,
        ),
    )

    service = theme_utilities.WeatherService()
    service.do_fetch()

    assert len(requested) == 1
    assert "key=test-key" in requested[0][0]
    assert service.get() is not None
