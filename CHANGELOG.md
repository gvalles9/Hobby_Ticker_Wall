# Hobby Ticker Changelog

All notable changes to Hobby Ticker are documented here. Earlier entries record the
upstream FlightTracker release history on which this fork is based.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
release numbers use the `major.minor.patch` scheme from
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) with one local rule: the
patch field only runs from 0 to 9, so `1.1.9` is followed by `1.2.0`, never
`1.1.10`. At 9 the next release bumps the minor number and resets the patch to 0.
The minor number goes up for a new feature, and the major number only for a change
that breaks existing settings or behaviour. Each field is a whole number, not a
decimal. (The first 1.2.0 release was briefly numbered 1.1.10 before this rule was
adopted.)

## [Unreleased]

## [1.7.2] - 2026-11-26

### Changed

- Ticking Birthday or a custom message now permits that dated scene into the
  idle rotation instead of forcing it: the scene must also be scheduled for
  today. Unticked dated scenes stay hidden, and Classic is the fallback when
  no scene is available. Debug previews still ignore the saved date.
- Birthday and date-matched custom scenes now lead the idle rotation, so they
  appear in the first slot whenever the display is idle.
- Date-triggered scenes now also appear at the end of the flight rotation:
  one 30-second slot per flight cycle, alternating between the scheduled
  scenes. The flight counter stays hidden on those pages.

## [1.7.1] - 2026-11-18

### Changed

- The startup QR splash stays up for 30 seconds instead of 5, so there is
  time to pick up a phone and scan it. First boot and the setup hotspot
  keep their 60-second window.

## [1.7.0] - 2026-11-18

### Added

- Once the setup hotspot closes, the splash says `WIFI CONFIGURED!` and
  `SCAN TO SETUP` beside a QR for the wizard on the home network, and the
  code is redrawn if DHCP hands out a different address.

### Fixed

- **Use network location** in the first-setup wizard works again. The
  lookup was redirected to the wizard page, so the browser reported
  `Unexpected token '<'` instead of filling in the coordinates.

## [1.6.3] - 2026-11-18

### Fixed

- The setup QR is centred on its panel instead of starting two rows down,
  which pushed the last row of a taller code onto the bottom edge. The
  hotspot address moved to the middle panel and the code now encodes the
  site root, so it stays small enough to sit comfortably on the display.
  First boot and the setup hotspot also keep the splash up for 60 seconds
  instead of 5, giving more time to scan it.

## [1.6.2] - 2026-11-18

### Fixed

- The hotspot splash caption (`SCAN TO JOIN`) sits level with the Hobby
  Ticker branding and clear of the aircraft artwork instead of low on the
  middle panel. Redrawing the splash also clears the previous layout, so
  the loading text no longer shows through it.

## [1.6.1] - 2026-11-18

### Changed

- New installations start at brightness `1` (the dimmest level) instead of `3`.
  Existing configurations keep their saved brightness; change it under
  Settings → System → Display brightness.

## [1.6.0] - 2026-11-18

### Added

- A dedicated **Wi-Fi** tab in Settings shows the current network and IP
  address, connects the Pi to a new network without restarting the web
  interface, and gathers the setup-hotspot and forget-network actions. The
  first-setup wizard now has a Wi-Fi card that is required while the setup
  hotspot is open without Ethernet.
- The Admin recovery card now labels its Wi-Fi action **Open Hotspot** and
  directs network changes to the Wi-Fi tab.

### Fixed

- After **Prepare for Handoff**, `/` and the login page open `/wifi-setup`
  instead of skipping straight to the first-setup wizard, so the next owner
  joins the hotspot and enters the home Wi-Fi details first. An Ethernet escape
  link keeps the wizard reachable when no Wi-Fi is needed.

## [1.5.1] - 2026-11-17

### Fixed

- The **Fine-tune Schedule** sidebar link now lands on the schedule section
  even while Simple mode is selected, instead of scrolling to a hidden card.

## [1.5.0] - 2026-11-17

### Added

- A dedicated **Sleep** tab in Settings now gathers the night-standby controls:
  the sleep/wake times, sunrise & sunset mode, night brightness and the
  fine-tune schedule. The feature is no longer buried inside the System page,
  which keeps only the base brightness and points at the new tab.
- The first-run setup wizard has an optional **Sleep** card, so a new unit can
  be given overnight quiet hours before setup finishes. It validates both
  times and saves the simple schedule at brightness `0`.

### Changed

- The brightness-mode switch (Simple / Fine-tune) moved from the System page to
  the Sleep tab, next to the schedule it controls.

## [1.4.0] - 2026-11-17

### Changed

- Night standby now actually stops background polling. While the brightness
  schedule holds the display at `0`, the weather and satellite (TLE) threads
  make no requests, the render loop drops to four frames per second, and the
  first refresh after waking starts within 30 seconds. The panels also get a
  full repaint on wake instead of waiting for a scene to redraw. The README
  documents the sleep schedule and its `0 = off` setting.

