# Sigenergy Home Dashboard

An interactive, real-time home energy monitoring system designed for the **Pimoroni Presto** (RP2350) display, powered by a lightweight **Raspberry Pi** backend daemon interfacing with the **Sigenergy Open API**.

---

## System Architecture Overview

To avoid direct microcontroller cloud authentication overhead and API rate limit concerns, the system operates using a two-tier local architecture:

### Key Components

* **Raspberry Pi Backend (`raspberry-pi/`)**
  * Periodically polls Sigenergy's `/openapi/systems/{systemId}/energyFlow` endpoint.
  * Manages OAuth authentication and request signature hashing (`SHA256`).
  * Caches telemetry locally and exposes a lightweight JSON API on port `5000`.
  * Includes a 5-minute staleness guard to gracefully detect and report lost cloud connectivity.
  * Optional Modbus TCP simulator (`sim_modbus.py`) for local register testing and prototyping.

* **Pimoroni Presto Display (`presto-app/`)**
  * Written in MicroPython running in native 480x480 resolution using **PicoVector** for anti-aliased vector typography and UI card rendering.
  * Displays live metrics for **Solar Generation**, **House Load**, **EV Charger Draw**, and **Grid Import / Export**.
  * Features a custom retro Windows 3.1-style battery State of Charge (SOC) progress bar.
  * Dynamically adjusts UI colour themes and rear LED backlighting based on real-time grid and solar conditions.
  * Includes an isolated, robust touch-and-hold exit handler (1 second) that triggers a clean hardware reboot back to the Presto OS 3D carousel launcher menu.

---

## Configuration & Credentials Setup

### 1. Raspberry Pi Configuration (`raspberry-pi/credentials.json`)

Create a local `credentials.json` file inside the `raspberry-pi/` directory.

A template is provided in `credentials.json.example`:

```json
{
  "base_url": "https://api-eu.sigencloud.com",
  "app_key": "YOUR_APP_KEY_HERE",
  "app_secret": "YOUR_APP_SECRET_HERE",
  "username": "YOUR_EMAIL_HERE",
  "password": "YOUR_PASSWORD_HERE",
  "system_id": "YOUR_SYSTEM_ID_HERE",
  "debug_modbus": false,
  "inverter_ip": "YOUR_INVERTER_IP_HERE",
  "inverter_port": 502,
  "debug_inverter_ip": "127.0.0.1",
  "debug_inverter_port": 5020
}
```

### 2. Pimoroni Presto Configuration (`presto-app/secrets.py`)

Create a local `secrets.py` file on your Pimoroni Presto display root directory.

A template is provided in `secrets.py.example`:

```python
# secrets.py — Pimoroni Presto Local Network Configuration
WIFI_SSID = "YOUR_WIFI_NAME_HERE"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD_HERE"

# Raspberry Pi Backend IP Address
PI_IP = "YOUR_PI_LAN_IP_HERE"
PI_BASE_URL = f"http://{PI_IP}:5000"
```

> **Security Note:** Both `credentials.json` and `secrets.py` contain private credentials/IPs and are explicitly ignored by `.gitignore`. Never commit these files to source control.

---

## Regional Base URLs (`base_url`)

Sigenergy's Open API is deployed on regional cloud clusters. Ensure your `base_url` matches the geographic region where your account and system are registered:

| Region | Base URL |
| :--- | :--- |
| **Europe (EU)** | `[https://api-eu.sigencloud.com](https://api-eu.sigencloud.com)` |
| **Australia (AUS)** | `[https://api-aus.sigencloud.com](https://api-aus.sigencloud.com)` |
| **North America / Other Regions** | Check your application details in the Sigenergy Developer Portal |

> **Note:** Using an incorrect regional base URL (for example, `api-aus` for an EU-registered account) may result in errors such as `404 Not Found` or `Code 1201: Access restriction`.

---

## Finding Your `system_id`

Your `system_id` uniquely identifies your Sigenergy installation and is required when calling Open API endpoints.

### Method 1: Sigenergy Developer Portal (Recommended)

