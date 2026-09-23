import json
import time
import hashlib
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from sigenergy_auth import get_token
from pymodbus.client import ModbusTcpClient

CONFIG_PATH = '/home/webs_admin/sigenergy-env/credentials.json'

# Token & Telemetry Cache Containers
cached_token_data = {
    "token": None,
    "base_url": None,
    "app_key": None,
    "expiry": 0
}

telemetry_cache = {
    "data": None,
    "last_fetch": 0
}

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_cached_token():
    global cached_token_data
    now = time.time()
    
    if not cached_token_data["token"] or now >= cached_token_data["expiry"]:
        token, base_url, app_key = get_token()
        if token:
            cached_token_data["token"] = token
            cached_token_data["base_url"] = base_url
            cached_token_data["app_key"] = app_key
            cached_token_data["expiry"] = now + (10 * 3600)  # Re-use token for 10 hours
        else:
            return None, None, None
            
    return cached_token_data["token"], cached_token_data["base_url"], cached_token_data["app_key"]

def test_modbus_connection():
    config = load_config()
    is_debug = config.get("debug_modbus", True)
    
    target_ip = config.get("debug_inverter_ip", "127.0.0.1") if is_debug else config.get("inverter_ip", "172.18.4.20")
    target_port = config.get("debug_inverter_port", 5020) if is_debug else config.get("inverter_port", 502)
    
    now = datetime.now()
    time_payload = {
        "timestamp": int(time.time()),
        "time_str": now.strftime("%H:%M:%S"),
        "date_str": now.strftime("%a %d %b %Y")
    }

    client = ModbusTcpClient(target_ip, port=target_port)
    if not client.connect():
        return {
            "port_open": False,
            "read_ok": False,
            "write_ok": False,
            "message": f"Port {target_port} Refused / Offline ({target_ip})",
            "debug_mode": is_debug,
            "target_ip": target_ip,
            **time_payload
        }
    
    try:
        read_res = client.read_holding_registers(address=1, count=1)
        read_ok = not read_res.isError()
        
        write_res = client.write_register(address=1, value=100)
        write_ok = not write_res.isError()
        
        client.close()
        return {
            "port_open": True,
            "read_ok": read_ok,
            "write_ok": write_ok,
            "message": "Modbus TCP Read/Write Active (DEBUG)" if is_debug else "Live Inverter Modbus Active",
            "debug_mode": is_debug,
            "target_ip": target_ip,
            **time_payload
        }
    except Exception as e:
        client.close()
        return {
            "port_open": True,
            "read_ok": False,
            "write_ok": False,
            "message": f"Modbus Exception: {str(e)}",
            "debug_mode": is_debug,
            "target_ip": target_ip,
            **time_payload
        }

def fetch_telemetry_data():
    global telemetry_cache
    config = load_config()
    is_debug = config.get("debug_modbus", True)

    now = datetime.now()
    now_ts = time.time()
    
    base_payload = {
        "timestamp": int(now_ts),
        "time_str": now.strftime("%H:%M"),
        "date_str": now.strftime("%a %d %b %Y")
    }

    # Return local mock data ONLY when Debug Mode is explicitly set to true
    if is_debug:
        return {
            **base_payload,
            "pv_power_kw": 2.50,
            "grid_power_kw": 0.00,
            "battery_power_kw": 1.20,
            "load_power_kw": 1.30,
            "battery_soc": 75.0,
            "ev_power_kw": 0.00,
            "heat_pump_power_kw": 0.00
        }

    # Live Mode: Serve cached response if pulled within 300 seconds (5 mins)
    if telemetry_cache["data"] and (now_ts - telemetry_cache["last_fetch"] < 300):
        return {
            **telemetry_cache["data"],
            **base_payload
        }

    system_id = config.get("system_id", "WCYBD1788875121")
    app_secret = config.get("app_secret", "")
    
    token, base_url, app_key = get_cached_token()
    if not token:
        # Fallback to last valid telemetry reading if token refresh fails during Live Mode
        if telemetry_cache["data"]:
            return {**telemetry_cache["data"], **base_payload, "is_stale": True}
        return {"error": "Authentication failed", **base_payload}

    ts_ms = str(int(now_ts * 1000))
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

    url = f"{base_url}/openapi/systems/{system_id}/energyFlow"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 0:
            data_raw = json.loads(res_json.get("data", "{}"))
            fetched_data = {
                "pv_power_kw": data_raw.get("pvPower", 0.0),
                "grid_power_kw": data_raw.get("gridPower", 0.0),
                "battery_power_kw": data_raw.get("batteryPower", 0.0),
                "load_power_kw": data_raw.get("loadPower", 0.0),
                "battery_soc": data_raw.get("batterySoc", 0.0),
                "ev_power_kw": data_raw.get("acPower", 0.0),
                "heat_pump_power_kw": data_raw.get("heatPumpPower", 0.0)
            }
            telemetry_cache["data"] = fetched_data
            telemetry_cache["last_fetch"] = now_ts
            return {**fetched_data, **base_payload}
        else:
            if telemetry_cache["data"]:
                return {**telemetry_cache["data"], **base_payload, "is_stale": True}
            return {"error": res_json.get("msg", "API Error"), **base_payload}
    except Exception as e:
        if telemetry_cache["data"]:
            return {**telemetry_cache["data"], **base_payload, "is_stale": True}
        return {"error": str(e), **base_payload}

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
            payload = test_modbus_connection()
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
    print(f"--- Sigenergy Local API Server running on port {port} ---")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")

if __name__ == '__main__':
    run_server()
