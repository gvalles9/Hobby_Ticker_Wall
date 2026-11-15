"""Guard the systemd unit against breaking the privileged helpers.

``FlightTracker.service`` runs as the ``pi`` user and calls ``sudo -n`` for
Wi-Fi recovery, the SSH toggle, helper sync, and the nightly restart.  A
restricted ``CapabilityBoundingSet`` is inherited by setuid-root binaries, so
it strips the capabilities ``sudo`` needs to switch to root.  The observed
failure is::

    sudo: unable to change to root gid: Operation not permitted
    sudo: error initializing audit plugin sudoers_audit

``AmbientCapabilities=CAP_SYS_NICE`` is enough to let the app use
``Nice=-10`` and realtime scheduling, and it does not restrict anything else.
"""

from pathlib import Path

SERVICE_FILE = (
    Path(__file__).resolve().parent.parent / "assets" / "FlightTracker.service"
)


def _unit_settings(text: str) -> dict[str, str]:
    settings: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";", "[")):
            continue
        key, separator, value = line.partition("=")
        if separator:
            settings[key.strip()] = value.strip()
    return settings


def test_service_keeps_sudo_capabilities_available():
    settings = _unit_settings(SERVICE_FILE.read_text(encoding="utf-8"))

    # Leave the bounding set at systemd's default (all capabilities) so sudo
    # can setuid, setgid, and initialise its audit plugin.
    assert "CapabilityBoundingSet" not in settings, (
        "FlightTracker.service must not set CapabilityBoundingSet: it strips "
        "CAP_SETUID/CAP_SETGID from setuid-root sudo, so every sudo -n "
        "helper fails with 'unable to change to root gid'."
    )

    # The ambient capability is what makes Nice=-10 work with User=pi.
    assert "CAP_SYS_NICE" in settings.get("AmbientCapabilities", "").split()
