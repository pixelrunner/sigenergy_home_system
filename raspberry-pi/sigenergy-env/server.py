import os
import json
import time
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from sigenergy_auth import get_token
import socket
from pymodbus.client import ModbusTcpClient

INVERTER_IP = "172.18.4.20"  # Sigenergy inverter's static IP address

# 1. Load credentials globally at script startup
CONFIG_PATH = os.path.expanduser('~/sigenergy-env/credentials.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = 'credentials.json'

with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

SYSTEM_ID = config.get("system_id", "WCYBD1788875121")
APP_SECRET = config.get("app_secret", "")

# 2. In-Memory Caching (Prevents API rate limits)
cached_token = None
cached_base_url = None
cached_app_key = None
token_expiry = 0

cached_telemetry = None
last_telemetry_fetch = 0
TELEMETRY_CACHE_TTL = 15  # Minimum seconds between cloud requests


def get_cached_token():
    global cached_token, cached_base_url, cached_app_key, token_expiry
    now = time.time()

    # Request a new token only when uninitialized or expired
    if not cached_token or now >= token_expiry:
        token, base_url, app_key = get_token()
        if token:
            cached_token = token
            cached_base_url = base_url
            cached_app_key = app_key
            token_expiry = now + (10 * 3600)  # Valid for 10 hours
        else:
            return None, None, None

    return cached_token, cached_base_url, cached_app_key


def fetch_telemetry_data():
    global cached_telemetry, last_telemetry_fetch
    now = time.time()

    # Serve cached response if within TTL window
    if cached_telemetry and (now - last_telemetry_fetch < TELEMETRY_CACHE_TTL):
        return cached_telemetry

    token, base_url, app_key = get_cached_token()
    if not token:
        return cached_telemetry or {"error": "Authentication failed"}

    ts_ms = str(int(now * 1000))
    sign_str = f"{app_key}{ts_ms}{APP_SECRET}"
    signature = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "x-sigen-access-token": token,
        "x-sigen-app-key": app_key,
        "x-sigen-timestamp": ts_ms,
        "x-sigen-sign": signature
    }

    url = f"{base_url}/openapi/systems/{SYSTEM_ID}/energyFlow"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 0:
            data_raw = json.loads(res_json.get("data", "{}"))

            raw_ev = data_raw.get("evPower", 0.0)
            raw_ac = data_raw.get("acPower", 0.0)
            raw_load = data_raw.get("loadPower", 0.0)

            # EV power fallback if EV charger draw is routed via AC power
            ev_kw = raw_ev if raw_ev > 0.0 else raw_ac

            cached_telemetry = {
                "timestamp": res_json.get("timestamp"),
                "pv_power_kw": data_raw.get("pvPower", 0.0),
                "grid_power_kw": data_raw.get("gridPower", 0.0),
                "battery_power_kw": data_raw.get("batteryPower", 0.0),
                "load_power_kw": raw_load,
                "ac_power_kw": raw_ac,
                "battery_soc": data_raw.get("batterySoc", 0.0),
                "ev_power_kw": ev_kw,
                "heat_pump_power_kw": data_raw.get("heatPumpPower", 0.0)
            }
            last_telemetry_fetch = now
            return cached_telemetry
        else:
            return cached_telemetry or {"error": res_json.get("msg", "API Error")}
    except Exception as e:
        return cached_telemetry or {"error": str(e)}

def check_modbus_status():
    status = {
        "port_open": False,
        "read_ok": False,
        "write_ok": False,
        "message": "Unknown",
    }

    # 1. Test raw TCP Port 502 connectivity
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)
    result = sock.connect_ex((INVERTER_IP, 502))
    sock.close()

    if result != 0:
        status["message"] = "Port 502 Refused / Offline"
        return status

    status["port_open"] = True

    # 2. Test Modbus TCP Read and Write Access
    client = ModbusTcpClient(INVERTER_IP, port=502, timeout=3)
    if client.connect():
        # Attempt to read holding registers (Unit ID 1 or 247)
        res_read = client.read_holding_registers(address=0, count=1, slave=1)
        if not res_read.isError():
            status["read_ok"] = True

            # Attempt a safe test write (writing back existing value or checking response exception)
            # Note: Modbus Write Permission OFF returns Exception Code 01 or 02
            current_val = res_read.registers[0]
            res_write = client.write_register(
                address=0, value=current_val, slave=1
            )

            if not res_write.isError():
                status["write_ok"] = True
                status["message"] = "Modbus TCP Read/Write Active!"
            else:
                status["message"] = "Read OK | Write Permission Disabled"
        else:
            status["message"] = "Connected | Modbus Read Failed"
        client.close()
    else:
        status["message"] = "Modbus TCP Handshake Failed"

    return status

class DashboardRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/dashboard':
            payload = fetch_telemetry_data()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
	elif self.path == '/api/modbus/test':
            payload = check_modbus_status()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')

    def log_message(self, format, *args):
        # Suppress standard HTTP request logging
        return


def run_server(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardRequestHandler)
    print(f"--- Sigenergy LAN Dashboard API running on http://0.0.0.0:{port}/api/dashboard ---")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")


if __name__ == '__main__':
    run_server()
