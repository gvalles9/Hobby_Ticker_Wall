# Hobby Ticker V1

Hobby Ticker is a Raspberry Pi flight, weather, and satellite display based on
[Colin Waddell's FlightTracker](https://github.com/ColinWaddell/FlightTracker).
It is customized primarily for a Raspberry Pi 3 B+ driving **three 64×32 HUB75
panels in a horizontal chain** (192×32 logical pixels). The chain dimensions
are set in `setup/screen.py`.

## What this fork adds

- **Three-panel display support** and Pi 3 B+ setup adjustments.
- **Flight details at a glance:** four configurable telemetry fields, with
  heading, vertical speed, altitude, and ground speed as defaults.
- **Approximate route progress** along the bottom of the display. The indicator
  is hidden when aircraft position or airport coordinates are missing.
- **Flight-screen layout refinements:** left-to-right aircraft-model scrolling,
  a right-aligned flight page count, and compact, right-aligned telemetry.
- **Idle weather and forecasts:** a classic screen and a three-day forecast can
  cycle automatically. NOAA/NWS is used for U.S. locations when no optional
  WeatherAPI key is configured.
- **Separate unit profiles:** flight and satellite scenes default to metric;
  idle weather defaults to standard units. Both profiles are configurable.
- **First-boot Wi-Fi setup and recovery** for supported Pi installations.
- **Fork-based updates:** the web updater checks `main` in
  `gvalles9/Hobby_Ticker_Wall`, regardless of the inherited FlightTracker
  upstream configuration. Updates fast-forward only and refuse tracked local
  changes or diverged branches.

The original FlightTracker documentation remains useful for general hardware
and driver background: [build guide](https://flight-tracker.dev/build/) ·
[software guide](https://flight-tracker.dev/install/).

## Installation

### Option 1: Prebuilt OS Image (Recommended)

For the easiest installation, use the prebuilt Hobby Ticker OS image. This includes everything pre-installed - no command line required.

1. Download and install [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Open Imager and go to **App Options → Content Repository → Custom URL**
3. Enter: `https://raw.githubusercontent.com/gvalles9/Hobby_Ticker_OS/main/os_list.json`
4. Select "Hobby Ticker OS" from the OS list
5. Choose the version for your Pi:
   - **32-bit** for Raspberry Pi 3
   - **64-bit** for Raspberry Pi 4/5
6. Set your Wi-Fi details and hostname (e.g., `hobbyticker`)
7. Flash to SD card
8. Boot your Pi and configure at `http://hobbyticker.local:8584`

See the [Hobby Ticker OS repository](https://github.com/gvalles9/Hobby_Ticker_OS) for more details.

### Option 2: Manual Install

The Raspberry Pi installers clone the Hobby Ticker `main` branch from this
repository. Run the matching script from the Pi's terminal:

```bash
# Raspberry Pi 3/4/Zero
curl -sSL https://raw.githubusercontent.com/gvalles9/Hobby_Ticker_Wall/main/platforms/pi/install.sh | bash

# Raspberry Pi 5
curl -sSL https://raw.githubusercontent.com/gvalles9/Hobby_Ticker_Wall/main/platforms/pi5/install.sh | bash
```

The installer requires an internet connection and interactive terminal access.
The application remains in `~/FlightTracker` to preserve existing service and
configuration conventions; its Git remote points to this Hobby Ticker repo.

The optional first-boot Wi-Fi setup is available after its services have been
installed. On first boot, the Pi starts a temporary setup hotspot. Scan the QR
code on the matrix to join, then browse to `http://192.168.4.1:8584/wifi-setup`
and enter your home Wi-Fi credentials. The hotspot shuts off once the Pi
connects. To enable it on an existing installation, run the helper from the
repository directory, then reboot:

```bash
cd "$HOME/FlightTracker"
sudo bash platforms/common/install-wifi-setup.sh "$(id -un)" "$HOME/FlightTracker"
sudo reboot
```

After setup, the configuration website remains available on your home network at
`http://<pi-hostname>.local:8584/settings` (for example, `http://raspberrypi.local:8584/settings`).
The installers enable mDNS hostname discovery; the Pi and your phone/computer must be
on the same local network.

The Admin page includes separate recovery buttons to reset Hobby Ticker settings
(while keeping the web password and Wi-Fi credentials) or reopen the Wi-Fi setup
hotspot to change networks. If the saved Wi-Fi connection is unavailable for 10
minutes, the Pi automatically opens the protected setup hotspot and displays its QR.
The saved network credentials are retained, so if that network reconnects the Pi
returns to it and closes the temporary hotspot.

On Raspberry Pi, a systemd timer checks the install's `origin` branch daily at
2:00 AM local time. The Hobby Ticker installers set `origin` to this fork. It
fast-forwards only when the working tree is clean, updates Python dependencies
when source changes, and restarts the display service after a successful update.
Failed dependency updates are retried the next night.
User configuration is stored outside the source checkout and is not reset by
code updates. Check the result with
`sudo journalctl -u FlightTracker-NightlyUpdate.service`.

The Pygame simulator uses the same local config mechanism, but closing its window
resets that simulator installation's settings to defaults. This behavior applies
only to the simulator, not to Raspberry Pi installations.

Hobby Ticker's product version (`1.0.0`) is separate from the retained upstream
compatibility version used for backup metadata.

## Platform guides

### Step-by-step install

If you'd rather do it manually - or you want to understand what the script does - follow the guide for your platform:

| Platform | Guide |
|----------|-------|
| Raspberry Pi 3 / 4 / Zero | [platforms/pi/INSTALL.md](platforms/pi/INSTALL.md) |
| Raspberry Pi 5 | [platforms/pi5/INSTALL.md](platforms/pi5/INSTALL.md) |
| Desktop simulator | [platforms/simulator/INSTALL.md](platforms/simulator/INSTALL.md) |

The Pi guides retain some upstream-specific clone/install commands and are not
yet fully rewritten for Hobby Ticker. Use them as hardware and driver
references; for an automated install, use the Hobby Ticker commands above.

## 3D Printed Case

The original project's 3D-printable case was designed for a 64×32 HUB75 RGB LED matrix (4mm pitch). It's a two-piece interlocking design that works with any Raspberry Pi model and prints on a normal-sized bed with minimal supports.

- Ready-to-print files on [Printables](https://www.printables.com/model/1820229-flight-tracker-screen-for-raspberry-pi-any-model-6)
- OpenSCAD source and assembly instructions on [GitHub](https://github.com/ColinWaddell/FlightTracker-Case)

![The original FlightTracker in its 3D printed case](assets/flight-tracker-case.jpg)

---

## Optional features

### Loading LED

An LED wired to a GPIO pin can blink while flight data is loading. Enable it in the web UI under Hardware settings, and set the GPIO pin number to match your wiring.

### Rainfall chart

Weather uses the free NOAA/NWS API by default for U.S. locations. Add a WeatherAPI.com key in the web UI to use that provider instead. Set the weather mode to "temperature + rainfall" to display a 24-hour rainfall chart alongside the temperature.
The default idle screen alternates between the Classic display and a 3-day forecast (today plus the next two days), showing each for 30 seconds. Temperatures default to Fahrenheit; choose Fahrenheit or Celsius under **Settings → Hardware → Defaults → Units**. Daily forecast temperatures are labeled with their low/high and unit (for example, `Lo 46°F Hi 68°F`). Precipitation defaults to inches; choose inches or millimetres in the same Units section. On the Classic screen, enabled weather shows labeled current temperature, humidity, precipitation, and wind values alongside a condition icon. If weather data is unavailable, the time/date remain visible without weather readings or forecast icons.

[![Example Weather Chart](https://raw.githubusercontent.com/ColinWaddell/FlightTracker/refs/heads/main/assets/weather.jpg)](https://raw.githubusercontent.com/ColinWaddell/FlightTracker/refs/heads/main/assets/weather.jpg)

### Using a local ADS-B receiver (tar1090)

By default the tracker pulls flight data from FlightRadar24. If you run your own ADS-B receiver with [tar1090](https://github.com/wiedehopf/tar1090) or a compatible [PiAware](https://www.flightaware.com/adsb/piaware/) / [dump1090-fa](https://github.com/flightaware/dump1090) setup, you can use that as your primary data source instead - no FlightRadar24 account or API access required.

The flight display's upper-right panel shows four configurable flight data fields (default: heading, vertical speed, altitude, and ground speed); choose fields under **Sky Monitoring → Plane Info Row → Flight Data Panel**. Choose separate Metric/Standard measurement profiles for flight scenes and idle screens under **Hardware → Defaults → Screen Units**. The bottom pixel row shows approximate route progress, estimated from the aircraft's direct distance from the origin relative to the origin-to-destination distance. The bar is hidden when the aircraft position or airport coordinates are unavailable; it does not represent the exact route flown.

#### What you need

- A device running dump1090-fa, readsb, or similar, with tar1090 installed
- The device must be reachable on your local network from the Hobby Ticker Pi
- tar1090-db enrichment active (the default in most installations) - it provides the aircraft type descriptions used by this software

#### Finding your aircraft.json URL

Try each of the following in your browser, replacing `your-receiver` with your device's hostname or IP address, until you get a response containing a list of aircraft:

```
http://your-receiver/tar1090/data/aircraft.json
http://your-receiver:8080/data/aircraft.json
http://your-receiver/dump1090-fa/data/aircraft.json
http://your-receiver/skyaware/data/aircraft.json
```

The response should be a JSON object with an `"aircraft"` array.

#### Enabling tar1090 as your data source

Once you have the URL, open the web UI and go to **Providers** → **Provider Settings** → **tar1090**, enter the URL, then enable tar1090 (and order it ahead of FlightRadar24 if you want the local receiver to win) under **Providers** → **Lookup Priority**.

#### Differences from FlightRadar24 mode

- Aircraft type (e.g. "Airbus A-320") is sourced directly from the tar1090 aircraft database
- Origin and destination airport codes are looked up via [adsbdb.com](https://api.adsbdb.com)
- All position and altitude data comes from your receiver in real time
- No rate limiting or API key required

### Using OpenSky Network as your data source

[OpenSky Network](https://opensky-network.org) is a free, community-driven ADS-B network that can be used instead of (or ahead of) FlightRadar24 as the flight data source. No subscription is required - a free registered account gives you enough API credits for 30-second polling.

#### What you need

- A free account at [opensky-network.org](https://opensky-network.org)
- An API client created under Account -> API Clients (gives you a Client ID and Client Secret)

#### Enabling OpenSky Network

1. Log in to the Hobby Ticker web interface
2. Go to **Providers** → **Provider Settings** → **OpenSky Network** and enter your **Client ID** and **Client Secret**
3. Enable OpenSky (and order it ahead of FlightRadar24) under **Providers** → **Lookup Priority**
4. Save - the tracker will restart and begin fetching from OpenSky

#### Differences from FlightRadar24 mode

- Uses OAuth2 credentials (Client ID + Client Secret) rather than a third-party library
- Aircraft type and route origin/destination are both looked up via [adsbdb.com](https://api.adsbdb.com), the same service used in tar1090 mode
- If your credentials are invalid the provider is quarantined for an hour and the tracker falls back to any other enabled flight provider
- Data refreshes every 30 seconds

---

## Location setup

On a fresh install, the tracker has no preset city. It uses an approximate location
from the server's public IP through [ipwho.is](https://ipwho.is/) so weather can load
without opening settings first. When the settings page is opened, the browser also tries
device location and uses it if available. IP-based locations are approximate, and the
service receives the server's public IP address. Review and save the detected location
in **Sky Monitoring → Location**. Existing custom coordinates and locations edited
manually are not replaced.

## Satellite Tracking

To see when a particular satellite is overhead, enter its [NORAD ID](https://celestrak.org/SATCAT/search.php) in **Sky Monitoring → Satellite Tracking**. The panel defaults to azimuth and elevation on the left of the globe plot, with estimated speed and altitude on the right. Choose each of the four fields independently in the same section.
To preview the scene without waiting for a real pass, open **Sky Monitoring → Debug**,
select **Satellite**, and enable **Simulate an active satellite pass**. The synthetic
pass is only used while Satellite is explicitly selected; set the scene back to
**Automatic** when finished. Flight scene forcing requires a live aircraft.

## Running the tracker from the command line

The main entrypoint is the script at the repo root:

```bash
cd /home/pi/FlightTracker
source env/bin/activate
python3 flight-tracker.py help
```

The CLI supports a small set of commands for configuration and maintenance:

```text
Usage: python flight-tracker.py [command]
Commands:
  config                 Dump current configuration as JSON
  data                   Print the platform data directory path
  reset password         Clear web_password_hash in the config
  reset settings         Delete the config.json file
  cache clear            Wipe all on-disk cache files (routes and TLE)
  interface enable       Enable the web interface in the config
  interface disable      Disable the web interface in the config
  test flights           Test the flight provider chain (JSON output)
  test flights --provider tar1090
                         Test a single provider
  test tle               Test TLE satellite lookup
  help                   Show this help message
  --version              Print the program version
```

Test commands accept `--parameters` and `--interval`/`--limit` for repeated runs. Run `python flight-tracker.py test <target> --help` for details.

For normal operation, start the tracker with `python3 flight-tracker.py` and use the configuration file or the web settings UI to control its behaviour.

---

## Updating to the most recent version

If your checkout is still on the old `master` branch, switch to `main` before pulling updates:

```bash
cd /home/pi/FlightTracker
git fetch --all
git checkout main
git pull
source env/bin/activate
pip install -r platforms/pi/requirements.txt
sudo systemctl restart FlightTracker.service
```

---

## Troubleshooting

- **The installation went well, you selected Convenience Mode (no soldering) and can't see anything:**
   Head into the settings interface and go into the `Hardware` section and select Convenience Mode
   for a second time, then hit save.

- **Only half of the screen is lit up:**
  If your LED matrix uses a 1:32 scan rate (often marked `32S` or `1/32` on the back of the panel), navigate to **Settings → Hardware** and select `1:32` as your scan rate.

- **Everything looks red**:
  Your power supply isn't supplying enough power to the screen.

- **I changed a setting now the device won't start:**
  Reset your settings by deleting your config and rebooting

```bash
# Before v2.3.0
rm ~/.local/share/FlightTracker/config.json
sudo reboot

# After v2.3.0
cd ~/FlightTracker
source env/bin/activate
python flight-tracker.py reset settings
```

- **Everything is broken and it wont boot:**
  If you are using the upstream FlightTracker release, [report the issue there](https://github.com/ColinWaddell/FlightTracker/issues/new?template=bug_report.yml). For Hobby Ticker-specific changes, report it in your fork. The most useful diagnostic output comes from running the program manually:

```bash
# Disable the service
sudo systemctl stop FlightTracker.service

# Get ready to run the code
cd ~/FlightTracker
source env/bin/activate

# Copy the output of this into a ticket
python flight-tracker.py

# Include this in the ticket
# Please remove any confidential information before posting (specifically: API keys)
python flight-tracker.py config

# If you want to restart the service
sudo systemctl start FlightTracker.service
```


---


## Settings reference

This table is for reference if you've disabled the web interface (`web_interface_enabled: false`). All settings are otherwise accessible through the web UI.

| Key | Description | Default |
|-----|-------------|---------|
| `location_source` | `"auto"` for first-run location detection, `"browser"` or `"ip"` for detected locations, `"manual"` to preserve manually set coordinates | `"auto"` |
| `flight_location_mode` | `"simple"` (centre + radius) or `"advanced"` (drawn box + observer) | `"simple"` |
| `flight_lat` / `flight_lng` | Centre of the flight search zone (simple mode); automatically detected when `location_source` is `"auto"` | `0.0` / `0.0` (unset) |
| `flight_radius` | Search radius in km (simple mode) | `20.0` |
| `flight_zone_tl_y` / `flight_zone_tl_x` | Search box top-left corner, lat/lng (advanced mode) | `56.05` / `-4.57` |
| `flight_zone_br_y` / `flight_zone_br_x` | Search box bottom-right corner, lat/lng (advanced mode) | `55.69` / `-3.93` |
| `flight_observer_lat` / `flight_observer_lng` | Observer position for weather, sunrise/sunset, satellite passes, and flight distance sorting (advanced mode) | `0.0` / `0.0` (unset) |
| `flight_min_altitude` | Ignore aircraft below this altitude (metres) | `100.0` |
| `flight_max_altitude` | Ignore aircraft above this altitude (metres) | `10000.0` |
| `airport_display_style` | `0` = short code, `1` = airport name, `2` = abbreviated name, `3` = municipality, `4` = municipality + country | `0` |
| `home_airport_code` | IATA code of your local airport - highlighted on the display | `""` |
| `journey_blank_filler` | Filler shown for blank journey segments | `"???"` |
| `details` | Bottom row: `0` = aircraft make/model, `1` = altitude/speed/heading | `0` |
| `flight_data_point_1`–`flight_data_point_4` | Four configurable fields shown in the upper-right flight data panel; defaults are heading, vertical speed, altitude, and ground speed | `heading`, `vertical_speed`, `altitude`, `ground_speed` |
| `weatherapi_key` | Optional API key for [weatherapi.com](https://www.weatherapi.com/pricing.aspx). When blank, use NOAA/NWS (U.S. locations only) | `""` |
| `weather_mode` | `0` = off, `1` = temperature only, `2` = temperature + 24-hour rainfall graph | `1` |
| `rain_sensitivity` | `0` = dry, `1` = moderate, `2` = wet | `1` |
| `flight_units` | Flight scenes and satellite measurements: `"metric"` or `"standard"` | `"metric"` |
| `idle_units` | Idle-screen weather and forecast: `"metric"` or `"standard"` | `"standard"` |
| `theme` | `0` = default, `1` = monochrome, `2` = pastel | `0` |
| `brightness_mode` | `"simple"` (brightness slider + schedule) or `"advanced"` | `"simple"` |
| `screen_brightness` | Display brightness from `1` (dim) to `5` (full) | `3` |
| `screen_rotate` | Rotate the display by 180° | `false` |
| `display_speed` | Animation speed preset: `default`, `slower`, or `faster` | `"default"` |
| `screen_schedule_enabled` | Enable scheduled brightness changes | `false` |
| `screen_schedule_auto` | Use the brightness schedule automatically | `false` |
| `screen_schedule_start` | Schedule start time (`HH:MM`) | `"22:00"` |
| `screen_schedule_end` | Schedule end time (`HH:MM`) | `"07:00"` |
| `screen_schedule_brightness` | Brightness level used during the scheduled window | `0` |
| `screen_schedule_advanced` | Advanced schedule: JSON list of `{"time": "HH:MM", "brightness": 0-5}` pairs, sorted by time; each entry holds until the next, the last holds overnight | `[]` |
| `clock_24hr` | `true` for 24-hour clock | `true` |
| `date_format` | `0` = YYYY-MM-DD, `1` = DD-MM-YYYY, `2` = MM-DD-YYYY | `0` |
| `web_interface_enabled` | Enable the config UI and QR code on boot | `true` |
| `web_port` | TCP port for the Flask config server (1024-65535) | `8584` |
| `web_password_hash` | SHA-256 hash for the web UI password | `""` |
| `gpio_slowdown` | `1`-`4`; increase if the display flickers | `1` |
| `hat_pwm_enabled` | Enable PWM via Pi audio hardware (requires a solder bridge) | `true` |
| `loading_indicator` | Loading indicator mode: `"none"`, `"pixel"` (on-screen blink), or `"gpio"` (external LED) | `"pixel"` |
| `loading_led_gpio_pin` | GPIO pin number for the loading LED (only used when `loading_indicator` is `"gpio"`) | `""` |
| `flight_providers` | Ordered flight-provider list: `[{"provider": "fr24", "enabled": true}, ...]` | `[{"provider": "fr24", "enabled": true}]` |
| `route_providers` | Ordered route-provider list (aerodatabox, hexdb, adsbdb, fr24) | see defaults |
| `providers` | Per-provider settings keyed by provider id (e.g. `providers.tar1090.url`) | `{}` |
| `max_flight_lookup` | Number of nearby flights to track at once | `5` |
| `max_flight_track_minutes` | Drop a flight after this many minutes in the rotation (0-1440, decimals allowed e.g. `0.75` = 45 seconds); 0 tracks for as long as it stays in range. A flight that leaves and returns starts fresh | `0` |
| `callsign_format` | `"icao"` for ICAO callsign (e.g. BAW123), `"iata"` for IATA flight number (e.g. BA123) | `"icao"` |
| `satellite_tracking_enabled` | Enable satellite pass tracking | `true` |
| `satellite_norad_ids` | NORAD IDs for tracked satellites | `[25544]` |
| `satellite_min_elevation` | Minimum elevation for satellite passes | `20` |
| `satellite_max_count` | Maximum number of satellites to plot at once | `5` |
| `satellite_timeout_enabled` | Limit how long the satellite scene is shown per pass | `false` |
| `satellite_timeout_seconds` | Seconds from a pass's start (AOS) before the scene yields to flight tracking | `30` |
| `log_level` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` | `"INFO"` |

---

## Contributing

If you'd like to contribute to Hobby Ticker, please use the issue and pull-request tools for your fork.

---

## Acknowledgements

Hobby Ticker is a fork of **[FlightTracker](https://github.com/ColinWaddell/FlightTracker)** by **Colin Waddell**. It builds on the upstream project's code, documentation, and work from several open-source projects and contributors:

- **Display drivers** - thanks to Henner Zeller for the [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) C++ library and Python bindings (used on Pi 3/4/Zero), and to Adafruit for the [adafruit_blinka_raspberry_pi5_piomatter](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter) driver (used on Pi 5).
- **[plane-tracker-rgb-pi](https://github.com/c0wsaysmoo/plane-tracker-rgb-pi)** - thanks to c0wsaysmoo for letting me copy some of their great work.
- **[FlightRadarAPI](https://pypi.org/project/FlightRadarAPI/)** - thanks to JeanExtreme002 for the FlightRadar24 API library.

---

## License

Hobby Ticker is released under the GNU General Public License v3.0. You're welcome to use, modify, and share the code - keep it under the same license and include proper attribution (retain the copyright and license notice). See [LICENSE.md](LICENSE.md) for details.
