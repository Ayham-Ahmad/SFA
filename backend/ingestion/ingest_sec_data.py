import os
import sqlite3
import pandas as pd
import glob
import time

# --- Config ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw_data")

# Define Data Types for better memory usage and correct mapping
DTYPES = {
    'sub': {
        'adsh': str, 'cik': int, 'name': str, 'sic': float, 'countryba': str,
        'stprba': str, 'cityba': str, 'zipba': str, 'bas1': str, 'bas2': str, 
        'baph': str, 'countryma': str, 'stprma': str, 'cityma': str, 
        'zipma': str, 'mas1': str, 'mas2': str, 'countryinc': str,
        'stprinc': str, 'ein': str, 'former': str, 'changed': str, 
        'afs': str, 'wksi': str, 'fye': str, 'form': str, 'period': str, 
        'fy': float, 'fp': str, 'filed': str, 'accepted': str, 'prevrpt': str, 
        'detail': str, 'instance': str, 'ncik': str, 'acik': str
    },
    'tag': {
        'tag': str, 'version': str, 'custom': float, 'abstract': float, 
        'datatype': str, 'iord': str, 'crdr': str, 'tlabel': str, 'doc': str
    },
    'num': {
        'adsh': str, 'tag': str, 'version': str, 'coreg': str, 
        'ddate': str, 'qtrs': float, 'uom': str, 'value': float, 
        'footlen': float, 'dimh': str, 'iprx': float
    },
    'pre': {
        'adsh': str, 'report': float, 'line': float, 'stmt': str, 
        'inpth': float, 'rfile': str, 'tag': str, 'version': str, 'plabel': str, 'negating': float
    }
}

CHUNK_SIZE = 50000  # Rows per chunk for num.txt

def get_connection():
    """Returns a connection to the SQLite DB."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def recreate_tables(conn):
    """Drops and recreates tables to ensure clean schema."""
    print("Resetting database schema...")
    cursor = conn.cursor()
    
    # Drop existing
    cursor.execute("DROP TABLE IF EXISTS submissions")
    cursor.execute("DROP TABLE IF EXISTS tags")
    cursor.execute("DROP TABLE IF EXISTS numbers")
    cursor.execute("DROP TABLE IF EXISTS pre")
    
    # --- Create Tables ---
    
    # Submissions
    cursor.execute("""
    CREATE TABLE submissions (
        adsh TEXT PRIMARY KEY,
        cik INTEGER,
        name TEXT,
        sic INTEGER,
        countryba TEXT,
        cityba TEXT,
        zipba TEXT,
        fye TEXT,
        period TEXT,
        form TEXT,
        fy REAL,
        fp TEXT,
        filed TEXT
    )
    """)
    
    # Tags
    cursor.execute("""
    CREATE TABLE tags (
        tag TEXT,
        version TEXT,
        custom INTEGER,
        abstract INTEGER,
        datatype TEXT,
        tlabel TEXT,
        doc TEXT,
        PRIMARY KEY (tag, version)
    )
    """)
    
    # Numbers
    cursor.execute("""
    CREATE TABLE numbers (
        adsh TEXT,
        tag TEXT,
        version TEXT,
        ddate INTEGER,
        qtrs INTEGER,
        uom TEXT,
        value REAL,
        FOREIGN KEY(adsh) REFERENCES submissions(adsh)
    )
    """)
    
    # Pre (Presentation)
    cursor.execute("""
    CREATE TABLE pre (
        adsh TEXT,
        report INTEGER,
        line INTEGER,
        stmt TEXT,
        tag TEXT,
        version TEXT
    )
    """)
    
    conn.commit()
    print("Schema created.")

def ingest_file(filename, table_name, conn, use_chunking=False):
    """Reads a file and inserts it into the DB."""
    file_path = os.path.join(RAW_DATA_DIR, filename)
    if not os.path.exists(file_path):
        print(f"Skipping {filename}: File not found.")
        return

    print(f"Processing {filename} -> {table_name}...")
    start_time = time.time()
    
    # Determine columns to keep based on our table schema (simplified)
    # We only keep columns that exist in our CREATE TABLE statements
    target_cols = []
    if table_name == 'submissions':
        target_cols = ['adsh', 'cik', 'name', 'sic', 'countryba', 'cityba', 'zipba', 'fye', 'period', 'form', 'fy', 'fp', 'filed']
    elif table_name == 'tags':
        target_cols = ['tag', 'version', 'custom', 'abstract', 'datatype', 'tlabel', 'doc']
    elif table_name == 'numbers':
        target_cols = ['adsh', 'tag', 'version', 'ddate', 'qtrs', 'uom', 'value']
    elif table_name == 'pre':
        target_cols = ['adsh', 'report', 'line', 'stmt', 'tag', 'version']
        
    dtype = DTYPES.get(table_name.split('.')[0][:3], str) # basic key matching

    try:
        if use_chunking:
            total_rows = 0
            for chunk in pd.read_csv(file_path, sep='\t', chunksize=CHUNK_SIZE, dtype=dtype, on_bad_lines='skip', low_memory=False):
                # Filter cols
                chunk = chunk[[c for c in target_cols if c in chunk.columns]]
                
                # Write to DB
                chunk.to_sql(table_name, conn, if_exists='append', index=False)
                total_rows += len(chunk)
                print(f"  Processed {total_rows} rows...", end='\r')
            print(f"\n  Finished {filename}: {total_rows} rows.")
            
        else:
            df = pd.read_csv(file_path, sep='\t', dtype=dtype, on_bad_lines='skip', low_memory=False)
            # Filter cols
            df = df[[c for c in target_cols if c in df.columns]]
            
            df.to_sql(table_name, conn, if_exists='append', index=False)
            print(f"  Finished {filename}: {len(df)} rows.")
            
    except Exception as e:
        print(f"\nError processing {filename}: {e}")
        import traceback
        traceback.print_exc()

    print(f"  Time taken: {time.time() - start_time:.2f}s")


def create_indices(conn):
    print("Creating Indices...")
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_numbers_adsh ON numbers(adsh)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_numbers_tag ON numbers(tag)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_numbers_ddate ON numbers(ddate)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_cik ON submissions(cik)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_name ON submissions(name)")
    conn.commit()
    print("Indices created.")

def main():
    print(f"Starting Ingestion from {RAW_DATA_DIR}")
    conn = get_connection()
    
    try:
        recreate_tables(conn)
        
        # 1. Submissions (Small-ish)
        ingest_file('sub.txt', 'submissions', conn)
        
        # 2. Tags (Small-ish)
        ingest_file('tag.txt', 'tags', conn)
        
        # 3. Pre (Medium)
        ingest_file('pre.txt', 'pre', conn, use_chunking=True)
        
        # 4. Numbers (HUGE - ALWAYS CHUNK)
        ingest_file('num.txt', 'numbers', conn, use_chunking=True)
        
        create_indices(conn)
        
        print("\nIngestion Complete!")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
