#!/usr/bin/env python3
"""Fast-forward the installed checkout and restart after successful updates."""

import logging
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PENDING_MARKER = Path.home() / ".cache" / "flighttracker-update-pending"
SYSTEMCTL = "/usr/bin/systemctl"
logger = logging.getLogger("flighttracker-nightly-update")


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def _update_checkout() -> bool:
    status = _run(["git", "status", "--porcelain", "--untracked-files=no"])
    if status.stdout.strip():
        raise RuntimeError(
            "Tracked local changes found; refusing to overwrite the working tree."
        )

    upstream = _run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    ).stdout.strip()
    if not upstream:
        raise RuntimeError("The current branch has no configured upstream.")

    before = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    _run(["git", "fetch", "--quiet"], timeout=600)
    _run(["git", "merge", "--ff-only", upstream], timeout=300)
    after = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    return before != after


def _install_dependencies() -> None:
    model_path = Path("/proc/device-tree/model")
    model = (
        model_path.read_bytes().decode("utf-8", errors="ignore")
        if model_path.exists()
        else ""
    )
    platform = "pi5" if "Raspberry Pi 5" in model else "pi"

    requirements = PROJECT_ROOT / "platforms" / platform / "requirements.txt"
    if not requirements.is_file():
        raise RuntimeError(f"Requirements file not found: {requirements}")

    pip = PROJECT_ROOT / "env" / "bin" / "pip"
    if not pip.is_file():
        raise RuntimeError(f"Virtual environment pip not found: {pip}")
    _run([str(pip), "install", "-r", str(requirements)], timeout=1200)


def run_update() -> bool:
    """Return whether the service was restarted for an update."""
    updated = _update_checkout()
    if updated:
        PENDING_MARKER.parent.mkdir(parents=True, exist_ok=True)
        PENDING_MARKER.write_text("pending\n", encoding="utf-8")
        logger.info("Source updated; synchronizing Python dependencies.")

    if not PENDING_MARKER.exists():
        logger.info("No source updates available.")
        return False

    _install_dependencies()
    subprocess.run(
        ["sudo", "-n", SYSTEMCTL, "restart", "FlightTracker.service"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    PENDING_MARKER.unlink(missing_ok=True)
    logger.info("Update installed and FlightTracker restarted.")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run_update()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        logger.error("Nightly update failed: %s", exc)
        raise SystemExit(1) from exc
