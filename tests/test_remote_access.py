import json
import subprocess
from unittest.mock import MagicMock

import pytest


def _authenticated_client(csrf="test-csrf"):
    import web.app as web_app

    client = web_app.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
        session["csrf_token"] = csrf
    return client


def test_ssh_status_requires_login():
    import web.app as web_app

    response = web_app.app.test_client().get("/remote-access/ssh")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_ssh_status_returns_the_current_state(monkeypatch):
    import web.app as web_app

    state = {
        "available": True,
        "enabled": False,
        "active": False,
        "unit": "ssh.service",
    }
    monkeypatch.setattr(web_app.ssh_access, "status", lambda: state)

    response = _authenticated_client().get("/remote-access/ssh")

    assert response.status_code == 200
    assert response.json == state


def test_ssh_toggle_requires_csrf(monkeypatch):
    import web.app as web_app

    run = MagicMock()
    monkeypatch.setattr(web_app.subprocess, "run", run)

    response = _authenticated_client().post(
        "/remote-access/ssh",
        data={"action": "on"},
    )

    assert response.status_code == 403
    run.assert_not_called()


def test_ssh_toggle_rejects_unknown_actions(monkeypatch):
    import web.app as web_app

    run = MagicMock()
    monkeypatch.setattr(web_app.subprocess, "run", run)

    response = _authenticated_client().post(
        "/remote-access/ssh",
        data={"csrf_token": "test-csrf", "action": "maybe"},
    )

    assert response.status_code == 400
    run.assert_not_called()


@pytest.mark.parametrize("action", ["on", "off"])
def test_ssh_toggle_calls_the_privileged_helper(monkeypatch, action):
    import web.app as web_app

    calls = []
    state = {
        "available": True,
        "enabled": action == "on",
        "active": action == "on",
        "unit": "ssh.socket",
    }

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(state), stderr="")

    monkeypatch.setattr(web_app.subprocess, "run", run)

    response = _authenticated_client().post(
        "/remote-access/ssh",
        data={"csrf_token": "test-csrf", "action": action},
    )

    assert response.status_code == 200
    assert response.json["state"] == state
    assert response.json["message"]
    assert calls[0][0] == [
        "sudo",
        "-n",
        "/usr/local/sbin/flighttracker-set-ssh",
        action,
    ]


def test_ssh_toggle_reports_a_missing_helper(monkeypatch):
    import web.app as web_app

    def run(args, **kwargs):
        raise FileNotFoundError("sudo")

    monkeypatch.setattr(web_app.subprocess, "run", run)

    response = _authenticated_client().post(
        "/remote-access/ssh",
        data={"csrf_token": "test-csrf", "action": "on"},
    )

    assert response.status_code == 500
    assert "not installed" in response.json["error"]


def test_ssh_toggle_reports_helper_failure(monkeypatch):
    import web.app as web_app

    def run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="Could not enable ssh.socket."
        )

    monkeypatch.setattr(web_app.subprocess, "run", run)

    response = _authenticated_client().post(
        "/remote-access/ssh",
        data={"csrf_token": "test-csrf", "action": "on"},
    )

    assert response.status_code == 500
    assert response.json["error"] == "Could not enable ssh.socket."
