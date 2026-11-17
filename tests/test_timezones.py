"""Tests for the time-zone setting (issue #5).

The app follows a configured IANA zone by pointing ``TZ`` at it, so the
clock, date, sunrise/sunset and screen schedule all change without root or
a reflash.  These tests cover the helper, the config property, the form
parsers and the two pages that offer the picker.
"""

import os
import time
from unittest.mock import MagicMock

import pytest

from utilities import timezones


@pytest.fixture
def restore_tz():
    """Put the process TZ back the way it was after a test."""
    old = os.environ.get("TZ")
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    if hasattr(time, "tzset"):
        time.tzset()


# ---------------------------------------------------------------------------
# utilities.timezones
# ---------------------------------------------------------------------------


def test_known_zones_are_valid_and_unknown_ones_are_not():
    assert timezones.is_valid_zone("America/New_York")
    assert timezones.is_valid_zone("Europe/London")
    assert not timezones.is_valid_zone("Mars/Olympus")
    assert not timezones.is_valid_zone("")
    assert not timezones.is_valid_zone("../etc/passwd")


def test_available_zones_lists_real_regions_only():
    zones = timezones.available_zones()

    assert "America/New_York" in zones
    assert "Europe/London" in zones
    # Helper files that live alongside the zone data are not zones.
    assert "localtime" not in zones
    assert "posixrules" not in zones
    assert zones == sorted(zones)


def test_apply_zone_sets_tz_and_empty_restores_the_os_default(restore_tz):
    assert timezones.apply_zone("America/Chicago") is True
    assert os.environ["TZ"] == "America/Chicago"

    assert timezones.apply_zone("") is True
    assert "TZ" not in os.environ


def test_apply_zone_rejects_an_unknown_zone_without_changing_anything(restore_tz):
    os.environ["TZ"] = "UTC"

    assert timezones.apply_zone("Mars/Olympus") is False
    assert os.environ["TZ"] == "UTC"


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset is POSIX-only")
def test_apply_zone_changes_what_datetime_now_reports(restore_tz):
    """The whole point: every datetime.now() call follows the zone."""
    from datetime import datetime, timedelta

    assert timezones.apply_zone("UTC")
    utc_offset = datetime.now().astimezone().utcoffset()

    assert timezones.apply_zone("Pacific/Kiritimati")  # UTC+14, no DST
    local_offset = datetime.now().astimezone().utcoffset()

    assert local_offset - utc_offset == timedelta(hours=14)


def test_system_zone_reads_etc_timezone(tmp_path, monkeypatch):
    zone_file = tmp_path / "timezone"
    zone_file.write_text("America/Chicago\n", encoding="utf-8")
    monkeypatch.setattr(timezones, "SYSTEM_TZ_FILE", zone_file)
    monkeypatch.setattr(timezones, "LOCALTIME_FILE", tmp_path / "missing")

    assert timezones.system_zone() == "America/Chicago"


def test_system_zone_falls_back_to_the_localtime_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(timezones, "SYSTEM_TZ_FILE", tmp_path / "missing")
    monkeypatch.setattr(
        timezones.os.path,
        "realpath",
        lambda _path: "/usr/share/zoneinfo/Europe/Paris",
    )

    assert timezones.system_zone() == "Europe/Paris"


def test_system_zone_is_blank_when_nothing_is_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(timezones, "SYSTEM_TZ_FILE", tmp_path / "missing")
    monkeypatch.setattr(timezones.os.path, "realpath", lambda _path: "/etc/localtime")

    assert timezones.system_zone() == ""


# ---------------------------------------------------------------------------
# Config property
# ---------------------------------------------------------------------------


def test_config_keeps_a_valid_zone_and_discards_an_invalid_one(fresh_config):
    fresh_config.data_store["timezone"] = "America/New_York"
    assert fresh_config.timezone == "America/New_York"

    fresh_config.data_store["timezone"] = "Mars/Olympus"
    assert fresh_config.timezone == ""


# ---------------------------------------------------------------------------
# Form parsers
# ---------------------------------------------------------------------------


def test_settings_form_keeps_a_valid_zone(fresh_config):
    from web.app import parse_settings_form

    data = parse_settings_form({"timezone": "America/Chicago"}, fresh_config)

    assert data["timezone"] == "America/Chicago"


def test_any_saved_zone_becomes_a_manual_choice(fresh_config):
    """A value the owner saved must survive later automatic suggestions."""
    from web.app import parse_settings_form

    fresh_config.data_store["timezone_source"] = "auto"

    data = parse_settings_form({"timezone": "America/Chicago"}, fresh_config)

    assert data["timezone_source"] == "manual"


def test_clearing_the_zone_is_also_a_manual_choice(fresh_config):
    from web.app import parse_settings_form

    data = parse_settings_form({"timezone": ""}, fresh_config)

    assert data["timezone"] == ""
    assert data["timezone_source"] == "manual"


def test_settings_form_treats_blank_as_system_default(fresh_config):
    from web.app import parse_settings_form

    fresh_config.data_store["timezone"] = "America/New_York"
    data = parse_settings_form({"timezone": ""}, fresh_config)

    assert data["timezone"] == ""


