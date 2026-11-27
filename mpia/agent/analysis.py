"""Turns tool output into an evidence-backed answer. Everything here is deterministic: findings, hypotheses and
recommendations are assembled from tool results; every number traces to an evidence item (E1, E2, ...)."""
from __future__ import annotations

import re

from ..semantic.warehouse import Warehouse
from ..tools.base import ToolResult
from ..tools.budget import recommend_budget
from ..tools.campaigns import rank_underperformers
from ..tools.drivers import driver_analysis, factor_decomposition
from ..tools.funnel import funnel_analysis
from ..tools.kpi import compare_kpi
from . import fmt
from .intents import Intent

HYPOTHESES = {
    "ctr": ["Creative fatigue or audience saturation (the same audience engaging less with the same ads).",
            "A targeting or frequency change. Note: the warehouse has no creative-level or frequency data, so this cannot be confirmed here."],
    "cost": ["Higher auction prices (competition or seasonality).",
             "Spend scaled past the efficient delivery range (diminishing returns)."],
    "cvr": ["Landing-page or checkout friction (the funnel analysis can locate where).",
            "A change in traffic quality or offer."],
    "aov": ["A shift in product mix or discounting."],
    "tracking": ["Tracking, redirect or page-load problems between ad click and site session."],
}
RECS = {
    "ctr": "Refresh creative and review audience frequency for {name}; test new variants against the current best performer.",
    "cost": "Review bids, budget pacing and audience overlap for {name}, and check whether the cost increase is platform-wide.",
    "cvr": "Run the funnel drop-off analysis to locate the stage and landing page where conversion fell.",
    "aov": "Review promotions, bundles and product mix feeding {name}.",
    "tracking": "Audit tracking/UTM parameters and landing-page load time for {name}.",
}


def _short(m) -> str:
    """'Return on Ad Spend (ROAS)' -> 'ROAS' for readable prose."""
    mm = re.search(r"\(([^)]+)\)$", m.label)
    return mm.group(1) if mm else m.label


def _kind(factor_name: str) -> str:
    n = factor_name.lower()
    if "ctr" in n:
        return "ctr"
    if "cpm" in n or "reach" in n:
        return "cost"
    if "conversion" in n or "cvr" in n:
        return "cvr"
    if "aov" in n:
        return "aov"
    return "tracking"


def _delta(unit: str, v: float) -> str:
    if unit == "currency":
        return f"{'+' if v >= 0 else '-'}{fmt.money(abs(v), 2 if abs(v) < 100 else 0)}"
    if unit == "percent":
        return f"{v * 100:+.2f} pts"
    if unit == "ratio":
        return f"{v:+.2f}"
    return f"{v:+,.0f}"


def _factor_value(kind: str, v: float) -> str | None:
    if kind in ("ctr", "cvr"):
        return f"{v * 100:.2f}%"
    if kind == "aov":
        return fmt.money(v, 2)
    return None


class Evidence:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, title: str, tr: ToolResult) -> str:
        eid = f"E{len(self.items) + 1}"
        self.items.append({"id": eid, "title": title, "tool": tr.tool, "inputs": tr.inputs, "data": tr.data,
                           "sql": tr.sql, "notes": tr.notes})
        return eid


def _validation_limitations(validation: dict | None) -> list[str]:
    if not validation:
        return []
    return [c["detail"] for c in validation["checks"] if c["status"] == "warn"]


def _base(intent: Intent, kind: str) -> dict:
    return {"kind": kind, "headline": "", "findings": [], "hypotheses": [], "recommendations": [], "limitations": [],
            "assumptions": list(intent.assumptions), "follow_ups": [], "facts": {}, "proposal": None}


def _finding(a: dict, text: str, *eids: str) -> None:
    a["findings"].append({"text": text, "evidence": list(eids)})


