from services.database import DatabaseService


def _build_db_service():
    return DatabaseService()


db_service = _build_db_service()
