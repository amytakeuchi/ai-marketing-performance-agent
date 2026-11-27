"""Command-line interface.

  python -m mpia.agent.cli ask "Why did Meta ROAS decline in October compared with September?"
  python -m mpia.agent.cli pending
  python -m mpia.agent.cli approve ACT-XXXX --user amy --role marketing_manager [--edit META_RETARG=120]
  python -m mpia.agent.cli reject  ACT-XXXX --user amy --role marketing_manager
"""
from __future__ import annotations

import argparse
import json
import sys

from ..actions.service import ActionService, ApprovalError
from .graph import run_investigation


def print_answer(a: dict) -> None:
    print(f"\n[{a['status']}] {a['investigation_id']}  ({a['duration_ms']} ms, interpreter={a['interpreter']})")
    if a["status"] != "completed":
        print(a["message"])
        return
    print("\nSUMMARY\n" + a["summary"])
    print("\nFINDINGS")
    for f in a["findings"]:
        print(f"  - {f['text']}  {f['evidence']}")
    if a["hypotheses"]:
        print("\nHYPOTHESES (unverified)")
        for h in a["hypotheses"]:
            print("  ?", h)
    if a["recommendations"]:
        print("\nRECOMMENDATIONS")
        for r in a["recommendations"]:
            print(f"  * {r['text']}\n      why: {r['rationale']}")
    if a["limitations"]:
        print("\nLIMITATIONS")
        for l in a["limitations"]:
            print("  !", l)
    if a["assumptions"]:
        print("\nASSUMPTIONS")
        for s in a["assumptions"]:
            print("  ~", s)
    if a["proposed_action_id"]:
        print(f"\nPROPOSED ACTION {a['proposed_action_id']} is pending approval (see `pending` / `approve`).")
    print(f"\ngrounding={a.get('grounding_rate', 1):.0%}  evidence items={len(a['evidence'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mpia")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--user", default="cli"); p.add_argument("--json", action="store_true")
    sub.add_parser("pending")
    for name in ("approve", "reject"):
        q = sub.add_parser(name); q.add_argument("action_id"); q.add_argument("--user", required=True)
        q.add_argument("--role", default="viewer"); q.add_argument("--comment")
        if name == "approve":
            q.add_argument("--edit", action="append", default=[], help="CAMPAIGN_ID=new_daily_budget")
    args = ap.parse_args(argv)

    if args.cmd == "ask":
        ans = run_investigation(args.question, args.user)
        print(json.dumps(ans, indent=2, default=str)) if args.json else print_answer(ans)
        return 0
    svc = ActionService()
    if args.cmd == "pending":
        for a in svc.list_actions("pending_approval"):
            print(a["action_id"], a["created_at"], f"{len(a['payload']['changes'])} campaigns, budget ${a['payload']['total_monthly_budget']:,.0f}/mo")
        return 0
    try:
        edits = dict(e.split("=", 1) for e in getattr(args, "edit", []))
        out = svc.decide(args.action_id, args.user, args.role, args.cmd, {k: float(v) for k, v in edits.items()}, args.comment)
        print(json.dumps(out, indent=2, default=str))
        return 0
    except (ApprovalError, PermissionError) as e:
        print("DENIED:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
