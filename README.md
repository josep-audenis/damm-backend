# damm-backend

Backend API for Damm route/catalog data. Local database is JSON at `data/app_db.json`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run API

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/app/
http://127.0.0.1:8000/docs
```

If port `8000` is busy:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8001
```

## Test

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

Example:

```powershell
curl http://127.0.0.1:8000/api/v1/db/warehouses?limit=1
curl -X POST http://127.0.0.1:8000/api/v1/db/notes -H "Content-Type: application/json" -d "{\"title\":\"test\"}"
curl -X PATCH http://127.0.0.1:8000/api/v1/db/notes/1 -H "Content-Type: application/json" -d "{\"done\":true}"
```

## JSON DB CLI

Use CLI for quick local reads/writes without running API.

```powershell
.\.venv\Scripts\python.exe db_cli.py tables
.\.venv\Scripts\python.exe db_cli.py schema warehouses
.\.venv\Scripts\python.exe db_cli.py list warehouses --limit 5
.\.venv\Scripts\python.exe db_cli.py insert notes --data "{\"title\":\"test\"}"
.\.venv\Scripts\python.exe db_cli.py update notes 1 --data "{\"done\":true}"
.\.venv\Scripts\python.exe db_cli.py delete notes 1
```

## Demo Data

The app runs from `data/app_db.json`. Raw Excel workbooks and processed snapshots are not part of the runtime anymore.
