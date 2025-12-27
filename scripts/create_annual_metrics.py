"""
Annual Metrics Table Generator

This script creates a precomputed `annual_metrics` table that aggregates
the most complete financial data per company per year.

This dramatically simplifies SQL generation for the LLM - instead of complex
GROUP BY / MAX(qtrs) logic, it can just query a flat table.

Run: python -m backend.ingestion.create_annual_metrics
"""
import sqlite3
import os
from backend.utils.paths import DB_PATH

# Priority tags for annual metrics
ANNUAL_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "NetIncomeLoss",
    "GrossProfit",
    "OperatingIncomeLoss",
    "Assets",
    "AssetsCurrent",
    "Liabilities",
    "LiabilitiesCurrent",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "ProfitLoss",
    "CostOfRevenue",
    "LongTermDebt",
]

def create_annual_metrics_table():
    """
    Creates the annual_metrics table with precomputed annual data.
    Takes the MAX value per company/tag/year to get the most complete data.
    """
    print("=" * 60)
    print("Creating Annual Metrics Table")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop existing table if it exists
    print("\n1. Dropping existing annual_metrics table (if any)...")
    cursor.execute("DROP TABLE IF EXISTS annual_metrics")
    
    # Create the annual_metrics table
    print("2. Creating annual_metrics table...")
    
    # Build the tag filter
    tag_list = ", ".join([f"'{tag}'" for tag in ANNUAL_TAGS])
    
    create_sql = f"""
    CREATE TABLE annual_metrics AS
    SELECT 
        s.cik,
        s.name AS company_name,
        n.tag,
        CAST(n.ddate / 10000 AS INTEGER) AS fiscal_year,
        MAX(n.value) AS value,
        n.uom,
        MAX(n.ddate) AS latest_date,
        MAX(n.qtrs) AS max_qtrs
    FROM numbers n
    JOIN submissions s ON n.adsh = s.adsh
    WHERE n.tag IN ({tag_list})
      AND n.uom = 'USD'
      AND n.value IS NOT NULL
      AND n.value > 0
    GROUP BY s.cik, s.name, n.tag, CAST(n.ddate / 10000 AS INTEGER), n.uom
    ORDER BY s.name, n.tag, fiscal_year DESC;
    """
    
    cursor.execute(create_sql)
    
    # Count rows
    cursor.execute("SELECT COUNT(*) FROM annual_metrics")
    row_count = cursor.fetchone()[0]
    print(f"   Created table with {row_count:,} rows")
    
    # Create indexes for fast queries
    print("3. Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_am_company ON annual_metrics(company_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_am_tag ON annual_metrics(tag)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_am_year ON annual_metrics(fiscal_year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_am_cik ON annual_metrics(cik)")
    print("   Indexes created: company_name, tag, fiscal_year, cik")
    
    # Show sample data
    print("\n4. Sample data (Apple revenue):")
    cursor.execute("""
        SELECT company_name, tag, fiscal_year, value, uom
        FROM annual_metrics
        WHERE company_name = 'APPLE INC' 
          AND tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
        ORDER BY fiscal_year DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    for row in rows:
        value_formatted = f"${row[3]/1e9:.2f}B" if row[3] >= 1e9 else f"${row[3]/1e6:.2f}M"
        print(f"   {row[0]} | {row[2]} | {value_formatted}")
    
    # Show unique companies count
    cursor.execute("SELECT COUNT(DISTINCT company_name) FROM annual_metrics")
    company_count = cursor.fetchone()[0]
    print(f"\n5. Unique companies in table: {company_count:,}")
    
    # Show unique tags count
    cursor.execute("SELECT COUNT(DISTINCT tag) FROM annual_metrics")
    tag_count = cursor.fetchone()[0]
    print(f"6. Unique tags in table: {tag_count:,}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ Annual Metrics Table Created Successfully!")
    print("=" * 60)
    print("\nUsage Example:")
    print("  SELECT company_name, fiscal_year, value")
    print("  FROM annual_metrics")
    print("  WHERE company_name = 'APPLE INC'")
    print("    AND tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'")
    print("  ORDER BY fiscal_year DESC;")
    
    return True

if __name__ == "__main__":
    create_annual_metrics_table()
