from __future__ import annotations

import os

from services.database import DatabaseService


def _build_db_service():
    backend = os.environ.get("DAMM_DB_BACKEND", "json").strip().lower()
    if backend == "mongo":
        from services.mongo_database import MongoDatabaseService

        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("DAMM_DB_BACKEND=mongo requires MONGODB_URI")
        return MongoDatabaseService(uri, os.environ.get("MONGODB_DB", "damm_smart_truck"))
    return DatabaseService()


db_service = _build_db_service()
