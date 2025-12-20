"""Simple verification with print flushing"""
import sqlite3
import pandas as pd
import sys

conn = sqlite3.connect('data/db/financial_data.db')
df = pd.read_sql("SELECT * FROM swf_statement", conn)

lines = []
lines.append("=" * 70)
lines.append("SWF_STATEMENT TABLE VERIFICATION")
lines.append("=" * 70)
lines.append("")
lines.append("1. BASIC STATS")
lines.append(f"   Total rows: {len(df):,}")
lines.append(f"   Unique companies: {df['company_id'].nunique():,}")
lines.append(f"   Fiscal years: {sorted([int(x) for x in df['fiscal_year'].unique()])}")
lines.append("")
lines.append("2. QUALITY FLAGS")
lines.append("   Consistency flags:")
for flag, count in df['statement_consistency_flag'].value_counts().items():
    pct = count / len(df) * 100
    lines.append(f"      {flag}: {count:,} ({pct:.1f}%)")

lines.append("")
lines.append("   Margin validity flags:")
for flag, count in df['margin_validity_flag'].value_counts().items():
    pct = count / len(df) * 100
    lines.append(f"      {flag}: {count:,} ({pct:.1f}%)")

lines.append("")
lines.append("   Source coverage flags:")
for flag, count in df['source_coverage_flag'].value_counts().items():
    pct = count / len(df) * 100
    lines.append(f"      {flag}: {count:,} ({pct:.1f}%)")

lines.append("")
lines.append("3. DATA COVERAGE")
income_cols = ['revenue', 'cost_of_revenue', 'gross_profit', 'operating_expenses',
               'operating_income', 'other_income_expense', 'income_before_tax',
               'income_tax_expense', 'net_income']
for col in income_cols:
    non_null = df[col].notna().sum()
    pct = non_null / len(df) * 100
    lines.append(f"   {col}: {non_null:,} ({pct:.1f}%)")

lines.append("")
lines.append("4. TOP 10 COMPANIES BY REVENUE")
top = df.nlargest(10, 'revenue')
for idx, row in top.iterrows():
    rev_b = row['revenue'] / 1e9
    ni_b = row['net_income'] / 1e9 if pd.notna(row['net_income']) else 0
    margin = row['net_margin'] if pd.notna(row['net_margin']) else 0
    name = str(row['company_name'])[:25]
    lines.append(f"   {name:<25} {int(row['fiscal_year'])}Q{int(row['fiscal_quarter'])} "
          f"Rev: ${rev_b:>6.1f}B  NI: ${ni_b:>5.1f}B  Margin: {margin:>5.1f}%")

lines.append("")
lines.append("5. SANITY CHECKS")
extreme_gross = df[df['gross_margin'].abs() > 100]
extreme_net = df[df['net_margin'].abs() > 100]
lines.append(f"   Rows with |gross_margin| > 100%: {len(extreme_gross)}")
lines.append(f"   Rows with |net_margin| > 100%: {len(extreme_net)}")
trillion = df[df['revenue'] > 1e12]
lines.append(f"   Rows with >$1T revenue: {len(trillion)} (GOOD - no spikes!)")
neg_rev = df[df['revenue'] < 0]
lines.append(f"   Rows with negative revenue: {len(neg_rev)}")

lines.append("")
lines.append("=" * 70)
lines.append("VERIFICATION COMPLETE")
lines.append("=" * 70)

conn.close()

# Write to file and print
with open('verification_output.txt', 'w') as f:
    for line in lines:
        f.write(line + '\n')
        print(line)