## [1.3.2] - 2026-11-17

### Added

- A **Materials used** table in the README lists the hardware the reference
  build uses: the Raspberry Pi, a 2×20 riser header, three P5-320X160-16S
  64×32 HUB75 panels, the Adafruit Triple LED Matrix Bonnet, the 5 V power
  supply and its mains cord, the 18 AWG wire and micro USB screw-terminal
  adapter that feed the Pi, and a 16 GB microSD card. A short **Power
  wiring** walkthrough covers the mains input, the panel feeds and the Pi
  feed, with a mains safety warning, and an **Enclosure** note records the
  custom wooden box.
- The README's settings reference now documents `display_scan_rate` and
  `panel_colour_order`.

### Changed

- The README moved the flight-display description out of the tar1090 section
  into its own **Flight display** section, standardised arrow characters, and
  clarified the mains-cord colours, the scan-rate default and the reset
  instructions. The prebuilt-image note now says the image installs `main`
  without maintainer instructions in the install steps, and the riser header is
  listed in the install requirements.

### Removed

- The README no longer carries the unverified "everything looks red" power
  troubleshooting tip, and the unused `assets/flight-tracker-case.jpg` was
  deleted.

## [1.3.1] - 2026-11-17

### Fixed

- A failing scene can no longer crash the display or send the unit into a
  restart loop. Errors from polling, entering or drawing a scene are caught and
  logged with a full traceback, the scene is left out of the rotation for five
  minutes, and the idle screen carries on. A scene that cannot even be built at
  startup (flight, image, satellite or INDYCAR) is skipped instead of stopping
  the boot, and rebuilding the idle rotation at midnight keeps the old rotation
  if the new one cannot be made.
- The panel now says what went wrong: for ten seconds it shows
  `<SCENE> FAILED` above `SEE LOG VIEWER`, then returns to the idle screen. The
  message repeats whenever a retry fails again, so the cause is visible without
  watching a terminal. The full details are in the web interface's Log Viewer.

## [1.3.0] - 2026-11-17

### Added

- A "Use network location" button on the Location card re-runs the public-IP
  lookup on demand and fills in the latitude, longitude, observer pin and
  search box. A unit that has moved, or whose estimate was wrong, can be
  re-located without typing coordinates, and a manual pick can be handed back
  to automatic location the same way. The first-setup wizard gains the same
  button beside its coordinate fields. Nothing moves unless the button is
  pressed, and the result is only kept when the settings are saved.

## [1.2.3] - 2026-11-17

### Fixed

- Coordinates entered in the first-setup wizard now stick. They are saved as
  a manual location, so the IP estimate can no longer replace them on the next
  weather refresh, and the observer pin and search box that Advanced mode reads
  are filled in at the same time, so switching mode later no longer starts
  from 0,0. Half a coordinate pair, or a value that is not a number, is now
  rejected with a readable message instead of being silently discarded. A
  brand-new unit also shows empty boxes rather than the 0,0 placeholder when no
  location has been detected yet, and the card notes that longitudes west of
  Greenwich are negative.

### Changed

- The IP location lookup identifies itself as Hobby Ticker rather than the
  upstream FlightTracker project.

## [1.2.2] - 2026-11-17

### Fixed

- Weather no longer disappears when the National Weather Service is serving only
  part of a forecast. NWS publishes the hourly, daily and precipitation
  documents separately and can return 503 for one while the others are healthy;
  the hourly forecast is the usual casualty. Each document is now optional, and
  when the hourly forecast is unavailable the current temperature, wind and
  condition come from the first daily period instead of the whole weather row
  going blank.

### Changed

- User-Agent strings and support links now point at this fork instead of the
  upstream FlightTracker repository, so NWS and CelesTrak traffic and bug
  reports reach the project that actually runs the code. Attribution to Colin
  Waddell is unchanged.

## [1.2.1] - 2026-11-17

### Fixed

- The Classic idle screen no longer crash-loops on Raspberry Pi 3/4. The 1.1.8
  date-alignment change asked the font for glyph bitmaps, but only the Pi 5 and
  simulator font type provides those; the Pi 3/4 driver font raised
  `AttributeError`, so systemd restarted the app roughly every 25 seconds. Glyph
  data now falls back to the same BDF file the panel driver loaded, and the idle
  screen renders normally again.

## [1.2.0] - 2026-11-17

### Fixed

- The settings menu on the left of the browser UI now scrolls on its own when
  the list is taller than the window, instead of running off the bottom of the
  screen. It also pins below the top navigation bar rather than sliding under
  it, and uses a thin scrollbar.

## [1.1.9] - 2026-11-17

### Fixed

- The update check no longer logs a red "No such remote 'hobby-ticker'" error
  on a freshly cloned unit. A missing update remote is normal before the first
  check, so it is now probed quietly and then created exactly as before; the
  update itself was never affected.

