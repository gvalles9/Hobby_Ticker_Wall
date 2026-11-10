# INDYCAR team logos

The official INDYCAR feeds publish driver headshots, car illustrations, and
engine logos, but no team logos. The display therefore falls back to a compact
coloured tile with the team's initials whenever a PNG is missing.

To use a real logo, save a square PNG here using the team name from the feed,
lower-cased and hyphenated. Examples:

| Feed team name          | File name                    |
| ----------------------- | ---------------------------- |
| Chip Ganassi Racing     | `chip-ganassi-racing.png`    |
| Andretti Global         | `andretti-global.png`        |
| Team Penske             | `team-penske.png`            |
| Arrow McLaren           | `arrow-mclaren.png`          |
| HMD Motorsports         | `hmd-motorsports.png`        |

Notes:

- PNG with transparency is recommended. Images are resized with nearest-neighbour
  scaling, so small, high-contrast artwork works best on the 192x32 matrix.
- The Top 3 scene draws logos at 7x7 pixels; the tracked-driver and champion
  scenes draw them at 16x16 pixels. A 16x16 (or larger) source is ideal.
- Files are cached after first load. Restart the display service after adding or
  replacing a logo.
- No logos are bundled with the project, so the placeholders are fully
  replaceable later without any code changes.
