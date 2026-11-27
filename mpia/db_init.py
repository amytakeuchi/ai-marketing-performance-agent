"""Create the database (if needed), schemas, least-privilege roles, audit and mock-API tables.

Usage: python -m mpia.db_init
"""
from __future__ import annotations

from pathlib import Path

import psycopg

from . import config, db

SQL_DIR = config.ROOT / "sql" / "init"


def main() -> None:
    # 1) create database if missing
    with psycopg.connect(db.conninfo(None, dbname="postgres"), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.PGDATABASE,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{config.PGDATABASE}"')
            print(f"created database {config.PGDATABASE}")

    # 2) run init scripts (idempotent)
    subs = {
        "analyst_ro_pw": config.ROLES["analyst_ro"],
        "agent_rw_pw": config.ROLES["agent_rw"],
        "mock_api_rw_pw": config.ROLES["mock_api_rw"],
    }
    with psycopg.connect(db.conninfo(None), autocommit=True) as conn:
        for f in sorted(Path(SQL_DIR).glob("*.sql")):
            sql = f.read_text()
            for k, v in subs.items():
                sql = sql.replace("{" + k + "}", v)
            conn.execute(sql)
            print(f"ran {f.name}")
        conn.execute(f'GRANT CONNECT ON DATABASE "{config.PGDATABASE}" TO analyst_ro, agent_rw, mock_api_rw')


if __name__ == "__main__":
    main()
