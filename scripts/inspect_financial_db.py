from sqlalchemy import create_engine, inspect
import os
from backend.utils.paths import DB_PATH

if not os.path.exists(DB_PATH):
    print(f"Error: {DB_PATH} not found.")
    exit(1)

engine = create_engine(f"sqlite:///{DB_PATH}")
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables found: {tables}")

if tables:
    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text(f"SELECT COUNT(*) FROM {tables[0]}")).scalar()
        print(f"Rows in {tables[0]}: {result}")
