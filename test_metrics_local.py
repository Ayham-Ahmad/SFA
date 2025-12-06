import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.analytics.metrics import get_key_metrics, get_revenue_trend, get_income_trend

print("Testing get_key_metrics...")
try:
    m = get_key_metrics()
    print("Metrics:", m)
except Exception as e:
    print("Metrics Failed:", e)
    import traceback
    traceback.print_exc()

print("\nTesting get_revenue_trend...")
try:
    t = get_revenue_trend()
    print("Revenue Trend Keys:", t.keys())
    print("Count:", len(t.get('values', [])))
except Exception as e:
    print("Revenue Trend Failed:", e)
    import traceback
    traceback.print_exc()
    
print("\nTesting get_income_trend...")
try:
    i = get_income_trend()
    print("Income Trend Keys:", i.keys())
    print("Count:", len(i.get('values', [])))
except Exception as e:
    print("Income Trend Failed:", e)
    import traceback
    traceback.print_exc()
