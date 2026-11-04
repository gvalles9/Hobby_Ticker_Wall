import re


def test_login_page_uses_hobby_ticker_brand_and_product_version():
    from web.app import app

    response = app.test_client().get("/login")

    assert response.status_code == 200
    html = response.data.decode()
    assert "<title>Hobby Ticker - Login</title>" in html
    assert "Hobby Ticker v1.0.0" in html


def test_footer_attributes_flighttracker_upstream():
    from web.app import app

    client = app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True

    response = client.get("/status")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Hobby Ticker v1.0.0" in html
    assert "Based on" in html
    assert "Colin Waddell" in html


def test_settings_version_tab_uses_hobby_ticker_product_version(monkeypatch):
    from web import app as web_app

    class ConfigStub:
        brightness_schedule_window = None

        def get(self, key):
            return "manual"

        def is_in_brightness_schedule(self):
            return False

        def active_advanced_entry(self):
            return None

    monkeypatch.setattr(
        web_app,
        "_provider_ui_data",
        lambda _cfg: {
            "cfg": {},
            "providers_meta": [],
            "flight_order": [],
            "route_order": [],
            "mask_token": "",
        },
    )
    monkeypatch.setattr(web_app, "airports_json", lambda: "[]")
    monkeypatch.setattr(web_app, "csrf_token", lambda: "token")

    with web_app.app.test_request_context():
        page_data = web_app._settings_page_data(ConfigStub())

    assert page_data["current_version"] == "v1.0.0"
    assert page_data["current_version"] == web_app.version_string(web_app.APP_VERSION)
    assert page_data["current_version"] != web_app.version_string(web_app.VERSION)


def test_update_page_tracks_fork_branch_and_displays_product_version(monkeypatch):
    from web import app as web_app

    client = web_app.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
    monkeypatch.setattr(
        web_app,
        "get_update_info",
        lambda: {
            "current_version": "v1.0.0",
            "latest_version": "abcdef1",
            "update_available": False,
            "upstream_ref": "hobby-ticker/main",
            "commit": "abcdef1234567890",
            "error": None,
        },
    )

    response = client.get("/update")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Hobby Ticker version" in html
    assert "Latest upstream commit" in html
    assert re.search(r'id="current-version">\s*v1\.0\.0\s*</div>', html)
    assert re.search(r'id="latest-version">\s*abcdef1\s*</div>', html)
    assert "Tracking <code>hobby-ticker/main</code>" in html
    assert (
        'href="https://github.com/gvalles9/Hobby_Ticker_Wall/commit/abcdef1234567890"'
        in html
    )
