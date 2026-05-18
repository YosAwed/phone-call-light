# Standalone Raspberry Pi Zero AP mode

This note records the field setup used when the installation site has no existing Wi-Fi network.

In this mode, the Raspberry Pi Zero W/WH becomes a local Wi-Fi access point. Android/Tasker connects to that local network and calls the Pi directly:

```text
Android phone / Tasker
  -> Wi-Fi SSID: <AP_SSID>
  -> http://192.168.4.1/call/start
  -> Raspberry Pi Zero W/WH
  -> GPIO4 relay
  -> patrol lamp
```

The HTTP controller can run without Flask or gpiozero. It uses only Python standard library plus Raspberry Pi OS `pinctrl`, so it still works when the Pi has no Internet access after AP conversion.

> Replace all placeholder values such as `<PI_USER>`, `<AP_SSID>`, `<AP_PASSPHRASE>`, and `<USB_IF_ALIAS>` before using these commands on a real device. Do not commit real local passwords, Wi-Fi passphrases, or personal account names.

## 1. Keep a USB recovery path

Before changing `wlan0` into an AP, configure Raspberry Pi Zero USB Ethernet Gadget. This avoids losing access when Wi-Fi settings are wrong.

On the `bootfs` partition:

### `config.txt`

Append:

```text
dtoverlay=dwc2
```

### `cmdline.txt`

Keep the whole file as a single line. Add:

```text
modules-load=dwc2,g_ether
```

Optionally add a fixed USB IPv4 address:

```text
ip=10.0.0.2::10.0.0.1:255.255.255.0:<HOSTNAME>:usb0:off
```

Windows side example:

```powershell
# Run as Administrator
New-NetIPAddress -InterfaceAlias "<USB_IF_ALIAS>" -IPAddress 10.0.0.1 -PrefixLength 24
```

Then connect:

```powershell
ssh <PI_USER>@10.0.0.2
```

If IPv4 is not fixed, `ssh <PI_USER>@<HOSTNAME>.local` may work via IPv6 link-local, but fixed IPv4 is much easier to debug.

## 2. Install required AP packages

The Pi needs Internet only while installing `hostapd` and `dnsmasq`.

If the Pi is currently isolated on USB only, temporarily restore its normal Wi-Fi or share the PC Internet connection over the USB/RNDIS adapter.

```bash
sudo apt update
sudo apt install -y hostapd dnsmasq
```

## 3. Stop NetworkManager from managing wlan0

`nmcli` hotspot mode can fail with `supplicant-timeout` even though the driver supports AP mode. In that case, use `hostapd` directly.

```bash
sudo mkdir -p /etc/NetworkManager/conf.d

sudo tee /etc/NetworkManager/conf.d/unmanaged-wlan0.conf >/dev/null <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF

sudo systemctl restart NetworkManager
```

Check:

```bash
nmcli device status
```

`wlan0` should become unmanaged.

## 4. Configure wlan0 address

For a quick manual test:

```bash
sudo ip link set wlan0 down
sudo ip addr flush dev wlan0
sudo ip addr add 192.168.4.1/24 dev wlan0
sudo ip link set wlan0 up
```

For boot-time setup, create `/etc/systemd/system/patlamp-wlan0.service`:

```ini
[Unit]
Description=Configure wlan0 for Phone Call Light AP
Before=hostapd.service dnsmasq.service
After=NetworkManager.service

[Service]
Type=oneshot
ExecStart=/bin/ip link set wlan0 down
ExecStart=/bin/ip addr flush dev wlan0
ExecStart=/bin/ip addr add 192.168.4.1/24 dev wlan0
ExecStart=/bin/ip link set wlan0 up
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl enable patlamp-wlan0.service
sudo systemctl restart patlamp-wlan0.service
```

## 5. Configure hostapd

Copy the example, then edit `<AP_SSID>` and `<AP_PASSPHRASE>`:

```bash
sudo cp setup/hostapd.conf.example /etc/hostapd/hostapd.conf
sudo nano /etc/hostapd/hostapd.conf
```

If `hostapd` is masked:

```bash
sudo systemctl unmask hostapd
sudo systemctl daemon-reload
```

Start it:

