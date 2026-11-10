"""Persistencia SQLite. Datos personales cifrados; consultas parametrizadas."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings
from core import security

SCHEMA = """
CREATE TABLE IF NOT EXISTS avaluos (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    cedula_index TEXT NOT NULL,
    matricula TEXT NOT NULL,
    direccion TEXT NOT NULL,
    payload_enc TEXT NOT NULL
)"""

LIST_COLS = ("id", "created_at", "created_by", "matricula", "direccion")


class Repository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(SCHEMA)

    def save(self, user: str, payload: dict) -> str:
        avaluo_id = uuid.uuid4().hex
        row = (
            avaluo_id,
            datetime.now(timezone.utc).isoformat(),
            user,
            security.blind_index(str(payload.get("cedula", ""))),
            payload.get("matricula", ""),
            payload.get("direccion", ""),
            security.encrypt(json.dumps(payload, ensure_ascii=False, default=str)),
        )
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("INSERT INTO avaluos VALUES (?,?,?,?,?,?,?)", row)
        return avaluo_id

    def list_recent(self, limit: int = 50) -> list[dict]:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            rows = conn.execute(
                "SELECT id, created_at, created_by, matricula, direccion "
                "FROM avaluos ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(zip(LIST_COLS, r)) for r in rows]

    def get(self, avaluo_id: str) -> dict | None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute("SELECT payload_enc FROM avaluos WHERE id = ?", (avaluo_id,)).fetchone()
        return json.loads(security.decrypt(row[0])) if row else None

    def find_by_cedula(self, cedula: str) -> list[dict]:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            rows = conn.execute(
                "SELECT id, created_at, matricula, direccion FROM avaluos WHERE cedula_index = ?",
                (security.blind_index(cedula),),
            ).fetchall()
        return [dict(zip(("id", "created_at", "matricula", "direccion"), r)) for r in rows]
