import json
import time
import hashlib
import requests
from sigenergy_auth import get_token

token, base_url, app_key = get_token()
if not token:
    print("Authentication failed.")
    exit(1)

with open('credentials.json', 'r') as f:
    config = json.load(f)
app_secret = config.get('app_secret', '')

ts_ms = str(int(time.time() * 1000))
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

system_id = config.get("system_id", "")
url = f"{base_url}/openapi/systems/{system_id}/energyFlow"

print(f"Querying: {url}")
try:
    res = requests.get(url, headers=headers, timeout=10)
    print(f"GET Status: {res.status_code}")
    print(f"GET Response: {res.text}")
except Exception as e:
    print(f"Error: {e}")
