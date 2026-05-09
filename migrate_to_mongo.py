"""
One-shot migration: app_db.json → MongoDB Atlas

Usage (from damm-backend/):
    python migrate_to_mongo.py

Reads MONGODB_URI and MONGODB_DB from .env (or environment).
Drops and recreates each collection, then bulk-inserts all rows.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env if python-dotenv is available, otherwise fall back to manual parse
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from pymongo import MongoClient

MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB  = os.environ.get("MONGODB_DB", "damm_smart_truck")
DB_PATH     = Path(__file__).parent / "data" / "app_db.json"

if not MONGODB_URI:
    sys.exit("ERROR: MONGODB_URI not set. Add it to .env or the environment.")

print(f"Connecting to MongoDB…")
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

print(f"Loading {DB_PATH} …")
data = json.loads(DB_PATH.read_text(encoding="utf-8"))
tables = data.get("tables", {})

total_inserted = 0

for table, rows in tables.items():
    if not rows:
        print(f"  {table}: empty, skipping")
        continue

    col = db[table]
    col.drop()                         # fresh start
    col.insert_many(rows)              # bulk insert (no _id conflict since rows use int id)
    count = col.count_documents({})
    total_inserted += count
    print(f"  {table}: {count} documents inserted")

# Also sync the sequence counters so future inserts get correct IDs
seq_col = db["_seq"]
seq_col.drop()
seq_data = data.get("seq", {})
if seq_data:
    seq_col.insert_many([{"_id": k, "seq": v} for k, v in seq_data.items()])
    print(f"  _seq: {len(seq_data)} counters synced")

print(f"\nDone. {total_inserted} total documents migrated to '{MONGODB_DB}'.")
print("Verify on Atlas: https://cloud.mongodb.com")