```bash
sudo systemctl enable --now hostapd
```

Check:

```bash
systemctl status hostapd --no-pager -l
iw dev
```

Expected `iw dev` output includes:

```text
Interface wlan0
        ssid <AP_SSID>
        type AP
        channel 6
```

## 6. Configure dnsmasq

Copy the example:

```bash
sudo cp setup/dnsmasq-patlamp.conf.example /etc/dnsmasq.d/patlamp.conf
sudo systemctl restart dnsmasq
sudo systemctl enable dnsmasq
```

DHCP debugging:

```bash
sudo journalctl -u dnsmasq -f
```

Expected log entries when a phone connects:

```text
DHCPDISCOVER
DHCPOFFER
DHCPREQUEST
DHCPACK
```

## 7. Install the dependency-free HTTP controller

Copy the repository to `/home/<PI_USER>/phone-call-light`, then update the service path if your username is not `pi`:

```bash
chmod +x /home/<PI_USER>/phone-call-light/scripts/patlamp-standalone.py
sudo cp /home/<PI_USER>/phone-call-light/setup/patlamp.service /etc/systemd/system/patlamp.service
sudo systemctl daemon-reload
sudo systemctl enable --now patlamp.service
```

The field-tested relay wiring used this setting:

```text
relay IN  -> GPIO4 / BCM4 / physical pin 7
relay VCC -> 5V
relay GND -> GND
relay type -> active-high
```

`setup/patlamp.service` therefore defaults to:

```ini
Environment=PATLAMP_GPIO=4
Environment=PATLAMP_ACTIVE_LOW=0
```

If your relay turns on when GPIO is low, use:

```ini
Environment=PATLAMP_ACTIVE_LOW=1
```

To override locally:

```bash
sudo mkdir -p /etc/systemd/system/patlamp.service.d
sudo tee /etc/systemd/system/patlamp.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment=PATLAMP_GPIO=4
Environment=PATLAMP_ACTIVE_LOW=0
EOF
sudo systemctl daemon-reload
sudo systemctl restart patlamp
```

Check:

```bash
systemctl status patlamp --no-pager
journalctl -u patlamp -f
curl http://127.0.0.1/status
```

Manual GPIO verification:

```bash
curl http://127.0.0.1/call/start
pinctrl get 4
curl http://127.0.0.1/call/end
pinctrl get 4
```

For the active-high relay used in the field test:

```text
/call/start -> GPIO4 high -> relay ON -> lamp ON
/call/end   -> GPIO4 low  -> relay OFF -> lamp OFF
```

## 8. Endpoints

When the phone is connected to the local AP:

```text
GET http://192.168.4.1/             health check
GET http://192.168.4.1/call/start   lamp on
GET http://192.168.4.1/call/end     lamp off
GET http://192.168.4.1/on           manual on
GET http://192.168.4.1/off          manual off
GET http://192.168.4.1/status       JSON status
```

## 9. Tasker settings

Use HTTP Request actions:

```text
Incoming call  -> GET http://192.168.4.1/call/start
Phone idle/end -> GET http://192.168.4.1/call/end
Emergency off  -> GET http://192.168.4.1/off
```

The Android phone may warn that the local AP has no Internet access. Choose the option equivalent to "keep using this network" or "connect anyway". Otherwise Android may associate, complete WPA, then disconnect immediately.

## 10. Useful diagnostics

```bash
rfkill list
iw dev
ip -4 addr show wlan0
ip neigh
systemctl status hostapd dnsmasq patlamp --no-pager
sudo journalctl -u hostapd -n 50 --no-pager
sudo journalctl -u dnsmasq -n 50 --no-pager
sudo journalctl -u patlamp -n 50 --no-pager
```

Known-good signs:

```text
hostapd: AP-ENABLED
iw dev: type AP, ssid <AP_SSID>
wlan0: 192.168.4.1/24
phone: 192.168.4.x lease from dnsmasq
```

## 11. Safety notes

Keep AC mains wiring physically separated from the Raspberry Pi/GPIO side. Use a covered terminal block, strain relief, and a fuse near the AC input. If possible, use a 12V/24V DC patrol lamp with a certified power supply rather than bringing AC mains deep into the low-voltage control enclosure.
