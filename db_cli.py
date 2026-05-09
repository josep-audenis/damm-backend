from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from services.database import DB_PATH, DatabaseService


def _json_arg(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON payload must be an object")
    return payload


def _json_file(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"Invalid JSON file: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON file payload must be an object")
    return payload


def _payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.data is not None and args.file is not None:
        raise SystemExit("Use --data or --file, not both")
    if args.file is not None:
        return _json_file(args.file)
    if args.data is not None:
        return args.data
    return {}


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and write the JSON database.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help=f"JSON DB path. Default: {DB_PATH}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tables", help="List tables and row counts.")

    schema_parser = subparsers.add_parser("schema", help="Describe observed fields and Python value types.")
    schema_parser.add_argument("table")

    list_parser = subparsers.add_parser("list", help="List rows from a table.")
    list_parser.add_argument("table")
    list_parser.add_argument("--limit", type=int, default=20)

    get_parser = subparsers.add_parser("get", help="Get one row by id.")
    get_parser.add_argument("table")
    get_parser.add_argument("id", type=int)

    insert_parser = subparsers.add_parser("insert", help="Insert a row. Unknown tables are created.")
    insert_parser.add_argument("table")
    insert_parser.add_argument("--data", type=_json_arg)
    insert_parser.add_argument("--file")

    update_parser = subparsers.add_parser("update", help="Patch a row by id.")
    update_parser.add_argument("table")
    update_parser.add_argument("id", type=int)
    update_parser.add_argument("--data", type=_json_arg)
    update_parser.add_argument("--file")

    delete_parser = subparsers.add_parser("delete", help="Delete one row by id.")
    delete_parser.add_argument("table")
    delete_parser.add_argument("id", type=int)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    service = DatabaseService(db_path=args.db)
    service.init_db()

    if args.command == "tables":
        _print_json(service.list_tables())
    elif args.command == "schema":
        _print_json(service.describe_table(args.table))
    elif args.command == "list":
        _print_json(service.list_rows(args.table, limit=args.limit))
    elif args.command == "get":
        row = service.get_row(args.table, args.id)
        if row is None:
            raise SystemExit(f"Row not found: {args.table}/{args.id}")
        _print_json(row)
    elif args.command == "insert":
        _print_json(service.insert_row(args.table, _payload(args)))
    elif args.command == "update":
        row = service.update_row(args.table, args.id, _payload(args))
        if row is None:
            raise SystemExit(f"Row not found: {args.table}/{args.id}")
        _print_json(row)
    elif args.command == "delete":
        row = service.delete_row(args.table, args.id)
        if row is None:
            raise SystemExit(f"Row not found: {args.table}/{args.id}")
        _print_json(row)


if __name__ == "__main__":
    main()
