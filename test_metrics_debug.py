import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_metrics():
    print(f"Testing metrics endpoint at {BASE_URL}...")
    try:
        # Register if needed
        requests.post(f"{BASE_URL}/api/users", json={"username": "manager", "password": "password123", "role": "manager"})
        
        # Login
        resp = requests.post(f"{BASE_URL}/token", data={"username": "manager", "password": "password123"})
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            return
        
        token = resp.json()["access_token"]
        print("Login OK")
        
        # Get Metrics
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/dashboard/metrics", headers=headers)
        
        print(f"Metrics Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.text}")
        else:
            data = resp.json()
            print("Trend keys:", data.get("trend", {}).keys())
            print("Income trend keys:", data.get("income_trend", {}).keys())
            
            trend_vals = data.get("trend", {}).get("values", [])
            print(f"Trend data points: {len(trend_vals)}")
            if len(trend_vals) > 0:
                print(f"First trend val: {trend_vals[0]}")
                
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_metrics()
