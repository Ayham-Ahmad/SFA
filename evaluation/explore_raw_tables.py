"""
Detailed exploration of raw SEC data files for SWF table creation.
"""
import pandas as pd

# ============================================================
# 1. SUBMISSIONS (sub.txt) - Company filings
# ============================================================
print("=" * 80)
print("SUBMISSIONS (sub.txt) - Company Filing Metadata")
print("=" * 80)

sub_df = pd.read_csv("data/raw_data/sub.txt", sep="\t", nrows=100)
print(f"Columns: {list(sub_df.columns)}")
print(f"\nSample data:")
print(sub_df[['adsh', 'cik', 'name', 'sic', 'fy', 'fp', 'form', 'filed', 'period']].head(10).to_string())

# ============================================================
# 2. NUMBERS (num.txt) - Financial Facts
# ============================================================
print("\n" + "=" * 80)
print("NUMBERS (num.txt) - Financial Facts")
print("=" * 80)

num_df = pd.read_csv("data/raw_data/num.txt", sep="\t", nrows=1000)
print(f"Columns: {list(num_df.columns)}")
print(f"\nSample data:")
print(num_df.head(10).to_string())

# Check for income statement tags
income_tags = ['Revenues', 'Revenue', 'CostOfRevenue', 'GrossProfit', 
               'OperatingExpenses', 'OperatingIncomeLoss', 'NetIncomeLoss',
               'IncomeTaxExpenseBenefit', 'IncomeBeforeIncomeTaxes']
print(f"\nLooking for income statement tags...")
for tag in income_tags:
    matches = num_df[num_df['tag'].str.contains(tag, case=False, na=False)]
    if len(matches) > 0:
        print(f"  Found {len(matches)} rows with '{tag}'")

# ============================================================
# 3. TAGS (tag.txt) - Tag Definitions
# ============================================================
print("\n" + "=" * 80)
print("TAGS (tag.txt) - Tag Definitions")
print("=" * 80)

tag_df = pd.read_csv("data/raw_data/tag.txt", sep="\t", nrows=500)
print(f"Columns: {list(tag_df.columns)}")
print(f"\nSample data:")
print(tag_df.head(10).to_string())

# ============================================================
# 4. PRESENTATIONS (pre.txt) - Statement Structure
# ============================================================
print("\n" + "=" * 80)
print("PRESENTATIONS (pre.txt) - Statement Structure")
print("=" * 80)

pre_df = pd.read_csv("data/raw_data/pre.txt", sep="\t", nrows=500)
print(f"Columns: {list(pre_df.columns)}")
print(f"\nSample data (IS = Income Statement):")
is_pre = pre_df[pre_df['stmt'] == 'IS'].head(20)
print(is_pre.to_string())

# ============================================================
# 5. Total row counts
# ============================================================
print("\n" + "=" * 80)
print("TOTAL ROW COUNTS (may take a moment)")
print("=" * 80)

import subprocess
result = subprocess.run(['wc', '-l', 'data/raw_data/num.txt'], capture_output=True, text=True, shell=True)
print(f"num.txt estimating...")

# Use chunked reading for row count
for fname in ['sub.txt', 'num.txt', 'tag.txt', 'pre.txt']:
    try:
        count = sum(1 for _ in open(f"data/raw_data/{fname}", encoding='utf-8', errors='ignore'))
        print(f"  {fname}: {count:,} rows")
    except Exception as e:
        print(f"  {fname}: Error - {e}")
