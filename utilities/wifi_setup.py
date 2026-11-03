#!/usr/bin/python3
"""First-boot Wi-Fi setup helpers for Raspberry Pi OS with NetworkManager."""

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from contextlib import suppress

AP_CONNECTION = "FlightTracker-Setup"
HOME_CONNECTION = "FlightTracker-Home"
SETUP_MARKER = "/run/flighttracker-wifi-setup"
CONFIGURED_MARKER = "/var/lib/flighttracker/wifi-configured"
CONNECTIONS_DIR = "/etc/NetworkManager/system-connections"


def _keyfile_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(" ", "\\s")


def configure_wifi(ssid: str, password: str) -> None:
    """Create and activate a home Wi-Fi connection without logging its password."""
    if not isinstance(ssid, str) or not ssid or len(ssid.encode("utf-8")) > 32:
        raise ValueError("Enter a valid Wi-Fi network name (SSID).")
    if any(ord(char) < 32 or ord(char) == 127 for char in ssid):
        raise ValueError("The Wi-Fi network name contains unsupported characters.")
    if (
        not isinstance(password, str)
        or not password.isascii()
        or not (
            8 <= len(password) <= 63
            or (len(password) == 64 and re.fullmatch(r"[0-9a-fA-F]{64}", password))
        )
    ):
        raise ValueError("Wi-Fi password must be 8–63 characters (or a 64-digit key).")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ValueError("The Wi-Fi password contains unsupported characters.")

    connection_path = os.path.join(CONNECTIONS_DIR, "FlightTracker-Home.nmconnection")
    previous_connection = None
    try:
        with open(connection_path, "rb") as connection_file:
            previous_connection = connection_file.read()
    except FileNotFoundError:
        pass

    subprocess.run(
        ["nmcli", "connection", "delete", HOME_CONNECTION],
        check=False,
        capture_output=True,
        text=True,
    )
    content = (
        "[connection]\n"
        f"id={HOME_CONNECTION}\n"
        f"uuid={uuid.uuid4()}\n"
        "type=wifi\n"
        "interface-name=wlan0\n"
        "autoconnect=true\n"
        "\n[wifi]\n"
        "mode=infrastructure\n"
        f"ssid={_keyfile_escape(ssid)}\n"
        "\n[wifi-security]\n"
        "key-mgmt=wpa-psk\n"
        f"psk={_keyfile_escape(password)}\n"
        "\n[ipv4]\n"
        "method=auto\n"
        "\n[ipv6]\n"
        "method=auto\n"
    )
    fd, temporary_path = tempfile.mkstemp(
        prefix=".flighttracker-home-", suffix=".nmconnection", dir=CONNECTIONS_DIR
    )
    try:
        os.chmod(temporary_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as connection_file:
            connection_file.write(content)
        os.replace(temporary_path, connection_path)
        subprocess.run(
            ["nmcli", "connection", "reload"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        subprocess.run(
            ["nmcli", "connection", "up", HOME_CONNECTION, "ifname", "wlan0"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception:
        with suppress(FileNotFoundError):
            os.unlink(temporary_path)
        with suppress(FileNotFoundError):
            os.unlink(connection_path)
        if previous_connection is not None:
            with open(connection_path, "wb") as connection_file:
                os.chmod(connection_path, 0o600)
                connection_file.write(previous_connection)
        subprocess.run(
            ["nmcli", "connection", "reload"],
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["nmcli", "connection", "up", AP_CONNECTION],
            check=False,
            capture_output=True,
            text=True,
        )
        raise
    subprocess.run(
        ["nmcli", "connection", "down", AP_CONNECTION],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    os.makedirs(os.path.dirname(CONFIGURED_MARKER), exist_ok=True)
    with open(CONFIGURED_MARKER, "w", encoding="utf-8") as marker:
        marker.write("configured\n")
    with suppress(FileNotFoundError):
        os.unlink(SETUP_MARKER)


def start_setup_hotspot() -> None:
    """Open setup access without deleting the saved home Wi-Fi connection."""
    subprocess.run(
        [
            "nmcli",
            "connection",
            "modify",
            HOME_CONNECTION,
            "connection.autoconnect",
            "no",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    subprocess.run(
        ["nmcli", "connection", "down", HOME_CONNECTION],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    subprocess.run(
        ["nmcli", "connection", "up", AP_CONNECTION],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    os.makedirs(os.path.dirname(SETUP_MARKER), exist_ok=True)
    with open(SETUP_MARKER, "w", encoding="utf-8") as marker:
        marker.write("manual\n")


def configure_wifi_from_stdin() -> int:
    """Read the setup payload from stdin and configure Wi-Fi as root."""
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Invalid Wi-Fi setup request.")
        if payload.get("action") == "start_setup":
            start_setup_hotspot()
        else:
            configure_wifi(payload["ssid"], payload["password"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError):
        print("Could not connect to that Wi-Fi network.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(configure_wifi_from_stdin())
