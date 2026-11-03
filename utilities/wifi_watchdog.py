#!/usr/bin/python3
"""Reopen the setup hotspot after a sustained loss of the saved Wi-Fi network."""

import logging
import os
import subprocess
import time
from contextlib import suppress

HOME_CONNECTION = "FlightTracker-Home"
AP_CONNECTION = "FlightTracker-Setup"
WLAN_DEVICE = "wlan0"
CONFIGURED_MARKER = "/var/lib/flighttracker/wifi-configured"
SETUP_MARKER = "/run/flighttracker-wifi-setup"
DISCONNECT_TIMEOUT = 600
POLL_INTERVAL = 15
RECOVERY_RETRY_INTERVAL = 300

logger = logging.getLogger("flighttracker-wifi-watchdog")


def _active_connection() -> str:
    result = subprocess.run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", WLAN_DEVICE],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _set_setup_mode(enabled: bool, reason: str = "recovery") -> None:
    if enabled:
        subprocess.run(
            ["nmcli", "connection", "up", AP_CONNECTION],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        with open(SETUP_MARKER, "w", encoding="utf-8") as marker:
            marker.write(f"{reason}\n")
    else:
        subprocess.run(
            ["nmcli", "connection", "down", AP_CONNECTION],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        with suppress(FileNotFoundError):
            os.unlink(SETUP_MARKER)

    subprocess.run(
        ["systemctl", "restart", "FlightTracker.service"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _retry_saved_connection() -> bool:
    result = subprocess.run(
        [
            "nmcli",
            "connection",
            "up",
            HOME_CONNECTION,
            "ifname",
            WLAN_DEVICE,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode:
        logger.info(
            "Saved Wi-Fi network is still unavailable; keeping setup hotspot active."
        )
        subprocess.run(
            ["nmcli", "connection", "up", AP_CONNECTION],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return False
    return True


def run() -> None:
    disconnected_since = None
    last_recovery_attempt = None
    while True:
        if not os.path.exists(CONFIGURED_MARKER):
            disconnected_since = None
            last_recovery_attempt = None
            time.sleep(POLL_INTERVAL)
            continue

        try:
            active = _active_connection()
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Could not check Wi-Fi state: %s", exc)
            active = ""

        setup_active = os.path.exists(SETUP_MARKER)
        if active == HOME_CONNECTION:
            disconnected_since = None
            last_recovery_attempt = None
            if setup_active:
                try:
                    _set_setup_mode(False)
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.error("Could not close the setup hotspot: %s", exc)
        else:
            if disconnected_since is None:
                disconnected_since = time.monotonic()
            elif (
                not setup_active
                and time.monotonic() - disconnected_since >= DISCONNECT_TIMEOUT
            ):
                try:
                    _set_setup_mode(True)
                    last_recovery_attempt = time.monotonic()
                    logger.warning(
                        "Wi-Fi has been disconnected for 10 minutes; "
                        "the setup hotspot is now available."
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.error("Could not open the setup hotspot: %s", exc)
                    disconnected_since = time.monotonic()
            elif setup_active:
                try:
                    with open(SETUP_MARKER, encoding="utf-8") as marker:
                        reason = marker.read().strip()
                except OSError as exc:
                    logger.error("Could not read Wi-Fi setup state: %s", exc)
                    reason = "manual"
                now = time.monotonic()
                if reason == "recovery" and (
                    last_recovery_attempt is None
                    or now - last_recovery_attempt >= RECOVERY_RETRY_INTERVAL
                ):
                    last_recovery_attempt = now
                    try:
                        _retry_saved_connection()
                    except (OSError, subprocess.SubprocessError) as exc:
                        logger.warning(
                            "Could not retry the saved Wi-Fi network: %s", exc
                        )

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
