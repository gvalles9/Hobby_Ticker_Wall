import subprocess

import pytest


def test_checkout_update_fast_forwards_configured_upstream(monkeypatch):
    import utilities.nightly_update as nightly_update

    calls = []
    outputs = iter(
        [
            "",
            "origin/main",
            "old-sha",
            "",
            "",
            "new-sha",
        ]
    )

    def run(args, timeout=120):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=next(outputs), stderr="")

    monkeypatch.setattr(nightly_update, "_run", run)

    assert nightly_update._update_checkout() is True
    assert calls == [
        ["git", "status", "--porcelain", "--untracked-files=no"],
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        ["git", "rev-parse", "HEAD"],
        ["git", "fetch", "--quiet"],
        ["git", "merge", "--ff-only", "origin/main"],
        ["git", "rev-parse", "HEAD"],
    ]


def test_checkout_update_refuses_tracked_local_changes(monkeypatch):
    import utilities.nightly_update as nightly_update

    monkeypatch.setattr(
        nightly_update,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout=" M local.py\n", stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="Tracked local changes"):
        nightly_update._update_checkout()


def test_nightly_update_installs_dependencies_then_restarts(monkeypatch, tmp_path):
    import utilities.nightly_update as nightly_update

    pending = tmp_path / "flighttracker-update-pending"
    monkeypatch.setattr(nightly_update, "PENDING_MARKER", pending)
    monkeypatch.setattr(nightly_update, "_update_checkout", lambda: True)
    installed = []
    monkeypatch.setattr(
        nightly_update, "_install_dependencies", lambda: installed.append(True)
    )
    restarted = []

    def run(args, **kwargs):
        restarted.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(nightly_update.subprocess, "run", run)

    assert nightly_update.run_update() is True
    assert installed == [True]
    assert restarted == [
        ["sudo", "-n", "/usr/bin/systemctl", "restart", "FlightTracker.service"]
    ]
    assert not pending.exists()


def test_nightly_update_skips_when_no_new_commits(monkeypatch, tmp_path):
    import utilities.nightly_update as nightly_update

    monkeypatch.setattr(
        nightly_update, "PENDING_MARKER", tmp_path / "flighttracker-update-pending"
    )
    monkeypatch.setattr(nightly_update, "_update_checkout", lambda: False)
    install = []
    restart = []
    monkeypatch.setattr(
        nightly_update, "_install_dependencies", lambda: install.append(True)
    )
    monkeypatch.setattr(
        nightly_update.subprocess, "run", lambda *args, **kwargs: restart.append(args)
    )

    assert nightly_update.run_update() is False
    assert install == []
    assert restart == []


def test_nightly_update_retries_dependencies_after_previous_failure(
    monkeypatch, tmp_path
):
    import utilities.nightly_update as nightly_update

    pending = tmp_path / "flighttracker-update-pending"
    pending.write_text("pending\n", encoding="utf-8")
    monkeypatch.setattr(nightly_update, "PENDING_MARKER", pending)
    monkeypatch.setattr(nightly_update, "_update_checkout", lambda: False)
    monkeypatch.setattr(nightly_update, "_install_dependencies", lambda: None)
    monkeypatch.setattr(
        nightly_update.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0),
    )

    assert nightly_update.run_update() is True
    assert not pending.exists()


def test_nightly_update_keeps_pending_marker_when_dependency_install_fails(
    monkeypatch, tmp_path
):
    import utilities.nightly_update as nightly_update

    pending = tmp_path / "flighttracker-update-pending"
    monkeypatch.setattr(nightly_update, "PENDING_MARKER", pending)
    monkeypatch.setattr(nightly_update, "_update_checkout", lambda: True)

    def fail_install():
        raise subprocess.CalledProcessError(1, ["pip"])

    monkeypatch.setattr(nightly_update, "_install_dependencies", fail_install)

    try:
        nightly_update.run_update()
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("Expected dependency installation failure.")

    assert pending.exists()
