import json
import subprocess

import pytest


def _completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)


def test_status_reports_socket_when_present(monkeypatch):
    import utilities.ssh_access as ssh_access

    def run(args, **kwargs):
        if args[:2] == ["systemctl", "list-unit-files"]:
            return _completed(args, stdout="ssh.socket enabled\n")
        if args[:2] == ["systemctl", "is-enabled"]:
            state = "enabled\n" if args[2] == "ssh.socket" else "disabled\n"
            return _completed(args, stdout=state)
        if args[:2] == ["systemctl", "is-active"]:
            state = "active\n" if args[2] == "ssh.socket" else "inactive\n"
            return _completed(args, stdout=state)
        raise AssertionError(args)

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    assert ssh_access.status() == {
        "available": True,
        "enabled": True,
        "active": True,
        "unit": "ssh.socket",
    }


def test_status_falls_back_to_the_service_unit(monkeypatch):
    import utilities.ssh_access as ssh_access

    def run(args, **kwargs):
        if args[:2] == ["systemctl", "list-unit-files"]:
            return _completed(args, returncode=1)
        if args[:2] == ["systemctl", "is-enabled"]:
            return _completed(args, stdout="disabled\n")
        if args[:2] == ["systemctl", "is-active"]:
            return _completed(args, stdout="inactive\n")
        raise AssertionError(args)

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    assert ssh_access.status() == {
        "available": True,
        "enabled": False,
        "active": False,
        "unit": "ssh.service",
    }


def test_status_reports_unavailable_without_systemctl(monkeypatch):
    import utilities.ssh_access as ssh_access

    def run(args, **kwargs):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    assert ssh_access.status() == {
        "available": False,
        "enabled": False,
        "active": False,
        "unit": None,
    }


def test_enable_generates_host_keys_before_starting_ssh(monkeypatch):
    import utilities.ssh_access as ssh_access

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "ssh-keygen":
            return _completed(args)
        if args[:2] == ["systemctl", "list-unit-files"]:
            return _completed(args, stdout="ssh.socket enabled\n")
        if args[1] in ("is-enabled", "is-active"):
            state = "disabled\n" if args[1] == "is-enabled" else "inactive\n"
            return _completed(args, stdout=state)
        if args[:2] == ["systemctl", "enable"]:
            return _completed(args)
        raise AssertionError(args)

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    ssh_access.enable()

    assert calls[0] == ["ssh-keygen", "-A"]
    assert calls[-1] == ["systemctl", "enable", "--now", "ssh.service"]


def test_enable_stops_when_host_keys_cannot_be_generated(monkeypatch):
    import utilities.ssh_access as ssh_access

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return _completed(args, returncode=1, stderr="permission denied")

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    with pytest.raises(RuntimeError, match="permission denied"):
        ssh_access.enable()

    assert calls == [["ssh-keygen", "-A"]]


def test_disable_handles_static_service_with_the_socket_unit(monkeypatch):
    import utilities.ssh_access as ssh_access

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["systemctl", "list-unit-files"]:
            return _completed(args, stdout="ssh.socket enabled\n")
        if args[:2] == ["systemctl", "is-enabled"]:
            state = "enabled\n" if args[2] == "ssh.socket" else "static\n"
            return _completed(args, stdout=state)
        if args[:2] == ["systemctl", "is-active"]:
            return _completed(args, stdout="inactive\n")
        if args[:2] == ["systemctl", "disable"]:
            return _completed(args)
        if args[:2] == ["systemctl", "stop"]:
            return _completed(args)
        raise AssertionError(args)

    monkeypatch.setattr(ssh_access.subprocess, "run", run)

    ssh_access.disable()

    assert ["systemctl", "disable", "--now", "ssh.socket"] in calls
    assert ["systemctl", "stop", "ssh.service"] in calls
    assert ["systemctl", "disable", "--now", "ssh.service"] not in calls


def test_main_rejects_unknown_actions(capsys):
    import utilities.ssh_access as ssh_access

    assert ssh_access.main(["flighttracker-set-ssh", "maybe"]) == 2
    assert "Usage" in capsys.readouterr().err


def test_main_prints_status_as_json(monkeypatch, capsys):
    import utilities.ssh_access as ssh_access

    state = {
        "available": True,
        "enabled": False,
        "active": False,
        "unit": "ssh.service",
    }
    monkeypatch.setattr(ssh_access, "status", lambda: state)

    assert ssh_access.main(["flighttracker-set-ssh", "status"]) == 0
    assert json.loads(capsys.readouterr().out) == state
