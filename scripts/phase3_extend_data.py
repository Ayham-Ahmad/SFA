"""
Phase 3 REVISED: Generate More Realistic Historical Data
=========================================================
- Add natural quarterly variability (not smooth growth)
- Include 2 loss quarters in 1996-2011 (like the 2014 Q4 loss)
- Preserve original 2012-2025 data completely
"""
import sqlite3
import pandas as pd
import numpy as np
import random

DB_PATH = "data/db/financial_data.db"
CSV_PATH = "data/SWF.csv"
ORIGINAL_CSV_PATH = "data/SWF_original_backup.csv"

# Set seed for reproducibility
np.random.seed(42)
random.seed(42)

def load_original_data():
    """Load only the original 2012-2025 data."""
    try:
        df = pd.read_csv(ORIGINAL_CSV_PATH)
        print(f"   Loaded from backup: {len(df)} rows")
    except:
        df = pd.read_csv(CSV_PATH)
        df = df[df['data_coverage_flag'] == 'COMPLETE'].copy()
        df.to_csv(ORIGINAL_CSV_PATH, index=False)
        print(f"   Created backup of original data: {len(df)} rows")
    
    return df

def generate_realistic_historical_data(original_df, target_start_year=1996):
    """
    Generate historical data with REALISTIC variability.
    Projects FORWARDS from a base point, adding natural variation.
    """
    
    # Get the 2012 Q1 anchor point
    anchor = original_df[
        (original_df['year'] == 2012) & 
        (original_df['quarter'] == 1)
    ].iloc[0].to_dict()
    
    # Financial columns
    value_cols = ['revenue', 'cost_of_revenue', 'gross_profit', 'operating_expenses',
                  'operating_income', 'other_income_expense', 'income_before_tax',
                  'income_tax_expense', 'net_income']
    
    # Define LOSS quarters (2 in the historical period)
    loss_quarters = {
        (2008, 4),  # 2008 financial crisis
        (2001, 3),  # Dot-com bubble burst
    }
    
    # Generate list of (year, quarter) tuples from 1996 to 2011
    quarters_list = []
    for year in range(target_start_year, 2012):
        for quarter in range(1, 5):
            quarters_list.append((year, quarter))
    
    # Total quarters from 1996 Q1 to 2011 Q4 = 64 quarters
    num_quarters = len(quarters_list)
    
    # Calculate starting values (1996 Q1) - about 20% of 2012 Q1 values
    start_factor = 0.20
    
    # Revenue growth from 1996 to 2012 (quarterly compound rate)
    # If revenue goes from 20% to 100% over 64 quarters:
    # 1.0 = 0.2 * (1 + r)^64  => r = (1/0.2)^(1/64) - 1 ≈ 0.0256 (2.56% per quarter)
    quarterly_growth = (1 / start_factor) ** (1 / num_quarters)  # ≈ 1.0256
    
    historical_rows = []
    
    # Start from 1996 Q1 base values
    base_values = {col: anchor[col] * start_factor for col in value_cols if anchor[col] is not None}
    
    for idx, (year, quarter) in enumerate(quarters_list):
        
        # Random quarterly variation (-5% to +8%)
        random_factor = 1.0 + np.random.uniform(-0.05, 0.08)
        
        # Seasonal adjustment (Q4 higher, Q1 lower)
        seasonal = {1: 0.95, 2: 0.98, 3: 1.02, 4: 1.05}
        season_factor = seasonal[quarter]
        
        # Calculate growth factor for this quarter
        growth_factor = (quarterly_growth ** idx) * random_factor * season_factor
        
        row = {
            'year': year,
            'quarter': quarter,
        }
        
        # Calculate values
        for col in value_cols:
            if col in base_values and base_values[col] is not None:
                row[col] = base_values[col] * growth_factor
            else:
                row[col] = None
        
        # Handle LOSS quarters (only these 2 specific quarters)
        is_loss_quarter = (year, quarter) in loss_quarters
        
        if is_loss_quarter:
            # Make net income negative (loss)
            if row['revenue']:
                loss_ratio = np.random.uniform(0.005, 0.015)  # 0.5% to 1.5% loss
                row['operating_income'] = -abs(row['revenue']) * loss_ratio
                row['net_income'] = row['operating_income'] * 0.75  # After tax benefit
                row['income_before_tax'] = row['operating_income']
                row['income_tax_expense'] = row['operating_income'] * 0.25  # Tax benefit
        
        # Ensure positive net_income for non-loss quarters
        if not is_loss_quarter and row.get('net_income') is not None:
            row['net_income'] = abs(row['net_income'])
            row['operating_income'] = abs(row.get('operating_income', row['net_income'] * 1.2))
            row['income_before_tax'] = abs(row.get('income_before_tax', row['operating_income']))
        
        # Recalculate gross_profit
        if row.get('revenue') and row.get('cost_of_revenue'):
            row['gross_profit'] = row['revenue'] + row['cost_of_revenue']  # cost is negative
        
        # Calculate margins
        if row.get('revenue') and row['revenue'] > 0:
            row['gross_margin'] = row['gross_profit'] / row['revenue'] if row.get('gross_profit') else 0.35
            row['operating_margin'] = row['operating_income'] / row['revenue'] if row.get('operating_income') else 0.10
            row['net_margin'] = row['net_income'] / row['revenue'] if row.get('net_income') else 0.08
        else:
            row['gross_margin'] = None
            row['operating_margin'] = None
            row['net_margin'] = None
        
        row['data_coverage_flag'] = 'PROJECTED'
        row['margin_validity_flag'] = 'VALID'
        
        historical_rows.append(row)
    
    return pd.DataFrame(historical_rows)

