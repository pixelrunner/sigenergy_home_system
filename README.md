# Sigenergy Home Dashboard

An interactive, real-time home energy monitoring system designed for the **Pimoroni Presto** (RP2350) display, powered by a lightweight **Raspberry Pi** backend daemon interfacing with the **Sigenergy Open API**.

---

## System Architecture Overview

To circumvent direct microcontroller cloud authentication overhead and rate limits, the system operates on a 2-tier local architecture:

### Key Components

* **Raspberry Pi Backend (`raspberry-pi/`)**
  * Periodically polls Sigenergy's `/openapi/systems/{systemId}/energyFlow` endpoint[cite: 3].
  * Manages signature hashing (`SHA256`) and OAuth tokens[cite: 3].
  * Caches telemetry and serves a clean, lightweight JSON endpoint on local port `5000`[cite: 3].
  * Features a 5-minute staleness guard to flag lost cloud connectivity gracefully[cite: 3].

* **Pimoroni Presto Display (`presto-app/`)**
  * Written in MicroPython using `PicoVector` for typography and UI elements.
  * Displays dynamic metrics for **Solar Generation**, **House Load**, **EVAC Charger Draw**, and **Grid Import/Export**.
  * Features a custom retro Windows 3.1-style battery state-of-charge (SOC) progress bar.
  * Adjusts UI color themes and rear LED backlighting dynamically based on system state (Red for Grid Import, Yellow for Excess Solar, Green for Self-Sufficiency/Battery Discharge).
  * Includes a long-press touch-to-exit handler that triggers a hardware reboot back to the primary device menu/launcher.

---

## Raspberry Pi Setup

### 1. Installation & Environment

SSH into your Raspberry Pi and set up the project:

```bash
# Clone repository
git clone [https://github.com/pixelrunner/sigenergy-home-system.git](https://github.com/pixelrunner/sigenergy-home-system.git)
cd sigenergy-home-system/raspberry-pi

# Create and activate Python virtual environment
python3 -m venv ~/sigenergy-env
source ~/sigenergy-env/bin/activate

# Install dependencies
pip install requests

# Configure secrets
cp credentials.json.example credentials.json
nano credentials.json   # Add your live Sigenergy App Key, Secret, and User credentials
```

---

### 2. Running Headless with `systemd`

To ensure `server.py` runs continuously in the background and restarts automatically on Pi reboots, configure it as a `systemd` service.

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
