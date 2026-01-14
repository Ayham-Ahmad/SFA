"""
Live Data Simulator
====================
Run this script locally to simulate live financial data being pushed to Railway.
It calls the /api/test/add-live-data endpoint on the deployed SFA app.

Usage:
    python simulate_live_data.py

Requirements:
    pip install requests

Configuration:
    Set RAILWAY_URL to your Railway app URL
    Set USERNAME and PASSWORD to a valid SFA user account
"""
import time
import requests
import sys

# ========== CONFIGURATION ==========
RAILWAY_URL = "https://sfa-production-e08e.up.railway.app"  # Change to your Railway URL
USERNAME = "5"  # Your SFA username
PASSWORD = "5"  # Your SFA password
INTERVAL_SECONDS = 5  # Time between data pushes
# ===================================


def login(base_url, username, password):
    """Login and get JWT token."""
    response = requests.post(
        f"{base_url}/token",
        data={"username": username, "password": password}
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"✅ Logged in as {username}")
        return token
    else:
        print(f"❌ Login failed: {response.text}")
        return None


def add_live_data(base_url, token):
    """Call the add-live-data endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{base_url}/api/test/add-live-data",
        headers=headers
    )
    if response.status_code == 200:
        data = response.json().get("data", {})
        print(f"📊 Added: Rev=${data.get('revenue', 0):,.2f} | Cost=${data.get('cost', 0):,.2f} | Users={data.get('active_users', 0)}")
        return True
    else:
        print(f"❌ Error: {response.text}")
        return False


def clear_data(base_url, token):
    """Clear all live_metrics data."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(
        f"{base_url}/api/database/query",
        headers=headers,
        json={"query": "DELETE FROM live_metrics"}
    )
    if response.status_code == 200:
        print("🗑️ Cleared all live_metrics data!")
        return True
    else:
        print(f"❌ Error clearing: {response.text}")
        return False



def main():
    
    
    print("=" * 50)
    print("🚀 SFA Live Data Simulator")
    print("=" * 50)
    print(f"Target: {RAILWAY_URL}")
    print(f"Interval: {INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop\n")
    
    # Login first
    token = login(RAILWAY_URL, USERNAME, PASSWORD)
    if not token:
        return
    
    # Check for --clear flag
    if "--clear" in sys.argv:
        clear_data(RAILWAY_URL, token)
        print("Done! Exiting...")
        return
    
    # Push data continuously
    count = 0
    try:
        while True:
            count += 1
            print(f"\n[{count}] Pushing data...")
            add_live_data(RAILWAY_URL, token)
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print(f"\n\n✅ Stopped. Added {count} data points.")


if __name__ == "__main__":
    main()

