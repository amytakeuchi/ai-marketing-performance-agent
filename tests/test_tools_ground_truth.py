"""Do the tools recover the root causes planted in the synthetic data (data/ground_truth.json)?"""
import json
from datetime import date

import pytest

from conftest import BASE, CUR
from mpia import config
from mpia.tools.budget import recommend_budget
from mpia.tools.campaigns import rank_underperformers
from mpia.tools.drivers import driver_analysis, factor_decomposition
from mpia.tools.funnel import funnel_analysis
from mpia.tools.validation import validate_data

pytestmark = pytest.mark.db
GT = json.loads(config.GROUND_TRUTH_PATH.read_text())["scenarios"] if config.GROUND_TRUTH_PATH.exists() else {}


def test_driver_contributions_sum_exactly_to_total_change(wh):
    for metric in ("roas", "cpa", "ctr", "revenue", "cac", "conversion_rate"):
        for dim in ("campaign_id", "platform"):
            r = driver_analysis(wh, metric, dim, CUR, BASE, None)
            assert r.data["reconciliation_error"] < 1e-9, (metric, dim)


def test_factor_decomposition_is_exact(wh):
    for metric in ("roas", "cpa"):
        r = factor_decomposition(wh, metric, CUR, BASE, "Meta Ads")
        assert r.data["reconciliation_error"] < 1e-9


def test_S1_lookalike_fatigue_is_top_driver_and_ctr_is_dominant(wh):
    s1 = GT["S1_meta_lal_creative_fatigue"]
    d = driver_analysis(wh, "roas", "campaign_id", CUR, BASE, "Meta Ads")
    assert d.data["top"][0]["segment"] == s1["campaign_id"]
    f = factor_decomposition(wh, "roas", CUR, BASE, "Meta Ads", [s1["campaign_id"]])
    assert f.data["dominant_factor"] == s1["expected_dominant_factor"]


def test_S3_mobile_checkout_bug_is_the_only_flagged_dropoff_and_onset_is_close(wh):
    s3 = GT["S3_mobile_checkout_bug"]
    f = funnel_analysis(wh, *CUR, ["landing_page", "device"], None, BASE)
    flagged = f.data["significant_dropoffs"]
    assert [x["segment"] for x in flagged] == [f"{s3['landing_page_id']} / {s3['device']}"]
    assert flagged[0]["stage"] == s3["stage"]
    onset = date.fromisoformat(f.data["onset"]["date"])
    assert abs((onset - date.fromisoformat(s3["start"])).days) <= 3


def test_no_false_alarm_on_healthy_period(wh):
    f = funnel_analysis(wh, "2026-08-01", "2026-08-31", ["landing_page", "device"], None, ("2026-07-01", "2026-07-31"))
    assert f.data["significant_dropoffs"] == []


def test_underperformers_surface_the_planted_problem_campaigns(wh):
    r = rank_underperformers(wh, CUR, BASE)
    top3 = [c["campaign_id"] for c in r.data["top"][:3]]
    assert "META_PROSP_LAL" in top3[:1] and "META_ADV_CAT" in top3


def test_budget_constraints_and_policies(wh):
    d = recommend_budget(wh, 50_000).data
    al = {a["campaign_id"]: a for a in d["allocations"]}
    assert sum(a["proposed_daily"] for a in al.values()) == pytest.approx(d["total_daily_budget"], abs=0.02)
    assert max(abs(a["change_pct"]) for a in al.values()) <= d["max_shift"] + 1e-6
    assert al["GOOG_BRAND"]["status"] == "hold_policy" and al["GOOG_BRAND"]["change_pct"] == 0
    assert al["META_PROSP_LAL"]["status"] == "decrease"               # fatigued, over-scaled campaign loses budget
    assert d["uplift_p10"] <= d["modelled_uplift"] <= d["uplift_p90"]
    assert all(a["proposed_daily"] > 0 for a in al.values())


def test_budget_scales_with_requested_total(wh):
    a = recommend_budget(wh, 30_000).data
    assert sum(x["proposed_daily"] for x in a["allocations"]) == pytest.approx(1000, abs=0.02)


def test_validation_detects_planted_defects(wh):
    gap = validate_data(wh, "2026-09-01", "2026-09-30", "Google Ads")
    names = {c["name"]: c for c in gap.data["checks"]}
    assert names["ad_feed_gaps"]["status"] == "warn" and names["ad_feed_gaps"]["value"] == 3
    assert names["revenue_reconciliation"]["status"] == "pass"
    future = validate_data(wh, "2027-03-01", "2027-03-31")
    assert future.data["status"] == "fail"
