import json
import subprocess
from unittest.mock import MagicMock

import pytest


def test_wifi_credentials_create_connection_and_disable_setup_ap(monkeypatch, tmp_path):
    import utilities.wifi_setup as wifi_setup

    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(wifi_setup.subprocess, "run", run)
    monkeypatch.setattr(wifi_setup, "CONNECTIONS_DIR", str(tmp_path))
    monkeypatch.setattr(
        wifi_setup, "CONFIGURED_MARKER", str(tmp_path / "wifi-configured")
    )
    monkeypatch.setattr(wifi_setup, "SETUP_MARKER", str(tmp_path / "setup-active"))
    (tmp_path / "setup-active").write_text("active")

    wifi_setup.configure_wifi("Home Network", "secure-pass-123")

    assert calls[0][0][:3] == ["nmcli", "connection", "delete"]
    assert calls[1][0] == ["nmcli", "connection", "reload"]
    assert calls[2][0] == [
        "nmcli",
        "connection",
        "up",
        "FlightTracker-Home",
        "ifname",
        "wlan0",
    ]
    assert calls[3][0] == ["nmcli", "connection", "down", "FlightTracker-Setup"]
    connection_file = tmp_path / "FlightTracker-Home.nmconnection"
    assert "ssid=Home\\sNetwork" in connection_file.read_text()
    assert "psk=secure-pass-123" in connection_file.read_text()
    assert "secure-pass-123" not in repr([call[0] for call in calls])
    assert (tmp_path / "wifi-configured").exists()
    assert not (tmp_path / "setup-active").exists()


@pytest.mark.parametrize(
    ("ssid", "password"),
    [
        ("", "valid-pass-123"),
        ("A" * 33, "valid-pass-123"),
        ("Home", "short"),
        ("Home", "bad\npassword"),
    ],
)
def test_wifi_credentials_reject_invalid_values(monkeypatch, ssid, password):
    import utilities.wifi_setup as wifi_setup

    run = MagicMock()
    monkeypatch.setattr(wifi_setup.subprocess, "run", run)

    with pytest.raises(ValueError):
        wifi_setup.configure_wifi(ssid, password)

    run.assert_not_called()


def test_start_setup_hotspot_keeps_saved_home_network(monkeypatch, tmp_path):
    import utilities.wifi_setup as wifi_setup

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(wifi_setup.subprocess, "run", run)
    monkeypatch.setattr(wifi_setup, "SETUP_MARKER", str(tmp_path / "setup-active"))
    monkeypatch.setattr(wifi_setup, "CONFIGURED_MARKER", str(tmp_path / "configured"))
    (tmp_path / "configured").write_text("configured")

    wifi_setup.start_setup_hotspot()

    assert calls == [
        [
            "nmcli",
            "connection",
            "modify",
            "FlightTracker-Home",
            "connection.autoconnect",
            "no",
        ],
        ["nmcli", "connection", "down", "FlightTracker-Home"],
        ["nmcli", "connection", "up", "FlightTracker-Setup"],
    ]
    assert (tmp_path / "configured").exists()
    assert (tmp_path / "setup-active").exists()


def test_wifi_change_failure_restores_saved_connection_and_setup_hotspot(
    monkeypatch, tmp_path
):
    import utilities.wifi_setup as wifi_setup

    calls = []
    connection_path = tmp_path / "FlightTracker-Home.nmconnection"
    previous_content = b"[connection]\nid=FlightTracker-Home\n"
    connection_path.write_bytes(previous_content)

    def run(args, **kwargs):
        calls.append(args)
        if args[:4] == ["nmcli", "connection", "up", "FlightTracker-Home"]:
            raise subprocess.CalledProcessError(1, args, stderr="no connection")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(wifi_setup.subprocess, "run", run)
    monkeypatch.setattr(wifi_setup, "CONNECTIONS_DIR", str(tmp_path))
    monkeypatch.setattr(wifi_setup, "CONFIGURED_MARKER", str(tmp_path / "configured"))
    monkeypatch.setattr(wifi_setup, "SETUP_MARKER", str(tmp_path / "setup-active"))

    with pytest.raises(subprocess.CalledProcessError):
        wifi_setup.configure_wifi("New Network", "secure-pass-123")

    assert connection_path.read_bytes() == previous_content
    assert ["nmcli", "connection", "up", "FlightTracker-Setup"] in calls
    assert not (tmp_path / "configured").exists()


def test_wifi_watchdog_retries_every_saved_network_and_keeps_hotspot_on_failure(
    monkeypatch,
):
    import utilities.wifi_watchdog as wifi_watchdog

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[:3] == ["nmcli", "-t", "-f"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=(
                    "FlightTracker-Setup:802-11-wireless\n"
                    "Home Network:802-11-wireless\n"
                    "Wired connection 1:802-3-ethernet\n"
                ),
            )
        code = 1 if args[:4] == ["nmcli", "connection", "up", "Home Network"] else 0
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(wifi_watchdog.subprocess, "run", run)

    assert wifi_watchdog._retry_saved_connection() is False
    assert calls == [
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        ["nmcli", "connection", "up", "Home Network", "ifname", "wlan0"],
        ["nmcli", "connection", "up", "FlightTracker-Setup"],
    ]


