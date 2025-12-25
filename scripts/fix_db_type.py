"""Fix db_type values to use uppercase enum values."""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH_DB_PATH = os.path.join(BASE_DIR, "data", "db", "users_accounts_data.db")

conn = sqlite3.connect(AUTH_DB_PATH)
cursor = conn.cursor()

# Fix lowercase values to uppercase
cursor.execute("UPDATE users SET db_type = 'NONE' WHERE db_type = 'none' OR db_type IS NULL")
print(f"Updated {cursor.rowcount} rows")

conn.commit()
conn.close()
print("Done!")
