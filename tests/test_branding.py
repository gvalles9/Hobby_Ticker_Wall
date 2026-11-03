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
            "upstream_ref": "origin/main",
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
    assert "Tracking <code>origin/main</code>" in html
    assert (
        'href="https://github.com/gvalles9/Hobby_Ticker_Wall/commit/abcdef1234567890"'
        in html
    )
