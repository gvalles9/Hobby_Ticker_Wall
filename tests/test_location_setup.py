import json
from unittest.mock import MagicMock


def _authenticated_client():
    from web.app import app

    client = app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
    return client


def test_ip_location_requires_login():
    from web.app import app

    assert app.test_client().get("/api/location/ip").status_code == 302


def test_ip_location_returns_validated_coordinates(monkeypatch):
    import utilities.location as location

    monkeypatch.setattr(location, "ip_location", lambda: (40.7, -74.0))

    result = _authenticated_client().get("/api/location/ip")

    assert result.status_code == 200
    assert result.get_json() == {"latitude": 40.7, "longitude": -74.0}


def test_ip_location_works_during_first_setup(monkeypatch, fresh_config):
    """The wizard offers the button, so the guard must let the lookup through.

    Without an exemption the authenticated fetch was redirected to the wizard
    HTML page, and the browser reported "Unexpected token '<'".
    """
    import utilities.location as location

    fresh_config.data_store["web_password_hash"] = ""
    monkeypatch.setattr(location, "ip_location", lambda: (40.7, -74.0))

    result = _authenticated_client().get("/api/location/ip")

    assert result.status_code == 200
    assert result.is_json
    assert result.get_json() == {"latitude": 40.7, "longitude": -74.0}


def test_ip_location_rejects_invalid_coordinates(monkeypatch):
    import utilities.location as location

    def invalid_location():
        raise ValueError("IP location provider returned out-of-range coordinates")

    monkeypatch.setattr(location, "ip_location", invalid_location)

    result = _authenticated_client().get("/api/location/ip")

    assert result.status_code == 502
    assert "IP-based location lookup failed" in result.get_json()["error"]


def test_ip_location_provider_validates_response(monkeypatch):
    import utilities.location as location

    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {"success": True, "latitude": 40.7, "longitude": -74.0}
    ).encode()
    monkeypatch.setattr(
        location.urllib.request, "urlopen", lambda *args, **kwargs: response
    )

    assert location.ip_location() == (40.7, -74.0)
    # No time zone in the payload: callers fall back to the OS zone.
    assert location.ip_timezone() == ""


def test_ip_location_provider_rejects_out_of_range_coordinates(monkeypatch):
    import utilities.location as location

    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {"success": True, "latitude": 95, "longitude": 0}
    ).encode()
    monkeypatch.setattr(
        location.urllib.request, "urlopen", lambda *args, **kwargs: response
    )

    try:
        location.ip_location()
    except ValueError as exc:
        assert "out-of-range" in str(exc)
    else:
        raise AssertionError("Expected out-of-range location to be rejected")


def test_auto_location_is_persisted_and_manual_location_is_untouched(monkeypatch):
    from utilities.location import resolve_auto_location

    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "location_source": "auto",
        "timezone_source": "auto",
        "timezone": "",
    }.get(key, default)

    import utilities.location as location

    monkeypatch.setattr(
        location, "ip_details", lambda: (40.7, -74.0, "America/New_York")
    )
    assert resolve_auto_location(config)
    updated = config.update.call_args.args[0]
    assert updated["flight_lat"] == 40.7
    assert updated["flight_lng"] == -74.0
    assert updated["flight_observer_lat"] == 40.7
    assert updated["flight_observer_lng"] == -74.0
    assert updated["location_source"] == "ip"
    assert updated["timezone"] == "America/New_York"
    config.save.assert_called_once()

    config.get.side_effect = lambda key, default=None: {
        "location_source": "manual",
    }.get(key, default)
    config.update.reset_mock()
    assert not resolve_auto_location(config)
    config.update.assert_not_called()


def test_auto_location_never_overwrites_a_chosen_zone(monkeypatch):
    import utilities.location as location

    monkeypatch.setattr(
        location, "ip_details", lambda: (40.7, -74.0, "America/New_York")
    )

    for stored, source in (("America/Chicago", "auto"), ("America/Chicago", "manual")):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None, _s=stored, _src=source: {
            "location_source": "auto",
            "timezone_source": _src,
            "timezone": _s,
        }.get(key, default)

        assert location.resolve_auto_location(config)
        assert "timezone" not in config.update.call_args.args[0]


def test_ip_timezone_is_validated_against_the_zone_database(monkeypatch):
    import utilities.location as location

    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {
            "success": True,
            "latitude": 40.7,
            "longitude": -74.0,
            "timezone": {"id": "America/New_York", "offset": -18000},
        }
    ).encode()
    monkeypatch.setattr(
        location.urllib.request, "urlopen", lambda *args, **kwargs: response
    )

    assert location.ip_details() == (40.7, -74.0, "America/New_York")

    # A provider that names something we cannot resolve is ignored.
    response.__enter__.return_value.read.return_value = json.dumps(
        {
            "success": True,
            "latitude": 40.7,
            "longitude": -74.0,
            "timezone": {"id": "Mars/Olympus"},
        }
    ).encode()
    assert location.ip_timezone() == ""
