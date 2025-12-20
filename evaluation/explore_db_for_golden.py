"""
Database Explorer for Golden Dataset Creation
Extracts schema, sample data, and calculates ground truth values
"""
import sqlite3
import json

DB_PATH = "data/db/financial_data.db"

def explore_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"=== TABLES ({len(tables)}) ===")
    print(tables)
    
    # Get schema for each table
    print("\n=== SCHEMAS ===")
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print(f"\n{table}:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    
    # Get year ranges
    print("\n=== DATA RANGES ===")
    
    # Check swf_financials
    try:
        cursor.execute("SELECT MIN(fiscal_year), MAX(fiscal_year), COUNT(*) FROM swf_financials")
        row = cursor.fetchone()
        print(f"swf_financials: Years {row[0]}-{row[1]}, Rows: {row[2]}")
    except Exception as e:
        print(f"swf_financials: {e}")
    
    # Check market_daily_data
    try:
        cursor.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM market_daily_data")
        row = cursor.fetchone()
        print(f"market_daily_data: Years {row[0]}-{row[1]}, Rows: {row[2]}")
    except Exception as e:
        print(f"market_daily_data: {e}")
    
    conn.close()

def get_ground_truth_values():
    """Calculate actual values for ground truth queries"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    results = {}
    
    # === REVENUE QUERIES ===
    print("\n=== GROUND TRUTH VALUES ===\n")
    
    # Total Revenue 2024
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2024")
    results["revenue_2024_total"] = cursor.fetchone()[0]
    print(f"Total Revenue 2024: ${results['revenue_2024_total']:,.2f}")
    
    # Revenue by Quarter 2024
    cursor.execute("""
        SELECT fiscal_quarter, SUM(Revenue) as quarterly_revenue 
        FROM swf_financials 
        WHERE fiscal_year = 2024 
        GROUP BY fiscal_quarter 
        ORDER BY fiscal_quarter
    """)
    results["revenue_2024_quarterly"] = cursor.fetchall()
    print(f"Revenue 2024 by Quarter: {results['revenue_2024_quarterly']}")
    
    # Total Revenue 2023
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2023")
    results["revenue_2023_total"] = cursor.fetchone()[0]
    print(f"Total Revenue 2023: ${results['revenue_2023_total']:,.2f}")
    
    # === NET INCOME QUERIES ===
    cursor.execute("SELECT SUM(Net_Income) FROM swf_financials WHERE fiscal_year = 2024")
    results["net_income_2024"] = cursor.fetchone()[0]
    print(f"Net Income 2024: ${results['net_income_2024']:,.2f}")
    
    cursor.execute("SELECT SUM(Net_Income) FROM swf_financials WHERE fiscal_year = 2023")
    results["net_income_2023"] = cursor.fetchone()[0]
    print(f"Net Income 2023: ${results['net_income_2023']:,.2f}")
    
    # === GROSS PROFIT ===
    cursor.execute("SELECT SUM(Gross_Profit) FROM swf_financials WHERE fiscal_year = 2024")
    results["gross_profit_2024"] = cursor.fetchone()[0]
    print(f"Gross Profit 2024: ${results['gross_profit_2024']:,.2f}")
    
    # === MARGINS ===
    cursor.execute("SELECT AVG(gross_margin) FROM swf_financials WHERE fiscal_year = 2024")
    results["avg_gross_margin_2024"] = cursor.fetchone()[0]
    print(f"Avg Gross Margin 2024: {results['avg_gross_margin_2024']:.4f}")
    
    cursor.execute("SELECT AVG(net_margin) FROM swf_financials WHERE fiscal_year = 2024")
    results["avg_net_margin_2024"] = cursor.fetchone()[0]
    print(f"Avg Net Margin 2024: {results['avg_net_margin_2024']:.4f}")
    
    # === STOCK DATA ===
    cursor.execute("SELECT AVG(close_price) FROM market_daily_data WHERE year = 2024")
    results["avg_stock_price_2024"] = cursor.fetchone()[0]
    print(f"Avg Stock Price 2024: ${results['avg_stock_price_2024']:.2f}")
    
    cursor.execute("SELECT MAX(close_price), MIN(close_price) FROM market_daily_data WHERE year = 2024")
    row = cursor.fetchone()
    results["max_stock_price_2024"] = row[0]
    results["min_stock_price_2024"] = row[1]
    print(f"Stock Price Range 2024: ${row[1]:.2f} - ${row[0]:.2f}")
    
    cursor.execute("SELECT SUM(trade_volume) FROM market_daily_data WHERE year = 2024")
    results["total_volume_2024"] = cursor.fetchone()[0]
    print(f"Total Volume 2024: {results['total_volume_2024']:,}")
    
    # === Q1 2024 Specific ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2024 AND fiscal_quarter = 1")
    results["revenue_2024_q1"] = cursor.fetchone()[0]
    print(f"Revenue Q1 2024: ${results['revenue_2024_q1']:,.2f}")
    
    # === COMPARISON DATA ===
    # YoY Growth
    if results["revenue_2023_total"] and results["revenue_2024_total"]:
        results["revenue_yoy_growth"] = ((results["revenue_2024_total"] - results["revenue_2023_total"]) / results["revenue_2023_total"]) * 100
        print(f"Revenue YoY Growth: {results['revenue_yoy_growth']:.2f}%")
    
    # === AVAILABLE YEARS ===
    cursor.execute("SELECT DISTINCT fiscal_year FROM swf_financials ORDER BY fiscal_year")
    results["available_years_financials"] = [r[0] for r in cursor.fetchall()]
    print(f"Available Years (financials): {results['available_years_financials']}")
    
    cursor.execute("SELECT DISTINCT year FROM market_daily_data ORDER BY year")
    results["available_years_stock"] = [r[0] for r in cursor.fetchall()]
    print(f"Available Years (stock): {results['available_years_stock']}")
    
    # === ADDITIONAL VALUES FOR HARDER QUERIES ===
    
    # Best/Worst Quarter
    cursor.execute("""
        SELECT fiscal_year, fiscal_quarter, SUM(Revenue) as qtr_rev 
        FROM swf_financials 
        WHERE fiscal_year = 2024
        GROUP BY fiscal_year, fiscal_quarter 
        ORDER BY qtr_rev DESC
        LIMIT 1
    """)
    results["best_quarter_2024"] = cursor.fetchone()
    print(f"Best Quarter 2024: {results['best_quarter_2024']}")
    
    # Operating Expenses (if exists)
    try:
        cursor.execute("SELECT SUM(Operating_Expenses) FROM swf_financials WHERE fiscal_year = 2024")
        results["operating_expenses_2024"] = cursor.fetchone()[0]
        print(f"Operating Expenses 2024: ${results['operating_expenses_2024']:,.2f}")
    except:
        print("Operating Expenses: Column not found")
    
    # Monthly stock data
    cursor.execute("""
        SELECT month, AVG(close_price) 
        FROM market_daily_data 
        WHERE year = 2024 
        GROUP BY month 
        ORDER BY month
    """)
    results["monthly_avg_price_2024"] = cursor.fetchall()
    print(f"Monthly Avg Prices 2024: {results['monthly_avg_price_2024']}")
    
    conn.close()
    return results

if __name__ == "__main__":
    explore_database()
    values = get_ground_truth_values()
    
    # Save for reference
    with open("evaluation/ground_truth_values.json", "w") as f:
        # Convert to serializable format
        serializable = {}
        for k, v in values.items():
            if isinstance(v, (int, float, str, list)):
                serializable[k] = v
            else:
                serializable[k] = str(v)
        json.dump(serializable, f, indent=2)
    
    print("\n\nGround truth values saved to evaluation/ground_truth_values.json")
