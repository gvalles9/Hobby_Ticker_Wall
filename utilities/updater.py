"""Hobby Ticker update manager for the fork's main branch."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from version import APP_VERSION

logger = logging.getLogger("updater")

GITHUB_OWNER = "gvalles9"
GITHUB_REPO = "Hobby_Ticker_Wall"
GITHUB_REPOSITORY_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
UPDATE_REMOTE = "hobby-ticker"
UPDATE_BRANCH = "main"
UPDATE_REF = f"{UPDATE_REMOTE}/{UPDATE_BRANCH}"

# Project root is the parent of the utilities/ directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Root-owned helper copies refreshed after updates (see
# platforms/common/install-wifi-setup.sh, which installs this command and
# grants the application user passwordless sudo for exactly it).
HELPER_SYNC_COMMAND = "/usr/local/sbin/flighttracker-sync-helpers"


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


def parse_version(tag: str) -> list[int]:
    """Parse a tag string like 'v2.0.1' or '2.0.1' into [major, minor, patch]."""
    cleaned = tag.lstrip("vV").strip()
    parts = cleaned.split(".")
    result: list[int] = []
    for part in parts:
        try:
            result.append(int(part))
        except ValueError:
            # Ignore non-numeric suffixes (e.g. "2.0.1-rc1" -> [2, 0, 1])
            numeric = ""
            for ch in part:
                if ch.isdigit():
                    numeric += ch
                else:
                    break
            result.append(int(numeric) if numeric else 0)
    # Pad to 3 elements
    while len(result) < 3:
        result.append(0)
    return result[:3]


def is_newer(remote: list[int], local: list[int]) -> bool:
    """Return True if remote version is strictly greater than local."""
    for r, lcl in zip(remote, local):
        if r > lcl:
            return True
        if r < lcl:
            return False
    return False  # equal


def compare_versions(a: list[int], b: list[int]) -> int:
    """Compare two version lists element-wise.

    Returns -1 if ``a`` < ``b``, 0 if equal, +1 if ``a`` > ``b``.

    Unlike :func:`is_newer` this performs a full three-way comparison and
    handles differing lengths by treating missing elements as 0, so
    ``[2, 6]`` compares equal to ``[2, 6, 0]``.
    """
    max_len = max(len(a), len(b))
    for i in range(max_len):
        ai = a[i] if i < len(a) else 0
        bi = b[i] if i < len(b) else 0
        if ai < bi:
            return -1
        if ai > bi:
            return 1
    return 0


def version_string(version: list[int]) -> str:
    """Format a version list as 'v2.0.1'."""
    return "v" + ".".join(map(str, version))


def _ensure_update_remote() -> tuple[bool, str]:
    """Make the updater's remote point at this fork, not an upstream project."""
    ok, remote_url = _run_git(["remote", "get-url", UPDATE_REMOTE])
    if not ok:
        return _run_git(["remote", "add", UPDATE_REMOTE, GITHUB_REPOSITORY_URL])
    if remote_url.rstrip("/").removesuffix(".git") != GITHUB_REPOSITORY_URL:
        return _run_git(["remote", "set-url", UPDATE_REMOTE, GITHUB_REPOSITORY_URL])
    return True, ""


def get_update_info() -> dict:
    """Compare the local checkout with this fork's main branch."""
    info = {
        "current_version": version_string(APP_VERSION),
        "latest_version": None,
        "update_available": False,
        "upstream_ref": None,
        "commit": None,
        "error": None,
    }

    ok, message = _ensure_update_remote()
    if not ok:
        info["error"] = f"Unable to configure Hobby Ticker update source: {message}"
        return info

    ok, message = _run_git(
        ["fetch", "--quiet", UPDATE_REMOTE, UPDATE_BRANCH], timeout=600
    )
    if not ok:
        info["error"] = f"Unable to check for updates: {message}"
        return info

    ok, counts = _run_git(
        ["rev-list", "--left-right", "--count", f"HEAD...{UPDATE_REF}"]
    )
    if not ok:
        info["error"] = f"Unable to compare with {UPDATE_REF}: {counts}"
        return info

    try:
        local_ahead, remote_ahead = (int(value) for value in counts.split())
    except (TypeError, ValueError):
        info["error"] = f"Unable to parse commit comparison for {UPDATE_REF}."
        return info

    ok, commit = _run_git(["rev-parse", "--short", UPDATE_REF])
    if not ok:
        info["error"] = f"Unable to identify latest commit on {UPDATE_REF}: {commit}"
        return info

    info["latest_version"] = commit
    info["upstream_ref"] = UPDATE_REF
    info["commit"] = commit
    if local_ahead and remote_ahead:
        info["error"] = (
            f"The local branch and {UPDATE_REF} have diverged; "
            "a fast-forward update is not possible."
        )
    else:
        info["update_available"] = remote_ahead > 0
    return info


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def detect_platform() -> str:
    """Detect whether we're on a Pi 5 or older Pi.

    Returns 'pi5' or 'pi'.
    """
    try:
        import adafruit_blinka_raspberry_pi5_piomatter  # noqa: F401

        return "pi5"
    except ImportError:
        return "pi"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    """Run a git command in the project root. Returns (success, output)."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            logger.error(
                "git %s failed (rc=%d): %s", " ".join(args), result.returncode, output
            )
            return False, output
        logger.info("git %s succeeded: %s", " ".join(args), output)
        return True, output
    except subprocess.TimeoutExpired:
        return False, f"git {' '.join(args)} timed out after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return False, f"git {' '.join(args)} error: {exc}"


def is_dirty_tree() -> bool:
    """Check if the git working tree has uncommitted changes to tracked files.

    Untracked files (e.g. .bak files left by config migration) are ignored
    so they don't block updates.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=100,
        )
        return bool(result.stdout.strip())
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Update execution
# ---------------------------------------------------------------------------


