# Installation Guide - Raspberry Pi 5

This guide covers installing Hobby Ticker on a Raspberry Pi 5 using Adafruit's `adafruit-blinka-raspberry-pi5-piomatter` library, which drives the RGB panel via the Pi 5's PIO subsystem - no C++ compilation needed. The application is installed in `~/FlightTracker` to preserve its service and configuration conventions.

---

## Hardware

- Raspberry Pi 5
- [Adafruit RGB Matrix Bonnet](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi/overview) + 64x32 RGB LED matrix
- *Solder bridge not required for the Raspberry Pi 5*

---

## Automated install (recommended)

```bash
curl -sSL https://raw.githubusercontent.com/gvalles9/Hobby_Ticker_Wall/main/platforms/pi5/install.sh | bash
```

The installer detects your hardware, clones the repo, creates a virtual environment, installs dependencies, and sets up a systemd service.

---

## Manual install

### 1. System update

```bash
sudo apt-get update
sudo apt-get dist-upgrade
```

### 2. Clone and install Hobby Ticker

```bash
git clone https://github.com/gvalles9/Hobby_Ticker_Wall.git "$HOME/FlightTracker"
cd "$HOME/FlightTracker"
python3 -m venv env
source env/bin/activate
pip install -r platforms/pi5/requirements.txt
```

### 3. Verify piomatter

```bash
python3 -c "import adafruit_blinka_raspberry_pi5_piomatter; print('piomatter OK')"
```

---

## Configuration

On the first boot after a fresh install, the Pi starts a temporary, password-protected
setup hotspot. Scan the matrix QR code with your phone to join it, then open
`http://192.168.4.1:8584/wifi-setup` and enter your home Wi-Fi name and password. The
hotspot turns off when the Pi joins your network. The matrix then displays the regular
settings QR code until initial settings are saved.

The hotspot password is random and shown only inside the QR code. Anyone who can
photograph or copy the QR code can also join while setup mode is active. The installer
needs internet access to download FlightTracker and dependencies. Use Ethernet or
temporary Wi-Fi during installation; the first-boot hotspot lets you set the Wi-Fi
credentials you want to keep afterward.

Scan the QR code or open a browser on the same network and go to:

```
http://<pi-ip-address>:8584
```

You can also use the Pi’s local hostname, such as
`http://raspberrypi.local:8584/settings`. The installer enables mDNS discovery; your
phone/computer and Pi must be on the same network.

The Admin page can restore FlightTracker defaults while keeping your web password
and Wi-Fi credentials, or reopen the protected Wi-Fi setup hotspot to change networks.
If the saved Wi-Fi is unavailable for 10 minutes, the Pi automatically opens that
hotspot and displays its QR. It retains the saved credentials and returns to the
same network if it becomes available again.

FlightTracker also checks its configured Git upstream every night at 2:00 AM local
time. It updates only a clean checkout, installs changed Python dependencies, and
restarts after a successful update; saved configuration is kept. To inspect update
logs, run `sudo journalctl -u FlightTracker-NightlyUpdate.service`.

The settings page covers everything: your location (with a map), flight filters, airport display, weather, display theme, brightness, clock, and hardware options. FlightTracker generates and manages the configuration file automatically.

If you've disabled the web interface, see the [main README](../../README.md) for the full settings reference.

---

## Running manually

```bash
cd /home/pi/FlightTracker
env/bin/python3 flight-tracker.py
```

Press `Ctrl-C` to quit.

---

## Running on boot (systemd)

```bash
sudo cp /home/pi/FlightTracker/assets/FlightTracker.service /etc/systemd/system/FlightTracker.service
sudo systemctl daemon-reload
sudo systemctl enable FlightTracker.service
sudo systemctl start FlightTracker.service
```

Check status and logs:

```bash
sudo systemctl status FlightTracker.service
journalctl -u FlightTracker.service -f
```

---

## Upgrading from a previous version

If your checkout is still on the old `master` branch, switch to `main` before pulling updates:

```bash
cd /home/pi/FlightTracker
git fetch --all
git checkout main
git pull
source env/bin/activate
pip install -r platforms/pi5/requirements.txt
```

Install the latest service file and restart FlightTracker:

```bash
sudo cp /home/pi/FlightTracker/assets/FlightTracker.service \
    /etc/systemd/system/FlightTracker.service
sudo systemctl daemon-reload
sudo systemctl restart FlightTracker.service
```

---

## Using a local ADS-B receiver (tar1090)

See the [main README](../../README.md) for tar1090 setup instructions - this is platform-independent.