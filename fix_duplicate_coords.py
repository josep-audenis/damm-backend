"""
fix_duplicate_coords.py
-----------------------
Re-geocodes the 11 customers in app_db.json that share coordinates with another
customer (likely geocoding snap errors). Updates the file in place.

Run from the damm-backend directory:
    python fix_duplicate_coords.py

Requirements: httpx (already in requirements.txt)
"""

from __future__ import annotations
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

DB_PATH = Path(__file__).parent / "data" / "app_db.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "damm-smart-truck-fix/1.0"

# The 11 customer ID prefixes that need re-geocoding, with their correct addresses
TARGETS = [
    # (full_id_prefix_8chars, address, city, postal_code)
    ("7ced1fba", "CARRER BERENGUER III 57",      "MOLLET DEL VALLES",         "08100"),
    ("41bca6a6", "BERENGUER III 71",              "MOLLET DEL VALLÈS",         "08100"),
    ("77d472aa", "RAMBLA NOVA 93",                "MOLLET DEL VALLES",         "08100"),
    ("3f4dfcd1", "RAMBLA NOVA 93",                "MOLLET DEL VALLES",         "08100"),
    ("f3c8caa0", "CARRER GIRONA 49",              "GRANOLLERS",                "08402"),
    ("1f1266dd", "CARRER GIRONA 12",              "GRANOLLERS",                "08400"),
    ("1a5ff8f1", "CARRER RAFAEL CASANOVA 64",     "GRANOLLERS",                "08401"),
    ("cf8a1b57", "CARRER RAFAEL CASANOVA 60",     "GRANOLLERS",                "08401"),
    ("013d0af6", "CARRER RAFAEL CASANOVA 50",     "GRANOLLERS",                "08401"),
    ("694fdec8", "CARRER DEL PLA DE BALENYÀ 9",   "VIC",                       "08500"),
    ("822f3a15", "CARRER DEL PLA DE BALENYÀ 7",   "VIC",                       "08500"),
]


async def geocode(client: httpx.AsyncClient, address: str, city: str, postal: str) -> tuple[float, float] | None:
    queries = [
        f"{address}, {postal} {city}, Spain",
        f"{address}, {city}, Spain",
        f"{postal} {city}, Spain",
    ]
    for query in queries:
        try:
            r = await client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "es"},
                headers={"User-Agent": USER_AGENT},
            )
            r.raise_for_status()
            data = r.json()
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                display = data[0].get("display_name", "")
                print(f"  ✓ {query}\n    → {lat}, {lng}\n    ({display[:80]})")
                return lat, lng
        except Exception as e:
            print(f"  ✗ Error for '{query}': {e}")
        await asyncio.sleep(1.2)  # Nominatim rate limit
    return None


async def main() -> None:
    print(f"Reading {DB_PATH} …")
    raw = DB_PATH.read_text(encoding="utf-8")

    # File has trailing whitespace after the JSON object — use raw_decode
    decoder = json.JSONDecoder()
    db, _ = decoder.raw_decode(raw)

    customers = db["tables"]["customers"]
    id_to_customer = {c["id"][:8]: c for c in customers}

    print(f"Total customers: {len(customers)}\n")

    updated = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for id_prefix, address, city, postal in TARGETS:
            customer = id_to_customer.get(id_prefix)
            if not customer:
                print(f"WARNING: customer {id_prefix} not found in DB")
                continue

            old_lat, old_lng = customer["lat"], customer["lng"]
            print(f"\n[{id_prefix}] {customer['name']}")
            print(f"  Address in DB: {customer['address']}, {customer['city']}")
            print(f"  Old coords: {old_lat}, {old_lng}")
            print(f"  Geocoding: {address}, {city}, {postal}")

            result = await geocode(client, address, city, postal)
            if result:
                new_lat, new_lng = result
                customer["lat"] = new_lat
                customer["lng"] = new_lng
                print(f"  Updated: {old_lat},{old_lng} → {new_lat},{new_lng}")
                updated += 1
            else:
                print(f"  SKIPPED (no result) — keeping old coords")

            await asyncio.sleep(1.2)

    print(f"\n{'='*60}")
    print(f"Updated {updated} / {len(TARGETS)} customers.")

    if updated > 0:
        print(f"Writing {DB_PATH} …")
        DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Done. ✓")
    else:
        print("Nothing to write.")


if __name__ == "__main__":
    asyncio.run(main())
