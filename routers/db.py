from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from services.database import db_service


router = APIRouter(prefix="/api/v1/db", tags=["db"])


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "id" in payload:
        raise HTTPException(status_code=400, detail="Payload must not include id")
    return payload


@router.get("/tables")
def list_tables() -> dict[str, int]:
    return db_service.list_tables()


@router.get("/{table}/schema")
def describe_table(table: str) -> dict[str, list[str]]:
    return db_service.describe_table(table)


@router.get("/{table}")
def list_rows(table: str, limit: int = Query(default=100, ge=1, le=10000)) -> list[dict[str, Any]]:
    return db_service.list_rows(table, limit=limit)


@router.get("/{table}/{row_id}")
def get_row(table: str, row_id: int) -> dict[str, Any]:
    row = db_service.get_row(table, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return row


@router.post("/{table}", status_code=201)
def insert_row(table: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return db_service.insert_row(table, _validate_payload(payload))


@router.patch("/{table}/{row_id}")
def update_row(table: str, row_id: int, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    row = db_service.update_row(table, row_id, _validate_payload(payload))
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return row


@router.delete("/{table}/{row_id}")
def delete_row(table: str, row_id: int) -> dict[str, Any]:
    row = db_service.delete_row(table, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return row