# ====================================================================================================
def kpi_investigation(intent: Intent, wh: Warehouse, run, ev: Evidence, validation: dict | None) -> dict:
    reg = wh.registry
    m = reg.get(intent.metric)
    ml = _short(m)
    cur, base, plat = intent.current, intent.baseline, intent.platform
    scope = plat or "All paid media"
    a = _base(intent, "kpi_investigation")

    k = run(compare_kpi, wh, intent.metric, cur, base, plat)
    e1 = ev.add(f"{m.label}: current vs baseline", k)
    d = k.data
    cv, bv, pc = d["current"]["value"], d["baseline"]["value"], d["pct_change"]
    if pc is None:
        a["headline"] = f"{scope} {ml} could not be computed for one of the periods (no volume)."
        a["limitations"] = _validation_limitations(validation)
        return a
    cl, bl = fmt.period_label(cur), fmt.period_label(base)
    unit = m.unit
    if d["direction"] == "flat":
        a["headline"] = (f"{scope} {ml} was essentially unchanged: {fmt.value(unit, bv)} in {bl} vs "
                         f"{fmt.value(unit, cv)} in {cl} ({fmt.pct(pc)}).")
        _finding(a, a["headline"], e1)
        a["limitations"] = _validation_limitations(validation)
        a["follow_ups"] = [f"Which campaigns are underperforming in {cl}?"]
        return a
    verb = "rose" if pc > 0 else "fell"
    a["headline"] = (f"{scope} {ml} {verb} {fmt.pct(abs(pc), signed=False)} "
                     f"({fmt.value(unit, bv)} in {bl} to {fmt.value(unit, cv)} in {cl}).")
    _finding(a, a["headline"], e1)

    # which platform / campaign drives it
    if plat is None:
        dp = run(driver_analysis, wh, intent.metric, "platform", cur, base, None)
        ep = ev.add(f"{m.label} change by platform", dp)
        segs = dp.data["segments"]
        parts = [f"{s['segment']} ({_delta(unit, s['contribution'])}, {fmt.pct(s['pct_change'])})" for s in segs]
        _finding(a, f"By platform, the change in {ml} splits as: " + "; ".join(parts) + ".", ep)

    dc = run(driver_analysis, wh, intent.metric, "campaign_id", cur, base, plat)
    ec = ev.add(f"{m.label} change by campaign", dc)
    total = dc.data["total_change"]
    segs = dc.data["segments"]
    same = [s for s in segs if s["contribution"] * total > 0]
    opp = [s for s in segs if s["contribution"] * total < 0]
    top = same[:3]
    for i, s in enumerate(top):
        label = s["name"] or s["segment"]
        sh = s["share_of_change"]
        txt = (f"{label} {'is the largest driver' if i == 0 else 'also contributes'}: it accounts for {fmt.pct(sh, signed=False, d=0)} "
               f"of the {ml} change ({_delta(unit, s['contribution'])} of {_delta(unit, total)}).")
        if m.type == "ratio" and s["value_current"] is not None and s["value_baseline"] is not None:
            txt += (f" Its own {ml} moved {fmt.value(unit, s['value_baseline'])} to {fmt.value(unit, s['value_current'])} "
                    f"({fmt.pct(s['pct_change'])}); of the total, {_delta(unit, s['rate_effect'])} is performance and "
                    f"{_delta(unit, s['mix_effect'])} is budget mix.")
        sp = s.get("spend_pct_change")
        if sp is not None and abs(sp) >= 0.2:
            txt += f" Its spend {'rose' if sp > 0 else 'fell'} {fmt.pct(abs(sp), signed=False, d=0)} over the same period."
        _finding(a, txt, ec)
    offs = [s for s in opp if abs(s["contribution"]) >= 0.05 * abs(total)][:2]
    if offs:
        _finding(a, "Partly offsetting: " + "; ".join(
            f"{s['name'] or s['segment']} ({_delta(unit, s['contribution'])}, {fmt.pct(s['pct_change'])})" for s in offs) + ".", ec)

    top_seg = top[0] if top else None
    dom_kind = None
    if m.driver_chain and top_seg:
        fd = run(factor_decomposition, wh, intent.metric, cur, base, plat, [top_seg["segment"]])
        ef = ev.add(f"Funnel-factor decomposition of {m.label} for {top_seg['name'] or top_seg['segment']}", fd)
        f = fd.data
        tot_log = f["total_log_change"]
        dom = next(x for x in f["factors"] if x["factor"] == f["dominant_factor"])
        dom_kind = _kind(dom["factor"])
        val = _factor_value(dom_kind, dom["value_current"])
        txt = (f"Within {top_seg['name'] or top_seg['segment']}, {dom['factor']} is the dominant factor: it "
               f"{'rose' if dom['pct_change'] > 0 else 'fell'} {fmt.pct(abs(dom['pct_change']), signed=False)}")
        if val:
            txt += f" ({_factor_value(dom_kind, dom['value_baseline'])} to {val})"
        txt += f" and explains {fmt.pct(dom['share_of_change'], signed=False, d=0)} of the change."
        others = [x for x in f["factors"] if x is not dom and abs(x["share_of_change"] or 0) >= 0.15]
        if others:
            txt += " Other factors: " + "; ".join(
                f"{x['factor']} {fmt.pct(x['pct_change'])} ({'adds to' if x['log_contribution'] * tot_log > 0 else 'offsets'} the change)"
                for x in others) + "."
        _finding(a, txt, ef)
        ctr_like = [x for x in f["factors"] if _kind(x["factor"]) == "cvr"]
        if ctr_like and dom_kind != "cvr":
            c = ctr_like[0]
            _finding(a, f"Conversion rate was not the problem: it moved {fmt.pct(c['pct_change'])} within {top_seg['name'] or top_seg['segment']}.", ef)
        a["hypotheses"] = [f"{h} (hypothesis, not verified)" for h in HYPOTHESES[dom_kind]]
        a["recommendations"].append({"text": RECS[dom_kind].format(name=top_seg["name"] or top_seg["segment"]),
                                     "rationale": f"{dom['factor']} is the dominant factor ({fmt.pct(dom['share_of_change'], signed=False, d=0)} of the change).",
                                     "evidence": [ef]})
        if len(f["factors"]) and plat is None or True:
            pass
    sp = (top_seg or {}).get("spend_pct_change")
    if top_seg and sp is not None and sp >= 0.2 and total * top_seg["contribution"] > 0 and m.higher_is_better is not None \
            and ((total < 0) == bool(m.higher_is_better)):
        a["recommendations"].append({
            "text": f"Spend on {top_seg['name'] or top_seg['segment']} rose {fmt.pct(sp, signed=False, d=0)} while {ml} worsened; "
                    "consider holding or phasing back that increase until efficiency recovers (the budget analysis can size the shift).",
            "rationale": "Scaling spend while efficiency falls compounds the decline.", "evidence": [ec]})
    a["limitations"] = [
        f"{ml} uses {reg.attribution.split('.')[0].lower().replace('revenue and orders are ', '')}; it shows correlation, not incremental causal impact."
        if m.name in ("roas", "cpa", "cac", "revenue", "conversions", "aov", "conversion_rate") else "",
        "Hypotheses above cannot be confirmed with warehouse data (no creative, frequency, bid or auction data).",
        "The comparison is one period vs the preceding one; with 12 months of data, year-over-year seasonality cannot be controlled.",
        *_validation_limitations(validation)]
    a["limitations"] = [x for x in a["limitations"] if x]
    a["follow_ups"] = [f"Where are users dropping off in the funnel in {cl}?", f"Which campaigns are underperforming in {cl}?",
                       "How should I allocate a $50,000 monthly budget?"]
    a["facts"] = {"metric": intent.metric, "pct_change": pc, "direction": d["direction"],
                  "top_driver_campaign": top_seg["segment"] if top_seg else None,
                  "top_driver_share": top_seg["share_of_change"] if top_seg else None,
                  "dominant_factor": dom["factor"] if m.driver_chain and top_seg else None,
                  "reconciliation_error": dc.data["reconciliation_error"]}
    return a