def test_settings_form_keeps_the_saved_zone_when_the_key_is_absent(fresh_config):
    from web.app import parse_settings_form

    fresh_config.data_store["timezone"] = "America/New_York"
    fresh_config.data_store["timezone_source"] = "auto"
    data = parse_settings_form({}, fresh_config)

    assert data["timezone"] == "America/New_York"
    assert data["timezone_source"] == "auto"


def test_settings_form_rejects_an_unknown_zone(fresh_config):
    from web.app import parse_settings_form

    with pytest.raises(ValueError, match="Unknown time zone"):
        parse_settings_form({"timezone": "Mars/Olympus"}, fresh_config)


def test_first_setup_form_accepts_a_zone(fresh_config):
    from web.app import parse_first_setup_form

    data = parse_first_setup_form(
        {"bonnet_type": "triple", "timezone": "America/Chicago"}, fresh_config
    )

    assert data["timezone"] == "America/Chicago"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _authenticated_client():
    import web.app as web_app

    client = web_app.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["csrf_token"] = "tok"
    return client


def test_settings_page_offers_the_time_zone_picker(fresh_config):
    fresh_config.data_store["web_password_hash"] = "deadbeef"

    html = _authenticated_client().get("/settings").get_data(as_text=True)

    # The picker itself lives in HardwarePage.js; the page ships it the
    # zone list, the current OS zone and the lookup URL.
    assert "timezoneOptions" in html
    assert "America/New_York" in html
    assert "systemTimezone" in html
    assert "/api/timezone/ip" in html


def test_first_setup_page_offers_the_time_zone_picker(fresh_config):
    fresh_config.data_store["web_password_hash"] = ""

    html = _authenticated_client().get("/first-setup").get_data(as_text=True)

    assert 'name="timezone"' in html
    assert "America/New_York" in html


def test_settings_post_saves_the_zone(fresh_config, monkeypatch):
    import web.app as web_app

    fresh_config.data_store["web_password_hash"] = "deadbeef"
    restarts = []
    monkeypatch.setattr(
        web_app, "restart_after", lambda delay=1.0: restarts.append(delay)
    )

    response = _authenticated_client().post(
        "/settings",
        data={"csrf_token": "tok", "timezone": "America/Chicago"},
    )

    assert response.status_code == 200
    assert fresh_config.get("timezone") == "America/Chicago"
    assert restarts == [1.0]


def test_settings_post_rejects_an_unknown_zone(fresh_config, monkeypatch):
    import web.app as web_app

    fresh_config.data_store["web_password_hash"] = "deadbeef"
    monkeypatch.setattr(web_app, "restart_after", MagicMock())

    response = _authenticated_client().post(
        "/settings",
        data={"csrf_token": "tok", "timezone": "Mars/Olympus"},
    )

    assert response.status_code == 400
    assert "Unknown time zone" in response.get_data(as_text=True)
    assert "timezone" not in fresh_config.data_store
    web_app.restart_after.assert_not_called()


# ---------------------------------------------------------------------------
# "Use network location" suggestion
# ---------------------------------------------------------------------------


def test_config_timezone_source_only_accepts_known_values(fresh_config):
    assert fresh_config.timezone_source == "auto"

    fresh_config.data_store["timezone_source"] = "MANUAL"
    assert fresh_config.timezone_source == "manual"

    fresh_config.data_store["timezone_source"] = "something else"
    assert fresh_config.timezone_source == "auto"


def test_ip_timezone_endpoint_requires_login():
    import web.app as web_app

    assert web_app.app.test_client().get("/api/timezone/ip").status_code == 302


def test_ip_timezone_endpoint_returns_the_network_zone(monkeypatch):
    import utilities.location as location

    monkeypatch.setattr(location, "ip_timezone", lambda: "America/Chicago")

    response = _authenticated_client().get("/api/timezone/ip")

    assert response.status_code == 200
    assert response.get_json() == {"timezone": "America/Chicago"}


def test_ip_timezone_endpoint_reports_a_failed_lookup(monkeypatch):
    import utilities.location as location

    def boom():
        raise OSError("network unreachable")

    monkeypatch.setattr(location, "ip_timezone", boom)

    response = _authenticated_client().get("/api/timezone/ip")

    assert response.status_code == 502
    assert "failed" in response.get_json()["error"].lower()


def test_ip_timezone_endpoint_reports_an_unknown_zone(monkeypatch):
    import utilities.location as location

    monkeypatch.setattr(location, "ip_timezone", lambda: "")

    response = _authenticated_client().get("/api/timezone/ip")

    assert response.status_code == 502
    assert "could not be determined" in response.get_json()["error"]


def test_ip_timezone_endpoint_works_during_first_setup(monkeypatch, fresh_config):
    """The wizard offers the button, so the guard must let the lookup through."""
    import utilities.location as location

    fresh_config.data_store["web_password_hash"] = ""
    monkeypatch.setattr(location, "ip_timezone", lambda: "America/New_York")

    response = _authenticated_client().get("/api/timezone/ip")

    assert response.status_code == 200
    assert response.get_json() == {"timezone": "America/New_York"}


def test_first_setup_page_shows_the_detect_button(fresh_config):
    fresh_config.data_store["web_password_hash"] = ""

    html = _authenticated_client().get("/first-setup").get_data(as_text=True)

    assert 'id="timezone-detect"' in html
    assert "/api/timezone/ip" in html
