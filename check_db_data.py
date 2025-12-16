import sqlite3
c = sqlite3.connect('data/db/financial_data.db').cursor()

# Check stock_metrics for volatility
print("=== STOCK_METRICS VIEW ===")
c.execute("PRAGMA table_info(stock_metrics)")
cols = [r[1] for r in c.fetchall()]
print(f"Columns: {cols}")

c.execute("SELECT * FROM stock_metrics WHERE yr = 2020 LIMIT 3")
rows = c.fetchall()
print(f"2020 data sample:")
for row in rows:
    print(f"  {row}")

# Check if intraday_volatility_pct exists
if 'intraday_volatility_pct' in cols:
    c.execute("SELECT AVG(intraday_volatility_pct) FROM stock_metrics WHERE yr = 2020")
    avg_vol = c.fetchone()[0]
    print(f"\nAverage volatility 2020: {avg_vol:.2f}%")

# Check SWF table for operating expenses
print("\n=== SWF TABLE ===")
c.execute("PRAGMA table_info(swf)")
cols = [r[1] for r in c.fetchall()]
print(f"Columns: {cols}")

c.execute("SELECT DISTINCT item FROM swf WHERE item LIKE '%perat%' OR item LIKE '%xpense%' LIMIT 15")
print(f"Expense-related items: {[r[0] for r in c.fetchall()]}")
