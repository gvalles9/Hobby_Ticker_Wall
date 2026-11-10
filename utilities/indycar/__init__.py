"""INDYCAR public feed client and normalized snapshot models.

This package only fetches and normalizes the public INDYCAR leaderboard
feeds.  It deliberately does not render anything or touch configuration,
so the display scene and settings can be designed separately.

Public entry points::

    from utilities.indycar import IndyCarFeeds, IndyCarService

    snapshot = IndyCarService().snapshot()
    if snapshot.is_live:
        print(snapshot.session.event_name)
"""

from utilities.indycar.client import FEED_PATHS, IndyCarFeeds
from utilities.indycar.models import (
    ActivitySession,
    Championship,
    DriverTiming,
    NextRace,
    RaceEvent,
    SessionState,
    Snapshot,
    Standing,
    TrackConfig,
)
from utilities.indycar.monitor import IndyCarMonitor
from utilities.indycar.service import IndyCarService

__all__ = [
    "FEED_PATHS",
    "ActivitySession",
    "Championship",
    "DriverTiming",
    "IndyCarFeeds",
    "IndyCarMonitor",
    "IndyCarService",
    "NextRace",
    "RaceEvent",
    "SessionState",
    "Snapshot",
    "Standing",
    "TrackConfig",
]
