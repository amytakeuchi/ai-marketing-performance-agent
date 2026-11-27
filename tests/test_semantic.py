import pytest

from mpia.semantic.registry import MetricRegistry, UnknownMetricError, load_registry

R = load_registry()


def test_all_metrics_valid_and_documented():
    assert len(R.metrics) >= 12
    for m in R.metrics.values():
        d = R.definition(m.name)
        assert d["formula"] and d["description"] and d["supported_dimensions"]


def test_ratio_is_ratio_of_sums_not_mean_of_ratios():
    # day 1: 100 rev / 100 spend (1.0); day 2: 900 rev / 300 spend (3.0). mean-of-ratios = 2.0, ratio-of-sums = 2.5
    comps = {"revenue": 1000, "spend": 400}
    assert R.evaluate("roas", comps) == pytest.approx(2.5)


def test_zero_or_null_denominator_returns_none_not_zero_or_inf():
    assert R.evaluate("roas", {"revenue": 10, "spend": 0}) is None
    assert R.evaluate("ctr", {"clicks": None, "impressions": 100}) is None
    assert R.evaluate("cpa", {"spend": 5, "orders": None}) is None


def test_scale_applied_for_cpm():
    assert R.evaluate("cpm", {"spend": 13, "impressions": 1000}) == pytest.approx(13.0)


def test_synonym_resolution_longest_match():
    assert R.find("what is our return on ad spend") == "roas"
    assert R.find("cost per click trend") == "cpc"
    assert R.find("platform reported roas") == "platform_reported_roas"
    assert R.find("how is the weather") is None


def test_unknown_metric_raises():
    with pytest.raises(UnknownMetricError):
        R.get("vibes")


def test_driver_chains_telescope_to_metric():
    for m in R.metrics.values():
        if m.driver_chain:
            R._check_chain(m)


def test_bad_chain_is_rejected():
    spec = {"source_model": "x", "measures": ["a", "b", "c"], "dimensions": {"d": "d"}, "default_filter": "t",
            "attribution": "x", "time_grain": "day",
            "metrics": {"m": {"label": "M", "description": "d", "type": "ratio", "numerator": "a", "denominator": "b",
                              "unit": "ratio", "dimensions": ["d"], "driver_chain": [{"name": "x", "num": "a", "den": "c"}]}}}
    with pytest.raises(ValueError):
        MetricRegistry(spec)


def test_unknown_dimension_whitelist():
    with pytest.raises(ValueError):
        R.dimension_column("1; DROP TABLE x")
