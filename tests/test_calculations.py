"""Warehouse + semantic layer vs an independent pandas oracle built from the raw CSVs."""
import pytest

from conftest import BASE, CUR

pytestmark = pytest.mark.db

METRICS = ["spend", "impressions", "clicks", "conversions", "revenue", "roas", "ctr", "cpc", "cpm", "cpa", "cac",
           "conversion_rate", "aov", "platform_reported_roas"]
SLICES = [(None, None), ("Meta Ads", None), ("Google Ads", None), (None, "META_PROSP_LAL"), (None, "GOOG_BRAND")]


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("platform,campaign", SLICES)
@pytest.mark.parametrize("period", [CUR, BASE, ("2026-01-01", "2026-03-31")])
def test_metric_matches_oracle(wh, oracle, metric, platform, campaign, period):
    cids = [campaign] if campaign else None
    got, _, _ = wh.metric_value(metric, period[0], period[1], platform, cids)
    want = oracle.metric(metric, period[0], period[1], platform, campaign)
    if want is None:
        assert got is None
    else:
        assert got == pytest.approx(want, rel=1e-9, abs=1e-9)


def test_naive_average_of_daily_roas_is_biased_for_low_volume_campaigns(wh, oracle):
    """Averaging daily ratios is not just conceptually wrong: on a low-volume campaign it is off by >5%.
    (On large aggregates the gap is small - see docs/EVAL_REPORT.md - so this is about correctness, not drama.)"""
    correct, _, _ = wh.metric_value("roas", *CUR, None, ["GOOG_YT"])
    naive = oracle.naive_mean_of_daily_roas(*CUR, campaign_id="GOOG_YT")
    assert abs(naive - correct) / correct > 0.05


def test_dedup_and_null_handling_visible_in_marts(wh):
    from mpia import db
    assert db.query("analyst_ro", "SELECT count(*) n FROM (SELECT date_day, campaign_id FROM marts.mart_campaign_daily "
                                  "GROUP BY 1,2 HAVING count(*) > 1) x")[0]["n"] == 0
    assert db.query("analyst_ro", "SELECT count(*) n FROM marts.mart_campaign_daily WHERE clicks_missing")[0]["n"] == 8
    assert db.query("analyst_ro", "SELECT count(*) n FROM marts.mart_campaign_daily WHERE had_duplicate")[0]["n"] == 12


def test_revenue_reconciles_to_orders(wh):
    from mpia import db
    r = db.query("analyst_ro", "SELECT (SELECT sum(revenue) FROM marts.mart_campaign_daily) a, "
                               "(SELECT sum(revenue) FROM marts.fact_orders) b")[0]
    assert float(r["a"]) == pytest.approx(float(r["b"]), abs=0.01)
