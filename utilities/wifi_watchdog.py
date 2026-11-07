#!/usr/bin/python3
"""Reopen the setup hotspot after a sustained loss of the saved Wi-Fi network."""

import logging
import os
import subprocess
import time
from contextlib import suppress

AP_CONNECTION = "FlightTracker-Setup"
WLAN_DEVICE = "wlan0"
SETUP_MARKER = "/run/flighttracker-wifi-setup"
DISCONNECT_TIMEOUT = 600
POLL_INTERVAL = 15
RECOVERY_RETRY_INTERVAL = 300

logger = logging.getLogger("flighttracker-wifi-watchdog")


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _active_connection() -> str:
    result = subprocess.run(
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", WLAN_DEVICE],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _has_default_route() -> bool:
    """Return True when another interface (for example Ethernet) is online."""
    try:
        result = _run(["ip", "-4", "route", "show", "default"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _nmcli_unescape(value: str) -> str:
    return value.replace("\\:", ":").replace("\\\\", "\\")


def _saved_wifi_connections() -> list[str]:
    """Return saved infrastructure Wi-Fi profiles, excluding the setup AP."""
    result = _run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        timeout=10,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )

    names = []
    for line in result.stdout.splitlines():
        name, separator, connection_type = line.rpartition(":")
        if not separator or connection_type != "802-11-wireless":
            continue
        name = _nmcli_unescape(name)
        if name and name != AP_CONNECTION:
            names.append(name)
    return names


def _is_connected(active: str) -> bool:
    """Return True when nmcli reports a real, non-hotspot connection."""
    return bool(active) and active not in ("--", AP_CONNECTION)


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
    """Try every saved Wi-Fi profile; keep the hotspot up if none connect."""
    for name in _saved_wifi_connections():
        result = subprocess.run(
            ["nmcli", "connection", "up", name, "ifname", WLAN_DEVICE],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode == 0:
            logger.info("Reconnected to saved Wi-Fi network %s.", name)
            return True

    logger.info(
        "Saved Wi-Fi networks are still unavailable; keeping setup hotspot active."
    )
    subprocess.run(
        ["nmcli", "connection", "up", AP_CONNECTION],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return False


def run() -> None:
    disconnected_since = None
    last_recovery_attempt = None
    while True:
        try:
            active = _active_connection()
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Could not check Wi-Fi state: %s", exc)
            active = ""

        setup_active = os.path.exists(SETUP_MARKER)
        # Any active connection other than our own hotspot is a working
        # network. Imager-created profiles use the SSID as their name, so
        # there is no fixed "home" connection to look for.
        connected = _is_connected(active)

        if connected:
            disconnected_since = None
            last_recovery_attempt = None
            if setup_active:
                try:
                    _set_setup_mode(False)
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.error("Could not close the setup hotspot: %s", exc)
        elif _has_default_route() and not setup_active:
            # Ethernet or another interface is carrying traffic. Do not
            # interrupt it by raising the Wi-Fi hotspot.
            disconnected_since = None
            last_recovery_attempt = None
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