## [1.1.8] - 2026-11-17

### Fixed

- The date on the Classic idle screen now lines up with the weekday above it.
  Both rows are aligned on their first visible pixel instead of the text pen
  position, so glyphs with different left bearings (a "T" is inset one pixel
  in the 5x8 font, an "N" is flush) no longer leave the date a pixel or two
  to the left.

## [1.1.7] - 2026-11-17

### Fixed

- The idle screen no longer shows the moon icon during the day after setting a
  time zone. Sunrise and sunset are calculated in UTC but were compared against
  the display's local clock, so anywhere west of UTC read the morning (and part
  of the evening) as night. Solar times are now converted to the display's time
  zone before the day/night test, the sunrise/sunset text and the automatic
  brightness schedule use them, and daylight saving is applied correctly all
  year round.

## [1.1.6] - 2026-11-16

### Added

- A **Use network location** button next to the time-zone picker (Settings ->
  System -> Defaults -> Clock and Date, and the first-setup wizard). It asks
  the IP lookup the tracker already uses for the flight location and fills in
  the zone it reports - the provider returns the IANA name in the same response,
  so it costs no extra request. Nothing runs on page load or at startup: an
  offline unit renders instantly and simply reports that the lookup was
  unavailable.
- The zone from that lookup also seeds a fresh install, so a new unit starts on
  local time without anyone opening the picker. A saved choice always wins -
  `timezone_source` flips to `"manual"` the moment the form is submitted,
  including a cleared field - so the automatic suggestion never overwrites a
  decision.

## [1.1.5] - 2026-11-16

### Added

- A **Time zone** picker on the Settings page (System -> Defaults -> Clock and
  Date) and in the first-setup wizard. It accepts any IANA zone such as
  `America/New_York` or `America/Chicago`; leaving it blank follows the Pi's
  system time zone. Hobby Ticker applies the zone to its own clock, date,
  sunrise/sunset and screen schedule without root access or a reflash, so a
  unit can move between time zones - for example a handoff from Virginia to
  Indiana - without touching the OS image. Resetting settings or preparing the
  unit for handoff keeps the saved zone, so a same-region handoff shows the
  right time out of the box and a unit whose OS clock is still on UTC does not
  jump back to UTC.

### Fixed

- Satellite pass timing now uses an explicit UTC timestamp, so it stays correct
  when the display follows a non-UTC time zone.

## [1.1.4] - 2026-11-15

### Changed

- Resetting settings - or preparing the unit for handoff - no longer wipes the
  display hardware settings: bonnet type, panel colour order, scan rate, GPIO
  slowdown, PWM mode and the loading indicator. They describe the panels
  attached to the unit rather than the person using it, so both reset buttons
  keep them and the setup wizard pre-selects the saved bonnet type. Everything
  personal (location, birthday, INDYCAR, API keys, custom scenes, providers,
  password, Wi-Fi) still returns to defaults.

## [1.1.3] - 2026-11-15

### Fixed

- The setup-hotspot splash printed "JOIN, OPEN 192.168.4.1:8584" from the left
  edge, straight through the arrow and colour bars in the splash artwork, so
  both were hard to read. The instruction now sits on the middle panel
  ("SCAN TO JOIN") and the address is printed in black on the white strip
  below the QR code, clear of the artwork and of the code itself.

## [1.1.2] - 2026-11-15

### Changed

- The first-setup wizard is now mandatory until a web password other than the
  shared default is saved. Every authenticated page request redirects back to
  the wizard - including bookmarked URLs and `/login?next=...` targets - and
  settings form submissions are rejected until setup is done. **Prepare for
  Handoff** therefore always ends with the next owner choosing their own
  password before they can use the tracker.

### Removed

- The wizard's **Skip for now** button. The legacy `first_setup_complete` flag
  is still written for older config files but no longer satisfies the setup
  gate; only a real password does.

### Fixed

- A bookmarked page or a direct link to `/settings` could bypass initial setup
  and leave the unit running on the default web password.

## [1.1.1] - 2026-11-15

### Added

- Added three date-triggered **Custom Messages** scenes on the Default Screen
  settings page. Each slot has a message, a recurring month and day (the year
  is ignored), and a colour. Matching slots join the idle rotation
  automatically, even when they are not ticked; short messages loop
  continuously left-to-right around the display and longer messages use the
  bounce scroller. Empty slots stay off, so existing units are unchanged. The
  idle rotation is now also rebuilt at midnight, so date-triggered scenes
  (including the birthday scene) appear without a restart.

### Fixed

- Fixed the Admin recovery actions (Reset Wi-Fi, Forget Wi-Fi, Prepare for
  Handoff) and the Remote Access SSH toggle on installed units. The systemd
  unit restricted the capability bounding set to `CAP_SYS_NICE`, which left
  `sudo` unable to switch to root, so every privileged helper failed with
  "unable to change to root gid: Operation not permitted". The unit now keeps
  only the ambient capability it needs for realtime scheduling.

