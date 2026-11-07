#!/bin/bash

set -euo pipefail

APP_USER="${1:?Application user is required}"
INSTALL_DIR="${2:?Installation directory is required}"

# Remote Access (SSH) helper. This is installed before the Wi-Fi checks so the
# Admin page can still toggle SSH on a system without a wireless interface.
sudo install -o root -g root -m 0755 \
    "${INSTALL_DIR}/utilities/ssh_access.py" \
    /usr/local/sbin/flighttracker-set-ssh

SUDOERS_FILE="/etc/sudoers.d/flighttracker-wifi-setup"
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/flighttracker-configure-wifi, /usr/local/sbin/flighttracker-set-ssh\n%s ALL=(root) NOPASSWD: /usr/bin/systemctl restart FlightTracker.service\n' \
    "$APP_USER" "$APP_USER" | sudo tee "$SUDOERS_FILE" >/dev/null
sudo chmod 0440 "$SUDOERS_FILE"
sudo visudo -cf "$SUDOERS_FILE"

if ! command -v nmcli >/dev/null 2>&1; then
    echo "NetworkManager (nmcli) is required for Wi-Fi setup mode." >&2
    exit 1
fi

WLAN_DEVICE="wlan0"
if ! sudo nmcli -t -f DEVICE device status | grep -Fxq "$WLAN_DEVICE"; then
    echo "No wlan0 device found; skipping first-boot Wi-Fi setup." >&2
    exit 0
fi

if ! command -v avahi-daemon >/dev/null 2>&1; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y avahi-daemon
fi
sudo systemctl enable --now avahi-daemon.service

MAC_SUFFIX=$(cat "/sys/class/net/${WLAN_DEVICE}/address" | tr -d ':' | tail -c 5)
if [ ! -f /etc/flighttracker/setup-ap.json ] &&
    sudo nmcli -t -f NAME connection show | grep -Fxq "FlightTracker-Setup"; then
    sudo nmcli connection delete FlightTracker-Setup
fi
if [ -f /etc/flighttracker/setup-ap.json ]; then
    SSID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ssid"])' /etc/flighttracker/setup-ap.json)
    PASSWORD=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["password"])' /etc/flighttracker/setup-ap.json)
else
    SSID="F${MAC_SUFFIX}"
    PASSWORD=$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(9)))')
fi

if ! sudo nmcli -t -f NAME connection show | grep -Fxq "FlightTracker-Setup"; then
    sudo nmcli connection add \
        type wifi \
        ifname "$WLAN_DEVICE" \
        con-name FlightTracker-Setup \
        ssid "$SSID" \
        wifi.mode ap \
        wifi.band bg \
        wifi.channel 6 \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$PASSWORD" \
        ipv4.method shared \
        ipv4.addresses 192.168.4.1/24 \
        ipv6.method disabled \
        connection.autoconnect no
fi

sudo install -d -m 0755 /etc/flighttracker
printf '{"ssid":"%s","password":"%s"}\n' "$SSID" "$PASSWORD" |
    sudo tee /etc/flighttracker/setup-ap.json >/dev/null
sudo chown "root:$(id -gn "$APP_USER")" /etc/flighttracker/setup-ap.json
sudo chmod 0640 /etc/flighttracker/setup-ap.json

sudo install -o root -g root -m 0755 \
    "${INSTALL_DIR}/utilities/wifi_setup.py" \
    /usr/local/sbin/flighttracker-configure-wifi
sudo install -o root -g root -m 0755 \
    "${INSTALL_DIR}/utilities/wifi_watchdog.py" \
    /usr/local/sbin/flighttracker-wifi-watchdog

sudo tee /usr/local/sbin/flighttracker-wifi-setup >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail
# Prefer any saved Wi-Fi profile over the setup hotspot. This includes the
# profile Raspberry Pi Imager writes, which is named after the SSID rather
# than FlightTracker-Home.
while IFS= read -r line; do
    case "$line" in
        *:802-11-wireless)
            name="${line%:802-11-wireless}"
            if [ "$name" != "FlightTracker-Setup" ]; then
                exit 0
            fi
            ;;
    esac
done < <(nmcli -t -f NAME,TYPE connection show)
nmcli radio wifi on
nmcli connection up FlightTracker-Setup
touch /run/flighttracker-wifi-setup
EOF
sudo chmod 0755 /usr/local/sbin/flighttracker-wifi-setup

sudo install -m 0644 \
    "${INSTALL_DIR}/assets/FlightTracker-WifiSetup.service" \
    /etc/systemd/system/FlightTracker-WifiSetup.service
sudo install -m 0644 \
    "${INSTALL_DIR}/assets/FlightTracker-WifiWatchdog.service" \
    /etc/systemd/system/FlightTracker-WifiWatchdog.service
sed \
    -e "s|@APP_USER@|${APP_USER}|g" \
    -e "s|@INSTALL_DIR@|${INSTALL_DIR}|g" \
    "${INSTALL_DIR}/assets/FlightTracker-NightlyUpdate.service" \
    > /tmp/FlightTracker-NightlyUpdate.service
sudo install -m 0644 /tmp/FlightTracker-NightlyUpdate.service \
    /etc/systemd/system/FlightTracker-NightlyUpdate.service
rm -f /tmp/FlightTracker-NightlyUpdate.service
sudo install -m 0644 \
    "${INSTALL_DIR}/assets/FlightTracker-NightlyUpdate.timer" \
    /etc/systemd/system/FlightTracker-NightlyUpdate.timer
sudo systemctl daemon-reload
sudo systemctl enable FlightTracker-WifiSetup.service
sudo systemctl enable FlightTracker-WifiWatchdog.service
sudo systemctl enable --now FlightTracker-NightlyUpdate.timer
