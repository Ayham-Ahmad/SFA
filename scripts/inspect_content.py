from sqlalchemy import create_engine, text
import pandas as pd
from backend.utils.paths import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}")

def inspect_table(table_name):
    print(f"\n--- {table_name} ---")
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 3", engine)
        print(df.to_markdown(index=False))
        print("Columns:", df.columns.tolist())
    except Exception as e:
        print(f"Error reading {table_name}: {e}")

inspect_table("presentations")
inspect_table("submissions")
inspect_table("tags")
