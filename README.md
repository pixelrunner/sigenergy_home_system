# sigenergy_home_system
A few apps and dashboards for my Sigenergy Home System

## Raspberry Pi Setup

### 1. Installation & Environment

SSH into your Raspberry Pi and set up the project:

```bash
# Clone repository
git clone [https://github.com/YOUR-USERNAME/sigenergy-home-system.git](https://github.com/YOUR-USERNAME/sigenergy-home-system.git)
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
