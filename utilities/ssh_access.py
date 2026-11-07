#!/usr/bin/python3
"""Enable or disable the SSH server for the Admin page.

Installed as ``/usr/local/sbin/flighttracker-set-ssh`` and invoked through
``sudo -n`` by the web app.  Keeping this in a separate helper means the Flask
process never needs blanket ``systemctl`` rights.

Usage::

    flighttracker-set-ssh status
    flighttracker-set-ssh on
    flighttracker-set-ssh off

Every command prints a JSON status object on success.  ``on`` also generates
any missing host keys with ``ssh-keygen -A`` before starting the server.
"""

from __future__ import annotations

import json
import subprocess
import sys

SSH_SERVICE = "ssh.service"
SSH_SOCKET = "ssh.socket"
ENABLED_STATES = {"enabled", "enabled-runtime", "generated", "generated-runtime"}
COMMAND_TIMEOUT = 30


def _run(
    args: list[str], timeout: int = COMMAND_TIMEOUT
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _socket_available() -> bool:
    """Return True when the installed OpenSSH uses socket activation."""
    result = _run(
        ["systemctl", "list-unit-files", SSH_SOCKET, "--no-legend", "--no-pager"]
    )
    return result.returncode == 0 and SSH_SOCKET in result.stdout


def _units() -> list[str]:
    """Return the SSH units present on this system."""
    if _socket_available():
        return [SSH_SERVICE, SSH_SOCKET]
    return [SSH_SERVICE]


def _is_enabled(unit: str) -> bool:
    return _run(["systemctl", "is-enabled", unit]).stdout.strip() in ENABLED_STATES


def _is_active(unit: str) -> bool:
    return _run(["systemctl", "is-active", unit]).stdout.strip() == "active"


def _primary_unit() -> str:
    """Pick the unit that currently provides (or should provide) SSH.

    Debian enables ``ssh.service``; some distributions use ``ssh.socket``
    instead.  Prefer whichever unit is already enabled or running, and fall
    back to the service unit when SSH is completely off.
    """
    units = _units()
    for unit in units:
        if _is_enabled(unit) or _is_active(unit):
            return unit
    return SSH_SERVICE if SSH_SERVICE in units else units[0]


def status() -> dict:
    """Return the current SSH state without changing anything."""
    try:
        units = _units()
        enabled = any(_is_enabled(unit) for unit in units)
        active = any(_is_active(unit) for unit in units)
        unit = _primary_unit()
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "enabled": False, "active": False, "unit": None}

    return {
        "available": True,
        "enabled": enabled,
        "active": active,
        "unit": unit,
    }


def enable() -> None:
    """Generate missing host keys and enable the SSH server at boot."""
    result = _run(["ssh-keygen", "-A"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Could not generate SSH host keys.")

    unit = _primary_unit()
    result = _run(["systemctl", "enable", "--now", unit])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Could not enable {unit}.")


def disable() -> None:
    """Stop the SSH server and stop it from starting at boot."""
    units = _units()
    primary = _primary_unit()
    if _is_enabled(primary):
        result = _run(["systemctl", "disable", "--now", primary])
    else:
        result = _run(["systemctl", "stop", primary])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Could not disable {primary}.")

    # Make sure the other unit (for example a socket on a system that usually
    # runs the service directly) is not left listening.
    for unit in units:
        if unit != primary:
            _run(["systemctl", "stop", unit])


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("status", "on", "off"):
        print("Usage: flighttracker-set-ssh status|on|off", file=sys.stderr)
        return 2

    action = argv[1]
    try:
        if action == "on":
            enable()
        elif action == "off":
            disable()
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(status()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