# ====================================================================================================
def underperformers(intent: Intent, wh: Warehouse, run, ev: Evidence, validation: dict | None) -> dict:
    cur, base, plat = intent.current, intent.baseline, intent.platform
    a = _base(intent, "underperformers")
    r = run(rank_underperformers, wh, cur, base, plat)
    e = ev.add("Campaign ranking by spend-weighted underperformance", r)
    top = r.data["top"]
    cl, bl = fmt.period_label(cur), fmt.period_label(base)
    scope = plat or "paid media"
    if not top:
        a["headline"] = f"No {scope} campaigns with enough volume to rank in {cl}."
        _finding(a, a["headline"], e)
        return a
    a["headline"] = (f"In {cl}, {top[0]['campaign']} is the weakest {scope} campaign by spend-weighted score "
                     f"(ROAS {top[0]['roas']:.2f} vs {top[0]['peer_roas']:.2f} for {top[0]['funnel_stage']} peers).")
    for i, c in enumerate(top[:3]):
        txt = (f"{i + 1}. {c['campaign']} ({c['platform']}): ROAS {c['roas']:.2f} vs {c['peer_roas']:.2f} for {c['funnel_stage']} peers "
               f"({fmt.pct(c['shortfall_vs_peers'], signed=False, d=0)} shortfall) and {fmt.pct(c['roas_change'])} vs {bl}; "
               f"spend {fmt.money(c['spend'])}")
        if c.get("spend_change") is not None:
            txt += f" ({fmt.pct(c['spend_change'], d=0)} vs {bl})"
        _finding(a, txt + ".", e)
        if c["roas_change"] is not None and c["roas_change"] <= -0.10:
            a["recommendations"].append({"text": f"Investigate the recent decline in {c['campaign']} (ROAS {fmt.pct(c['roas_change'])}); "
                                                  f"ask 'Why did ROAS fall in {fmt.period_label(cur)} for {c['platform']}?' to see the drivers.",
                                         "rationale": "It is both below peers and getting worse.", "evidence": [e]})
        elif c["shortfall_vs_peers"] >= 0.2:
            a["recommendations"].append({"text": f"{c['campaign']} is persistently below its peers; test new audiences or creative, or cap its budget.",
                                         "rationale": f"{fmt.pct(c['shortfall_vs_peers'], signed=False, d=0)} below peer ROAS without a recent decline.",
                                         "evidence": [e]})
    lv = r.data["low_volume"]
    if lv:
        vf = r.data["volume_floor"]
        _finding(a, f"Not ranked for low volume (under {fmt.money(vf['min_spend'])} spend or {vf['min_orders']} orders): "
                    + ", ".join(c["campaign_id"] for c in lv) + ".", e)
    a["limitations"] = ["Peers are all paid campaigns in the same funnel stage; ROAS is last-click attributed (correlation, not incrementality).",
                        "The score is a prioritisation heuristic (spend x shortfall/decline), not a statistical test.",
                        *_validation_limitations(validation)]
    a["follow_ups"] = [f"Why did ROAS change for {top[0]['platform']} in {cl}?", "How should I allocate a $50,000 monthly budget?"]
    a["facts"] = {"top_campaigns": [c["campaign_id"] for c in top], "low_volume": [c["campaign_id"] for c in lv]}
    return a


