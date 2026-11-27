"""Mock marketing-platform API (stand-in for Meta/Google Ads budget endpoints).

 * POST /v1/budgets/apply  requires a valid HMAC approval token and an Idempotency-Key header.
 * Replaying the same Idempotency-Key returns the stored response and applies nothing twice.
Run:  uvicorn mpia.actions.mock_api:app --port 8000      Seed:  python -m mpia.actions.mock_api seed
"""
from __future__ import annotations

import hmac
import sys

from fastapi import FastAPI, Header, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .. import db
from .service import sign_approval

ROLE = "mock_api_rw"


class Change(BaseModel):
    campaign_id: str
    daily_budget: float = Field(gt=0)


class ApplyRequest(BaseModel):
    action_id: str
    approved_by: str
    approval_token: str
    changes: list[Change]


def create_app() -> FastAPI:
    app = FastAPI(title="Mock Marketing API", version="1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/campaigns/budgets")
    def budgets():
        return db.query(ROLE, "SELECT campaign_id, daily_budget::float AS daily_budget, updated_at, updated_by "
                              "FROM mock_ads.campaign_budgets ORDER BY campaign_id")

    @app.post("/v1/budgets/apply")
    def apply(req: ApplyRequest, idempotency_key: str | None = Header(default=None)):
        if not idempotency_key:
            raise HTTPException(400, "Idempotency-Key header is required")
        changes = [c.model_dump() for c in req.changes]
        expected = sign_approval(req.action_id, changes, req.approved_by)
        if not hmac.compare_digest(expected, req.approval_token or ""):
            raise HTTPException(403, "Missing or invalid approval token - change not applied")

        with db.connect(ROLE, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT response FROM mock_ads.idempotency_keys WHERE idempotency_key=%s", (idempotency_key,))
                prev = cur.fetchone()
                if prev:
                    return {**prev["response"], "idempotent_replay": True}
                cur.execute("SELECT campaign_id, daily_budget FROM mock_ads.campaign_budgets WHERE campaign_id = ANY(%s)",
                            ([c["campaign_id"] for c in changes],))
                old = {r["campaign_id"]: float(r["daily_budget"]) for r in cur.fetchall()}
                unknown = [c["campaign_id"] for c in changes if c["campaign_id"] not in old]
                if unknown:
                    raise HTTPException(422, f"Unknown campaigns: {unknown}")
                for c in changes:
                    cur.execute("UPDATE mock_ads.campaign_budgets SET daily_budget=%s, updated_at=now(), updated_by=%s "
                                "WHERE campaign_id=%s", (c["daily_budget"], req.approved_by, c["campaign_id"]))
                    cur.execute("INSERT INTO mock_ads.budget_change_log (action_id, campaign_id, old_daily_budget, "
                                "new_daily_budget, approved_by) VALUES (%s,%s,%s,%s,%s)",
                                (req.action_id, c["campaign_id"], old[c["campaign_id"]], c["daily_budget"], req.approved_by))
                resp = {"status": "applied", "action_id": req.action_id, "campaigns_updated": len(changes),
                        "idempotent_replay": False}
                cur.execute("INSERT INTO mock_ads.idempotency_keys (idempotency_key, action_id, response) VALUES (%s,%s,%s)",
                            (idempotency_key, req.action_id, Jsonb(resp)))
            conn.commit()
        return resp

    return app


app = create_app()


def seed_budgets() -> int:
    """Initialise mock budgets from each campaign's average daily spend over the last 28 days (admin task)."""
    rows = db.query(None, """
        SELECT campaign_id, round(sum(spend) / 28.0, 2) AS daily
        FROM marts.mart_campaign_daily
        WHERE is_paid AND date_day > (SELECT max(date_day) FROM marts.mart_campaign_daily) - 28
        GROUP BY campaign_id""")
    with db.connect(None) as conn:
        conn.execute("TRUNCATE mock_ads.campaign_budgets, mock_ads.budget_change_log, mock_ads.idempotency_keys")
        for r in rows:
            conn.execute("INSERT INTO mock_ads.campaign_budgets (campaign_id, daily_budget, updated_by) VALUES (%s,%s,'seed')",
                         (r["campaign_id"], r["daily"]))
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        print(f"seeded {seed_budgets()} campaign budgets")
    else:
        print(__doc__)