1. Sign in to the **[Sigenergy Developer Portal](https://developer.sigencloud.com/)**.
2. Navigate to **My Applications** -> **Bound Systems** (or view your application details page).
3. Locate your system identifier or bound system code.

Example format: `WCYBD1788875121`

---

### Method 2: mySigen Mobile App
1. Open the **mySigen** mobile app.
2. Navigate to **Settings** -> **System Info** (or **Station Details**).
3. Locate and copy the displayed System Code or Serial Number.

---

## Raspberry Pi Setup

### 1. Installation & Environment Setup

SSH into your Raspberry Pi and set up the project:

```bash
# Clone repository
git clone https://github.com/pixelrunner/sigenergy_home_system.git

# Enter backend directory
cd sigenergy_home_system/raspberry-pi

# Create Python virtual environment
python3 -m venv ~/sigenergy-env

# Activate environment
source ~/sigenergy-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp credentials.json.example credentials.json
nano credentials.json
```
Update `credentials.json` with your live Sigenergy credentials and system identifier.

---

### 2. Running Headless Services with `systemd`

To ensure services start automatically and remain running after reboots, configure them as `systemd` unit services.

#### Primary API Server Daemon (`sigenergy-server.service`)

1. **Create the service unit file:**
   ```bash
   sudo nano /etc/systemd/system/sigenergy-server.service
   ```

2. **Paste the configuration:**
   ```ini
   [Unit]
   Description=Sigenergy Energy Monitor Local API Server
   After=network.target

   [Service]
   Type=simple
   User=webs_admin
   WorkingDirectory=/home/webs_admin/sigenergy-env
   ExecStart=/home/webs_admin/sigenergy-env/bin/python3 /home/webs_admin/sigenergy-env/server.py
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. **Reload and enable the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sigenergy-server.service
   sudo systemctl start sigenergy-server.service
   ```

#### Optional Modbus Simulator (`sim-modbus.service`)

If using the local Modbus TCP simulator for testing register operations offline:

1. **Copy unit file and enable:**
   ```bash
   sudo cp sim-modbus.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable sim-modbus.service
   sudo systemctl start sim-modbus.service
   ```

#### Useful Service Commands
* **Check status:** `sudo systemctl status sigenergy-server.service`
* **Restart service:** `sudo systemctl restart sigenergy-server.service`
* **View live logs:** `journalctl -u sigenergy-server.service -f`
* **Stop service:** `sudo systemctl stop sigenergy-server.service`

---

## Project Structure

```text
sigenergy_home_system/
├── .gitignore
├── README.md
├── presto-app/
│   ├── energy_monitor.py       # Main Pimoroni Presto display dashboard app
│   ├── modbus_test.py          # Diagnostic test script for Modbus backend endpoints
│   ├── secrets.py.example      # Anonymized Wi-Fi & network config template
│   └── Roboto-Medium.af        # Custom PicoVector typography asset
└── raspberry-pi/
    ├── credentials.json.example # Anonymized API/Modbus credentials template
    ├── fetch_energy_flow.py    # Terminal diagnostic for live power flow
    ├── fetch_summary.py        # Terminal diagnostic for account summary & auth verification
    ├── requirements.txt        # Python package dependencies
    ├── server.py               # Production Flask/HTTP API daemon
    ├── sigenergy_auth.py       # OAuth signing and token generator module
    ├── sim_modbus.py           # Local Modbus TCP simulator daemon
    └── sim-modbus.service      # Systemd service file for Modbus simulator
```

---

## Features

- **Real-Time Energy Telemetry:** Live monitoring for Solar, House Load, EV Charger, and Grid Import/Export.
- **Local Caching Layer:** Fast 5-second display polling without overwhelming Sigenergy Open API rate limits.
- **MicroPython Native UI:** Clean vector typography and responsive layout using Pimoroni's PicoVector engine.
- **Retro Battery SOC Bar:** Windows 3.1 style segmented battery status display.
- **Dynamic LED & UI Themes:** Automated HSV color shifts matching grid state (Red = Import, Yellow = Solar Surplus, Green = Self-Sufficient).
- **Touch-to-Exit Gesture:** Stable 1-second long-press reset handler returning to the Presto carousel menu.
- **Cloud Staleness Detection:** Automated 5-minute timeout flag indicating lost upstream cloud connectivity.
- **Modbus TCP Simulation:** Built-in Modbus simulator for testing inverter register commands locally.
- **Headless & Autonomous:** Runs as background `systemd` services on boot.

---

## Disclaimer

This project is an independent community-developed dashboard and is not affiliated with or endorsed by Sigenergy.

Use at your own risk. Ensure any API credentials remain private and are never committed to source control.
