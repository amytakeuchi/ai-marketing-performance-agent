"""Budget re-allocation with explicit method, constraints and uncertainty.

Method
  1. For each campaign fit a diminishing-returns response curve on complete ISO weeks:
        daily_revenue = a * daily_spend ** b      (log-log OLS; b clipped to [0.2, 1.0])
     b < 1 means each extra dollar earns less than the last.
  2. Campaigns whose curve cannot be identified (slope t-statistic < 2 or < 8 weeks) are held flat.
  3. Brand-search campaigns are held flat by policy: they capture existing demand, so last-click ROAS
     overstates what extra budget would earn (a modelling limit, not something this data can resolve).
  4. Allocate the budget by equalising marginal revenue (greedy on a concave objective) subject to
        sum(spend) == budget and |change| <= max_shift per campaign.
  5. Bootstrap weeks (500x) to put an interval on the modelled uplift.
This is a model of historical, last-click-attributed correlation. It is NOT an incrementality
estimate and not a forecast.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from ..semantic.warehouse import Warehouse
from .base import ToolResult

B_MIN, B_MAX = 0.2, 1.0
MIN_WEEKS, MIN_T = 8, 2.0


def _fit(s: np.ndarray, r: np.ndarray) -> tuple[float, float, float, float]:
    """Return (a, b, r2, t_stat) for r = a * s**b with b clipped to [B_MIN, B_MAX]."""
    x, y = np.log(s), np.log(r)
    if np.ptp(x) < 1e-6 or len(x) < 3:
        return float(np.exp(y.mean() - 0.5 * x.mean())), 0.5, 0.0, 0.0
    b_raw, c = np.polyfit(x, y, 1)
    resid = y - (b_raw * x + c)
    sxx = float(((x - x.mean()) ** 2).sum())
    se = float(np.sqrt((resid ** 2).sum() / max(len(x) - 2, 1) / sxx)) if sxx else float("inf")
    t = float(b_raw / se) if se > 0 else 0.0
    r2 = float(np.corrcoef(x, y)[0, 1] ** 2)
    b = float(np.clip(b_raw, B_MIN, B_MAX))
    a = float(np.exp((y - b * x).mean()))
    return a, b, r2, t


def _rev(a: float, b: float, s: float) -> float:
    return a * max(s, 1e-9) ** b


def _allocate(curves: dict, current: dict, T: float, max_shift: float) -> dict:
    lo = {k: (1 - max_shift) * current[k] if curves[k]["usable"] else current[k] for k in current}
    hi = {k: (1 + max_shift) * current[k] if curves[k]["usable"] else current[k] for k in current}
    x = dict(lo)
    remaining = T - sum(x.values())
    step = T / 2000
    while remaining > 1e-9:
        cands = [k for k in x if x[k] < hi[k] - 1e-12]
        if not cands:
            break
        k = max(cands, key=lambda k: curves[k]["a"] * curves[k]["b"] * max(x[k], 1e-9) ** (curves[k]["b"] - 1))
        inc = min(step, hi[k] - x[k], remaining)
        x[k] += inc
        remaining -= inc
    return x


def recommend_budget(wh: Warehouse, total_monthly_budget: float, lookback_days: int = 240,
                     max_shift: float = 0.30, as_of: str | None = None, seed: int = 0,
                     hold_stages: tuple[str, ...] = ("brand",)) -> ToolResult:
    as_of_d = date.fromisoformat(as_of or wh.data_range()[1])
    # last complete ISO week ends on a Sunday <= as_of
    last_sun = as_of_d - timedelta(days=(as_of_d.weekday() + 1) % 7)
    start_d = last_sun - timedelta(days=lookback_days - 1)
    start_d = start_d - timedelta(days=start_d.weekday())            # align to Monday
    rows, sql_w = wh.components(["campaign_id", "campaign", "platform", "funnel_stage", "week"], str(start_d), str(last_sun),
                                measures=["spend", "revenue"])
    cur_rows, sql_c = wh.components(["campaign_id"], str(as_of_d - timedelta(days=27)), str(as_of_d), measures=["spend"])
    cur_daily = {r["campaign_id"]: (r["spend"] or 0.0) / 28 for r in cur_rows}
    meta = {r["campaign_id"]: (r["campaign_name"], r["platform"]) for r in rows}
    stage = {r["campaign_id"]: r["funnel_stage"] for r in rows}

    series: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for cid in cur_daily:
        pts = [(r["spend"] / 7, r["revenue"] / 7) for r in rows if r["campaign_id"] == cid and r["spend"] and r["revenue"]]
        series[cid] = (np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))

    T = total_monthly_budget / 30.0
    scale = T / sum(cur_daily.values())
    current = {k: v * scale for k, v in cur_daily.items()}
    curves = {}
    for cid, (s, r) in series.items():
        a, b, r2, tstat = _fit(s, r) if len(s) >= 3 else (0.0, 0.5, 0.0, 0.0)
        identified = len(s) >= MIN_WEEKS and tstat >= MIN_T
        policy = stage.get(cid) in hold_stages
        curves[cid] = {"a": a, "b": b, "r2": r2, "t": tstat, "n_weeks": int(len(s)),
                       "usable": bool(identified and not policy), "policy_hold": policy}

    proposed = _allocate(curves, current, T, max_shift)

    # bootstrap uplift of proposed vs current under refit curves
    rng = np.random.default_rng(seed)
    uplifts = []
    for _ in range(500):
        d_total = 0.0
        for cid, (s, r) in series.items():
            if not curves[cid]["usable"]:
                continue
            idx = rng.integers(0, len(s), len(s))
            a, b, _, _ = _fit(s[idx], r[idx])
            d_total += _rev(a, b, proposed[cid]) - _rev(a, b, current[cid])
        uplifts.append(d_total * 30)
    uplifts = np.array(uplifts)
    cur_model_rev = sum(_rev(curves[k]["a"], curves[k]["b"], current[k]) for k in current) * 30
    prop_model_rev = sum(_rev(curves[k]["a"], curves[k]["b"], proposed[k]) for k in proposed) * 30

    allocs = []
    for cid in sorted(current, key=lambda k: -current[k]):
        c = curves[cid]
        ch = proposed[cid] / current[cid] - 1
        status = ("hold_policy" if c["policy_hold"] else
                  "hold_low_confidence" if not c["usable"] else
                  "increase" if ch > 0.01 else "decrease" if ch < -0.01 else "hold")
        allocs.append({
            "campaign_id": cid, "campaign": meta.get(cid, ("", ""))[0], "platform": meta.get(cid, ("", ""))[1],
            "current_daily": round(current[cid], 2), "proposed_daily": round(proposed[cid], 2),
            "change_pct": ch, "current_monthly": round(current[cid] * 30, 2), "proposed_monthly": round(proposed[cid] * 30, 2),
            "elasticity_b": c["b"], "r2": c["r2"], "t_stat": c["t"], "n_weeks": c["n_weeks"], "status": status,
            "funnel_stage": stage.get(cid),
            "marginal_roas_current": c["a"] * c["b"] * current[cid] ** (c["b"] - 1) if c["usable"] else None,
            "marginal_roas_proposed": c["a"] * c["b"] * proposed[cid] ** (c["b"] - 1) if c["usable"] else None,
        })
    # Round to cents WITHOUT ever stepping outside the +/- max_shift limits (clamp inward), then push the
    # cent-level remainder onto the movable campaign with the most headroom so the total equals the budget.
    import math
    for a in allocs:
        lo, hi = (1 - max_shift) * a["current_daily"], (1 + max_shift) * a["current_daily"]
        if a["status"] in ("increase", "decrease"):
            a["proposed_daily"] = min(max(a["proposed_daily"], math.ceil(lo * 100) / 100), math.floor(hi * 100) / 100)
    diff = round(T - sum(a["proposed_daily"] for a in allocs), 2)
    if abs(diff) >= 0.01:
        def headroom(a):
            cur = a["current_daily"]
            return ((1 + max_shift) * cur - a["proposed_daily"]) if diff > 0 else (a["proposed_daily"] - (1 - max_shift) * cur)
        movable = [a for a in allocs if a["status"] in ("increase", "decrease") and headroom(a) > abs(diff) + 0.01]
        if movable:
            big = max(movable, key=headroom)
            big["proposed_daily"] = round(big["proposed_daily"] + diff, 2)
    for a in allocs:
        a["proposed_daily"] = round(a["proposed_daily"], 2)
        a["proposed_monthly"] = round(a["proposed_daily"] * 30, 2)
        a["change_pct"] = a["proposed_daily"] / a["current_daily"] - 1

    data = {
        "total_monthly_budget": total_monthly_budget, "total_daily_budget": round(T, 2),
        "lookback": {"start": str(start_d), "end": str(last_sun), "weeks": int(max(c["n_weeks"] for c in curves.values()))},
        "max_shift": max_shift, "hold_stages": list(hold_stages), "allocations": allocs,
        "modelled_monthly_revenue_current": cur_model_rev, "modelled_monthly_revenue_proposed": prop_model_rev,
        "modelled_uplift": float(np.median(uplifts)),
        "uplift_interval_level": 0.8, "uplift_p10": float(np.percentile(uplifts, 10)), "uplift_p90": float(np.percentile(uplifts, 90)),
        "prob_uplift_positive": float((uplifts > 0).mean()),
        "uplift_pct": float(np.median(uplifts) / cur_model_rev) if cur_model_rev else None,
        "method": "Per-campaign diminishing-returns curves (revenue = a * spend^b) fitted on weekly data; "
                  "marginal-revenue equalisation under +/- max_shift limits; 500x bootstrap for uncertainty.",
        "caveat": "Historical last-click correlation, not incrementality. Not a forecast or a guarantee.",
        "policies": ["Brand-search campaigns are held flat (they capture existing demand; last-click ROAS overstates incrementality).",
                     f"No campaign moves more than +/-{int(max_shift * 100)}%.",
                     "Campaigns whose spend-response cannot be identified (t < 2 or < 8 weeks) are held flat."],
    }
    return ToolResult("recommend_budget", {"total_monthly_budget": total_monthly_budget, "lookback_days": lookback_days,
                                           "max_shift": max_shift}, data, sql=[sql_w, sql_c])
