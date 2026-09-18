import json
import time
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from sigenergy_auth import get_token

SYSTEM_ID = config.get("system_id", "")

# --- In-Memory Caching ---
cached_token = None
cached_base_url = None
cached_app_key = None
token_expiry = 0

cached_telemetry = None
last_telemetry_fetch = 0
TELEMETRY_CACHE_TTL = 300  # Minimum 60 seconds between Sigenergy Cloud requests

def get_cached_token():
    global cached_token, cached_base_url, cached_app_key, token_expiry
    now = time.time()

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

    # Serve cached response if pulled within the TTL window
    if cached_telemetry and (now - last_telemetry_fetch < TELEMETRY_CACHE_TTL):
        return cached_telemetry

    token, base_url, app_key = get_cached_token()
    if not token:
        return cached_telemetry or {"error": "Authentication failed"}

    with open('credentials.json', 'r') as f:
        config = json.load(f)
    app_secret = config.get('app_secret', '')

    ts_ms = str(int(now * 1000))
    sign_str = f"{app_key}{ts_ms}{app_secret}"
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

    # Always update fetch timestamp to prevent rapid retry loops on errors
    last_telemetry_fetch = now

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res_json = res.json()

        if res_json.get("code") == 0:
            data_raw = json.loads(res_json.get("data", "{}"))
            cached_telemetry = {
                "timestamp": res_json.get("timestamp"),
                "pv_power_kw": data_raw.get("pvPower", 0.0),
                "grid_power_kw": data_raw.get("gridPower", 0.0),
                "battery_power_kw": data_raw.get("batteryPower", 0.0),
                "load_power_kw": data_raw.get("loadPower", 0.0),
                "battery_soc": data_raw.get("batterySoc", 0.0),
                "ev_power_kw": data_raw.get("acPower", 0.0),
                "heat_pump_power_kw": data_raw.get("heatPumpPower", 0.0)
            }
            return cached_telemetry
        else:
            print(f"Sigenergy API Response: {res_json}")
            # Fall back to previous valid payload if available during rate limits
            return cached_telemetry or {"error": res_json.get("msg", "API Error")}
    except Exception as e:
        return cached_telemetry or {"error": str(e)}

class DashboardRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/dashboard':
            payload = fetch_telemetry_data()
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