# ====================================================================================================
def funnel_dropoff(intent: Intent, wh: Warehouse, run, ev: Evidence, validation: dict | None) -> dict:
    cur, base, plat = intent.current, intent.baseline, intent.platform
    a = _base(intent, "funnel_dropoff")
    f = run(funnel_analysis, wh, cur[0], cur[1], ["landing_page", "device"], plat, base)
    e = ev.add("Funnel stage conversion by landing page and device", f)
    d = f.data
    cl, bl = fmt.period_label(cur), fmt.period_label(base)
    o = d["overall"]["rates"]
    _finding(a, f"Overall in {cl}: {fmt.pct(d['upstream']['ctr'], signed=False, d=2)} of impressions click, "
                f"{fmt.pct(d['upstream']['click_to_session'], signed=False, d=0)} of clicks arrive as sessions, "
                f"{fmt.pct(o['session_to_cart'], signed=False)} of sessions add to cart, "
                f"{fmt.pct(o['cart_to_checkout'], signed=False)} of carts reach checkout and "
                f"{fmt.pct(o['checkout_to_purchase'], signed=False)} of checkouts purchase.", e)
    flagged = d["significant_dropoffs"]
    if not flagged:
        a["headline"] = (f"No landing-page/device segment shows a statistically significant funnel drop-off in {cl} "
                         "(after correcting for multiple comparisons).")
        _finding(a, a["headline"], e)
    else:
        t = flagged[0]
        a["headline"] = (f"Biggest drop-off: {t['segment']} at {t['label']} converts {fmt.pct(t['rate'], signed=False)} vs "
                         f"{fmt.pct(t['expected_rate'], signed=False)} expected for its traffic mix ({fmt.pct(t['relative_gap'], d=0)}), "
                         f"costing roughly {t['est_lost_orders']:.0f} orders in {cl}.")
        for x in flagged:
            txt = (f"{x['segment']}, {x['label']}: {fmt.pct(x['rate'], signed=False)} vs {fmt.pct(x['expected_rate'], signed=False)} "
                   f"expected for its traffic mix ({fmt.pct(x['relative_gap'], d=0)}; significant after multiple-comparison correction); "
                   f"about {x['est_lost_orders']:.0f} lost orders.")
            if x.get("change_vs_baseline") is not None:
                txt += f" Versus {bl} this segment's rate changed {fmt.pct(x['change_vs_baseline'])}."
            _finding(a, txt, e)
        on = d["onset"]
        if on:
            _finding(a, f"The drop appears to start around {on['date']} (rate {fmt.pct(on['rate_before'], signed=False)} before, "
                        f"{fmt.pct(on['rate_after'], signed=False)} after).", e)
        if t["stage"] == "checkout_to_purchase":
            a["hypotheses"] = ["A technical or UX problem in checkout/payment for this page and device (for example a broken payment button or slow load) - hypothesis, not verified.",
                               "A pricing, shipping-cost or promo-code issue appearing late in checkout - hypothesis, not verified."]
            rec = f"Run a manual checkout test on {t['segment']} and check payment/error logs around {on['date'] if on else 'the onset date'}."
        elif t["stage"] == "cart_to_checkout":
            a["hypotheses"] = ["Unexpected costs or friction when moving from cart to checkout - hypothesis, not verified."]
            rec = f"Review the cart page and shipping/tax disclosure for {t['segment']}."
        else:
            a["hypotheses"] = ["Landing-page relevance or load-time problems for this traffic - hypothesis, not verified."]
            rec = f"Review landing-page relevance and load time for {t['segment']}."
        a["recommendations"].append({"text": rec, "rationale": f"Largest estimated order loss ({t['est_lost_orders']:.0f} orders).", "evidence": [e]})
        a["recommendations"].append({"text": f"After the fix, re-run this check: the segment should return to about {fmt.pct(t['expected_rate'], signed=False)}.",
                                     "rationale": "Confirms the issue was resolved.", "evidence": [e]})
    a["limitations"] = ["Segments are landing page x device only; browser, OS and error-log data are not in the warehouse.",
                        "Estimated lost orders assume the segment would otherwise convert at the rate its traffic mix predicts.",
                        *_validation_limitations(validation)]
    a["follow_ups"] = [f"Why did ROAS change in {cl}?", f"Which campaigns are underperforming in {cl}?"]
    a["facts"] = {"top_segment": flagged[0]["segment"] if flagged else None, "top_stage": flagged[0]["stage"] if flagged else None,
                  "n_flagged": len(flagged), "onset_date": d["onset"]["date"] if d["onset"] else None,
                  "flagged_segments": [x["segment"] for x in flagged]}
    return a


