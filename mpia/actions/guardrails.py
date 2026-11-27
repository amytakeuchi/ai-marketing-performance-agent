"""Deterministic guardrails applied to every proposed/edited budget change, independent of the LLM."""
from __future__ import annotations

MAX_CHANGE_PCT = 0.50      # hard per-campaign limit (agent targets +/-30%; humans may edit up to +/-50%)
TOTAL_TOLERANCE = 0.01     # approved total may not exceed the budget cap by more than 1%


def validate_budget_payload(payload: dict) -> list[str]:
    """Return a list of human-readable violations (empty list = OK)."""
    problems: list[str] = []
    changes = payload.get("changes") or []
    if not changes:
        problems.append("No budget changes in payload.")
    seen = set()
    total = 0.0
    for c in changes:
        cid = c.get("campaign_id")
        if cid in seen:
            problems.append(f"Duplicate campaign {cid}.")
        seen.add(cid)
        new, cur = c.get("proposed_daily"), c.get("current_daily")
        if not isinstance(new, (int, float)) or new <= 0:
            problems.append(f"{cid}: proposed daily budget must be a positive number.")
            continue
        total += new
        if cur and abs(new / cur - 1) > MAX_CHANGE_PCT + 1e-9:
            problems.append(f"{cid}: change of {(new / cur - 1) * 100:+.0f}% exceeds the +/-{int(MAX_CHANGE_PCT * 100)}% limit.")
    cap = payload.get("total_daily_budget")
    if cap and total > cap * (1 + TOTAL_TOLERANCE):
        problems.append(f"Total daily budget ${total:,.2f} exceeds the approved cap ${cap:,.2f}.")
    return problems
