"""Tests for the privileged-helper sync after updates."""

import subprocess
from pathlib import Path

INSTALL_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "platforms"
    / "common"
    / "install-wifi-setup.sh"
)


# ---------------------------------------------------------------------------
# utilities.updater.sync_privileged_helpers
# ---------------------------------------------------------------------------


def test_sync_skips_silently_when_the_command_is_not_installed(monkeypatch, tmp_path):
    from utilities import updater

    calls = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *args, **kwargs: calls.append(args)
    )
    monkeypatch.setattr(updater, "HELPER_SYNC_COMMAND", str(tmp_path / "missing"))

    assert updater.sync_privileged_helpers() is False
    assert calls == []


def test_sync_runs_the_installed_command_with_sudo(monkeypatch, tmp_path):
    from utilities import updater

    command = tmp_path / "flighttracker-sync-helpers"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(updater, "HELPER_SYNC_COMMAND", str(command))
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(updater.subprocess, "run", run)

    assert updater.sync_privileged_helpers() is True
    assert calls == [["sudo", "-n", str(command)]]


def test_sync_reports_failure_without_raising(monkeypatch, tmp_path):
    from utilities import updater

    command = tmp_path / "flighttracker-sync-helpers"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(updater, "HELPER_SYNC_COMMAND", str(command))
    monkeypatch.setattr(
        updater.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "boom"),
    )

    assert updater.sync_privileged_helpers() is False


def test_sync_swallows_a_missing_sudo(monkeypatch, tmp_path):
    from utilities import updater

    command = tmp_path / "flighttracker-sync-helpers"
    command.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(updater, "HELPER_SYNC_COMMAND", str(command))

    def run(args, **kwargs):
        raise FileNotFoundError("sudo")

    monkeypatch.setattr(updater.subprocess, "run", run)

    assert updater.sync_privileged_helpers() is False


# ---------------------------------------------------------------------------
# install-wifi-setup.sh generates the sync command
# ---------------------------------------------------------------------------


def test_install_script_grants_sudo_for_the_sync_command():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    # Present in the sudoers printf and in the generated command itself.
    assert text.count("/usr/local/sbin/flighttracker-sync-helpers") >= 2


def test_sync_command_covers_every_helper_copy():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    for source, destination in (
        ("utilities/wifi_setup.py", "flighttracker-configure-wifi"),
        ("utilities/ssh_access.py", "flighttracker-set-ssh"),
        ("utilities/wifi_watchdog.py", "flighttracker-wifi-watchdog"),
    ):
        assert source in text
        assert destination in text
