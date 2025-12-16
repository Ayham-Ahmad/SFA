"""
Phase 1: Data Layer Foundation
================================
1.1 Import stock_prices from data/4.csv
1.2 Create financial_targets table with synthetic targets
1.3 Verify tables are created correctly
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = 'data/db/financial_data.db'
CSV_PATH = 'data/4.csv'

def import_stock_prices():
    """Import stock price data from 4.csv into stock_prices table."""
    print("=" * 60)
    print("PHASE 1.1: Importing Stock Prices")
    print("=" * 60)
    
    # Read CSV
    df = pd.read_csv(CSV_PATH)
    print(f"Read {len(df)} rows from {CSV_PATH}")
    print(f"Columns: {list(df.columns)}")
    
    # Rename columns for consistency (lowercase, clean names)
    column_mapping = {
        'Date': 'date',
        'Symbol': 'symbol',
        'Series': 'series',
        'Prev Close': 'prev_close',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Last': 'last',
        'Close': 'close',
        'VWAP': 'vwap',
        'Volume': 'volume',
        'Turnover': 'turnover',
        'Trades': 'trades',
        'Deliverable Volume': 'deliverable_volume',
        '%Deliverble': 'pct_deliverable'
    }
    df = df.rename(columns=column_mapping)
    
    # Convert date to proper format
    df['date'] = pd.to_datetime(df['date'])
    
    # Add derived columns
    df['yr'] = df['date'].dt.year
    df['mo'] = df['date'].dt.month
    df['day'] = df['date'].dt.day
    
    # Calculate daily return
    df['daily_return'] = ((df['close'] - df['prev_close']) / df['prev_close'] * 100).round(2)
    
    print(f"\nSample data:")
    print(df.head())
    print(f"\nDate range: {df['date'].min()} to {df['date'].max()}")
    print(f"Years: {df['yr'].min()} to {df['yr'].max()}")
    
    # Save to SQLite
    conn = sqlite3.connect(DB_PATH)
    
    # Drop existing table if exists
    conn.execute("DROP TABLE IF EXISTS stock_prices")
    
    # Save dataframe
    df.to_sql('stock_prices', conn, index=False, if_exists='replace')
    
    # Verify
    count = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]
    print(f"\n✅ stock_prices table created with {count} rows")
    
    # Show sample
    sample = pd.read_sql("SELECT date, symbol, open, high, low, close, volume, daily_return FROM stock_prices LIMIT 5", conn)
    print(f"\nSample from database:")
    print(sample)
    
    conn.close()
    return count

def create_financial_targets():
    """Create financial_targets table with synthetic budget/target values."""
    print("\n" + "=" * 60)
    print("PHASE 1.2: Creating Financial Targets")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get actual values from swf to base targets on
    actual_data = pd.read_sql("""
        SELECT yr, qtr, item, SUM(val) as actual_value
        FROM swf
        WHERE yr >= 2015
        GROUP BY yr, qtr, item
    """, conn)
    
    print(f"Found {len(actual_data)} actual data points")
    
    # Create targets as +10% of previous year (or +5% for costs)
    targets = []
    
    for item in actual_data['item'].unique():
        item_data = actual_data[actual_data['item'] == item].copy()
        
        for yr in range(2016, 2026):
            for qtr in [1, 2, 3, 4]:
                # Get previous year's value
                prev = item_data[(item_data['yr'] == yr - 1) & (item_data['qtr'] == qtr)]
                
                if len(prev) > 0:
                    prev_val = prev['actual_value'].values[0]
                    
                    # Revenue/Income targets: +10% growth
                    # Cost targets: +5% (lower is better for costs)
                    if 'Revenue' in item or 'Income' in item or 'Profit' in item:
                        target_val = prev_val * 1.10  # 10% growth target
                    else:
                        target_val = prev_val * 1.05  # 5% cost increase acceptable
                    
                    targets.append({
                        'yr': yr,
                        'qtr': qtr,
                        'metric': item,
                        'target_value': round(target_val, 2),
                        'source': 'Budget (+10% YoY)'
                    })
    
    targets_df = pd.DataFrame(targets)
    print(f"Generated {len(targets_df)} target values")
    
    # Add stock price targets (based on historical averages)
    stock_targets = pd.read_sql("""
        SELECT yr, AVG(close) as avg_close, MAX(close) as max_close
        FROM stock_prices
        GROUP BY yr
    """, conn)
    
    for _, row in stock_targets.iterrows():
        # Target: 15% above previous year's average
        for qtr in [1, 2, 3, 4]:
            targets.append({
                'yr': int(row['yr']) + 1,
                'qtr': qtr,
                'metric': 'Stock Close Price',
                'target_value': round(row['avg_close'] * 1.15, 2),
                'source': 'Target (+15% YoY)'
            })
    
    targets_df = pd.DataFrame(targets)
    
    # Save to database
    conn.execute("DROP TABLE IF EXISTS financial_targets")
    targets_df.to_sql('financial_targets', conn, index=False, if_exists='replace')
    
    # Verify
    count = conn.execute("SELECT COUNT(*) FROM financial_targets").fetchone()[0]
    print(f"\n✅ financial_targets table created with {count} rows")
    
    # Show sample
    sample = pd.read_sql("SELECT * FROM financial_targets WHERE yr = 2024 LIMIT 10", conn)
    print(f"\nSample targets for 2024:")
    print(sample)
    
    conn.close()
    return count

def verify_tables():
    """Verify all Phase 1 tables exist and have data."""
    print("\n" + "=" * 60)
    print("PHASE 1.3: Verification")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    tables = ['swf', 'stock_prices', 'financial_targets']
    
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = [c[1] for c in cols]
            print(f"✅ {table}: {count} rows, columns: {col_names[:5]}...")
        except Exception as e:
            print(f"❌ {table}: ERROR - {e}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("PHASE 1 COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    import_stock_prices()
    create_financial_targets()
    verify_tables()
