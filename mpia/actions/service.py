"""Human-approval workflow for agent-proposed actions.

State machine (persisted in Postgres, so it survives restarts):
  pending_approval -> approved -> executed | execution_failed
                   -> rejected
Nothing reaches the (mock) marketing API without (1) an authorised human decision, (2) passing deterministic
guardrails, and (3) a signed approval token that the API verifies independently.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import uuid

import httpx
from psycopg.types.json import Jsonb

from .. import config, db
from . import guardrails

APPROVER_ROLES = {"marketing_manager", "admin"}
ROLE = "agent_rw"


class ApprovalError(Exception):
    pass


def payload_digest(changes: list[dict]) -> str:
    canon = sorted(({"campaign_id": c["campaign_id"], "daily_budget": round(float(c["daily_budget"]), 2)} for c in changes),
                   key=lambda c: c["campaign_id"])
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode()).hexdigest()


def sign_approval(action_id: str, changes: list[dict], approved_by: str, secret: str | None = None) -> str:
    msg = f"{action_id}|{payload_digest(changes)}|{approved_by}".encode()
    return hmac.new((secret or config.APPROVAL_SECRET).encode(), msg, hashlib.sha256).hexdigest()


class ActionService:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(base_url=config.MOCK_API_URL, timeout=10)

    # -- proposals -----------------------------------------------------------------------
    def create_proposal(self, investigation_id: str | None, payload: dict, action_type: str = "update_campaign_budgets") -> str:
        problems = guardrails.validate_budget_payload(payload)
        if problems:
            raise ApprovalError("Agent proposal violates guardrails: " + "; ".join(problems))
        action_id = "ACT-" + uuid.uuid4().hex[:10].upper()
        db.execute(ROLE, "INSERT INTO audit.proposed_actions (action_id, investigation_id, action_type, payload) "
                         "VALUES (%s,%s,%s,%s)", (action_id, investigation_id, action_type,
                                                  Jsonb(json.loads(json.dumps(payload, default=str)))))
        return action_id

    def get(self, action_id: str) -> dict | None:
        rows = db.query(ROLE, "SELECT * FROM audit.proposed_actions WHERE action_id=%s", (action_id,))
        return rows[0] if rows else None

    def list_actions(self, status: str | None = None) -> list[dict]:
        if status:
            return db.query(ROLE, "SELECT * FROM audit.proposed_actions WHERE status=%s ORDER BY created_at DESC", (status,))
        return db.query(ROLE, "SELECT * FROM audit.proposed_actions ORDER BY created_at DESC LIMIT 50")

    # -- decisions -----------------------------------------------------------------------
    def decide(self, action_id: str, user: str, role: str, decision: str, edits: dict[str, float] | None = None,
               comment: str | None = None) -> dict:
        """decision: 'approve' | 'reject'. edits: {campaign_id: new_daily_budget} (human override)."""
        action = self.get(action_id)
        if not action:
            raise ApprovalError(f"Unknown action {action_id}")
        if action["status"] != "pending_approval":
            raise ApprovalError(f"Action {action_id} is '{action['status']}', not pending approval.")
        if role not in APPROVER_ROLES:
            db.execute(ROLE, "INSERT INTO audit.approvals (action_id, decided_by, role, decision, comment) VALUES (%s,%s,%s,'denied',%s)",
                       (action_id, user, role, f"role '{role}' may not approve actions"))
            raise PermissionError(f"Role '{role}' is not allowed to approve or reject actions.")

        payload = copy.deepcopy(action["payload"])
        if decision == "reject":
            db.execute(ROLE, "INSERT INTO audit.approvals (action_id, decided_by, role, decision, comment) VALUES (%s,%s,%s,'rejected',%s)",
                       (action_id, user, role, comment))
            db.execute(ROLE, "UPDATE audit.proposed_actions SET status='rejected' WHERE action_id=%s", (action_id,))
            return {"action_id": action_id, "status": "rejected"}
        if decision != "approve":
            raise ApprovalError("decision must be 'approve' or 'reject'")

        edited = False
        for ch in payload["changes"]:
            if edits and ch["campaign_id"] in edits and round(float(edits[ch["campaign_id"]]), 2) != ch["proposed_daily"]:
                ch["proposed_daily"] = round(float(edits[ch["campaign_id"]]), 2)
                edited = True
        problems = guardrails.validate_budget_payload(payload)
        if problems:
            raise ApprovalError("Guardrails blocked this approval: " + "; ".join(problems))

        db.execute(ROLE, "INSERT INTO audit.approvals (action_id, decided_by, role, decision, edited, comment) VALUES (%s,%s,%s,'approved',%s,%s)",
                   (action_id, user, role, edited, comment))
        db.execute(ROLE, "UPDATE audit.proposed_actions SET status='approved', final_payload=%s WHERE action_id=%s",
                   (Jsonb(payload), action_id))
        return self._execute(action_id, payload, user)

    def _execute(self, action_id: str, payload: dict, approved_by: str) -> dict:
        changes = [{"campaign_id": c["campaign_id"], "daily_budget": c["proposed_daily"]} for c in payload["changes"]]
        token = sign_approval(action_id, changes, approved_by)
        idem = f"idem-{action_id}"
        body = {"action_id": action_id, "approved_by": approved_by, "approval_token": token, "changes": changes}
        try:
            resp = self.http.post("/v1/budgets/apply", json=body, headers={"Idempotency-Key": idem})
            status_code, out = resp.status_code, resp.json()
        except Exception as e:  # network failure etc.
            status_code, out = 0, {"error": str(e)}
        ok = status_code == 200
        db.execute(ROLE, "INSERT INTO audit.executions (action_id, idempotency_key, http_status, response) VALUES (%s,%s,%s,%s)",
                   (action_id, idem, status_code, Jsonb(out)))
        db.execute(ROLE, "UPDATE audit.proposed_actions SET status=%s WHERE action_id=%s",
                   ("executed" if ok else "execution_failed", action_id))
        return {"action_id": action_id, "status": "executed" if ok else "execution_failed",
                "http_status": status_code, "response": out}
