"""
Complete Database Restructure Script
1. Pivot SWF to wide format with swf_id
2. Add swf_id foreign key to stock_prices
3. Link the tables
"""
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "data/db/financial_data.db"

def restructure_database():
    conn = sqlite3.connect(DB_PATH)
    
    # ============ STEP 1: Pivot SWF to wide format ============
    print("=== Step 1: Pivoting SWF to wide format ===")
    
    # Load from backup (original long format)
    df = pd.read_sql("SELECT * FROM swf_backup WHERE yr >= 2012", conn)
    print(f"Loaded {len(df)} rows from swf_backup")
    
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
    
    # Add swf_id
    df_wide.insert(0, 'swf_id', range(1, len(df_wide) + 1))
    
    print(f"Pivoted to {len(df_wide)} rows, {len(df_wide.columns)} columns")
    print(f"Columns: {list(df_wide.columns)}")
    
    # Drop old swf and create new one
    conn.execute("DROP TABLE IF EXISTS swf")
    df_wide.to_sql('swf', conn, index=False)
    print("SWF table replaced with wide format")
    
    # ============ STEP 2: Add swf_id to stock_prices ============
    print("\n=== Step 2: Adding swf_id to stock_prices ===")
    
    cols = [c[1] for c in conn.execute('PRAGMA table_info(stock_prices)').fetchall()]
    if 'swf_id' not in cols:
        conn.execute('ALTER TABLE stock_prices ADD COLUMN swf_id INTEGER')
        print("Added swf_id column")
    else:
        print("swf_id already exists")
    
    # ============ STEP 3: Link tables ============
    print("\n=== Step 3: Linking stock_prices to swf ===")
    
    # Create lookup
    swf_lookup = {}
    for row in conn.execute('SELECT swf_id, yr, mo, wk FROM swf').fetchall():
        swf_lookup[(row[1], row[2], row[3])] = row[0]
    print(f"Created lookup with {len(swf_lookup)} entries")
    
    # Update stock_prices
    stock_rows = conn.execute('SELECT rowid, date, yr, mo FROM stock_prices').fetchall()
    matched = 0
    
    for rowid, date_str, yr, mo in stock_rows:
        try:
            dt = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
            wk = min((dt.day - 1) // 7 + 1, 4)
            key = (yr, mo, wk)
            if key in swf_lookup:
                conn.execute('UPDATE stock_prices SET swf_id = ? WHERE rowid = ?', 
                           (swf_lookup[key], rowid))
                matched += 1
        except:
            pass
    
    conn.commit()
    print(f"Matched {matched} of {len(stock_rows)} stock_prices rows")
    
    # ============ STEP 4: Verify ============
    print("\n=== Step 4: Verification ===")
    print(f"SWF rows: {conn.execute('SELECT COUNT(*) FROM swf').fetchone()[0]}")
    print(f"stock_prices rows: {conn.execute('SELECT COUNT(*) FROM stock_prices').fetchone()[0]}")
    print(f"stock_prices with swf_id: {conn.execute('SELECT COUNT(*) FROM stock_prices WHERE swf_id IS NOT NULL').fetchone()[0]}")
    
    # Sample join
    print("\nSample joined data:")
    sample = conn.execute('''
        SELECT sp.date, sp.close, s.swf_id, s.yr, s.mo, s.Revenue, s.Net_Income
        FROM stock_prices sp
        JOIN swf s ON sp.swf_id = s.swf_id
        LIMIT 3
    ''').fetchall()
    for row in sample:
        print(f"  {row}")
    
    conn.close()
    print("\n=== DONE! Database restructured successfully ===")

if __name__ == "__main__":
    restructure_database()