def test_wifi_watchdog_reconnects_to_the_first_saved_profile_that_works(monkeypatch):
    import utilities.wifi_watchdog as wifi_watchdog

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[:3] == ["nmcli", "-t", "-f"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=("Old Home:802-11-wireless\n" "New Home:802-11-wireless\n"),
            )
        code = 1 if args[:4] == ["nmcli", "connection", "up", "Old Home"] else 0
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(wifi_watchdog.subprocess, "run", run)

    assert wifi_watchdog._retry_saved_connection() is True
    assert [
        "nmcli",
        "connection",
        "up",
        "New Home",
        "ifname",
        "wlan0",
    ] in calls
    assert ["nmcli", "connection", "up", "FlightTracker-Setup"] not in calls


def test_wifi_watchdog_reads_escaped_profile_names(monkeypatch):
    import utilities.wifi_watchdog as wifi_watchdog

    def run(args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=(
                "Home\\: Network:802-11-wireless\n"
                "FlightTracker-Setup:802-11-wireless\n"
            ),
        )

    monkeypatch.setattr(wifi_watchdog.subprocess, "run", run)

    assert wifi_watchdog._saved_wifi_connections() == ["Home: Network"]


def test_wifi_watchdog_only_treats_real_profiles_as_connected():
    import utilities.wifi_watchdog as wifi_watchdog

    assert wifi_watchdog._is_connected("Home Network") is True
    assert wifi_watchdog._is_connected("") is False
    assert wifi_watchdog._is_connected("--") is False
    assert wifi_watchdog._is_connected("FlightTracker-Setup") is False


def test_wifi_watchdog_detects_an_ethernet_default_route(monkeypatch):
    import utilities.wifi_watchdog as wifi_watchdog

    def run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, stdout="default via 192.168.1.1 dev eth0\n"
        )

    monkeypatch.setattr(wifi_watchdog.subprocess, "run", run)

    assert wifi_watchdog._has_default_route() is True


def test_wifi_watchdog_default_route_lookup_failure_is_safe(monkeypatch):
    import utilities.wifi_watchdog as wifi_watchdog

    def run(args, **kwargs):
        raise FileNotFoundError("ip")

    monkeypatch.setattr(wifi_watchdog.subprocess, "run", run)

    assert wifi_watchdog._has_default_route() is False


def test_wifi_setup_page_only_available_while_hotspot_is_active(monkeypatch):
    import web.app as web_app

    class SetupPath:
        def __init__(self, path):
            self.path = path

        def exists(self):
            return False

    monkeypatch.setattr(web_app, "Path", SetupPath)

    response = web_app.app.test_client().get("/wifi-setup")

    assert response.status_code == 404


def test_wifi_setup_page_posts_credentials_to_privileged_helper(monkeypatch):
    import utilities.system_info as system_info
    import web.app as web_app

    class SetupPath:
        def __init__(self, path):
            self.path = path

        def exists(self):
            return self.path == "/run/flighttracker-wifi-setup"

    monkeypatch.setattr(web_app, "Path", SetupPath)
    monkeypatch.setattr(system_info, "hostname", lambda: "my-pi")
    result = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    run = MagicMock(return_value=result)
    monkeypatch.setattr(web_app.subprocess, "run", run)

    client = web_app.app.test_client()
    page = client.get("/wifi-setup")
    assert page.status_code == 200
    with client.session_transaction() as session:
        csrf = session["csrf_token"]

    response = client.post(
        "/wifi-setup",
        data={"csrf_token": csrf, "ssid": "Home Wi-Fi", "password": "valid-pass-123"},
    )

    assert response.status_code == 200
    assert b"Wi-Fi details saved" in response.data
    assert b"http://my-pi.local:8584/settings" in response.data
    args, kwargs = run.call_args
    assert args[0] == ["sudo", "-n", "/usr/local/sbin/flighttracker-configure-wifi"]
    assert json.loads(kwargs["input"]) == {
        "ssid": "Home Wi-Fi",
        "password": "valid-pass-123",
    }


def test_reset_wifi_route_starts_hotspot_and_restarts(monkeypatch):
    import web.app as web_app

    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, stderr=""))
    monkeypatch.setattr(web_app.subprocess, "run", run)
    restarts = []
    monkeypatch.setattr(
        web_app, "restart_after", lambda delay=1.0: restarts.append(delay)
    )

    client = web_app.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["csrf_token"] = "reset-csrf"
    response = client.post(
        "/wifi-setup/reset",
        data={"csrf_token": "reset-csrf"},
    )

    assert response.status_code == 200
    assert response.json["message"]
    assert run.call_args.kwargs["input"] == '{"action": "start_setup"}'
    assert restarts == [1.0]


def test_reset_settings_route_restores_defaults_and_keeps_web_password(monkeypatch):
    import web.app as web_app

    cfg = MagicMock()
    cfg.data_store = {"web_password_hash": "existing-hash", "flight_radius": 80}
    cfg.get.side_effect = lambda key, default=None: cfg.data_store.get(key, default)
    monkeypatch.setattr(web_app.Config, "instance", lambda: cfg)
    monkeypatch.setattr(
        web_app, "DEFAULTS", {"flight_radius": 20, "web_password_hash": ""}
    )
    monkeypatch.setattr(web_app, "_migrate_provider_lists", lambda data, loaded: None)
    restarts = []
    monkeypatch.setattr(
        web_app, "restart_after", lambda delay=1.0: restarts.append(delay)
    )

    client = web_app.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["csrf_token"] = "reset-csrf"
    response = client.post(
        "/settings/reset",
        data={"csrf_token": "reset-csrf"},
    )

    assert response.status_code == 200
    assert cfg.data_store == {"flight_radius": 20, "web_password_hash": "existing-hash"}
    cfg.save.assert_called_once_with()
    assert restarts == [1.0]
