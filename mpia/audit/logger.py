"""Investigation logs and audit records (Postgres, `audit` schema, written as least-privilege role agent_rw)."""
from __future__ import annotations

import json
import uuid

from psycopg.types.json import Jsonb

from .. import db


def _j(obj):
    return Jsonb(json.loads(json.dumps(obj, default=str)))


class AuditLogger:
    ROLE = "agent_rw"

    def start_investigation(self, question: str, user: str) -> str:
        inv_id = "INV-" + uuid.uuid4().hex[:10].upper()
        db.execute(self.ROLE, "INSERT INTO audit.investigations (investigation_id, requested_by, question) "
                              "VALUES (%s, %s, %s)", (inv_id, user, question))
        return inv_id

    def set_intent(self, inv_id: str, intent: dict, interpreter: str) -> None:
        db.execute(self.ROLE, "UPDATE audit.investigations SET intent = %s, interpreter = %s WHERE investigation_id = %s",
                   (_j(intent), interpreter, inv_id))

    def log_tool_call(self, inv_id: str, node: str, tool: str, inputs: dict, output_summary: dict | None,
                      sql: list[str] | None, status: str, error: str | None, duration_ms: int) -> None:
        db.execute(self.ROLE, """INSERT INTO audit.tool_calls
            (investigation_id, node, tool, inputs, output_summary, sql_executed, status, error, duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (inv_id, node, tool, _j(inputs), _j(output_summary), _j(sql or []), status, error, duration_ms))

    def finish(self, inv_id: str, status: str, answer: dict | None, duration_ms: int) -> None:
        db.execute(self.ROLE, "UPDATE audit.investigations SET status=%s, answer=%s, duration_ms=%s "
                              "WHERE investigation_id=%s", (status, _j(answer), duration_ms, inv_id))

    # -- reads (for UI / evals) ----------------------------------------------------------
    def list_investigations(self, limit: int = 50) -> list[dict]:
        return db.query(self.ROLE, "SELECT investigation_id, created_at, requested_by, question, interpreter, status, "
                                   "duration_ms FROM audit.investigations ORDER BY created_at DESC LIMIT %s", (limit,))

    def get_investigation(self, inv_id: str) -> dict | None:
        rows = db.query(self.ROLE, "SELECT * FROM audit.investigations WHERE investigation_id = %s", (inv_id,))
        if not rows:
            return None
        inv = rows[0]
        inv["tool_calls"] = db.query(self.ROLE, "SELECT call_id, node, tool, inputs, output_summary, sql_executed, status, "
                                                "error, duration_ms, created_at FROM audit.tool_calls "
                                                "WHERE investigation_id = %s ORDER BY call_id", (inv_id,))
        inv["actions"] = db.query(self.ROLE, "SELECT * FROM audit.proposed_actions WHERE investigation_id = %s", (inv_id,))
        return inv

    def audit_trail_for_action(self, action_id: str) -> dict:
        return {
            "approvals": db.query(self.ROLE, "SELECT * FROM audit.approvals WHERE action_id=%s ORDER BY approval_id", (action_id,)),
            "executions": db.query(self.ROLE, "SELECT * FROM audit.executions WHERE action_id=%s ORDER BY execution_id", (action_id,)),
        }
