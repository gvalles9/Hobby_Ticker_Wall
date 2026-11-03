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
    config.get.return_value = "auto"

    import utilities.location as location

    monkeypatch.setattr(location, "ip_location", lambda: (40.7, -74.0))
    assert resolve_auto_location(config)
    updated = config.update.call_args.args[0]
    assert updated["flight_lat"] == 40.7
    assert updated["flight_lng"] == -74.0
    assert updated["flight_observer_lat"] == 40.7
    assert updated["flight_observer_lng"] == -74.0
    assert updated["location_source"] == "ip"
    config.save.assert_called_once()

    config.get.return_value = "manual"
    config.update.reset_mock()
    assert not resolve_auto_location(config)
    config.update.assert_not_called()