## [1.1.0] - 2026-11-09

### Added

- Added **Admin → Remote Access**, which shows whether SSH is running and can
  enable or disable it. The choice persists across reboots, and the page warns
  that SSH is reachable only from the local network. The privileged helper is
  installed by `platforms/common/install-wifi-setup.sh`.
- Added Wi-Fi recovery helpers to the first-boot installation path so the
  prebuilt OS image actually installs the setup hotspot, watchdog, and sudoers
  rules.
- Added a first-setup wizard at `/first-setup`. It asks for the two things
  every installation needs - the LED matrix bonnet type and a new web password -
  followed by clearly labelled optional sections (location, units, brightness,
  clock and date format, idle scenes, birthday date, and satellite tracking)
  that keep their current or default values when untouched. The root page,
  the post-login redirect, and the splash QR code all forward to the wizard
  on first run, until a web password is set or the wizard is skipped.
- Added **Admin → Recovery** actions for testing and handoff: **Reset Web
  Password** restores the default password and re-opens the first-setup
  wizard, **Forget Wi-Fi** deletes every saved Wi-Fi network and opens the
  first-boot setup hotspot (exactly like a fresh install), and **Prepare for
  Handoff** does both plus a settings reset in one click for gifting the
  device.
- Added automatic refresh of the root-owned helper copies (Wi-Fi setup, SSH
  toggle, Wi-Fi watchdog) after updates, so helper changes reach
  already-installed units without re-running the installer. Updates run the
  new `/usr/local/sbin/flighttracker-sync-helpers` command, granted to the
  application user via sudoers; it only rewrites files that actually changed.
- Added multi-select idle scenes: tick any combination of Classic, Forecast,
  Current Conditions, INDYCAR next event, and Happy Birthday, and the idle
  screen rotates through every selected scene for 30 seconds each. Existing
  single-theme and cycle settings migrate automatically, and the forecast
  uses its three-day form whenever several scenes are selected.
- Added a Happy Birthday idle scene. Entering a birthday date in settings (or
  the first-setup wizard) automatically adds the celebration scene to the
  rotation on that month and day each year; clearing the date removes it.
- Added INDYCAR support (opt-in): a live timing feed and schedule client with
  race/qualifying/practice detection, top-3 standings, tracked-driver and
  champion scenes with team logos, a next-event countdown idle scene, a
  champion-flash celebration when the season is decided, debug previews for
  every scene, and a test mode for off-season development. Live INDYCAR
  sessions preempt flight and satellite scenes.

### Changed

- The default bonnet type is now `triple` (three chained 64×32 panels,
  192×32 total). Missing or invalid values fall back to that default.

### Fixed

- Wi-Fi recovery now detects any saved NetworkManager Wi-Fi profile, including
  the SSID-named profile written by Raspberry Pi Imager, instead of requiring a
  connection named `FlightTracker-Home`.
- The setup hotspot is no longer raised while another interface (for example
  Ethernet) provides a default route, and retries try every saved Wi-Fi profile.
- Fixed a flight-screen crash when the native matrix font has no `text_width`
  attribute.

## [1.0.0] - 2026-11-02

### Added

- Configured the display for three daisy-chained 64×32 HUB75 panels
  (192×32 total), including platform-aware panel initialization and Pi 3 B+
  installation guidance.
- Added four configurable flight telemetry fields to the flight screen, with
  heading, vertical speed, altitude, and ground speed as defaults.
- Added an approximate flight-route progress indicator using aircraft
  position and bundled airport coordinates. It hides when required position
  or route data is unavailable.
- Added independent measurement profiles for flight/satellite scenes and
  idle screens. Flight defaults to metric; idle weather defaults to standard.
- Added cycling between the classic idle screen and a three-day forecast,
  clearer weather/date presentation, and improved behavior for incomplete or
  unavailable forecast data.
- Added first-boot Wi-Fi setup and recovery support, including a setup
  hotspot, QR-assisted connection flow, and a watchdog for disconnected
  networks.
- Added a simulator exit reset: closing the Pygame window restores that
  simulator installation's configuration to defaults. Raspberry Pi
  configuration is not reset by this behavior.
- Added branch-based update checks against the configured Git upstream.
  Updates use fast-forward-only merges, refuse tracked local changes and
  diverged branches, and synchronize platform dependencies after updating.

### Changed

- Rebranded user-facing startup, CLI, web, and documentation surfaces as
  Hobby Ticker V1. Product version `1.0.0` is distinct from the retained
  upstream compatibility version used for backup metadata.
- Refined the flight layout with a right-aligned page count and telemetry,
  left-to-right aircraft-model scrolling, and the route progress bar along the
  bottom row.
- Updated Raspberry Pi installation and recovery instructions for this fork
  and its three-panel configuration.

### Attribution

