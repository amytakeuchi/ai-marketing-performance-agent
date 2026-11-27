"""Load generated CSVs into the raw.* schema (idempotent: tables are recreated).

Usage: python -m mpia.datagen.load_raw
"""
from __future__ import annotations

import csv

from .. import config, db

DDL = {
    "campaigns": "campaign_id text, campaign_name text, platform text, funnel_stage text",
    "landing_pages": "landing_page_id text, path text, page_type text",
    "ad_performance": ("date date, campaign_id text, impressions bigint, clicks bigint, spend numeric(14,2), "
                       "platform_reported_conversions int, platform_reported_revenue numeric(14,2)"),
    "web_analytics": ("date date, campaign_id text, landing_page_id text, device text, sessions int, "
                      "add_to_carts int, checkouts int, purchases int"),
    "orders": ("order_id text, order_ts timestamp, customer_id text, campaign_id text, "
               "revenue numeric(14,2), is_new_customer boolean"),
    "customers": "customer_id text, first_order_ts timestamp, acquisition_campaign_id text",
}


def main() -> None:
    with db.connect(None) as conn:
        for table, cols in DDL.items():
            path = config.RAW_DIR / f"{table}.csv"
            if not path.exists():
                raise SystemExit(f"{path} not found - run `python -m mpia.datagen.generate` first")
            conn.execute(f"DROP TABLE IF EXISTS raw.{table} CASCADE")
            conn.execute(f"CREATE TABLE raw.{table} ({cols})")
            with open(path, newline="") as f, conn.cursor() as cur:
                header = next(csv.reader(f))
                f.seek(0)
                with cur.copy(f"COPY raw.{table} ({', '.join(header)}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                    while chunk := f.read(1 << 20):
                        cp.write(chunk)
            n = conn.execute(f"SELECT count(*) AS n FROM raw.{table}").fetchone()["n"]
            print(f"raw.{table:15s} {n:>8,d} rows")


if __name__ == "__main__":
    main()
