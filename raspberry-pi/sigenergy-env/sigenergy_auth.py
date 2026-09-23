import json
import time
import requests

CONFIG_PATH = '/home/webs_admin/sigenergy-env/credentials.json'
TOKEN_CACHE_PATH = '/tmp/sigen_token.json'

def get_token():
    # 1. Read existing cached token safely
    try:
        with open(TOKEN_CACHE_PATH, 'r') as f:
            cache = json.load(f)
            if isinstance(cache, dict) and time.time() < cache.get("expiry", 0):
                return cache.get("token"), cache.get("base_url"), cache.get("app_key")
    except Exception:
        pass

    # 2. Load configuration file safely
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            if not isinstance(config, dict):
                print("Auth Config Error: credentials.json is not a JSON object.")
                return None, None, None
    except Exception as e:
        print(f"Auth Config Error: {e}")
        return None, None, None

    base_url = config.get("base_url", "https://api-eu.sigencloud.com").rstrip('/')
    app_key = config.get("app_key", "")
    username = config.get("username", "")
    password = config.get("password", "")

    url = f"{base_url}/openapi/auth/login/password"
    headers = {"Content-Type": "application/json"}
    payload = {
        "username": username,
        "password": password
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res_json = res.json()
        if isinstance(res_json, dict) and res_json.get("code") in (0, 200):
            data = res_json.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = {}
            
            token = data.get("accessToken") if isinstance(data, dict) else None
            expires_in = data.get("expiresIn", 43200) if isinstance(data, dict) else 43200
            
            if token:
                token_cache = {
                    "token": token,
                    "base_url": base_url,
                    "app_key": app_key,
                    "expiry": time.time() + expires_in - 300
                }
                with open(TOKEN_CACHE_PATH, 'w') as f:
                    json.dump(token_cache, f)
                    
                return token, base_url, app_key
            else:
                print("Auth Error: accessToken missing in response payload.")
                return None, None, None
        else:
            code = res_json.get('code') if isinstance(res_json, dict) else 'Unknown'
            msg = res_json.get('msg') if isinstance(res_json, dict) else res.text
            print(f"Auth Cloud Error [{code}]: {msg}")
            return None, None, None
    except Exception as e:
        print(f"Auth Request Exception: {e}")
        return None, None, None

if __name__ == '__main__':
    token, base, key = get_token()
    if token:
        print(f"Successfully obtained token: {token[:15]}...")
    else:
        print("Failed to obtain token.")
