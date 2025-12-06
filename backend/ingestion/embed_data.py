import os
import sqlite3
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Paths
DB_PATH = "data/db/financial_data.db"
CHROMA_PATH = "data/vector_store"

# 1. Connect to Database
if not os.path.exists(DB_PATH):
    print(f"Error: Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)

# 2. Initialize Models
print("Initializing Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

print("Initializing ChromaDB...")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="financial_data")

# 3. Embed Tags (Definitions)
print("Reading Tags...")
try:
    df_tags = pd.read_sql("SELECT tag, doc, tlabel FROM tags WHERE doc IS NOT NULL LIMIT 1000", conn) # Limit for speed in dev
    print(f"Found {len(df_tags)} tags.")
    
    ids = []
    documents = []
    metadatas = []
    
    for idx, row in tqdm(df_tags.iterrows(), total=len(df_tags), desc="Processing Tags"):
        # Text to embed: "Tag: NetIncome. Label: Net Income. Description: The portion of profit..."
        text = f"Tag: {row['tag']}. Label: {row['tlabel']}. Description: {row['doc']}"
        
        ids.append(f"tag_{idx}")
        documents.append(text)
        metadatas.append({"type": "tag", "tag": row['tag'], "source": "financial_data.db"})
    
    if documents:
        print("Embedding Tags...")
        embeddings = model.encode(documents)
        print("Upserting Tags to Chroma...")
        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas
        )
        print("Tags upserted.")

except Exception as e:
    print(f"Error processing tags: {e}")

# 4. Embed Submissions (Companies)
print("Reading Submissions (Companies)...")
try:
    # adsh is unique ID for submission, but name is company name
    df_subs = pd.read_sql("SELECT adsh, name, sic, ein, cityba, stprba FROM submissions LIMIT 1000", conn)
    print(f"Found {len(df_subs)} submissions.")
    
    ids = []
    documents = []
    metadatas = []
    
    for idx, row in tqdm(df_subs.iterrows(), total=len(df_subs), desc="Processing Submissions"):
        # Text to embed: "Company: Apple Inc. SIC: 3571. Location: Cupertino, CA."
        text = f"Company: {row['name']}. SIC: {row['sic']}. EIN: {row['ein']}. Location: {row['cityba']}, {row['stprba']}."
        
        ids.append(f"sub_{row['adsh']}")
        documents.append(text)
        metadatas.append({"type": "company", "name": row['name'], "adsh": row['adsh'], "source": "financial_data.db"})
    
    if documents:
        print("Embedding Submissions...")
        embeddings = model.encode(documents)
        print("Upserting Submissions to Chroma...")
        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas
        )
        print("Submissions upserted.")

except Exception as e:
    print(f"Error processing submissions: {e}")

print(f"Done. Collection count: {collection.count()}")
conn.close()
