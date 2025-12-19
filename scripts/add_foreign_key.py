"""
Add Foreign Key Relationship between SWF and stock_prices

SWF (parent): 1 row = 1 week with P&L data
stock_prices (child): Multiple rows per week (daily data)

Steps:
1. Add swf_id primary key to swf table
2. Add swf_id foreign key to stock_prices
3. Match each stock_price to its corresponding swf week
"""

import sqlite3
from datetime import datetime

DB_PATH = "data/db/financial_data.db"

def add_foreign_key():
    conn = sqlite3.connect(DB_PATH)
    
    # Step 0: Save and drop dependent views
    print("Step 0: Saving dependent views...")
    views_to_recreate = []
    for view_name in ['profitability_metrics', 'variance_analysis', 'growth_metrics', 'stock_metrics']:
        try:
            sql = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='view' AND name='{view_name}'").fetchone()
            if sql:
                views_to_recreate.append((view_name, sql[0]))
                conn.execute(f'DROP VIEW IF EXISTS {view_name}')
                print(f"  Dropped view: {view_name}")
        except:
            pass
    
    # Step 1: Add swf_id to swf table
    print("\nStep 1: Adding swf_id to swf table...")
    
    # Check if swf_id already exists
    cols = [c[1] for c in conn.execute('PRAGMA table_info(swf)').fetchall()]
    if 'swf_id' not in cols:
        # Create new table with swf_id
        conn.execute('''
            CREATE TABLE swf_new AS 
            SELECT ROW_NUMBER() OVER (ORDER BY yr, qtr, mo, wk) as swf_id, *
            FROM swf
        ''')
        conn.execute('DROP TABLE swf')
        conn.execute('ALTER TABLE swf_new RENAME TO swf')
        print("  Added swf_id column to swf")
    else:
        print("  swf_id already exists")
    
    # Step 1.5: Recreate views
    print("\nStep 1.5: Recreating dependent views...")
    for view_name, sql in views_to_recreate:
        try:
            conn.execute(sql)
            print(f"  Recreated view: {view_name}")
        except Exception as e:
            print(f"  Failed to recreate {view_name}: {e}")
    
    # Step 2: Add swf_id to stock_prices
    print("\nStep 2: Adding swf_id to stock_prices...")
    
    cols = [c[1] for c in conn.execute('PRAGMA table_info(stock_prices)').fetchall()]
    if 'swf_id' not in cols:
        conn.execute('ALTER TABLE stock_prices ADD COLUMN swf_id INTEGER')
        print("  Added swf_id column to stock_prices")
    else:
        print("  swf_id already exists")
    
    # Step 3: Match stock_prices to swf weeks
    print("\nStep 3: Matching stock_prices to swf weeks...")
    
    # Get all swf rows
    swf_rows = conn.execute('SELECT swf_id, yr, mo, wk FROM swf').fetchall()
    print(f"  Found {len(swf_rows)} swf weeks")
    
    # Create lookup: (yr, mo, wk) -> swf_id
    swf_lookup = {(row[1], row[2], row[3]): row[0] for row in swf_rows}
    
    # Get stock_prices
    stock_rows = conn.execute('SELECT rowid, date, yr, mo FROM stock_prices').fetchall()
    print(f"  Processing {len(stock_rows)} stock_prices...")
    
    # Match and update
    matched = 0
    unmatched = 0
    
    for rowid, date_str, yr, mo in stock_rows:
        # Parse date and get week of month
        try:
            if isinstance(date_str, str):
                dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            else:
                dt = date_str
            
            # Week of month (1-4 based on day)
            day = dt.day
            wk = (day - 1) // 7 + 1
            if wk > 4:
                wk = 4
            
            # Look up swf_id
            key = (yr, mo, wk)
            if key in swf_lookup:
                swf_id = swf_lookup[key]
                conn.execute('UPDATE stock_prices SET swf_id = ? WHERE rowid = ?', (swf_id, rowid))
                matched += 1
            else:
                unmatched += 1
        except Exception as e:
            unmatched += 1
    
    conn.commit()
    print(f"  Matched: {matched}, Unmatched: {unmatched}")
    
    # Verify
    print("\nVerification:")
    linked = conn.execute('SELECT COUNT(*) FROM stock_prices WHERE swf_id IS NOT NULL').fetchone()[0]
    print(f"  stock_prices with swf_id: {linked}")
    
    # Sample
    print("\nSample joined data:")
    sample = conn.execute('''
        SELECT sp.date, sp.close, s.yr, s.mo, s.wk, s.Revenue, s.Net_Income
        FROM stock_prices sp
        JOIN swf s ON sp.swf_id = s.swf_id
        LIMIT 5
    ''').fetchall()
    for row in sample:
        print(f"  {row}")
    
    conn.close()
    print("\nDone! Foreign key relationship created.")

if __name__ == "__main__":
    add_foreign_key()
