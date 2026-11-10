"""Tests for the first-setup wizard (/first-setup)."""

import hashlib
from unittest.mock import MagicMock

import pytest


def _authenticated_client(csrf="tok"):
    import web.app as web_app

    client = web_app.app.test_client()
    with client.session_transaction() as sess:
        sess["authenticated"] = True
        sess["csrf_token"] = csrf
    return client


def _wizard_form(**overrides):
    form = {
        "csrf_token": "tok",
        "bonnet_type": "triple",
        "new_password": "s3cret-pass",
        "confirm_password": "s3cret-pass",
        "idle_screen_themes_submitted": "1",
        "idle_screen_themes": ["classic", "forecast"],
    }
    form.update(overrides)
    return form


# ---------------------------------------------------------------------------
# parse_first_setup_form
# ---------------------------------------------------------------------------


class TestParseFirstSetupForm:
    def test_marks_setup_complete_and_defaults_bonnet(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form({"bonnet_type": "triple"}, fresh_config)

        assert data["first_setup_complete"] is True
        assert data["bonnet_type"] == "triple"

    def test_invalid_bonnet_falls_back_to_default(self, fresh_config):
        import web.app as web_app
        from setup.configuration import DEFAULT_BONNET_TYPE

        data = web_app.parse_first_setup_form({"bonnet_type": "quad"}, fresh_config)

        assert data["bonnet_type"] == DEFAULT_BONNET_TYPE

    def test_blank_location_keeps_current_values(self, fresh_config):
        import web.app as web_app

        fresh_config.set("flight_lat", 51.5)
        fresh_config.set("flight_lng", -0.12)
        fresh_config.set("flight_radius", 42.0)

        data = web_app.parse_first_setup_form(
            {"flight_lat": "", "flight_lng": ""}, fresh_config
        )

        assert data["flight_lat"] == 51.5
        assert data["flight_lng"] == pytest.approx(-0.12)
        assert data["flight_radius"] == 42.0

    def test_submitted_location_wins(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"flight_lat": "40.7", "flight_lng": "-74.0", "flight_radius": "15"},
            fresh_config,
        )

        assert data["flight_lat"] == 40.7
        assert data["flight_lng"] == -74.0
        assert data["flight_radius"] == 15.0

    def test_omitted_units_keep_defaults(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form({}, fresh_config)

        assert data["flight_units"] == "metric"
        assert data["idle_units"] == "standard"
        assert data["height_unit"] == "m"
        assert data["speed_unit"] == "kmh"
        assert data["temperature_unit"] == "f"

    def test_submitted_units_apply(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"flight_units": "standard", "idle_units": "metric"}, fresh_config
        )

        assert data["flight_units"] == "standard"
        assert data["idle_units"] == "metric"
        assert data["height_unit"] == "ft"
        assert data["speed_unit"] == "mph"
        assert data["temperature_unit"] == "c"

    def test_idle_theme_selection_and_legacy_fields(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {
                "idle_screen_themes_submitted": "1",
                "idle_screen_themes": ["indycar_next", "classic"],
            },
            fresh_config,
        )

        assert data["idle_screen_themes"] == ["indycar_next", "classic"]
        assert data["idle_screen_theme"] == "indycar_next"
        assert data["idle_cycle_include_indycar"] is True

    def test_empty_theme_selection_defaults_to_classic(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"idle_screen_themes_submitted": "1"}, fresh_config
        )

        assert data["idle_screen_themes"] == ["classic"]
        assert data["idle_screen_theme"] == "classic"

    def test_valid_birthday_date_is_kept(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"birthday_date": "2026-03-14"}, fresh_config
        )

        assert data["birthday_date"] == "2026-03-14"
        assert data["birthday_enabled"] is True

    def test_invalid_birthday_date_clears_the_scene(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"birthday_date": "not-a-date"}, fresh_config
        )

        assert data["birthday_date"] == ""
        assert data["birthday_enabled"] is False

    def test_satellite_ids_parse_and_drop_junk(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"satellite_norad_ids": "25544\nnope\n48274"}, fresh_config
        )

        assert data["satellite_norad_ids"] == [25544, 48274]

    def test_brightness_and_clock_defaults(self, fresh_config):
        import web.app as web_app

        data = web_app.parse_first_setup_form(
            {"screen_brightness": "9", "clock_24hr": "on", "date_format": "2"},
            fresh_config,
        )

        # brightness clamped to 1-5; clock/date passed through
        assert data["screen_brightness"] == 5
        assert data["clock_24hr"] is True
        assert data["date_format"] == 2


