"""Driver analysis: which segments and which funnel factors explain a KPI change.

All arithmetic is deterministic and exact:
 * Segment contribution (ratio metric M = sum_i w_i * m_i, w_i = share of denominator, m_i = segment ratio)
     delta M = sum_i [ avg(w_i) * delta m_i ]      <- "rate effect" (segment got better/worse)
             + sum_i [ delta w_i * (avg(m_i) - avg(M)) ]   <- "mix effect" (budget/traffic shifted between segments)
   The identity is exact, so contributions always sum to the total change (verified by tests).
 * Funnel-factor decomposition: a ratio such as ROAS is a product of stage ratios
   (impressions/$ x CTR x click->session x CVR x AOV). ln(M1/M0) splits additively across the factors.
"""
from __future__ import annotations

import math

from ..semantic.warehouse import Warehouse
from .base import ToolResult, pct_change


def _by_segment(wh: Warehouse, dim_cols: list[str], period, platform):
    rows, sql = wh.components(dim_cols, period[0], period[1], platform)
    key = lambda r: r[wh.registry.dimension_column(dim_cols[0])]  # noqa: E731
    return {key(r): r for r in rows}, sql


def driver_analysis(wh: Warehouse, metric: str, dimension: str, current, baseline,
                    platform: str | None = None, top_n: int = 5) -> ToolResult:
    reg = wh.registry
    m = reg.get(metric)
    dims = [dimension] if dimension == "campaign_id" else [dimension]
    group = ["campaign_id", "campaign"] if dimension == "campaign_id" else [dimension]
    # fetch both periods grouped by the segment
    rows1, sql1 = wh.components(group, current[0], current[1], platform)
    rows0, sql0 = wh.components(group, baseline[0], baseline[1], platform)
    kcol = reg.dimension_column(group[0])
    cur = {r[kcol]: r for r in rows1}
    base = {r[kcol]: r for r in rows0}
    names = {r[kcol]: r.get(reg.dimension_column("campaign")) for r in [*rows0, *rows1]} if dimension == "campaign_id" else {}
    keys = sorted(set(cur) | set(base))
    tot1, tot0 = (lambda rs: {ms: sum((r.get(ms) or 0) for r in rs) for ms in reg.measures})(rows1), \
                 (lambda rs: {ms: sum((r.get(ms) or 0) for r in rs) for ms in reg.measures})(rows0)
    M1, M0 = reg.evaluate(metric, tot1), reg.evaluate(metric, tot0)
    if M1 is None or M0 is None:
        raise ValueError(f"{metric} is undefined in one of the periods (zero denominator)")
    delta = M1 - M0

    segs = []
    if m.type == "additive":
        for k in keys:
            v1 = reg.evaluate(metric, cur[k]) if k in cur else 0.0
            v0 = reg.evaluate(metric, base[k]) if k in base else 0.0
            v1, v0 = v1 or 0.0, v0 or 0.0
            segs.append({"segment": k, "name": names.get(k), "value_current": v1, "value_baseline": v0,
                         "rate_effect": v1 - v0, "mix_effect": 0.0, "contribution": v1 - v0})
    else:
        D1 = tot1[m.denominator] or 0.0
        D0 = tot0[m.denominator] or 0.0
        for k in keys:
            c, b = cur.get(k, {}), base.get(k, {})
            d1, d0 = (c.get(m.denominator) or 0.0), (b.get(m.denominator) or 0.0)
            m1 = reg.evaluate(metric, c) if d1 else None
            m0 = reg.evaluate(metric, b) if d0 else None
            if m1 is None and m0 is None:
                continue
            m1_f, m0_f = (m1 if m1 is not None else m0), (m0 if m0 is not None else m1)  # fill so rate effect = 0
            w1, w0 = d1 / D1, d0 / D0
            rate = (w0 + w1) / 2 * (m1_f - m0_f)
            mix = (w1 - w0) * ((m0_f + m1_f) / 2 - (M0 + M1) / 2)
            segs.append({"segment": k, "name": names.get(k), "value_current": m1, "value_baseline": m0,
                         "weight_current": w1, "weight_baseline": w0, "rate_effect": rate, "mix_effect": mix,
                         "contribution": rate + mix,
                         "denominator_current": d1, "denominator_baseline": d0})
    for s in segs:
        c, b = cur.get(s["segment"], {}), base.get(s["segment"], {})
        s.update({"spend_current": c.get("spend") or 0.0, "spend_baseline": b.get("spend") or 0.0,
                  "orders_current": c.get("orders") or 0.0, "orders_baseline": b.get("orders") or 0.0})
        s["spend_pct_change"] = pct_change(s["spend_current"], s["spend_baseline"])
        s["share_of_change"] = s["contribution"] / delta if delta else None
        s["pct_change"] = pct_change(s["value_current"], s["value_baseline"])
    segs.sort(key=lambda s: abs(s["contribution"]), reverse=True)
    recon_err = abs(sum(s["contribution"] for s in segs) - delta)
    data = {"metric": metric, "label": m.label, "dimension": dimension, "platform": platform,
            "total_current": M1, "total_baseline": M0, "total_change": delta, "total_pct_change": pct_change(M1, M0),
            "segments": segs, "top": segs[:top_n], "reconciliation_error": recon_err,
            "method": "Exact rate/mix decomposition; contributions sum to the total change."
            if m.type == "ratio" else "Per-segment difference; contributions sum to the total change."}
    return ToolResult("driver_analysis", {"metric": metric, "dimension": dimension, "current": list(current),
                                          "baseline": list(baseline), "platform": platform}, data, sql=[sql1, sql0])


def factor_decomposition(wh: Warehouse, metric: str, current, baseline, platform: str | None = None,
                         campaign_ids: list[str] | None = None) -> ToolResult:
    m = wh.registry.get(metric)
    if not m.driver_chain:
        raise ValueError(f"{metric} has no driver_chain in the semantic layer")
    rows1, sql1 = wh.components([], current[0], current[1], platform, campaign_ids)
    rows0, sql0 = wh.components([], baseline[0], baseline[1], platform, campaign_ids)
    c1, c0 = rows1[0], rows0[0]
    total_log = math.log(wh.registry.evaluate(metric, c1) / wh.registry.evaluate(metric, c0))
    factors = []
    for link in m.driver_chain:
        f1 = c1[link["num"]] / c1[link["den"]]
        f0 = c0[link["num"]] / c0[link["den"]]
        lc = math.log(f1 / f0)
        factors.append({"factor": link["name"], "value_current": f1, "value_baseline": f0,
                        "pct_change": f1 / f0 - 1, "log_contribution": lc,
                        "share_of_change": lc / total_log if total_log else None})
    factors.sort(key=lambda f: abs(f["log_contribution"]), reverse=True)
    same_sign = [f for f in factors if f["log_contribution"] * total_log > 0]
    dominant = (same_sign or factors)[0]["factor"]
    return ToolResult("factor_decomposition",
                      {"metric": metric, "current": list(current), "baseline": list(baseline),
                       "platform": platform, "campaign_ids": campaign_ids},
                      {"metric": metric, "total_log_change": total_log, "factors": factors,
                       "dominant_factor": dominant,
                       "reconciliation_error": abs(sum(f["log_contribution"] for f in factors) - total_log),
                       "method": "Log decomposition of the metric into its funnel-stage ratios (exact)."},
                      sql=[sql1, sql0])
