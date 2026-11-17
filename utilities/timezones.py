#!/usr/bin/python3
"""Read and apply the time zone used by the display.

Hobby Ticker renders its clock, date, sunrise/sunset and screen schedule
from the process's local time (``datetime.now()``).  Pointing the ``TZ``
environment variable at an IANA zone and calling ``time.tzset()`` makes
every one of those calls follow the owner's zone, with no root access and
no reflash.  The OS time zone in ``/etc/localtime`` is left untouched:
this changes how the running application reads the system clock, not the
clock itself.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

# Debian/Raspberry Pi OS records the configured zone here.  The tests swap
# these paths for temporary files.
SYSTEM_TZ_FILE = Path("/etc/timezone")
LOCALTIME_FILE = Path("/etc/localtime")
_ZONEINFO_MARKER = "/zoneinfo/"

# Regions that are not real places.  ``available_timezones()`` also lists
# helper files such as ``posixrules`` and ``localtime``; filtering to names
# with a slash (plus the bare UTC/GMT zones) keeps the picker readable.
_NON_GEOGRAPHIC = {"UTC", "GMT"}


def available_zones() -> list[str]:
    """Return the IANA zone names offered by the web UI."""
    try:
        zones = available_timezones()
    except (OSError, ValueError):  # pragma: no cover - broken tzdata
        return []
    return sorted(z for z in zones if "/" in z or z in _NON_GEOGRAPHIC)


def is_valid_zone(name: str) -> bool:
    """True when *name* is a time zone this system can resolve."""
    if not name:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def system_zone() -> str:
    """Best-effort name of the OS time zone, or ``""`` when unknown."""
    try:
        name = SYSTEM_TZ_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        name = ""
    if name and is_valid_zone(name):
        return name

    # Raspberry Pi OS links /etc/localtime into /usr/share/zoneinfo.
    target = os.path.realpath(LOCALTIME_FILE)
    if _ZONEINFO_MARKER in target:
        candidate = target.split(_ZONEINFO_MARKER, 1)[1]
        if is_valid_zone(candidate):
            return candidate
    return ""


def apply_zone(name: str) -> bool:
    """Make ``datetime.now()`` follow *name* for this process.

    An empty *name* restores the OS default.  Returns ``False`` without
    changing anything when *name* is not a zone this system knows.
    """
    if name and not is_valid_zone(name):
        return False
    if name:
        os.environ["TZ"] = name
    else:
        os.environ.pop("TZ", None)
    # Windows has no tzset(); the Pi does.
    if hasattr(time, "tzset"):
        time.tzset()
    return True