# ====================================================================================================
def budget_allocation(intent: Intent, wh: Warehouse, run, ev: Evidence, validation: dict | None) -> dict:
    from ..actions import guardrails
    a = _base(intent, "budget_allocation")
    b = run(recommend_budget, wh, intent.budget_amount)
    e = ev.add("Budget re-allocation model", b)
    d = b.data
    movers_up = [x for x in d["allocations"] if x["status"] == "increase"]
    movers_dn = [x for x in d["allocations"] if x["status"] == "decrease"]
    B = fmt.money(d["total_monthly_budget"])
    a["headline"] = (f"For a {B} monthly budget, the model shifts spend toward "
                     f"{', '.join(x['campaign'] for x in movers_up) or 'no campaigns'} and away from "
                     f"{', '.join(x['campaign'] for x in movers_dn) or 'no campaigns'}, for a modelled uplift of about "
                     f"{fmt.money(d['modelled_uplift'])} per month in attributed revenue "
                     f"({int(d['uplift_interval_level'] * 100)}% interval {fmt.money(d['uplift_p10'])} to {fmt.money(d['uplift_p90'])}).")
    for x in movers_up + movers_dn:
        _finding(a, f"{x['campaign']}: {fmt.money(x['current_daily'], 2)} to {fmt.money(x['proposed_daily'], 2)} per day "
                    f"({fmt.pct(x['change_pct'], d=0)}); spend elasticity {x['elasticity_b']:.2f} "
                    f"(marginal ROAS {x['marginal_roas_current']:.2f} to {x['marginal_roas_proposed']:.2f}).", e)
    held = [x for x in d["allocations"] if x["status"] in ("hold_policy", "hold_low_confidence", "hold")]
    pol = [x["campaign"] for x in held if x["status"] == "hold_policy"]
    lowc = [x["campaign"] for x in held if x["status"] == "hold_low_confidence"]
    if pol:
        _finding(a, "Held flat by policy (brand search captures existing demand, so last-click ROAS overstates what extra budget would earn): "
                    + ", ".join(pol) + ".", e)
    if lowc:
        _finding(a, "Held flat because their spend-response could not be reliably estimated: " + ", ".join(lowc) + ".", e)
    _finding(a, f"Modelled uplift is {fmt.pct(d['uplift_pct'], d=1)} of modelled revenue and positive in "
                f"{fmt.pct(d['prob_uplift_positive'], signed=False, d=0)} of bootstrap resamples. This is a model of past correlation, not a forecast.", e)
    a["recommendations"] = [
        {"text": "Review the proposed allocation in the Approvals tab; you can edit any campaign before approving.",
         "rationale": "Nothing is applied without an authorised human decision.", "evidence": [e]},
        {"text": f"Roll out gradually (limits are +/-{int(d['max_shift'] * 100)}% per campaign) and compare actual ROAS against the model after 2-4 weeks.",
         "rationale": "Treat the modelled uplift as a hypothesis to test.", "evidence": [e]}]
    if any(x["campaign_id"] == "META_RETARG" for x in movers_up):
        a["recommendations"].append({"text": "Retargeting reach is capped by audience size; the model cannot see that limit, so scale META_RETARG cautiously.",
                                     "rationale": "Domain constraint not present in the data.", "evidence": [e]})
    a["limitations"] = [*d["policies"], d["caveat"],
                        f"Curves are fitted on {d['lookback']['weeks']} complete weeks ({d['lookback']['start']} to {d['lookback']['end']}); "
                        "recent events such as creative fatigue can bias them.", *_validation_limitations(validation)]
    payload = {"type": "update_campaign_budgets", "total_monthly_budget": d["total_monthly_budget"],
               "total_daily_budget": d["total_daily_budget"], "source": "recommend_budget",
               "changes": [{"campaign_id": x["campaign_id"], "campaign": x["campaign"], "current_daily": x["current_daily"],
                            "proposed_daily": x["proposed_daily"]} for x in d["allocations"]]}
    problems = guardrails.validate_budget_payload(payload)
    a["proposal"] = payload if not problems else None
    a["limitations"] += [f"Proposal withheld: {p}" for p in problems]
    a["follow_ups"] = ["Which campaigns are underperforming?", "Why did ROAS change last month?"]
    a["facts"] = {"increase": [x["campaign_id"] for x in movers_up], "decrease": [x["campaign_id"] for x in movers_dn],
                  "held_policy": [x["campaign_id"] for x in held if x["status"] == "hold_policy"],
                  "total_proposed_daily": round(sum(x["proposed_daily"] for x in d["allocations"]), 2),
                  "total_daily_budget": d["total_daily_budget"],
                  "max_abs_change": max(abs(x["change_pct"]) for x in d["allocations"]),
                  "guardrail_problems": problems, "uplift_p10": d["uplift_p10"]}
    return a


# ====================================================================================================
def metric_definition(intent: Intent, wh: Warehouse, run, ev: Evidence, validation: dict | None) -> dict:
    a = _base(intent, "metric_definition")
    d = wh.registry.definition(intent.metric)
    e = ev.add(f"Governed definition of {d['label']}", ToolResult("metric_definition", {"metric": intent.metric}, d))
    a["headline"] = f"{d['label']}: {d['description']}"
    for label, key in [("Formula", "formula"), ("Aggregation", "aggregation"), ("Filters", "filters"),
                       ("Attribution", "attribution"), ("Zero denominator", "zero_denominator"), ("Known limitations", "limitations")]:
        _finding(a, f"{label}: {d[key]}", e)
    a["facts"] = {"metric": intent.metric, "formula": d["formula"]}
    return a


BUILDERS = {"kpi_investigation": kpi_investigation, "underperformers": underperformers,
            "funnel_dropoff": funnel_dropoff, "budget_allocation": budget_allocation, "metric_definition": metric_definition}


def run_analysis(intent: Intent, wh: Warehouse, run, validation: dict | None = None) -> dict:
    ev = Evidence()
    a = BUILDERS[intent.intent](intent, wh, run, ev, validation)
    a["evidence"] = ev.items
    return a
