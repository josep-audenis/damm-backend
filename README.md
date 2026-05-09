# damm-backend

Backend API for Damm route/catalog data. Local database is JSON at `data/app_db.json`.

## Requirements

- Python 3.11+ (3.13 recommended; tested on 3.14).
- macOS or Windows. Linux works the same as macOS.

If you don't already have Python on macOS, install it with Homebrew:

```bash
brew install python@3.13
```

## Setup (macOS / Linux)

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

After this, `python` and `pytest` will resolve to the venv. Reactivate later with `source .venv/bin/activate`.

To leave the venv:

```bash
deactivate
```

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run API (macOS / Linux)

With the venv activated:

```bash
uvicorn main:app --reload
```

Or without activating the venv:

```bash
.venv/bin/uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/app/
http://127.0.0.1:8000/docs
```

If port `8000` is busy:

```bash
uvicorn main:app --reload --port 8001
```

### Run API (Windows PowerShell)

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

## Test (macOS / Linux)

The repo has no installable package, so tests need the project root on `PYTHONPATH`:

```bash
PYTHONPATH=. .venv/bin/pytest --basetemp .pytest_tmp
```

Or, with the venv activated:

```bash
PYTHONPATH=. pytest --basetemp .pytest_tmp
```

Run a single file:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_orders_import.py -q
```

### Test (Windows PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest_tmp
```

## JSON DB API

Generic DB endpoints read schema from local JSON data and allow dynamic rows/tables.

```text
GET    /api/v1/db/tables
GET    /api/v1/db/{table}/schema
GET    /api/v1/db/{table}?limit=100
GET    /api/v1/db/{table}/{row_id}
POST   /api/v1/db/{table}
PATCH  /api/v1/db/{table}/{row_id}
DELETE /api/v1/db/{table}/{row_id}
```

macOS examples:

```bash
curl 'http://127.0.0.1:8000/api/v1/db/warehouses?limit=1'
curl -X POST http://127.0.0.1:8000/api/v1/db/notes \
  -H 'Content-Type: application/json' \
  -d '{"title":"test"}'
curl -X PATCH http://127.0.0.1:8000/api/v1/db/notes/<row_id> \
  -H 'Content-Type: application/json' \
  -d '{"done":true}'
```

## Import Orders From CSV

Upload a CSV of new orders. The CSV must have a header row and use `;` or `,` as the delimiter. Required columns: `customer_name`, `qty`, `unit`. Optional columns: `material_code`, `material_name`, `due_date`.

The importer is strict: rows are inserted only when both the customer (matched by uppercase `name`) and the material (matched by uppercase `description`, falling back to `material_code`) already exist in the database. Unknown customers and materials are skipped, never created. A ready-to-use sample for the seeded demo DB lives at `data/sample_orders.csv`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/data/orders/import \
  -F "file=@data/sample_orders.csv" \
  -F "due_date=2026-05-09"
```

The response includes `received`, `inserted`, `skipped`, the list of `unknown_customers`, the list of `unknown_materials`, and the first 200 per-row errors.

## JSON DB CLI

Use CLI for quick local reads/writes without running the API.

macOS / Linux:

```bash
.venv/bin/python db_cli.py tables
.venv/bin/python db_cli.py schema warehouses
.venv/bin/python db_cli.py list warehouses --limit 5
.venv/bin/python db_cli.py insert notes --data '{"title":"test"}'
.venv/bin/python db_cli.py update notes <row_id> --data '{"done":true}'
.venv/bin/python db_cli.py delete notes <row_id>
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe db_cli.py tables
.\.venv\Scripts\python.exe db_cli.py schema warehouses
.\.venv\Scripts\python.exe db_cli.py list warehouses --limit 5
.\.venv\Scripts\python.exe db_cli.py insert notes --data "{\"title\":\"test\"}"
.\.venv\Scripts\python.exe db_cli.py update notes <row_id> --data "{\"done\":true}"
.\.venv\Scripts\python.exe db_cli.py delete notes <row_id>
```

## Demo Data

The app runs from `data/app_db.json`. Raw Excel workbooks and processed snapshots are not part of the runtime anymore. To seed new orders for testing the optimizer, use the CSV import endpoint above or `db_cli.py insert orders ...`.
