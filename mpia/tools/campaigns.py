"""Rank under-performing campaigns with a transparent priority score.

priority_score = current_spend x (0.6 x shortfall_vs_peers + 0.4 x roas_decline)
  shortfall_vs_peers = max(0, 1 - campaign_ROAS / peer_ROAS)   (peers = all paid campaigns in the same funnel stage)
  roas_decline       = max(0, -(ROAS change vs baseline))
Campaigns below the volume floor are listed separately instead of being ranked (their ratios are mostly noise).
"""
from __future__ import annotations

from ..semantic.warehouse import Warehouse
from .base import ToolResult, pct_change

MIN_SPEND, MIN_ORDERS = 1000.0, 30


def rank_underperformers(wh: Warehouse, current, baseline, platform: str | None = None, top_n: int = 5) -> ToolResult:
    reg = wh.registry
    g = ["campaign_id", "campaign", "platform", "funnel_stage"]
    cur, sql1 = wh.components(g, current[0], current[1], platform)
    base, sql0 = wh.components(g, baseline[0], baseline[1], platform)
    peers, sql_p = wh.components(["funnel_stage"], current[0], current[1], None)   # peers span all platforms
    peer_roas = {r["funnel_stage"]: reg.evaluate("roas", r) for r in peers}
    base_by = {r["campaign_id"]: r for r in base}

    ranked, low_volume = [], []
    for r in cur:
        b = base_by.get(r["campaign_id"], {})
        roas, roas_b = reg.evaluate("roas", r), reg.evaluate("roas", b) if b else None
        cpa, cpa_b = reg.evaluate("cpa", r), reg.evaluate("cpa", b) if b else None
        peer = peer_roas.get(r["funnel_stage"])
        row = {"campaign_id": r["campaign_id"], "campaign": r["campaign_name"], "platform": r["platform"],
               "funnel_stage": r["funnel_stage"], "spend": r["spend"], "spend_baseline": b.get("spend"),
               "orders": r["orders"], "revenue": r["revenue"], "roas": roas, "roas_baseline": roas_b,
               "roas_change": pct_change(roas, roas_b), "cpa": cpa, "cpa_baseline": cpa_b,
               "cpa_change": pct_change(cpa, cpa_b), "peer_roas": peer,
               "spend_change": pct_change(r["spend"], b.get("spend"))}
        if (r["spend"] or 0) < MIN_SPEND or (r["orders"] or 0) < MIN_ORDERS or roas is None or not peer:
            low_volume.append(row)
            continue
        shortfall = max(0.0, 1 - roas / peer)
        decline = max(0.0, -(row["roas_change"] or 0.0))
        row.update({"shortfall_vs_peers": shortfall, "roas_decline": decline,
                    "priority_score": r["spend"] * (0.6 * shortfall + 0.4 * decline)})
        ranked.append(row)
    ranked.sort(key=lambda x: x["priority_score"], reverse=True)
    return ToolResult("rank_underperformers", {"current": list(current), "baseline": list(baseline), "platform": platform},
                      {"ranked": ranked, "top": ranked[:top_n], "low_volume": low_volume,
                       "peer_roas": peer_roas,
                       "method": "priority_score = spend x (0.6 x shortfall vs funnel-stage peers + 0.4 x ROAS decline)",
                       "volume_floor": {"min_spend": MIN_SPEND, "min_orders": MIN_ORDERS}},
                      sql=[sql1, sql0, sql_p])