# ---------------------------------------------------------------------------
# /first-setup route
# ---------------------------------------------------------------------------


class TestFirstSetupRoute:
    def test_requires_login(self):
        import web.app as web_app

        resp = web_app.app.test_client().get("/first-setup")

        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_page_renders_required_and_optional_sections(self, fresh_config):
        resp = _authenticated_client().get("/first-setup")

        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "Required" in text
        assert "Optional" in text
        assert 'name="new_password"' in text
        assert 'name="bonnet_type"' in text
        assert 'name="idle_screen_themes"' in text

    def test_redirects_to_settings_once_complete(self, fresh_config):
        fresh_config.set("first_setup_complete", True)

        resp = _authenticated_client().get("/first-setup")

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/settings")

    def test_redirects_to_settings_when_password_already_set(self, fresh_config):
        fresh_config.set("web_password_hash", "deadbeef")

        resp = _authenticated_client().get("/first-setup")

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/settings")

    def test_post_requires_csrf(self, fresh_config):
        resp = _authenticated_client().post(
            "/first-setup", data=_wizard_form(csrf_token="")
        )

        assert resp.status_code == 400
        assert fresh_config.get("first_setup_complete") is not True

    def test_missing_password_is_rejected(self, fresh_config, monkeypatch):
        import web.app as web_app

        restart = MagicMock()
        monkeypatch.setattr(web_app, "restart_after", restart)

        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(new_password="", confirm_password=""),
        )

        assert resp.status_code == 400
        assert "password" in resp.get_data(as_text=True).lower()
        restart.assert_not_called()
        assert fresh_config.get("web_password_hash") is None
        assert fresh_config.get("first_setup_complete") is not True

    def test_password_mismatch_is_rejected(self, fresh_config, monkeypatch):
        import web.app as web_app

        restart = MagicMock()
        monkeypatch.setattr(web_app, "restart_after", restart)

        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(confirm_password="different"),
        )

        assert resp.status_code == 400
        restart.assert_not_called()
        assert fresh_config.get("first_setup_complete") is not True

    def test_invalid_bonnet_is_rejected(self, fresh_config, monkeypatch):
        import web.app as web_app

        restart = MagicMock()
        monkeypatch.setattr(web_app, "restart_after", restart)

        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(bonnet_type="quad"),
        )

        assert resp.status_code == 400
        restart.assert_not_called()

    def test_valid_post_saves_config_and_restarts(self, fresh_config, monkeypatch):
        import web.app as web_app

        restart = MagicMock()
        monkeypatch.setattr(web_app, "restart_after", restart)

        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(
                flight_lat="51.5",
                flight_lng="-0.12",
                flight_units="standard",
                screen_brightness="4",
                birthday_date="2026-03-14",
                satellite_norad_ids="25544",
            ),
        )

        assert resp.status_code == 200
        assert "restarting" in resp.get_data(as_text=True).lower()
        restart.assert_called_once()

        assert fresh_config.get("first_setup_complete") is True
        assert (
            fresh_config.get("web_password_hash")
            == hashlib.sha256(b"s3cret-pass").hexdigest()
        )
        assert fresh_config.get("bonnet_type") == "triple"
        assert fresh_config.get("flight_lat") == 51.5
        assert fresh_config.get("flight_units") == "standard"
        assert fresh_config.get("screen_brightness") == 4
        assert fresh_config.get("birthday_date") == "2026-03-14"
        assert fresh_config.get("satellite_norad_ids") == [25544]

    def test_skip_marks_complete_without_password_or_restart(
        self, fresh_config, monkeypatch
    ):
        import web.app as web_app

        restart = MagicMock()
        monkeypatch.setattr(web_app, "restart_after", restart)

        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(action="skip"),
        )

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/settings")
        restart.assert_not_called()
        assert fresh_config.get("first_setup_complete") is True
        assert fresh_config.get("web_password_hash") is None

    def test_index_redirects_to_wizard_while_pending(self, fresh_config):
        import web.app as web_app

        resp = web_app.app.test_client().get("/")

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/first-setup")

    def test_index_redirects_to_settings_once_complete(self, fresh_config):
        import web.app as web_app

        fresh_config.set("first_setup_complete", True)

        resp = web_app.app.test_client().get("/")

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/settings")

    def test_rejected_post_keeps_submitted_values(self, fresh_config):
        resp = _authenticated_client().post(
            "/first-setup",
            data=_wizard_form(
                flight_lat="51.5",
                birthday_date="2026-03-14",
                confirm_password="different",
            ),
        )

        text = resp.get_data(as_text=True)
        assert 'value="51.5"' in text
        assert 'value="2026-03-14"' in text