- Hobby Ticker is based on Colin Waddell's FlightTracker. Original project
  attribution and existing open-source acknowledgements are retained in the
  README, web footer, and license documentation.

## [2.12.5]

- New "Plane Info Row" option to highlight an aircraft
  squawking an emergency: the squawk code (7500 hijack, 7600 radio failure,
  7700 general emergency)
- Added the aircraft's ICAO type code to the custom scroller fields as
  `{icao_type}` (e.g. `A20N` for an Airbus A320-251N).
- The airplanes.live card in the Data Source settings now explains that its
  API is contributor-only

## [v2.12.4] - 2026-10-16
- Added squawk codes to the custom scroller fields

## [v2.12.3] - 2026-10-15
- Added distance_to_home to the custom scroller fields

## [v2.12.2] - 2026-09-26
- Last patch broken the save mechanism in the settings. This fixes it.
- See this issue for more details on how to fix a broken system:
  - https://github.com/ColinWaddell/FlightTracker/issues/117

## [v2.12.1] - 2026-09-26
- Data-source was landing on each page

## [v2.12.0] - 2026-09-26

- New "Image Upload API": POST images to /api/image and the display shows
  them immediately, with options for animations and loops.
- New "Max Tracking Time" option: aircraft circling overhead can be
  dropped from the display after the configured time instead.

## [v2.11.3] - 2026-09-19

- New config option to set daily/monthly API call limits per provider

## [v2.11.2] - 2026-09-13

- New "Code Format" option: display airports by their ICAO (4-letter) codes
  (e.g. EGPF) instead of IATA (3-letter) codes (e.g. GLA), applied to the
  short-code display and the full-name code prefix
- Airports without a known ICAO code keep showing their existing code

## [v2.11.1] - 2026-09-12

- Tweaks to the extended list
- CLI tooling to help debug the chain of lookups 

## [v2.11.0] - 2026-09-05

- Interface for a more fine-tuned timing schedule
- An "extended" list of airport names, allowing for regional 4-character codes

## [v2.10.1] - 2026-09-02

- Tweaks to how flight data is collated to reduce API usage (hopefully)
- Fixed rainfall graph timing
- New config option for pixel ordering

## [v2.10.0] - 2026-09-01

- API usage interface
- Properly tested the commercial API providers and got them working
- Moved to SQLite for caching to reduce SD-card wear
- Some UI tweaks to the data provider interface
- TLE Manager handles not being able to grab a new TLE more gracefully
- Caching duration now user-configurable
- Consistent DEBUG logging across all lookup provider

## [v2.9.0] - 2026-08-29

- All-new provider system: pick your data sources from a list and set their priority
- Optional official **Flight Radar 24 (Paid)** API alongside the free one
- New Status page: provider health and fetch details, plus Pi temperature, memory, storage and uptime
- `python flight-tracker.py test flights` checks your provider setup from the command line

## [v2.8.0] - 2026-08-25
- Complete rewrite of the settings page to move everything over to Vue.js
- Trimmed the pipe character in the plane-scroller so it doesn't swipe away he pixels above the scroller
- Changing the height/distance units also updates how they're displayed in the settings page

## [v2.7.3] - 2026-08-21
- Found the bug that was causing blank index number when using a scrolling callsign

## [v2.7.2] - 2026-08-17
- Merged in updates to flight-route and airline lookup code
- Clearer messaging about the 1:32 scan-rate change

## [v2.7.1] - 2026-08-17
- Another fix for 1:32 panels

## [v2.7.0] - 2026-08-16
- Config backup import/export added to settings
- Experimental support for 1:32 panels
- Move "Help" into its own card

## [v2.6.3] - 2026-08-10
 - Date/Time formatting fixes
 - Numeric seperator adding to config options
 - Plane details scroller is now the correct width

## [v2.6.2] - 2026-08-10
- Better TAR1090 support 
- New `{heading_direction}` tag for custom plane details scroller
- Spelling fixes

## [v2.6.1] - 2026-08-05
- Fix for PioMatter driver that prevent scroller from working

## [v2.6.0] - 2026-08-05
- Custom plane-details scroller
- Cached data can be selectively deleted

## [v2.5.0] - 2026-08-04
- Routing information now has a proper fall-back system
- Returned AeroDataBox as a source of routing info
- Returned asdb.db as a source of routing info
- Web interfaces to see cached and live data

