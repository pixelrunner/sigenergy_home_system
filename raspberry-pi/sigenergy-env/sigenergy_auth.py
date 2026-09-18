import json
import time
import hashlib
import requests

def get_token():
    with open('credentials.json', 'r') as f:
        config = json.load(f)

    base_url = config.get('base_url', 'https://api-eu.sigencloud.com').rstrip('/')
    app_key = config['app_key']
    app_secret = config['app_secret']
    username = config['username']
    password = config['password']

    timestamp = str(int(time.time() * 1000))
    sign_str = f"{app_key}{timestamp}{app_secret}"
    signature = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "x-sigen-app-key": app_key,
        "x-sigen-timestamp": timestamp,
        "x-sigen-sign": signature
    }

    url = f"{base_url}/openapi/auth/login/password"
    payload = {"username": username, "password": password}

    res = requests.post(url, headers=headers, json=payload, timeout=10)
    res.raise_for_status()
    data = res.json()

    if data.get("code") == 0:
        raw_data = data["data"]
        token_info = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        return token_info.get("accessToken"), base_url, app_key
    else:
        print(f"Auth failed: {data}")
        return None, base_url, app_key

if __name__ == "__main__":
    token, url, key = get_token()
    if token:
        print(f"Successfully obtained token!\nAccess Token: {token[:25]}...")
