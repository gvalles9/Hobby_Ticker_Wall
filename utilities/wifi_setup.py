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
from pathlib import Path

AP_CONNECTION = "FlightTracker-Setup"
HOME_CONNECTION = "FlightTracker-Home"
SETUP_MARKER = "/run/flighttracker-wifi-setup"
CONFIGURED_MARKER = "/var/lib/flighttracker/wifi-configured"
CONNECTIONS_DIR = "/etc/NetworkManager/system-connections"


def _read_command(args: list[str], timeout: float = 10) -> str:
    """Run a read-only query and return stdout, or "" when unavailable."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _unescape_nmcli(value: str) -> str:
    return value.replace("\\:", ":").replace("\\\\", "\\")


def setup_is_active() -> bool:
    """True while the protected first-boot setup hotspot is open."""
    return Path(SETUP_MARKER).exists()


def current_ssid() -> str:
    """The Wi-Fi network the Pi is using, or "" when it is not connected."""
    output = _read_command(["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"])
    for line in output.splitlines():
        active, separator, ssid = line.partition(":")
        if separator and active == "yes" and ssid:
            return _unescape_nmcli(ssid)

    # A hidden network does not appear in the scan list; fall back to the
    # active NetworkManager connection name (normally the SSID).
    output = _read_command(
        ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", "wlan0"]
    )
    for line in output.splitlines():
        _, separator, name = line.partition(":")
        if separator:
            name = _unescape_nmcli(name)
            if name and name != "--":
                return name
    return ""


def current_ip() -> str:
    """The wlan0 IPv4 address without the prefix length, or ""."""
    output = _read_command(
        ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", "wlan0"]
    )
    for line in output.splitlines():
        _, separator, address = line.partition(":")
        if separator and address:
            return address.split("/", 1)[0]
    return ""


def has_wired_default_route() -> bool:
    """True when a non-Wi-Fi interface owns the default route.

    An Ethernet connection is the escape hatch in the setup wizard: Wi-Fi is
    only required when the unit has no other way to reach the network.
    """
    output = _read_command(["ip", "route", "show", "default"])
    for line in output.splitlines():
        if " dev " not in line:
            continue
        device = line.split(" dev ", 1)[1].split()[0]
        if device != "wlan0":
            return True
    return False


def wifi_status() -> dict:
    """Read-only connection state for the settings page and wizard."""
    ssid = current_ssid()
    return {
        "setup_active": setup_is_active(),
        "connected": bool(ssid),
        "ssid": ssid,
        "ip": current_ip(),
        "wired": has_wired_default_route(),
        "configured": Path(CONFIGURED_MARKER).exists(),
    }


def _keyfile_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(" ", "\\s")


def validate_wifi_credentials(ssid: str, password: str) -> None:
    """Raise ValueError when the SSID/password cannot be saved."""
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
        raise ValueError("Wi-Fi password must be 8-63 characters (or a 64-digit key).")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ValueError("The Wi-Fi password contains unsupported characters.")


def configure_wifi(ssid: str, password: str) -> None:
    """Create and activate a home Wi-Fi connection without logging its password."""
    validate_wifi_credentials(ssid, password)

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


def _saved_wifi_connections() -> list[str]:
    """Return saved infrastructure Wi-Fi profile names, excluding the setup AP.

    Mirrors the watchdog's profile discovery so both scripts treat Imager
    SSID-named profiles the same way.
    """
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    names = []
    for line in result.stdout.splitlines():
        name, separator, connection_type = line.rpartition(":")
        if not separator or connection_type != "802-11-wireless":
            continue
        name = name.replace("\\:", ":").replace("\\\\", "\\")
        if name and name != AP_CONNECTION:
            names.append(name)
    return names


def forget_wifi_networks() -> None:
    """Delete every saved Wi-Fi profile and open the first-boot setup hotspot.

    Used before handing a device to someone else: with no saved profile the
    next boot starts the setup hotspot exactly like a fresh install.
    """
    for name in _saved_wifi_connections():
        subprocess.run(
            ["nmcli", "connection", "delete", name],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    with suppress(FileNotFoundError):
        os.unlink(CONFIGURED_MARKER)
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
        action = payload.get("action")
        if action == "start_setup":
            start_setup_hotspot()
        elif action == "forget_wifi":
            forget_wifi_networks()
        else:
            configure_wifi(payload["ssid"], payload["password"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError):
        print("Could not change the Wi-Fi configuration.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(configure_wifi_from_stdin())
