"""
Create Final Database Schema - 4 Tables

Based on user's comprehensive plan:
1. swf_financials - SFA internal use
2. market_daily_data - SFA internal use  
3. swf_financials_publish - Publishing dataset
4. market_daily_data_publish - Publishing dataset
"""
import sqlite3
import pandas as pd

DB_PATH = "data/db/financial_data.db"

def create_swf_financials():
    """Create swf_financials from existing swf table."""
    print("=" * 50)
    print("Creating swf_financials table...")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load existing swf data
    df = pd.read_sql("SELECT * FROM swf WHERE yr >= 2012", conn)
    print(f"Loaded {len(df)} rows from swf")
    
    # Create new dataframe with proper column names
    swf_fin = pd.DataFrame()
    
    # 1. Identifiers
    swf_fin['swf_id'] = range(1, len(df) + 1)
    swf_fin['entity_id'] = 'SYNTH_CO_01'
    swf_fin['data_source'] = 'SEC_SYNTHETIC'
    
    # 2. Time Structure (renamed for clarity)
    swf_fin['fiscal_year'] = df['yr'].values
    swf_fin['fiscal_quarter'] = df['qtr'].values
    swf_fin['month_in_quarter'] = df['mo'].values
    swf_fin['week_in_quarter'] = df['wk'].values
    swf_fin['period_id'] = df['yr'].values * 10 + df['qtr'].values
    
    # Calculate period_seq (sequential ordering)
    period_order = swf_fin.groupby(['fiscal_year', 'fiscal_quarter', 'month_in_quarter', 'week_in_quarter']).ngroup() + 1
    swf_fin['period_seq'] = period_order
    
    # 3. Core Financial Metrics
    swf_fin['item'] = df['item'].values
    swf_fin['value'] = df['val'].values
    
    # 4. Quality flags from original
    if 'drv' in df.columns:
        swf_fin['derived_flag'] = df['drv'].values
    if 'vf' in df.columns:
        swf_fin['validation_flag'] = df['vf'].values
    
    # 5. SFA Control Columns
    swf_fin['synthetic_flag'] = True
    swf_fin['agent_safe_to_use'] = True
    
    # Save to database
    conn.execute("DROP TABLE IF EXISTS swf_financials")
    swf_fin.to_sql('swf_financials', conn, index=False)
    
    print(f"Created swf_financials: {len(swf_fin)} rows, {len(swf_fin.columns)} columns")
    print(f"Columns: {list(swf_fin.columns)}")
    
    conn.commit()
    conn.close()
    return swf_fin


def create_market_daily_data():
    """Create market_daily_data from existing stock_prices table."""
    print("\n" + "=" * 50)
    print("Creating market_daily_data table...")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load existing stock_prices data
    df = pd.read_sql("SELECT * FROM stock_prices", conn)
    print(f"Loaded {len(df)} rows from stock_prices")
    
    # Create new dataframe with proper column names
    market = pd.DataFrame()
    
    # 1. Identifiers
    market['market_id'] = range(1, len(df) + 1)
    market['symbol'] = df['symbol'].values if 'symbol' in df.columns else 'SYNTH_STOCK'
    market['exchange_series'] = 'EQ'
    
    # 2. True Calendar Time
    market['trade_date'] = df['date'].values
    market['year'] = df['yr'].values
    market['month'] = df['mo'].values
    
    # Calculate fiscal_quarter from month
    market['fiscal_quarter'] = ((market['month'] - 1) // 3) + 1
    
    # 3. Price Metrics (rename to proper names)
    if 'open' in df.columns:
        market['open_price'] = df['open'].values
    if 'high' in df.columns:
        market['high_price'] = df['high'].values
    if 'low' in df.columns:
        market['low_price'] = df['low'].values
    if 'close' in df.columns:
        market['close_price'] = df['close'].values
    if 'last' in df.columns:
        market['last_price'] = df['last'].values
    if 'vwap' in df.columns:
        market['vwap'] = df['vwap'].values
    
    # 4. Market Activity Metrics
    if 'volume' in df.columns:
        market['trade_volume'] = df['volume'].values
    if 'turnover' in df.columns:
        market['turnover'] = df['turnover'].values
    if 'trades' in df.columns:
        market['number_of_trades'] = df['trades'].values
    if 'deliverable_volume' in df.columns:
        market['deliverable_volume'] = df['deliverable_volume'].values
    if 'pct_deliverable' in df.columns or '%deliverble' in df.columns:
        col_name = 'pct_deliverable' if 'pct_deliverable' in df.columns else '%deliverble'
        market['pct_deliverable'] = df[col_name].values
    
    # 5. Derived Market Metrics
    if 'daily_return' in df.columns:
        market['daily_return_pct'] = df['daily_return'].values
    elif 'open_price' in market.columns and 'close_price' in market.columns:
        market['daily_return_pct'] = ((market['close_price'] - market['open_price']) / market['open_price']) * 100
    
    # Save to database
    conn.execute("DROP TABLE IF EXISTS market_daily_data")
    market.to_sql('market_daily_data', conn, index=False)
    
    print(f"Created market_daily_data: {len(market)} rows, {len(market.columns)} columns")
    print(f"Columns: {list(market.columns)}")
    
    conn.commit()
    conn.close()
    return market


def create_publishing_tables():
    """Create clean publishing versions of both tables."""
    print("\n" + "=" * 50)
    print("Creating publishing tables...")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Publishing version of swf_financials (remove internal flags)
    conn.execute("DROP TABLE IF EXISTS swf_financials_publish")
    conn.execute("""
        CREATE TABLE swf_financials_publish AS
        SELECT 
            swf_id, entity_id,
            fiscal_year, fiscal_quarter, month_in_quarter, week_in_quarter,
            period_id, period_seq,
            item, value,
            derived_flag, validation_flag
        FROM swf_financials
    """)
    print("Created swf_financials_publish")
    
    # Publishing version of market_daily_data (clean columns)
    conn.execute("DROP TABLE IF EXISTS market_daily_data_publish")
    conn.execute("""
        CREATE TABLE market_daily_data_publish AS
        SELECT *
        FROM market_daily_data
    """)
    print("Created market_daily_data_publish")
    
    conn.commit()
    conn.close()


def verify_tables():
    """Verify all tables and show summary."""
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    tables = ['swf_financials', 'market_daily_data', 'swf_financials_publish', 'market_daily_data_publish']
    
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            print(f"\n{table}:")
            print(f"  Rows: {count}")
            print(f"  Columns: {cols}")
        except Exception as e:
            print(f"\n{table}: ERROR - {e}")
    
    # Show sample link query
    print("\n" + "=" * 50)
    print("SAMPLE LINK QUERY (fiscal_year + fiscal_quarter)")
    print("=" * 50)
    
    sample = conn.execute("""
        SELECT 
            s.fiscal_year, s.fiscal_quarter,
            COUNT(DISTINCT s.swf_id) as swf_records,
            COUNT(DISTINCT m.market_id) as market_records
        FROM swf_financials s
        LEFT JOIN market_daily_data m 
            ON s.fiscal_year = m.year 
            AND s.fiscal_quarter = m.fiscal_quarter
        GROUP BY s.fiscal_year, s.fiscal_quarter
        LIMIT 5
    """).fetchall()
    
    for row in sample:
        print(f"  Year {row[0]} Q{row[1]}: {row[2]} SWF records, {row[3]} market records")
    
    conn.close()


if __name__ == "__main__":
    create_swf_financials()
    create_market_daily_data()
    create_publishing_tables()
    verify_tables()
    print("\n✅ All 4 tables created successfully!")
