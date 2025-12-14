
import sqlite3
import pandas as pd
import os

# Path to the database
DB_PATH = os.path.join(os.getcwd(), "data", "db", "financial_data.db")

def verify_ground_truth():
    print(f"Connecting to database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERROR: Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    
    # List of checks corresponding to the ground truth items
    checks = [
        {
            "metric": "Apple Revenue",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'APPLE INC' 
              AND n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Microsoft Revenue",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'MICROSOFT CORP' 
              AND n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Apple Net Income",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'APPLE INC' 
              AND n.tag = 'NetIncomeLoss'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Microsoft Assets",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'MICROSOFT CORP' 
              AND n.tag = 'Assets'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Tesla Revenue",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name LIKE 'TESLA%' 
              AND n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Apple Gross Profit",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'APPLE INC' 
              AND n.tag = 'GrossProfit'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Microsoft Operating Income",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'MICROSOFT CORP' 
              AND n.tag = 'OperatingIncomeLoss'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Apple Cash",
            "query": """
            SELECT s.name, n.value, n.uom, n.ddate, n.tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE s.name = 'APPLE INC' 
              AND n.tag = 'CashAndCashEquivalentsAtCarryingValue'
              AND n.uom = 'USD'
            ORDER BY n.ddate DESC, n.value DESC LIMIT 1
            """
        },
        {
            "metric": "Top 5 Companies (Revenue)",
            "query": """
            SELECT s.name, MAX(n.value) as value, n.uom, MAX(n.ddate) as ddate, 'MAX(Revenue)' as tag
            FROM numbers n JOIN submissions s ON n.adsh = s.adsh 
            WHERE (n.tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' OR n.tag = 'Revenues')
              AND n.uom = 'USD'
            GROUP BY s.name
            ORDER BY value DESC
            LIMIT 5
            """
        }
    ]
    
    print("\n" + "="*80)
    print(f"{'METRIC':<30} | {'VALUE':<20} | {'DATE':<10} | {'QUERY INFO'}")
    print("="*80)
    
    for check in checks:
        try:
            df = pd.read_sql_query(check['query'], conn)
            if not df.empty:
                # Handle single row vs multi-row (Top 5)
                if len(df) > 1:
                    print(f"{check['metric']:<30} | {'(See List Below)':<20} | {'VARIES':<10} | Tag: Multiple")
                    for _, row in df.iterrows():
                        val = row['value']
                        formatted_val = f"${val/1e9:.2f}B" if val > 1e9 else f"${val:,.0f}"
                        # Truncate name if too long
                        name = (row['name'][:18] + '..') if len(row['name']) > 20 else row['name']
                        print(f"   -> {name:<20} : {formatted_val}")
                    print("-" * 80)
                else:
                    val = df.iloc[0]['value']
                    date = df.iloc[0]['ddate']
                    uom = df.iloc[0]['uom']
                    
                    # Format
                    formatted_val = f"${val/1e9:.2f}B" if val > 1e9 else f"${val:,.0f}" if uom == 'USD' else str(val)
                    
                    print(f"{check['metric']:<30} | {formatted_val:<20} | {date:<10} | Tag: {df.iloc[0]['tag']}")
                    print("-" * 80)
        except Exception as e:
            print(f"Error checking {check['metric']}: {e}")

    conn.close()

if __name__ == "__main__":
    verify_ground_truth()
