import pytest

from mpia.agent.grounding import grounding_rate, ungrounded_numbers
from mpia.tools.stats import change_point, two_prop_z

EV = [{"id": "E1", "data": {"roas": 1.5612, "pct": -0.1774, "spend": 12645.37, "share": 0.5312}, "inputs": {"start": "2026-10-01"}}]


def test_z_test_detects_difference_and_ignores_noise():
    _, p_diff = two_prop_z(410, 1000, 600, 1000)
    _, p_same = two_prop_z(500, 1000, 505, 1000)
    assert p_diff < 1e-6 and p_same > 0.5
    assert two_prop_z(0, 0, 5, 10) == (0.0, 1.0)


def test_change_point_finds_step():
    n = [200] * 30
    x = [120] * 15 + [60] * 15
    cp = change_point(x, n)
    assert cp and abs(cp["index"] - 15) <= 1
    assert cp["rate_before"] > cp["rate_after"]
    assert change_point([1, 2], [3, 4]) is None


def test_grounding_accepts_rounded_evidence_numbers():
    assert ungrounded_numbers("ROAS was 1.56, down 17.7% [E1]; spend $12,645 and 53% share.", EV) == []


def test_grounding_rejects_invented_numbers():
    bad = ungrounded_numbers("ROAS improved to 2.40 and spend was $99,000.", EV)
    assert "2.40" in bad and "$99,000" in bad


def test_grounding_ignores_dates_years_refs_small_ints():
    assert ungrounded_numbers("Top 3 campaigns in Oct 2026 (2026-10-31) [E1, E2].", EV) == []


def test_grounding_rate():
    assert grounding_rate("ROAS 1.56 and a made-up 7.77", EV) == pytest.approx(0.5)
