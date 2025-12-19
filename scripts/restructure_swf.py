"""
Restructure SWF Table - Convert from long to wide format

BEFORE (long):
| yr | qtr | mo | wk | item          | val      |
| 2024| 1  | 1  | 1  | Revenue       | 10000000 |
| 2024| 1  | 1  | 1  | Net Income    | 5000000  |

AFTER (wide):
| yr | qtr | mo | wk | Revenue  | Net_Income | Gross_Profit | ... |
| 2024| 1  | 1  | 1  | 10000000 | 5000000    | 7000000      | ... |

Also:
1. Delete rows where yr < 2012
2. Fill NULL values with 0
"""

import sqlite3
import pandas as pd

DB_PATH = "data/db/financial_data.db"

def restructure_swf():
    conn = sqlite3.connect(DB_PATH)
    
    # Step 1: Load current swf data
    print("Loading swf table...")
    df = pd.read_sql("SELECT * FROM swf", conn)
    print(f"Original: {len(df)} rows")
    
    # Step 2: Filter to yr >= 2012
    df = df[df['yr'] >= 2012]
    print(f"After filtering yr >= 2012: {len(df)} rows")
    
    # Step 3: Pivot - convert to wide format
    print("Pivoting to wide format...")
    df_wide = df.pivot_table(
        index=['yr', 'qtr', 'mo', 'wk'],
        columns='item',
        values='val',
        aggfunc='sum'
    ).reset_index()
    
    # Step 4: Clean column names (remove spaces, special chars)
    df_wide.columns = [c.replace(' ', '_').replace('/', '_') for c in df_wide.columns]
    
    # Step 5: Fill NaN with 0
    df_wide = df_wide.fillna(0)
    
    print(f"Wide format: {len(df_wide)} rows, {len(df_wide.columns)} columns")
    print(f"Columns: {list(df_wide.columns)}")
    
    # Step 6: Backup original table
    print("Backing up original swf table...")
    conn.execute("DROP TABLE IF EXISTS swf_backup")
    conn.execute("CREATE TABLE swf_backup AS SELECT * FROM swf")
    
    # Step 7: Drop original and create new
    print("Replacing swf table with wide format...")
    conn.execute("DROP TABLE swf")
    df_wide.to_sql('swf', conn, index=False)
    
    conn.commit()
    conn.close()
    
    print("Done! SWF table restructured to wide format.")
    print(f"Sample columns: {list(df_wide.columns[:10])}")

if __name__ == "__main__":
    restructure_swf()
