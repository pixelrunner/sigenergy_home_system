# Sigenergy Home Dashboard

An interactive, real-time home energy monitoring system designed for the **Pimoroni Presto** (RP2350) display, powered by a lightweight **Raspberry Pi** backend daemon interfacing with the **Sigenergy Open API**.

---

## System Architecture Overview

To circumvent direct microcontroller cloud authentication overhead and rate limits, the system operates on a 2-tier local architecture:

### Key Components

* **Raspberry Pi Backend (`raspberry-pi/`)**
  * Periodically polls Sigenergy's `/openapi/systems/{systemId}/energyFlow` endpoint.
  * Manages signature hashing (`SHA256`) and OAuth tokens.
  * Caches telemetry and serves a clean, lightweight JSON endpoint on local port `5000`.
  * Features a 5-minute staleness guard to flag lost cloud connectivity gracefully.

* **Pimoroni Presto Display (`presto-app/`)**
  * Written in MicroPython using `PicoVector` for typography and UI elements.
  * Displays dynamic metrics for **Solar Generation**, **House Load**, **EVAC Charger Draw**, and **Grid Import/Export**.
  * Features a custom retro Windows 3.1-style battery state-of-charge (SOC) progress bar.
  * Adjusts UI color themes and rear LED backlighting dynamically based on system state.
  * Includes a long-press touch-to-exit handler that triggers a hardware reboot back to the primary device menu/launcher.

---

## Configuration & Credentials Setup

Before starting the backend server or running diagnostic scripts, you must configure your local `credentials.json` file inside the `raspberry-pi/` directory.

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

### Regional Base URLs (`base_url`)

Sigenergy's Open API is deployed on regional cloud clusters. Ensure your `base_url` matches the geographic region where your account and station are registered:

| Region / Location | Base URL Domain |
| :--- | :--- |
| **Europe (EU)** | `https://api-eu.sigencloud.com` |
| **Australia (AUS)** | `https://api-aus.sigencloud.com` |
| **North America / Global** | Check your [Sigenergy Developer Portal](https://developer.sigencloud.com/) application details |

> **Note:** Setting an incorrect regional base URL (e.g., using `api-aus` for an EU-registered account) will result in `404 Not Found` or `Code 1201: Access restriction` API errors.

### How to Find Your `system_id`

Your `system_id` is the unique identifier assigned to your Sigenergy power station. You can locate it using either of the following methods:

#### Method 1: Sigenergy Developer Portal (Recommended)
1. Sign in to the **[Sigenergy Developer Portal](https://developer.sigencloud.com/)**.
2. Navigate to **My Applications** -> **Bound Systems** (or view your application details page).
3. Locate your bound station serial number or system code (typically formatted as a string such as `WCYBD1788875121` or `NDXZZ1731665796`).

#### Method 2: MySigen Mobile App
1. Open the **mySigen** app on your mobile device.
2. Go to **Settings** -> **System Info** (or **Station Details**).
3. Copy the **System Code** / **Serial Number** listed under your station details.

---

## Raspberry Pi Setup

### 1. Installation & Environment Setup

SSH into your Raspberry Pi and set up the project:

```bash
# Clone repository
git clone https://github.com/pixelrunner/sigenergy_home_system.git
cd sigenergy_home_system/raspberry-pi

# Create and activate Python virtual environment
python3 -m venv ~/sigenergy-env
source ~/sigenergy-env/bin/activate

# Install dependencies
pip install requests

# Configure secrets
cp credentials.json.example credentials.json
nano credentials.json   # Add your live Sigenergy credentials & system_id
```

---

### 2. Running Headless with `systemd`

To ensure `server.py` runs continuously in the background and restarts automatically on Pi reboots, configure it as a `systemd` service.

```ini
1. **Create the service unit file:**
   ```bash
   sudo nano /etc/systemd/system/sigenergy-server.service

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

3. **Enable and start the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sigenergy-server.service
   sudo systemctl start sigenergy-server.service
   ```
4. **Useful Service Commands:**
   * **Check status:** `sudo systemctl status sigenergy-server.service`
   * **Restart server:** `sudo systemctl restart sigenergy-server.service`
   * **View live logs:** `journalctl -u sigenergy-server.service -f`
