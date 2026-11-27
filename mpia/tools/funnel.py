"""Funnel drop-off analysis with an explicit, testable definition of "significant".

Each landing-page x device segment is compared with what its *traffic mix* predicts (indirect standardisation):
the expected stage rate is the average of each (campaign x device) stratum's rate on all OTHER traffic, weighted by
the segment's own mix. This stops the tool from blaming a page for simply receiving lower-intent traffic
(e.g. YouTube clicks) or for being mobile-heavy (mobile always converts lower than desktop).

A segment x stage is flagged as a significant drop-off when ALL hold:
  * observed rate is >= 15% (relative) below the mix-adjusted expected rate,
  * when a baseline period is supplied, the segment's own rate is also >= 10% below its baseline (a *change*, not a
    chronic structural difference). Chronic defects present in both periods are therefore NOT flagged.
  * a z-test of observed vs expected successes gives p < 0.01 / (number of tests)   [Bonferroni correction],
  * the segment has >= 200 units entering that stage.
Estimated lost orders = (expected - observed successes) x downstream conversion to purchase.
"""
from __future__ import annotations

import math
from collections import defaultdict

from ..semantic.warehouse import Warehouse
from .base import ToolResult, pct_change
from .stats import change_point

STAGES = [  # (key, label, numerator, denominator)
    ("session_to_cart", "Session -> Add to cart", "add_to_carts", "sessions"),
    ("cart_to_checkout", "Add to cart -> Checkout", "checkouts", "add_to_carts"),
    ("checkout_to_purchase", "Checkout -> Purchase", "purchases", "checkouts"),
]
MIN_UNITS, MAX_P, MIN_REL_GAP, MIN_BASELINE_DROP = 200, 0.01, 0.15, 0.10
COUNTS = ("sessions", "add_to_carts", "checkouts", "purchases")


def _rate(num, den):
    return (num / den) if den else None


def _stage_rates(row: dict) -> dict:
    return {k: _rate(row.get(n) or 0, row.get(d) or 0) for k, _, n, d in STAGES}


def _downstream(totals: dict) -> dict:
    """Overall probability that a unit entering stage k ends in a purchase."""
    r = _stage_rates(totals)
    return {"session_to_cart": (r["session_to_cart"] or 0) * (r["cart_to_checkout"] or 0) * (r["checkout_to_purchase"] or 0),
            "cart_to_checkout": (r["cart_to_checkout"] or 0) * (r["checkout_to_purchase"] or 0),
            "checkout_to_purchase": 1.0}


def _sum(rows: list[dict]) -> dict:
    return {m: sum((r.get(m) or 0) for r in rows) for m in COUNTS}


def _expected(seg_rows: list[dict], camp_tot: dict, num: str, den: str, fallback: float):
    """Mix-adjusted expected successes and variance for one segment/stage."""
    E = var = 0.0
    for r in seg_rows:
        n_c = r[den] or 0
        if not n_c:
            continue
        t = camp_tot[(r["campaign_id"], r["device"])]
        ex_n, ex_x = (t[den] or 0) - n_c, (t[num] or 0) - (r[num] or 0)
        p = ex_x / ex_n if ex_n > 0 else fallback
        E += n_c * p
        # binomial noise in the segment + noise in the *estimated* expected rate (matters when 'other' traffic is small)
        var += n_c * p * (1 - p) * (1 + (n_c / ex_n if ex_n > 0 else 0))
    return E, var


