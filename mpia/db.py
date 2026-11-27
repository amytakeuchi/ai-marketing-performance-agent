"""Thin psycopg helpers. Each runtime role gets its own least-privilege connection."""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from . import config


def conninfo(role: str | None = None, dbname: str | None = None) -> str:
    if role is None:
        user, pw = config.ADMIN_USER, config.ADMIN_PASSWORD
    else:
        user, pw = role, config.ROLES[role]
    db = dbname or config.PGDATABASE
    return f"host={config.PGHOST} port={config.PGPORT} dbname={db} user={user} password={pw}"


def connect(role: str | None = None, dbname: str | None = None, autocommit: bool = True) -> psycopg.Connection:
    opts = "-c default_transaction_read_only=on" if role == "analyst_ro" else ""
    return psycopg.connect(
        conninfo(role, dbname), row_factory=dict_row, autocommit=autocommit,
        options=opts or None,
    )


def query(role: str | None, sql: str, params: dict | tuple | None = None) -> list[dict]:
    with connect(role) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def execute(role: str | None, sql: str, params: dict | tuple | None = None) -> None:
    with connect(role) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