## [v2.4.0] - 2026-08-03
- Airline logos available for flight scenes
- Static origin/destination short-codes for full journey view (when there's no icon)
- Completely rewritten scroller engine

## [v2.3.3] - 2026-08-03
- Airport short-code lookup working in html

## [v2.3.2] - 2026-08-01
- Clear-cache now works as expected from the interface
- Fixed some installation instructions

## [v2.3.1] - 2026-07-30
- Finer grained approach to default units
- Slight tweaks to flight-lookup fallback code

## [v2.3.0] - 2026-07-28
- Added a screen-test to the CLI
- PWM choice should flow from setup script into first config

## [v2.2.5] - 2026-07-27
- Add some CLI options to make the system easier to reset

## [v2.2.4] - 2026-07-26
- Add UV index to conditions screen

## [v2.2.3] - 2026-07-25
- Updated the small-custom font to have the full character set

## [v2.2.2] - 2026-07-25
- Idle conditions was bouncing too fast

### Fixed

## [v2.2.1] - 2026-07-25

### Fixed
- **Map longitude wrapping bug** - the Leaflet maps in settings allowed zooming out to see multiple Earth copies. Clicking on a repeated copy could produce longitudes > 180 or < -180, which were stored verbatim. Fixed with three layers of defence:
  - `worldCopyJump: true` on both maps so Leaflet snaps click coordinates to the primary world copy
  - `maxBounds` + `maxBoundsViscosity` to prevent panning/zooming beyond a single Earth
  - `noWrap: true` on tile layers to stop repeated tile rendering
  - `wrapLng()` normalisation on every click, drag, double-click, and manual input handler in settings.js
- **Config longitude normalisation on load** - `Config.load()` now wraps all stored longitude fields (`flight_lng`, `flight_observer_lng`, `flight_zone_tl_x`, `flight_zone_br_x`) to [-180, 180) on startup, automatically fixing any bad data from the map bug
- **Form submission longitude normalisation** - `parse_settings_form()` in `web/app.py` now wraps longitudes before saving, as a backend safety net

## [v2.2.0] - 2026-07-24

### Added
- **Idle theme system** - the idle screen is now themeable, with a pluggable architecture making it easy to introduce new idle themes
- **Conditions idle theme** - new theme showing current weather conditions with animated weather sprites, wind direction, sunrise/sunset times, moon phase, and temperature
- **Forecast idle theme** - new theme displaying the weather forecast with min/max temperature colouring, sun rays, moon phase icons, and bouncy text descriptions
- **Classic idle theme** - the previous idle screen layout, preserved as a selectable theme
- **Animated weather sprites** - a sprite-based animation engine with animations for rain, snow, blowing snow, fog, mist, dust, sleet, thunder, moon rays, and sun rays, mapped to weather codes from all supported data sources
- **Moon phase display** - moon phase calculation with custom-drawn icons (new, waxing crescent, first quarter, waxing gibbous, full, waning gibbous, last quarter, waning crescent)
- **Wind direction icons** - compass direction icons (N, NE, E, SE, S, SW, W, NW) for weather display
- **Sunrise/sunset icons** - dedicated sunrise and sunset icons in the conditions theme
- **Sun times utility** - new `sun_times.py` module for sunrise/sunset lookups, cached locally as they are queried frequently
- **FR24 fallback for route lookups** - when hexdb.io returns no origin/destination for a callsign, the lookup now falls back to FlightRadar24, improving route coverage while keeping FR24 usage minimal (only on hexdb misses)
- **Release notes inline on update page** - the web UI update page now fetches and displays release notes from GitHub directly, with a lightweight markdown renderer
- **Theme selection in web UI** - theme picker added to settings, with a warning when selecting a new theme
- **Optional mist effect** - mist animation can be toggled off
- **Optional blinker** - the loading blinker LED is now optional (configurable)
- 26 new route lookup tests covering hexdb success/failure, FR24 fallback, and the public `get_route` interface
- New test suites for animations (290 tests), weather codes (113 tests), forecast (129 tests), and forecast sprites (182 tests)

### Changed
- **Idle scene refactored** - the monolithic idle scene has been split into a theme system under `scenes/idle/themes/`, with shared utilities in `theme_utilities.py`
- **Weather data expanded** - the conditions theme pulls in more weather data including wind direction and current conditions
- **Forecast trimmed to future-only** - forecast data is now trimmed to only include future time periods
- **Time display customised** - time font size bumped up and given more character in the idle themes
- **Temperature-based colour** - forecast min/max temperatures now drive the colour of the display text
- **Theme-aware loading blinker** - the blinker position now adjusts based on the active theme
- **Airport name fixes** - airport display names corrected; having no blinker is now an option
- **de421.bsp** - added to `.gitignore` and removed from git tracking
- **Animation engine rewritten** - the animation engine was rewritten for the new sprite-based system

### Fixed
- **Frame stall on TLE fetch** - `SatelliteScene.poll()` was blocking for 5 seconds when Celestrak was down because `recompute_passes()` called `tle_manager.get(timeout=5.0)`. Added a non-blocking `try_get()` variant to `TLEManager` so the display loop is no longer stalled
- **Celestrak failures no longer slow everything down** - TLE lookup failures are now handled gracefully with back-off
- **TLE lookup back-off** - added back-off logic to prevent hammering Celestrak on repeated failures
- **None guard** - added guard against `None` values in theme display
- **File handle leak** - file now properly closed after use in moon phase calculation
- **Update save error message** - improved error message when saving settings fails

### Removed
- **Astro theme** - the astronomy-themed idle screen has been removed (superseded by the new theme system)

## [v2.1.7] - 2026-07-19

### Fixed
- Simulator draws text at correct location now
- Scheduled brightness at 0 should be proper dark now

### Added
- Can override airport info when generating airport cache json
- When brightness is 0 at scheduled hours we no longer poll data sources
- Things for GitHub (PR template, etc)
- Proper info about the PWM generation enabled option


## [v2.1.6] - 2026-07-18

### Fixed
- Scroller has came down one pixel to avoid parenthesis bug

## [v2.1.5] - 2026-07-14

### Added
- Classic (v1) theme that mimics the original FlightTracker look

### Changed
- Font tweaks: aligned 0s and s characters to fit font widths
- Adjusted .service template for easier default Pi user installation

## [v2.1.4] - 2026-07-11

### Changed
- Loading screen tests to ensure data sources are working
- Moved to hexdb.io for flight lookups
- Can delete cache from web UI

### Fixed
- Logic around when to jog onto the next flight's details have been tweaked

## [v2.1.3] - 2026-07-12

### Changed
- Settings UI refactored: categories now split into separate pages using Vue Router (hash mode), with a persistent sidebar and a Save button always visible at the bottom.
- All CSS across the web templates consolidated into a shared `style.css` file.
- All settings page JavaScript extracted into a dedicated `settings.js` file.

## [v2.1.2] - 2026-07-11

### Changed
- OSN now polls at maximum rate the free API will allow

## [v2.1.1] - 2026-07-11

### Changed
- Minor UI updates for the data-sources network.

### Fixed
- Cache is now cleared on update so stale entries never survive a version change.

## [v2.1.0] - 2026-07-11

### Added
- **OpenSky Network data source** - use OSN as an alternative to FlightRadar24, authenticated via OAuth2 client credentials (Client ID + Client Secret obtained from your OSN account). Configured from the web UI under Data Source.
- **adsbdb.com unified lookup** - route origin/destination and aircraft type are now both resolved via [adsbdb.com](https://api.adsbdb.com) for tar1090 and OpenSky Network data sources, replacing the previous mix of adsb.im (routes) and hexdb.io (aircraft type). Route and aircraft lookups are now independent, each cached under their own key with a 24-hour TTL.
- `python flight-tracker.py cache clear` CLI command to wipe all on-disk cache files (routes and TLE).
- Cache is automatically cleared on a successful OTA update so stale entries never survive a version change.

### Changed
- `data_source` config key now accepts `"osn"` in addition to `"fr24"` and `"tar1090"`.
- `route_lookup.py` rewritten to use two separate adsbdb endpoints (`/v0/callsign/{callsign}` for routes, `/v0/aircraft/{mode_s}` for aircraft type) rather than the combined endpoint, which silently omitted route data when adsbdb could not verify the callsign-airframe association.
- Stale cache entries with empty origin and destination are now treated as cache misses and re-queried, fixing cases where old backend data blocked fresh lookups.

### Fixed
- Origin and destination showing blank for flights whose routes were known to adsbdb via the callsign endpoint but not resolvable via the combined aircraft endpoint (e.g. KLM933 -> AMS-DUB).
- Python 3.13 dummy-thread GC noise (`TypeError: 'NoneType' object does not support the context manager protocol`) eliminated by using persistent `requests.Session` objects in `route_lookup`, `overhead_tar1090`, and `overhead_osn`.

## [v2.0.7] - 2026-07-11

### Added
- Pytest test suite with 141 tests across 8 modules covering configuration migration, route caching, flight scene helpers, overhead data handling, CLI dispatch, satellite math, scene manager, and theme system
- `pyproject.toml` now includes `dev` optional dependencies (`pytest`, `pytest-cov`) and `[tool.pytest.ini_options]` configuration
- CI workflow expanded with a `test` job that installs dependencies and runs the full pytest suite
- GitHub issue templates (bug report with debug config export guidance, feature request linking to CONTRIBUTING.md)
- `SECURITY.md` with responsible disclosure guidance
- Ko-fi funding link in `.github/FUNDING.yml` and floating button on the gh-pages site
- `CHANGELOG.md` (Keep a Changelog format, covering v2.0.0 onward)

### Fixed
- Plane cache retrieval bugs where flights were not pulling out of cache correctly
- README license link corrected from `LICENSE` to `LICENSE.md`
- Ruff lint issues (42 auto-fixed, 11 manually fixed) across the codebase

### Changed
- LICENSE copyright year updated to 2026
- `.gitignore` updated with `node_modules/`, `_site/`, `.dev/`

## [v2.0.6] - 2026-07-11

### Changed
- Airport display options expanded from a simple full-name toggle to five styles: short code, full name, abbreviated name, municipality, and municipality + country
- Replaced `full_airport_name` and `abbreviate_name` config keys with a single `airport_display_style` setting (0-4)
- Bundled airports database significantly expanded (45,000+ entries) with richer metadata (name, municipality, country)
- Airport lookup now returns full airport info dict instead of just the name string, for both FR24 and tar1090 data sources

## [v2.0.5] - 2026-07-11

### Fixed
- Updater no longer blocked by untracked files (e.g. `.bak` files from config migration) - `git status` now uses `--untracked-files=no`

## [v2.0.4] - 2026-07-11

### Added
- Advanced flight zone mode: draw a bounding box on a map to define the search area instead of using a centre + radius
- Observer position setting (advanced mode) for weather, sunrise/sunset, satellite passes, and flight distance sorting
- Interactive map selector in the web UI for choosing between simple and advanced zone definitions

### Changed
- `flight_location_mode` config key added (`"simple"` or `"advanced"`)
- Web settings page reworked with map-based zone picker

## [v2.0.3] - 2026-07-11

### Added
- Satellite pass timeout: optionally limit how long the satellite scene is shown per pass, yielding back to flight tracking after a configurable number of seconds from acquisition of signal (AOS)
- `satellite_timeout_enabled` and `satellite_timeout_seconds` config keys
- Satellite timeout controls in the web UI

### Fixed
- Restored polling route for web UI status updates

## [v2.0.2] - 2026-07-09

Bundled the complete v2 overhaul (see [v2.0.0](#v200---2026-07-09)) along with several post-merge refinements.

### Added
- Password enforcement on first run
- CLI utilities (`config`, `data`, `reset-password`, `interface enable/disable`)
- Auto-update status reporting
- Documentation and README rewrite for the v2 branch structure

### Removed
- Old v1 scene files (`clock.py`, `date.py`, `day.py`, `flightdetails.py`, `journey.py`, `planedetails.py`, `weather.py`)
- `animator.py` (replaced by scene manager)
- Taps-aff weather service (replaced by WeatherAPI)

## [v2.0.1] - 2026-07-08

### Added
- Initial auto-update test release - verified the update mechanism works end-to-end from the web UI

## [v2.0.0] - 2026-07-09 - Overhaul released

Complete ground-up rewrite of FlightTracker, developed across `release/v2` and numerous feature/hotfix branches. Not separately tagged, but merged into `main` on 9 July 2026 and first released as v2.0.1.

### Added
- **Complete codebase rewrite** from the ground up, reorganised into `scenes/`, `display/`, `utilities/`, `setup/`, and `web/` packages
- **Scene manager architecture** (C++-style) with `on_enter`/`on_exit` lifecycle, making it straightforward to add new display scenes
- **Web configuration UI** with login page, password protection, settings editor, update page, and log viewer
- **Satellite tracking** - plot satellite passes with NORAD ID configuration, azimuth/elevation ring, and trajectory arcs
- **Idle screen** showing time, weather (temperature + optional 24-hour rainfall chart), date, and day
- **Splash screen** with custom bitmap logo and QR code for web UI access
- **Raspberry Pi 5 support** with dedicated installer, requirements, and `rgbpanel_piomatter` display driver
- **Desktop simulator** platform with `rgbpanel_simulator` for development without hardware
- **One-line install scripts** for Pi 3/4/Zero and Pi 5 with hardware detection, progress output, and systemd service setup
- **Auto-update system** - update from the web UI or CLI, with git pull, pip install, and service restart
- **CLI tools** - `config`, `data`, `reset-password`, `interface enable/disable`, `--version`
- **Structured logging** with configurable verbosity, accessible from the web UI
- **Brightness scheduling** based on sunrise/sunset, with configurable time windows and brightness levels
- **Themes** - default, monochrome, and pastel colour palettes
- **tar1090 / local ADS-B receiver support** as an alternative to FlightRadar24
- **adsbdb.com integration** for origin/destination airport lookups when using tar1090
- **Routes caching** to reduce repeated API calls
- **Loading LED** - optional GPIO LED that blinks while fetching flight data
- **Configurable airport display** - short code, full name, or abbreviated
- **Home airport highlighting** - emphasise your local IATA code on the display
- **Animation speed presets** - `default`, `slower`, `faster`
- **Callsign format selector** - ICAO callsign (e.g. BAW123) or IATA flight number (e.g. BA123), FR24 only
- **Rain sensitivity** setting for the rainfall chart
- **Imperial/metric units** toggle
- **24-hour/12-hour clock** and date format options
- **Screen rotation** (180°) and **brightness** controls (1-5)
- **Bundled airports database** (`airports.json`) with Python helper script to keep it updated

### Removed
- Old v1 scene files (`clock.py`, `date.py`, `day.py`, `flightdetails.py`, `journey.py`, `planedetails.py`, `weather.py`)
- `animator.py` (replaced by scene manager)
- Taps-aff weather service (replaced by WeatherAPI)

---

## v1

The original Python flight tracker for Raspberry Pi. Lives on the `master` branch.