def main():
    print("Phase 3 REVISED: Generate Realistic Historical Data")
    print("=" * 55)
    
    # Load original data
    print("\n1. Loading original 2012-2025 data...")
    original_df = load_original_data()
    print(f"   Year range: {original_df['year'].min()} - {original_df['year'].max()}")
    
    # Generate realistic historical data
    print("\n2. Generating realistic historical data (1996-2011)...")
    print("   - Adding natural quarterly variation (+/- 5-8%)")
    print("   - Adding seasonal patterns")
    print("   - Including 2 loss quarters: 2001 Q3 (dot-com), 2008 Q4 (financial crisis)")
    historical_df = generate_realistic_historical_data(original_df, target_start_year=1996)
    print(f"   Generated rows: {len(historical_df)}")
    
    # Combine datasets
    print("\n3. Combining datasets...")
    cols = original_df.columns.tolist()
    historical_df = historical_df[cols]
    
    combined_df = pd.concat([historical_df, original_df], ignore_index=True)
    combined_df = combined_df.sort_values(['year', 'quarter']).reset_index(drop=True)
    
    print(f"   Total rows: {len(combined_df)}")
    print(f"   Year range: {combined_df['year'].min()} - {combined_df['year'].max()}")
    
    # Show loss quarters
    losses = combined_df[combined_df['net_income'] < 0]
    print(f"\n   Loss quarters: {len(losses)} (expected: 3)")
    for _, row in losses.iterrows():
        print(f"     - {int(row['year'])} Q{int(row['quarter'])}: Net Income ${row['net_income']:,.0f}")
    
    # Save to CSV
    print("\n4. Saving extended data...")
    combined_df.to_csv(CSV_PATH, index=False)
    print(f"   Saved to: {CSV_PATH}")
    
    # Update database
    print("\n5. Updating database...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS swf_financials")
    combined_df.to_sql('swf_financials', conn, index=False, if_exists='replace')
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 55)
    print("Phase 3 REVISED Complete!")
    print("Historical data now has natural variability and 2 loss quarters")

if __name__ == "__main__":
    main()
