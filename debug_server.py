
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def debug():
    # 1. Login
    try:
        resp = requests.post(f"{BASE_URL}/token", data={"username": "1", "password": "1"})
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        
        token = resp.json()["access_token"]
        print("Login successful.")
        
        # 2. Check Live Data
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/manager/live-data", headers=headers)
        
        print(f"Live Data Status: {resp.status_code}")
        print(f"Live Data Response: {resp.text[:500]}...") # Print first 500 chars
        
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    debug()
