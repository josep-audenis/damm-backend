"""
Idempotent migration: app_db.json → MongoDB Atlas

Usage (from damm-backend/):
    python migrate_to_mongo.py            # skips collections that already have data
    python migrate_to_mongo.py --force    # drops and reimports everything

Reads MONGODB_URI and MONGODB_DB from .env (or environment).
Safe to re-run: by default any collection that already contains documents is
left untouched and reported as skipped.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FORCE = "--force" in sys.argv

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

print("Connecting to MongoDB…")
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

print(f"Loading {DB_PATH} …")
data = json.loads(DB_PATH.read_text(encoding="utf-8"))
tables = data.get("tables", {})

if FORCE:
    print("--force: all collections will be dropped and reimported.\n")
else:
    print("Safe mode: collections with existing data will be skipped. Use --force to reimport.\n")

total_inserted = 0
total_skipped = 0

for table, rows in tables.items():
    col = db[table]

    if not rows:
        print(f"  {table}: empty in source, skipping")
        continue

    existing = col.count_documents({})
    if existing > 0 and not FORCE:
        print(f"  {table}: already has {existing} documents — skipped")
        total_skipped += 1
        continue

    if FORCE:
        col.drop()

    col.insert_many(rows)              # rows already carry UUID string ids
    count = col.count_documents({})
    total_inserted += count
    print(f"  {table}: {count} documents inserted")

print(f"\nDone. {total_inserted} documents inserted, {total_skipped} collections skipped.")
print("Verify on Atlas: https://cloud.mongodb.com")
