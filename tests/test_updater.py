import subprocess


def test_update_info_compares_checkout_with_configured_upstream(monkeypatch):
    from utilities import updater

    calls = []
    responses = iter(
        [
            (True, "origin/main"),
            (True, ""),
            (True, "0\t2"),
            (True, "abcdef123456"),
        ]
    )

    def run_git(args, timeout=60):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(updater, "_run_git", run_git)

    info = updater.get_update_info()

    assert info == {
        "current_version": "v1.0.0",
        "latest_version": "abcdef123456",
        "update_available": True,
        "upstream_ref": "origin/main",
        "commit": "abcdef123456",
        "error": None,
    }
    assert calls == [
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        ["fetch", "--quiet"],
        ["rev-list", "--left-right", "--count", "HEAD...origin/main"],
        ["rev-parse", "--short", "origin/main"],
    ]


def test_update_info_reports_diverged_branch_without_offering_update(monkeypatch):
    from utilities import updater

    responses = iter(
        [(True, "origin/main"), (True, ""), (True, "1\t1"), (True, "abcdef1")]
    )
    monkeypatch.setattr(updater, "_run_git", lambda *args, **kwargs: next(responses))

    info = updater.get_update_info()

    assert info["update_available"] is False
    assert "have diverged" in info["error"]


def test_perform_update_fast_forwards_upstream_and_installs_dependencies(
    monkeypatch, tmp_path
):
    from utilities import updater

    requirements = tmp_path / "platforms" / "pi" / "requirements.txt"
    requirements.parent.mkdir(parents=True)
    requirements.touch()
    pip = tmp_path / "env" / "bin" / "pip"
    pip.parent.mkdir(parents=True)
    pip.touch()
    monkeypatch.setattr(updater, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(updater, "is_dirty_tree", lambda: False)
    monkeypatch.setattr(updater, "detect_platform", lambda: "pi")
    responses = iter(
        [
            (True, "origin/main"),
            (True, ""),
            (True, "Updating to latest commit"),
            (True, "abcdef1"),
        ]
    )
    git_calls = []

    def run_git(args, timeout=60):
        git_calls.append(args)
        return next(responses)

    monkeypatch.setattr(updater, "_run_git", run_git)
    monkeypatch.setattr(
        updater.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""),
    )

    success, message = updater.perform_update()

    assert success is True
    assert message == "Successfully updated to abcdef1."
    assert [
        "merge",
        "--ff-only",
        "origin/main",
    ] in git_calls
