"""Manual smoke test for the INDYCAR feed layer.

Usage::

    python -m utilities.indycar
    python -m utilities.indycar --json

This only fetches and prints data; it does not touch the display, scenes,
or saved configuration.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from utilities.indycar.service import IndyCarService


def _print_snapshot(snapshot) -> None:
    print(f"live: {'yes' if snapshot.is_live else 'no'}")

    session = snapshot.session
    if session is None:
        print("session: none")
    else:
        print(
            "session: "
            f"{session.event_name or '?'} | "
            f"{session.session_name or '?'} ({session.session_type or '?'}) "
            f"flag={session.flag or '?'} status={session.status or '?'} "
            f"time={session.time_to_go or '?'}"
        )
        for driver in session.drivers[:10]:
            print(
                f"  P{driver.position:<2} "
                f"{driver.car_number:>2} "
                f"{driver.short_name:<18} "
                f"gap={driver.gap or '-':>8} "
                f"laps={driver.laps:<3} "
                f"tire={driver.tire or '-'}"
            )

    if snapshot.next_race is not None:
        race = snapshot.next_race
        print(
            f"next: {race.event.name} on {race.event.date} "
            f"(T-{race.days_until}d) tv={race.event.tv or '?'}"
        )
    else:
        print("next: none")

    if snapshot.standings:
        print("standings:")
        for standing in snapshot.standings[:5]:
            print(
                f"  {standing.position}. {standing.driver:<20} "
                f"{standing.points:>4} pts ({standing.wins} wins)"
            )
    else:
        print("standings: none")

    if snapshot.error:
        print(f"error: {snapshot.error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch and print the current INDYCAR feed snapshot."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the normalized snapshot as JSON",
    )
    args = parser.parse_args()

    snapshot = IndyCarService().snapshot(force=True)
    if args.json:
        print(json.dumps(asdict(snapshot), default=str, indent=2))
    else:
        _print_snapshot(snapshot)


if __name__ == "__main__":
    main()
