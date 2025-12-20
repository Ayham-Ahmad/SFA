"""Check existing CSV files for historical data"""
import pandas as pd

# Check swf_financials.csv
print("=" * 60)
print("swf_financials.csv (original)")
print("=" * 60)
df1 = pd.read_csv('data/swf_financials.csv')
print(f"Rows: {len(df1)}")
print(f"Columns: {list(df1.columns)}")
if 'yr' in df1.columns:
    print(f"Years: {sorted(df1['yr'].unique())}")
print(df1.head(3))

# Check swf_full.csv
print("\n" + "=" * 60)
print("swf_full.csv")
print("=" * 60)
df2 = pd.read_csv('data/swf_full.csv')
print(f"Rows: {len(df2)}")
print(f"Columns: {list(df2.columns)}")
if 'yr' in df2.columns:
    print(f"Years: {sorted(df2['yr'].unique())}")
print(df2.head(3))

# Check processed_income_statement.csv
print("\n" + "=" * 60)
print("processed_income_statement.csv")
print("=" * 60)
df3 = pd.read_csv('data/processed_income_statement.csv', nrows=100)
print(f"Columns: {list(df3.columns)}")
if 'fiscal_year' in df3.columns:
    full_df = pd.read_csv('data/processed_income_statement.csv')
    print(f"Total rows: {len(full_df)}")
    print(f"Years: {sorted(full_df['fiscal_year'].unique())}")
