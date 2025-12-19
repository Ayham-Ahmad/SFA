"""
Create Linked Tables (as NEW tables - originals preserved)

Creates:
- swf_wide: Pivoted SWF table with swf_id
- stock_prices_linked: stock_prices with swf_id foreign key
"""
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "data/db/financial_data.db"

def create_linked_tables():
    conn = sqlite3.connect(DB_PATH)
    
    # ============ STEP 1: Create swf_wide (pivoted) ============
    print("=== Step 1: Creating swf_wide table ===")
    
    # Load from swf
    df = pd.read_sql("SELECT * FROM swf WHERE yr >= 2012", conn)
    print(f"Loaded {len(df)} rows from swf")
    
    # Pivot to wide format
    df_wide = df.pivot_table(
        index=['yr', 'qtr', 'mo', 'wk'],
        columns='item',
        values='val',
        aggfunc='sum'
    ).reset_index()
    
    # Clean column names
    df_wide.columns = [str(c).replace(' ', '_').replace('/', '_') for c in df_wide.columns]
    
    # Fill NaN with 0
    df_wide = df_wide.fillna(0)
    
    # Add swf_id as first column
    df_wide.insert(0, 'swf_id', range(1, len(df_wide) + 1))
    
    print(f"Pivoted to {len(df_wide)} rows, {len(df_wide.columns)} columns")
    print(f"Columns: {list(df_wide.columns)}")
    
    # Create new table (drop if exists)
    conn.execute("DROP TABLE IF EXISTS swf_wide")
    df_wide.to_sql('swf_wide', conn, index=False)
    print("Created swf_wide table")
    
    # ============ STEP 2: Create stock_prices_linked ============
    print("\n=== Step 2: Creating stock_prices_linked table ===")
    
    # Copy stock_prices with swf_id column
    conn.execute("DROP TABLE IF EXISTS stock_prices_linked")
    conn.execute('''
        CREATE TABLE stock_prices_linked AS 
        SELECT *, NULL as swf_id FROM stock_prices
    ''')
    print("Created stock_prices_linked with swf_id column")
    
    # ============ STEP 3: Link tables ============
    print("\n=== Step 3: Linking stock_prices to swf_wide ===")
    
    # Create lookup from swf_wide
    swf_lookup = {}
    for row in conn.execute('SELECT swf_id, yr, mo, wk FROM swf_wide').fetchall():
        swf_lookup[(row[1], row[2], row[3])] = row[0]
    print(f"Created lookup with {len(swf_lookup)} entries")
    
    # Update stock_prices_linked
    stock_rows = conn.execute('SELECT rowid, date, yr, mo FROM stock_prices_linked').fetchall()
    matched = 0
    
    for rowid, date_str, yr, mo in stock_rows:
        try:
            dt = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
            wk = min((dt.day - 1) // 7 + 1, 4)
            key = (yr, mo, wk)
            if key in swf_lookup:
                conn.execute('UPDATE stock_prices_linked SET swf_id = ? WHERE rowid = ?', 
                           (swf_lookup[key], rowid))
                matched += 1
        except:
            pass
    
    conn.commit()
    print(f"Matched {matched} of {len(stock_rows)} rows")
    
    # ============ STEP 4: Verify ============
    print("\n=== Step 4: Verification ===")
    print(f"swf_wide rows: {conn.execute('SELECT COUNT(*) FROM swf_wide').fetchone()[0]}")
    print(f"stock_prices_linked rows: {conn.execute('SELECT COUNT(*) FROM stock_prices_linked').fetchone()[0]}")
    print(f"Linked rows: {conn.execute('SELECT COUNT(*) FROM stock_prices_linked WHERE swf_id IS NOT NULL').fetchone()[0]}")
    
    # Sample join
    print("\nSample joined data:")
    sample = conn.execute('''
        SELECT sp.date, sp.close, s.swf_id, s.yr, s.mo, s.Revenue, s.Net_Income
        FROM stock_prices_linked sp
        JOIN swf_wide s ON sp.swf_id = s.swf_id
        LIMIT 5
    ''').fetchall()
    for row in sample:
        print(f"  {row}")
    
    # List all tables
    print("\nAll tables in database:")
    for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        print(f"  - {t[0]}")
    
    conn.close()
    print("\n=== DONE! New linked tables created ===")
    print("Original tables (swf, stock_prices) are preserved.")

if __name__ == "__main__":
    create_linked_tables()
