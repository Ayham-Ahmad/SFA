import sqlite3
import pandas as pd

db_path = "data/db/financial_data.db"

try:
    conn = sqlite3.connect(db_path)
    
    # Check for specific famous companies to ensure good queries
    target_companies = ['APPLE', 'MICROSOFT', 'TESLA', 'GOOGLE', 'AMAZON', 'NVIDIA', 'META', 'NETFLIX']
    print("\n--- Checking for Tech Giants ---")
    for comp in target_companies:
        res = pd.read_sql(f"SELECT name, adsh FROM submissions WHERE name LIKE '%{comp}%' LIMIT 1;", conn)
        if not res.empty:
            print(f"Found: {res.iloc[0]['name']}")
            # Check what data we have for them
            adsh = res.iloc[0]['adsh']
            data_count = pd.read_sql(f"SELECT COUNT(*) FROM numbers WHERE adsh='{adsh}'", conn).iloc[0,0]
            print(f"  -> Data Points: {data_count}")
        else:
            print(f"Not Found: {comp}")

    # Check for specific tags
    print("\n--- Checking for Key Financial Metrics ---")
    metrics = ['Revenues', 'NetIncomeLoss', 'Assets', 'Liabilities', 'StockholdersEquity', 'GrossProfit']
    for m in metrics:
        count = pd.read_sql(f"SELECT COUNT(*) FROM numbers WHERE tag='{m}'", conn).iloc[0,0]
        print(f"Metric '{m}': {count} entries")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