def sync_privileged_helpers() -> bool:
    """Refresh the root-owned helper copies under /usr/local/sbin.

    The Wi-Fi setup, SSH toggle, and Wi-Fi watchdog helpers are copied
    (root-owned) out of the checkout at install time; without this call a
    source update would leave those copies stale.  The sync command
    compares each file and only rewrites what changed, so this is a cheap
    no-op on every run.  Systems without it (development machines, the
    simulator) are skipped silently.
    """
    if not Path(HELPER_SYNC_COMMAND).is_file():
        logger.debug("Helper sync command not installed; skipping.")
        return False
    try:
        result = subprocess.run(
            ["sudo", "-n", HELPER_SYNC_COMMAND],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not sync privileged helpers: %s", exc)
        return False
    if result.returncode:
        logger.warning("Privileged helper sync failed: %s", result.stderr.strip())
        return False
    logger.info("Privileged helpers refreshed from the checkout.")
    return True


def perform_update() -> tuple[bool, str]:
    """Fast-forward to this fork's main branch and update dependencies.

    Returns (success, message).
    """
    # 1. Check for dirty working tree
    if is_dirty_tree():
        return (
            False,
            "Working tree has local modifications. Please commit or stash them "
            "before updating, or run 'git checkout -- .' to discard changes.",
        )

    # 2. Ensure updates always come from Hobby Ticker, never an inherited upstream.
    ok, msg = _ensure_update_remote()
    if not ok:
        return False, f"Unable to configure Hobby Ticker update source: {msg}"

    logger.info("Fetching updates for %s...", UPDATE_REF)
    ok, msg = _run_git(["fetch", "--quiet", UPDATE_REMOTE, UPDATE_BRANCH], timeout=600)
    if not ok:
        return False, f"git fetch failed: {msg}"

    # 3. Fast-forward only; never discard local commits.
    logger.info("Fast-forwarding to %s...", UPDATE_REF)
    ok, msg = _run_git(["merge", "--ff-only", UPDATE_REF], timeout=300)
    if not ok:
        return False, f"Unable to fast-forward to {UPDATE_REF}: {msg}"

    # 4. Update Python dependencies
    platform = detect_platform()
    requirements_file = PROJECT_ROOT / "platforms" / platform / "requirements.txt"
    if not requirements_file.exists():
        # Fall back to pi if platform-specific file missing
        requirements_file = PROJECT_ROOT / "platforms" / "pi" / "requirements.txt"

    venv_pip = PROJECT_ROOT / "env" / "bin" / "pip"
    if not venv_pip.exists():
        # Windows venv layout
        venv_pip = PROJECT_ROOT / "env" / "Scripts" / "pip.exe"

    logger.info("Installing dependencies from %s...", requirements_file)
    try:
        result = subprocess.run(
            [str(venv_pip), "install", "-r", str(requirements_file)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=1200,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            logger.error("pip install failed (rc=%d): %s", result.returncode, output)
            return False, f"pip install failed: {output}"
        logger.info("pip install succeeded")
    except subprocess.TimeoutExpired:
        return False, "pip install timed out after 120s"
    except Exception as exc:  # noqa: BLE001
        return False, f"pip install error: {exc}"

    # 5. Refresh the root-owned helper copies (Wi-Fi setup, SSH toggle,
    #    Wi-Fi watchdog) so helper changes reach already-installed units.
    sync_privileged_helpers()

    ok, updated_commit = _run_git(["rev-parse", "--short", "HEAD"])
    if not ok:
        return (
            False,
            f"Update installed, but could not read current commit: {updated_commit}",
        )
    return True, f"Successfully updated to {updated_commit}."
