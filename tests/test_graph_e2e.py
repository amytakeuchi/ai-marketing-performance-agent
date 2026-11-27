import pytest

from mpia import db
from mpia.agent.graph import run_investigation

pytestmark = pytest.mark.db


def test_core_investigation_end_to_end_and_audited(deps):
    a = run_investigation("Why did Meta ROAS decline in October compared with September?", "pytest", deps)
    assert a["status"] == "completed" and a["interpreter"] == "rules"
    assert a["facts"]["top_driver_campaign"] == "META_PROSP_LAL" and a["facts"]["dominant_factor"] == "CTR"
    assert a["facts"]["pct_change"] == pytest.approx(-0.1774, abs=2e-3)
    assert a["grounding_rate"] == 1.0
    assert a["hypotheses"] and all("not verified" in h for h in a["hypotheses"])     # causes are labelled as hypotheses
    assert a["limitations"] and a["evidence"] and all(f["evidence"] for f in a["findings"])
    inv = deps.audit.get_investigation(a["investigation_id"])
    assert inv["status"] == "completed" and inv["intent"]["metric"] == "roas"
    tools = [c["tool"] for c in inv["tool_calls"]]
    assert {"validate_data", "compare_kpi", "driver_analysis", "factor_decomposition"} <= set(tools)
    assert all(c["status"] == "ok" for c in inv["tool_calls"])
    assert all(c["sql_executed"] for c in inv["tool_calls"] if c["tool"] in ("compare_kpi", "driver_analysis"))


@pytest.mark.parametrize("q,status", [("Why did performance drop in March 2027?", "blocked"),
                                      ("How should I allocate my budget?", "clarification"),
                                      ("what's the weather", "unsupported")])
def test_failure_modes_are_explicit(deps, q, status):
    a = run_investigation(q, "pytest", deps)
    assert a["status"] == status and a["message"] and not a["findings"]
    assert deps.audit.get_investigation(a["investigation_id"])["status"] == status


def test_funnel_and_underperformer_and_definition(deps):
    f = run_investigation("Where are users dropping off between ad click and purchase?", "pytest", deps)
    assert f["facts"]["top_segment"] == "lp_collection_v2 / mobile" and f["facts"]["top_stage"] == "checkout_to_purchase"
    u = run_investigation("Which campaigns are underperforming this month?", "pytest", deps)
    assert u["facts"]["top_campaigns"][0] == "META_PROSP_LAL"
    d = run_investigation("How do you define ROAS?", "pytest", deps)
    assert d["status"] == "completed" and "SUM(revenue) / SUM(spend)" in d["findings"][0]["text"]


def test_tool_failure_is_reported_not_hidden(deps, monkeypatch):
    import mpia.agent.analysis as an
    def boom(*a, **k):
        raise RuntimeError("db exploded")
    monkeypatch.setattr(an, "compare_kpi", boom)
    a = run_investigation("Why did Meta ROAS decline in October?", "pytest", deps)
    assert a["status"] == "error" and "no answer was produced" in a["message"]
    errs = [c for c in deps.audit.get_investigation(a["investigation_id"])["tool_calls"] if c["status"] == "error"]
    assert errs and "db exploded" in errs[0]["error"]


def test_all_findings_are_grounded_across_questions(deps):
    for q in ["Why did Google CPA change in September?", "Why did CTR change in October?", "Why did revenue fall in October?",
              "Which Meta campaigns are underperforming?", "How should I allocate a $50,000 marketing budget?"]:
        a = run_investigation(q, "pytest", deps)
        assert a["status"] == "completed", (q, a.get("message"))
        assert a["grounding_rate"] == 1.0, (q, a["grounding_rate"])
