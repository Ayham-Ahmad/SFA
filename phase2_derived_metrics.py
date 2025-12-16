"""
Phase 2: Derived Metrics Engine
================================
2.1 Create profitability_metrics view
2.2 Create stock_metrics view  
2.3 Add variance calculations
2.4 Verify all metrics work
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = 'data/db/financial_data.db'

def create_profitability_metrics_view():
    """Create view for profitability ratios by year/quarter."""
    print("=" * 60)
    print("PHASE 2.1: Creating Profitability Metrics View")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Drop existing view if exists
    conn.execute("DROP VIEW IF EXISTS profitability_metrics")
    
    # Create view with profitability ratios
    view_sql = """
    CREATE VIEW profitability_metrics AS
    SELECT 
        yr,
        qtr,
        SUM(CASE WHEN item = 'Revenue' THEN val ELSE 0 END) as revenue,
        SUM(CASE WHEN item = 'Cost of Revenue' THEN val ELSE 0 END) as cost_of_revenue,
        SUM(CASE WHEN item = 'Gross Profit' THEN val ELSE 0 END) as gross_profit,
        SUM(CASE WHEN item = 'Operating Expenses' THEN val ELSE 0 END) as operating_expenses,
        SUM(CASE WHEN item = 'Operating Income' THEN val ELSE 0 END) as operating_income,
        SUM(CASE WHEN item = 'Net Income' THEN val ELSE 0 END) as net_income,
        
        -- Profitability Ratios
        ROUND(SUM(CASE WHEN item = 'Gross Profit' THEN val ELSE 0 END) / 
              NULLIF(SUM(CASE WHEN item = 'Revenue' THEN val ELSE 0 END), 0) * 100, 2) as gross_margin_pct,
        
        ROUND(SUM(CASE WHEN item = 'Operating Income' THEN val ELSE 0 END) / 
              NULLIF(SUM(CASE WHEN item = 'Revenue' THEN val ELSE 0 END), 0) * 100, 2) as operating_margin_pct,
        
        ROUND(SUM(CASE WHEN item = 'Net Income' THEN val ELSE 0 END) / 
              NULLIF(SUM(CASE WHEN item = 'Revenue' THEN val ELSE 0 END), 0) * 100, 2) as net_margin_pct
    FROM swf
    GROUP BY yr, qtr
    ORDER BY yr, qtr
    """
    
    conn.execute(view_sql)
    conn.commit()
    
    # Verify
    sample = pd.read_sql("""
        SELECT yr, qtr, 
               printf('$%.2fB', revenue/1e9) as revenue,
               printf('%.1f%%', gross_margin_pct) as gross_margin,
               printf('%.1f%%', operating_margin_pct) as op_margin,
               printf('%.1f%%', net_margin_pct) as net_margin
        FROM profitability_metrics
        WHERE yr >= 2020
        ORDER BY yr, qtr
        LIMIT 12
    """, conn)
    
    print("✅ profitability_metrics view created")
    print(f"\nSample (2020+):")
    print(sample.to_string(index=False))
    
    conn.close()

def create_stock_metrics_view():
    """Create view for stock price metrics."""
    print("\n" + "=" * 60)
    print("PHASE 2.2: Creating Stock Metrics View")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Drop existing view if exists
    conn.execute("DROP VIEW IF EXISTS stock_metrics")
    
    # Create view with stock metrics
    # Note: SQLite doesn't have window functions for moving averages, so we'll use a subquery
    view_sql = """
    CREATE VIEW stock_metrics AS
    SELECT 
        date,
        yr,
        mo,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        daily_return,
        
        -- Monthly stats (approximation via subquery)
        (SELECT AVG(s2.close) FROM stock_prices s2 
         WHERE s2.yr = stock_prices.yr AND s2.mo = stock_prices.mo) as monthly_avg_close,
        
        (SELECT MAX(s2.close) FROM stock_prices s2 
         WHERE s2.yr = stock_prices.yr AND s2.mo = stock_prices.mo) as monthly_high,
        
        (SELECT MIN(s2.close) FROM stock_prices s2 
         WHERE s2.yr = stock_prices.yr AND s2.mo = stock_prices.mo) as monthly_low,
        
        -- Volatility indicator (high - low) / close
        ROUND((high - low) / NULLIF(close, 0) * 100, 2) as intraday_volatility_pct
        
    FROM stock_prices
    """
    
    conn.execute(view_sql)
    conn.commit()
    
    # Verify
    sample = pd.read_sql("""
        SELECT date, symbol, 
               printf('$%.2f', close) as close,
               printf('%.2f%%', daily_return) as daily_return,
               printf('$%.2f', monthly_avg_close) as mo_avg,
               printf('%.2f%%', intraday_volatility_pct) as volatility
        FROM stock_metrics
        WHERE yr = 2020
        ORDER BY date
        LIMIT 10
    """, conn)
    
    print("✅ stock_metrics view created")
    print(f"\nSample (2020):")
    print(sample.to_string(index=False))
    
    conn.close()

def create_variance_analysis_view():
    """Create view for budget vs actual variance analysis."""
    print("\n" + "=" * 60)
    print("PHASE 2.3: Creating Variance Analysis View")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Drop existing view if exists
    conn.execute("DROP VIEW IF EXISTS variance_analysis")
    
    # Create view joining actuals with targets
    view_sql = """
    CREATE VIEW variance_analysis AS
    SELECT 
        a.yr,
        a.qtr,
        a.item as metric,
        a.actual_value,
        t.target_value,
        
        -- Absolute variance
        ROUND(a.actual_value - COALESCE(t.target_value, 0), 2) as variance_abs,
        
        -- Percentage variance
        ROUND((a.actual_value - COALESCE(t.target_value, 0)) / 
              NULLIF(ABS(t.target_value), 0) * 100, 2) as variance_pct,
        
        -- Status
        CASE 
            WHEN a.actual_value >= t.target_value AND a.item IN ('Revenue', 'Gross Profit', 'Operating Income', 'Net Income') THEN 'On Track'
            WHEN a.actual_value < t.target_value AND a.item IN ('Revenue', 'Gross Profit', 'Operating Income', 'Net Income') THEN 'Below Target'
            WHEN a.actual_value <= t.target_value AND a.item LIKE '%Cost%' THEN 'On Track'
            WHEN a.actual_value > t.target_value AND a.item LIKE '%Cost%' THEN 'Over Budget'
            ELSE 'N/A'
        END as status
        
    FROM (
        SELECT yr, qtr, item, SUM(val) as actual_value
        FROM swf
        GROUP BY yr, qtr, item
    ) a
    LEFT JOIN financial_targets t 
        ON a.yr = t.yr AND a.qtr = t.qtr AND a.item = t.metric
    WHERE t.target_value IS NOT NULL
    ORDER BY a.yr DESC, a.qtr DESC, a.item
    """
    
    conn.execute(view_sql)
    conn.commit()
    
    # Verify
    sample = pd.read_sql("""
        SELECT yr, qtr, metric,
               printf('$%.2fB', actual_value/1e9) as actual,
               printf('$%.2fB', target_value/1e9) as target,
               printf('%.1f%%', variance_pct) as variance,
               status
        FROM variance_analysis
        WHERE yr = 2024 AND metric IN ('Revenue', 'Net Income', 'Cost of Revenue')
        ORDER BY qtr, metric
        LIMIT 12
    """, conn)
    
    print("✅ variance_analysis view created")
    print(f"\nSample (2024 variance):")
    print(sample.to_string(index=False))
    
    conn.close()

def create_growth_metrics_view():
    """Create view for quarter-over-quarter growth rates."""
    print("\n" + "=" * 60)
    print("PHASE 2.3b: Creating Growth Metrics View")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Drop existing view if exists
    conn.execute("DROP VIEW IF EXISTS growth_metrics")
    
    # Create view with growth calculations
    view_sql = """
    CREATE VIEW growth_metrics AS
    WITH quarterly_data AS (
        SELECT 
            yr,
            qtr,
            item,
            SUM(val) as value,
            (yr * 4 + qtr) as period_num
        FROM swf
        GROUP BY yr, qtr, item
    )
    SELECT 
        curr.yr,
        curr.qtr,
        curr.item,
        curr.value as current_value,
        prev.value as previous_value,
        ROUND((curr.value - COALESCE(prev.value, curr.value)) / 
              NULLIF(ABS(COALESCE(prev.value, curr.value)), 0) * 100, 2) as growth_rate_qoq,
        CASE 
            WHEN curr.value > COALESCE(prev.value, 0) THEN 'Growing'
            WHEN curr.value < COALESCE(prev.value, 0) THEN 'Declining'
            ELSE 'Stable'
        END as trend
    FROM quarterly_data curr
    LEFT JOIN quarterly_data prev 
        ON curr.item = prev.item 
        AND curr.period_num = prev.period_num + 1
    ORDER BY curr.yr DESC, curr.qtr DESC, curr.item
    """
    
    conn.execute(view_sql)
    conn.commit()
    
    # Verify
    sample = pd.read_sql("""
        SELECT yr, qtr, item,
               printf('$%.2fB', current_value/1e9) as current,
               printf('%.1f%%', growth_rate_qoq) as qoq_growth,
               trend
        FROM growth_metrics
        WHERE yr >= 2023 AND item IN ('Revenue', 'Net Income')
        ORDER BY yr, qtr, item
        LIMIT 12
    """, conn)
    
    print("✅ growth_metrics view created")
    print(f"\nSample (2023+ growth):")
    print(sample.to_string(index=False))
    
    conn.close()

def verify_all_views():
    """Verify all Phase 2 views exist and work."""
    print("\n" + "=" * 60)
    print("PHASE 2.4: Verification")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    views = ['profitability_metrics', 'stock_metrics', 'variance_analysis', 'growth_metrics']
    
    for view in views:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            print(f"✅ {view}: {count} rows")
        except Exception as e:
            print(f"❌ {view}: ERROR - {e}")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("PHASE 2 COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    create_profitability_metrics_view()
    create_stock_metrics_view()
    create_variance_analysis_view()
    create_growth_metrics_view()
    verify_all_views()
