# INDYCAR test fixtures

These payloads were captured from the official INDYCAR leaderboard
backend on 2026-11-07:

- `https://indycar.blob.core.windows.net/racecontrol/timingscoring-ris.json`
- `https://indycar.blob.core.windows.net/racecontrol/tsconfig.json`
- `https://indycar.blob.core.windows.net/racecontrol/trackactivityleaderboardfeed.json`
- `https://indycar.blob.core.windows.net/racecontrol/schedulefeed.json`
- `https://indycar.blob.core.windows.net/racecontrol/driversfeed.json`

The schedule, driver, and activity payloads are trimmed to the fields the
parsers use so the fixtures stay small. `timing_race_live.json` is based
on the captured test session with only the session metadata, positions,
gaps, laps, and tire values changed to simulate a green-flag race.

These files are for offline parsing tests only. No test in this suite
should make a network request.
