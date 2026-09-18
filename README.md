# Sigenergy Home Dashboard

An interactive, real-time home energy monitoring system designed for the **Pimoroni Presto** (RP2350) display, powered by a lightweight **Raspberry Pi** backend daemon interfacing with the **Sigenergy Open API**.

---

## System Architecture Overview

To avoid direct microcontroller cloud authentication overhead and API rate limit concerns, the system operates using a two-tier local architecture:

### Key Components

* **Raspberry Pi Backend (`raspberry-pi/)**
  * Periodically polls Sigenergy's `/openapi/systems/{systemId}/energyFlow` endpoint.
  * Manages OAuth authentication and request signature hashing (`SHA256`).
  * Caches telemetry locally and exposes a lightweight JSON API on port `5000`.
  * Includes a 5-minute staleness guard to gracefully detect and report lost cloud connectivity.

* **Pimoroni Presto Display (`presto-app/`)**
  * Written in MicroPython using **PicoVector** for typography and ui rendering.
  * Displays live metrics for **Solar Generation**, **House Load**, **EV Charger Draw**, and **Grid Import / Export**.
  * Features a custom retro Windows 3.1-style battery State of Charge (SOC) progress bar.
  * Dynamically adjusts UI colour themes and rear LED backlighting based on system conditions.
  * Includes a touch-and-hold exit handler that triggers a hardware reboot back to the Presto launcher.

---

## Configuration & Credentials Setup

Before starting the backend server or running diagnostic scripts, create a local `credentials.json` file inside the `raspberry-pi/` directory.

A template is provided in `credentials.json.example`:

```json
{
  "base_url": "https://api-eu.sigencloud.com",
  "app_key": "YOUR_APP_KEY_HERE",
  "app_secret": "YOUR_APP_SECRET_HERE",
  "username": "YOUR_EMAIL_HERE",
  "password": "YOUR_PASSWORD_HERE",
  "system_id": "YOUR_SYSTEM_ID_HERE"
}
```

---

## Regional Base URLs (`base_url`)

Sigenergy's Open API is deployed on regional cloud clusters. Ensure your `base_url` matches the geographic region where your account and system are registered:

| Region | Base URL |
| :--- | :--- |
| **Europe (EU)** | `https://api-eu.sigencloud.com` |
| **Australia (AUS)** | `https://api-aus.sigencloud.com` |
| **North America / Other Regions** | Check your application details in the Sigenergy Developer Portal |

> **Note:** Using an incorrect regional base URL (for example, `api-aus` for an EU-registered account) may result in errors such as `404 Not Found` or `Code 1201: Access restriction`.

---

## Finding Your `system_id`

Your `system_id` uniquely identifies your Sigenergy installation and is required when calling Open API endpoints.

### Method 1: Sigenergy Developer Portal (Recommended)

1. Sign in to the **[Sigenergy Developer Portal](https://developer.sigencloud.com/)**.
2. Navigate to **My Applications** -> **Bound Systems** (or view your application details page).
3. Locate your system identifier or bound system code.

Example formats:
```text
WCNBD1785875121
NDXPZ1731665296
```

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
pip install requests

# Configure credentials
cp credentials.json.example credentials.json
nano credentials.json
```
update `credentials.json` with your live Sigenergy credentials and system identifier.

---

### 2. Running Headless with `systemd`

To ensure `server.py` starts automatically and remains running after reboots, configure it as a `systemd` service.

1. **Create the service unit file:**
   ```bash
   sudo nano /etc/systemd/system/sigenergy-server.service
   ```

2. **Paste the following configuration:**
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

3. **Reload and enable the service:**`bash
   sudo systemctl daemon-reload
   sudo systemctl enable sigenergy-server.service
   sudo systemctl start sigenergy-server.service
   ```

4. **Useful Service Commands:**
   * **Check status:** `sudo systemctl status sigenergy-server.service`
   * **Restart service:** `sudo systemctl restart sigenergy-server.service`
   * **View live logs:** `journalctl -u sigenergy-server.service -f`
   * **Stop service:** `sudo systemctl stop sigenergy-server.service`
   * **Disable startup:** `sudo systemctl disable sigenergy-server.service`

---

## Project Structure

```text
sigenergy_home_system/

   raspberry-pi/
       server.py
       credentials.json.example
       credentials.json
       requirements.txt

   presto-app/
       main.py
       assets/
       fonts/

   README.md
```

---

## Features

- Real-time home energy monitoring
- Local API caching layer
- Sigenergy Open API integration
- EV charging visibility
- Solar generation monitoring
- Battery State of Charge tracking
- Grid import/export visualisation
- Dynamic UI theme changes
- Đynamic LED backlight feedback
- Cloud connectivity staleness detection
- Fully autonomous startup via systemd
- Optimised for Pimoroni Presto RP2350 hardware

---

## Disclaimer

This project is an independent community-developed dashboard and is not affiliated with or endorsed by Sigenergy.


Use at your own risk. Ensure any API credentials remain private and are never committed to source control.
