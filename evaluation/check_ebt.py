"""Check Income Before Tax tag coverage"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/db/financial_data.db')

# Check what EBT tags are actually in the data
query = """
SELECT tag, COUNT(*) as cnt 
FROM numbers 
WHERE tag LIKE '%Income%Tax%' 
   OR tag LIKE '%Pretax%'
   OR tag LIKE '%EBT%'
GROUP BY tag 
ORDER BY cnt DESC 
LIMIT 20
"""
print("Income/Tax-related tags in numbers table:")
print(pd.read_sql(query, conn).to_string())

print("\n\n" + "="*60)
print("Current canonical tags for income_before_tax:")
print("  - IncomeLossFromContinuingOperationsBeforeIncomeTaxes")
print("  - IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems")
print("  - IncomeLossBeforeIncomeTaxes")

# Check if these exist in data
query2 = """
SELECT tag, COUNT(*) as cnt 
FROM numbers 
WHERE tag IN (
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxes',
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItems',
    'IncomeLossBeforeIncomeTaxes',
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments'
)
GROUP BY tag
"""
print("\nActual counts for configured tags:")
print(pd.read_sql(query2, conn).to_string())

conn.close()
