from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.database import DatabaseService


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_database_service_creates_dynamic_tables(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "app_db.json")

    row = service.insert_row("experiments", {"name": "json-db", "enabled": True})
    updated = service.update_row("experiments", row["id"], {"score": 42})

    assert row["id"] == 1
    assert updated == {"id": 1, "name": "json-db", "enabled": True, "score": 42}
    assert service.list_tables()["experiments"] == 1
    assert service.describe_table("experiments") == {
        "enabled": ["bool"],
        "id": ["int"],
        "name": ["str"],
        "score": ["int"],
    }

    assert service.clear_table("experiments") == 1
    assert service.list_rows("experiments") == []


def test_db_cli_reads_and_writes_dynamic_json_db(tmp_path: Path) -> None:
    db_path = tmp_path / "cli_db.json"

    insert = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "db_cli.py"),
            "--db",
            str(db_path),
            "insert",
            "notes",
            "--data",
            '{"title":"first","tags":["dev"]}',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    inserted = json.loads(insert.stdout)
    assert inserted == {"id": 1, "title": "first", "tags": ["dev"]}

    update = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "db_cli.py"),
            "--db",
            str(db_path),
            "update",
            "notes",
            "1",
            "--data",
            '{"done":true}',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    updated = json.loads(update.stdout)
    assert updated["done"] is True

    listed = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "db_cli.py"),
            "--db",
            str(db_path),
            "list",
            "notes",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(listed.stdout) == [updated]
