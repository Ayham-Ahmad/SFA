"""
Extended database explorer for more ground truth values
"""
import sqlite3
import json

DB_PATH = "data/db/financial_data.db"

def get_extended_values():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    results = {}
    
    # === 2023 DATA ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2023")
    results["revenue_2023"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(Net_Income) FROM swf_financials WHERE fiscal_year = 2023")
    results["net_income_2023"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(Gross_Profit) FROM swf_financials WHERE fiscal_year = 2023")
    results["gross_profit_2023"] = cursor.fetchone()[0]
    
    # === 2022 DATA ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2022")
    results["revenue_2022"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(Net_Income) FROM swf_financials WHERE fiscal_year = 2022")
    results["net_income_2022"] = cursor.fetchone()[0]
    
    # === 2021 DATA ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2021")
    results["revenue_2021"] = cursor.fetchone()[0]
    
    # === 2020 DATA ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2020")
    results["revenue_2020"] = cursor.fetchone()[0]
    
    # === Q2 2024 ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2024 AND fiscal_quarter = 2")
    results["revenue_2024_q2"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(Net_Income) FROM swf_financials WHERE fiscal_year = 2024 AND fiscal_quarter = 2")
    results["net_income_2024_q2"] = cursor.fetchone()[0]
    
    # === Q3 2024 ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2024 AND fiscal_quarter = 3")
    results["revenue_2024_q3"] = cursor.fetchone()[0]
    
    # === Q4 2024 ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2024 AND fiscal_quarter = 4")
    results["revenue_2024_q4"] = cursor.fetchone()[0]
    
    # === STOCK 2023 ===
    cursor.execute("SELECT AVG(close_price) FROM market_daily_data WHERE year = 2023")
    results["avg_stock_2023"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(close_price), MIN(close_price) FROM market_daily_data WHERE year = 2023")
    row = cursor.fetchone()
    results["max_stock_2023"] = row[0]
    results["min_stock_2023"] = row[1]
    
    cursor.execute("SELECT SUM(trade_volume) FROM market_daily_data WHERE year = 2023")
    results["volume_2023"] = cursor.fetchone()[0]
    
    # === STOCK 2022 ===
    cursor.execute("SELECT AVG(close_price) FROM market_daily_data WHERE year = 2022")
    results["avg_stock_2022"] = cursor.fetchone()[0]
    
    # === STOCK 2020 ===
    cursor.execute("SELECT AVG(close_price) FROM market_daily_data WHERE year = 2020")
    results["avg_stock_2020"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(close_price), MIN(close_price) FROM market_daily_data WHERE year = 2020")
    row = cursor.fetchone()
    results["max_stock_2020"] = row[0]
    results["min_stock_2020"] = row[1]
    
    # === SPECIFIC DATES ===
    cursor.execute("SELECT close_price FROM market_daily_data WHERE year = 2024 AND month = 1 AND day = 2")
    result = cursor.fetchone()
    results["stock_jan2_2024"] = result[0] if result else None
    
    cursor.execute("SELECT close_price FROM market_daily_data WHERE year = 2024 AND month = 6 AND day = 28")
    result = cursor.fetchone()
    results["stock_jun28_2024"] = result[0] if result else None
    
    # === GROWTH CALCULATIONS ===
    if results["revenue_2023"] and results["revenue_2022"]:
        results["growth_2023_2022"] = ((results["revenue_2023"] - results["revenue_2022"]) / results["revenue_2022"]) * 100
    
    # === WORST QUARTER 2024 ===
    cursor.execute("""
        SELECT fiscal_quarter, SUM(Revenue) as qtr_rev 
        FROM swf_financials 
        WHERE fiscal_year = 2024
        GROUP BY fiscal_quarter 
        ORDER BY qtr_rev ASC
        LIMIT 1
    """)
    results["worst_quarter_2024"] = cursor.fetchone()
    
    # === PROFITABILITY METRICS ===
    cursor.execute("SELECT AVG(gross_margin) FROM swf_financials WHERE fiscal_year = 2023")
    results["gross_margin_2023"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(operating_margin) FROM swf_financials WHERE fiscal_year = 2024")
    results["operating_margin_2024"] = cursor.fetchone()[0]
    
    # === MONTHLY REVENUE (check if available) ===
    cursor.execute("""
        SELECT fiscal_quarter, COUNT(*) as weeks, SUM(Revenue)/COUNT(*) as avg_weekly
        FROM swf_financials 
        WHERE fiscal_year = 2024
        GROUP BY fiscal_quarter
    """)
    results["weekly_avg_by_quarter_2024"] = cursor.fetchall()
    
    # === FIRST WEEK 2025 DATA ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2025")
    results["revenue_2025"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT close_price FROM market_daily_data WHERE year = 2025 LIMIT 5")
    results["stock_2025_samples"] = [r[0] for r in cursor.fetchall()]
    
    # === COMPARISON: Best Year Revenue ===
    cursor.execute("""
        SELECT fiscal_year, SUM(Revenue) as total_rev
        FROM swf_financials
        GROUP BY fiscal_year
        ORDER BY total_rev DESC
        LIMIT 1
    """)
    results["best_revenue_year"] = cursor.fetchone()
    
    # === 2019 DATA (older) ===
    cursor.execute("SELECT SUM(Revenue) FROM swf_financials WHERE fiscal_year = 2019")
    results["revenue_2019"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(close_price) FROM market_daily_data WHERE year = 2019")
    results["avg_stock_2019"] = cursor.fetchone()[0]
    
    # === DAILY RETURN ===
    cursor.execute("SELECT AVG(daily_return_pct) FROM market_daily_data WHERE year = 2024")
    results["avg_daily_return_2024"] = cursor.fetchone()[0]
    
    # === VOLATILITY ===
    cursor.execute("SELECT COUNT(*) FROM market_daily_data WHERE year = 2024 AND volatility_flag = 1")
    results["volatility_days_2024"] = cursor.fetchone()[0]
    
    conn.close()
    
    # Print all results
    for k, v in results.items():
        if isinstance(v, float):
            print(f"{k}: {v:,.2f}")
        else:
            print(f"{k}: {v}")
    
    return results

if __name__ == "__main__":
    values = get_extended_values()
    
    # Save
    with open("evaluation/extended_ground_truth.json", "w") as f:
        serializable = {}
        for k, v in values.items():
            if isinstance(v, (int, float, str, list, type(None))):
                serializable[k] = v
            else:
                serializable[k] = str(v)
        json.dump(serializable, f, indent=2)
    
    print("\nSaved to evaluation/extended_ground_truth.json")