def funnel_analysis(wh: Warehouse, start: str, end: str, group_by: list[str] | None = None,
                    platform: str | None = None, baseline: tuple[str, str] | None = None,
                    top_n: int = 5) -> ToolResult:
    group_by = group_by or ["landing_page", "device"]
    dims = list(dict.fromkeys([*group_by, "campaign_id", "device"]))
    segc_rows, sql_seg = wh.funnel_components(dims, start, end, platform)
    camp_rows, sql_camp = wh.funnel_components(["campaign_id", "device"], start, end, platform)
    tot_rows, sql_tot = wh.funnel_components([], start, end, platform)
    totals, camp_tot = tot_rows[0], {(r["campaign_id"], r["device"]): r for r in camp_rows}
    overall = {"counts": {m: totals[m] for m in COUNTS}, "rates": _stage_rates(totals),
               "session_to_purchase": _rate(totals["purchases"], totals["sessions"])}
    down = _downstream(totals)

    up_rows, sql_up = wh.components([], start, end, platform, measures=["impressions", "clicks", "sessions"])
    u = up_rows[0]
    upstream = {"ctr": _rate(u["clicks"] or 0, u["impressions"] or 0),
                "click_to_session": _rate(u["sessions"] or 0, u["clicks"] or 0)}

    sqls = [sql_seg, sql_camp, sql_tot, sql_up]
    base_by_seg: dict = {}
    if baseline:
        b_rows, sql_b = wh.funnel_components(group_by, baseline[0], baseline[1], platform)
        base_by_seg = {tuple(r[g] for g in group_by): r for r in b_rows}
        sqls.append(sql_b)

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for r in segc_rows:
        grouped[tuple(r[g] for g in group_by)].append(r)

    n_tests = max(1, sum(1 for rows in grouped.values() for _, _, _, d in STAGES if _sum(rows)[d] >= MIN_UNITS))
    alpha = MAX_P / n_tests
    segments, flagged = [], []
    for key, rows in sorted(grouped.items()):
        sums = _sum(rows)
        rates = _stage_rates(sums)
        seg = {"segment": " / ".join(str(k) for k in key), "key": dict(zip(group_by, key)), "counts": sums,
               "rates": rates, "stages": {}}
        for k, label, num, den in STAGES:
            x, n = sums[num], sums[den]
            if not n:
                continue
            other_n, other_x = (totals[den] or 0) - n, (totals[num] or 0) - x
            fb = other_x / other_n if other_n > 0 else (_rate(totals[num], totals[den]) or 0)
            E, var = _expected(rows, camp_tot, num, den, fb)
            if E <= 0 or var <= 0:
                continue
            z = (x - E) / math.sqrt(var)
            p = math.erfc(abs(z) / math.sqrt(2))
            exp_rate = E / n
            gap = rates[k] / exp_rate - 1
            st = {"label": label, "rate": rates[k], "expected_rate": exp_rate, "relative_gap": gap, "z": z,
                  "p_value": p, "units": n, "est_lost_orders": max(0.0, E - x) * down[k]}
            if base_by_seg.get(key):
                br = _stage_rates(base_by_seg[key]).get(k)
                st["baseline_rate"], st["change_vs_baseline"] = br, pct_change(rates[k], br)
            dropped = (not baseline) or st.get("change_vs_baseline") is None or st["change_vs_baseline"] <= -MIN_BASELINE_DROP
            st["significant"] = n >= MIN_UNITS and p < alpha and gap <= -MIN_REL_GAP and dropped
            seg["stages"][k] = st
            if st["significant"]:
                flagged.append({"segment": seg["segment"], "key": seg["key"], "stage": k, **st})
        segments.append(seg)
    flagged.sort(key=lambda f: f["est_lost_orders"], reverse=True)

    onset = None
    if flagged:
        top = flagged[0]
        num, den = next((n, d) for k, _, n, d in STAGES if k == top["stage"])
        filt = {g: top["key"][g] for g in group_by if g in ("landing_page", "device", "campaign_id", "funnel_stage")}
        daily, sql_d = wh.funnel_components(["date"], start, end, platform, filters=filt)
        sqls.append(sql_d)
        cp = change_point([r[num] or 0 for r in daily], [r[den] or 0 for r in daily])
        if cp and cp["llr"] > 10:
            onset = {"date": daily[cp["index"]]["date"], "rate_before": cp["rate_before"], "rate_after": cp["rate_after"],
                     "relative_change": cp["rate_after"] / cp["rate_before"] - 1, "segment": top["segment"], "stage": top["stage"]}

    data = {"start": start, "end": end, "platform": platform, "group_by": group_by, "overall": overall,
            "upstream": upstream, "stage_labels": {k: l for k, l, _, _ in STAGES},
            "segments": segments, "significant_dropoffs": flagged[:top_n], "onset": onset,
            "definition": {"min_units": MIN_UNITS, "max_p_value": MAX_P, "bonferroni_tests": n_tests,
                           "adjusted_alpha": alpha, "min_relative_gap": MIN_REL_GAP, "min_baseline_drop": MIN_BASELINE_DROP,
                           "baseline_for_expected": "campaign x device mix-adjusted rate of all other traffic"}}
    return ToolResult("funnel_analysis", {"start": start, "end": end, "group_by": group_by, "platform": platform,
                                          "baseline": list(baseline) if baseline else None}, data, sql=sqls)
