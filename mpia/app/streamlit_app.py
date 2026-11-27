"""Streamlit UI: Ask / Approvals / History / Metric definitions.   Run: streamlit run mpia/app/streamlit_app.py"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mpia import config
from mpia.actions.service import ActionService, ApprovalError
from mpia.agent.graph import Deps, run_investigation
from mpia.audit.logger import AuditLogger
from mpia.semantic.registry import load_registry
from mpia.tools.kpi import kpi_timeseries

st.set_page_config(page_title="Marketing Performance Agent", page_icon="📈", layout="wide")

EXAMPLES = ["Why did Meta ROAS decline in October compared with September?",
            "Which campaigns are underperforming this month?",
            "Where are users dropping off between ad click and purchase?",
            "How should I allocate a $50,000 marketing budget?",
            "How do you define ROAS?"]


@st.cache_resource
def get_deps() -> Deps:
    return Deps()


deps = get_deps()
audit = AuditLogger()

# ---------------- sidebar ----------------
with st.sidebar:
    st.title("📈 Marketing Performance Agent")
    st.caption("Evidence-based investigations with human-approved actions.")
    user = st.text_input("Your name", "amy")
    role = st.selectbox("Your role", ["viewer", "analyst", "marketing_manager", "admin"], index=2,
                        help="Only marketing_manager and admin may approve actions.")
    st.markdown(f"**Interpreter:** {'Claude (' + config.ANTHROPIC_MODEL + ')' if deps.llm else 'deterministic rules (no API key)'}")
    try:
        ActionService().http.get("/health", timeout=2)
        st.success("Mock marketing API: online")
    except Exception:
        st.warning("Mock marketing API offline - approvals can be recorded but execution will fail. "
                   "Start it with `make api`.")


# ---------------- charts ----------------
def _ev(ans, tool, **match):
    for e in ans["evidence"]:
        if e["tool"] == tool and all(e["inputs"].get(k) == v for k, v in match.items()):
            return e
    return None


def charts(ans: dict) -> None:
    kind = ans.get("kind")
    if kind == "kpi_investigation":
        metric, plat = ans["intent"]["metric"], ans["intent"]["platform"]
        ts = kpi_timeseries(deps.wh, metric, "2026-05-01", ans["intent"]["current_end"], plat, "week")
        s = [p for p in ts.data["series"] if p["value"] is not None]
        fig = go.Figure(go.Scatter(x=[p["period"] for p in s], y=[p["value"] for p in s], mode="lines+markers"))
        fig.update_layout(title=f"Weekly {metric.upper()} ({plat or 'all paid media'})", height=300, margin=dict(t=40, b=20))
        st.plotly_chart(fig, width="stretch")
        e = _ev(ans, "driver_analysis", dimension="campaign_id")
        if e:
            segs = e["data"]["segments"]
            fig = go.Figure(go.Bar(x=[s["contribution"] for s in segs], y=[s["name"] or s["segment"] for s in segs],
                                   orientation="h", marker_color=["#c0392b" if s["contribution"] < 0 else "#27ae60" for s in segs]))
            fig.update_layout(title=f"Contribution to the {metric.upper()} change, by campaign", height=320, margin=dict(t=40, b=20),
                              yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")
        e = _ev(ans, "factor_decomposition")
        if e:
            fs = e["data"]["factors"]
            fig = go.Figure(go.Bar(x=[f["pct_change"] * 100 for f in fs], y=[f["factor"] for f in fs], orientation="h"))
            fig.update_layout(title="Funnel factors inside the top driver (% change)", height=300, margin=dict(t=40, b=20),
                              yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")
    elif kind == "funnel_dropoff":
        e = _ev(ans, "funnel_analysis")
        segs = [s for s in e["data"]["segments"] if s["stages"].get("checkout_to_purchase")]
        fig = go.Figure(go.Bar(x=[s["segment"] for s in segs], y=[s["stages"]["checkout_to_purchase"]["rate"] * 100 for s in segs]))
        fig.update_layout(title="Checkout -> Purchase rate by landing page / device (%)", height=320, margin=dict(t=40, b=20))
        st.plotly_chart(fig, width="stretch")
    elif kind == "budget_allocation":
        e = _ev(ans, "recommend_budget")
        al = e["data"]["allocations"]
        fig = go.Figure([go.Bar(name="Current", x=[a["campaign_id"] for a in al], y=[a["current_daily"] for a in al]),
                         go.Bar(name="Proposed", x=[a["campaign_id"] for a in al], y=[a["proposed_daily"] for a in al])])
        fig.update_layout(barmode="group", title="Daily budget: current vs proposed ($)", height=340, margin=dict(t=40, b=20))
        st.plotly_chart(fig, width="stretch")
    elif kind == "underperformers":
        e = _ev(ans, "rank_underperformers")
        top = e["data"]["ranked"]
        fig = go.Figure(go.Bar(x=[c["campaign_id"] for c in top], y=[c["priority_score"] for c in top]))
        fig.update_layout(title="Priority score (spend-weighted underperformance)", height=320, margin=dict(t=40, b=20))
        st.plotly_chart(fig, width="stretch")


def render(ans: dict) -> None:
    if ans["status"] != "completed":
        icon = {"unsupported": "🚫", "clarification": "❓", "blocked": "⛔", "error": "⚠️"}.get(ans["status"], "ℹ️")
        st.info(f"{icon} {ans['message']}")
        return
    st.subheader(ans["headline"])
    st.write(ans["summary"])
    if ans["summary_source"] == "llm":
        st.caption("Summary written by Claude and verified: every number was matched to tool evidence.")
    t1, t2, t3, t4 = st.tabs(["Findings & recommendations", "Charts", "Evidence & SQL", "Audit trail"])
    with t1:
        for f in ans["findings"]:
            st.markdown(f"- {f['text']}  `{', '.join(f['evidence'])}`")
        if ans["hypotheses"]:
            st.markdown("**Possible causes (unverified hypotheses)**")
            for h in ans["hypotheses"]:
                st.markdown(f"- ❓ {h}")
        if ans["recommendations"]:
            st.markdown("**Recommendations**")
            for r in ans["recommendations"]:
                st.markdown(f"- ✅ {r['text']}  \n  <small>Why: {r['rationale']}</small>", unsafe_allow_html=True)
        if ans["assumptions"]:
            st.caption("Assumptions: " + " ".join(ans["assumptions"]))
        with st.expander("Limitations & data quality"):
            for l in ans["limitations"]:
                st.markdown(f"- {l}")
        if ans["proposed_action_id"]:
            st.warning(f"Proposed action **{ans['proposed_action_id']}** is waiting in the **Approvals** tab. Nothing has been changed.")
        if ans["follow_ups"]:
            st.caption("Try next: " + " | ".join(ans["follow_ups"]))
    with t2:
        try:
            charts(ans)
        except Exception as e:  # charts are optional
            st.caption(f"Charts unavailable: {e}")
    with t3:
        for e in ans["evidence"]:
            with st.expander(f"{e['id']} - {e['title']}  ({e['tool']})"):
                st.json(e["inputs"])
                for q in e["sql"]:
                    st.code(q, language="sql")
                with st.popover("Raw tool output"):
                    st.json(e["data"], expanded=False)
    with t4:
        inv = audit.get_investigation(ans["investigation_id"])
        st.caption(f"{ans['investigation_id']} - {ans['duration_ms']} ms - interpreter: {ans['interpreter']} - grounding {ans.get('grounding_rate', 1):.0%}")
        st.dataframe(pd.DataFrame([{"node": c["node"], "tool": c["tool"], "status": c["status"], "ms": c["duration_ms"]}
                                   for c in inv["tool_calls"]]), width="stretch", hide_index=True)


tab_ask, tab_appr, tab_hist, tab_defs = st.tabs(["💬 Ask", "✅ Approvals", "🗂 History", "📖 Metric definitions"])

with tab_ask:
    st.write("Ask a question about campaign performance (synthetic data, Nov 2025 - Oct 2026).")
    cols = st.columns(len(EXAMPLES))
    for c, ex in zip(cols, EXAMPLES):
        if c.button(ex, width="stretch", key=ex):
            st.session_state["q"] = ex
    q = st.text_input("Question", key="q", placeholder="e.g. Why did Meta ROAS decline in October compared with September?")
    if st.button("Investigate", type="primary") and q:
        with st.spinner("Validating data, running analyses..."):
            st.session_state["answer"] = run_investigation(q, user, deps)
    if "answer" in st.session_state:
        render(st.session_state["answer"])

with tab_appr:
    svc = ActionService()
    pending = svc.list_actions("pending_approval")
    st.write(f"{len(pending)} action(s) waiting for approval.")
    for act in pending:
        pl = act["payload"]
        with st.container(border=True):
            st.markdown(f"**{act['action_id']}** - update campaign budgets - cap ${pl['total_daily_budget']:,.2f}/day "
                        f"(${pl['total_monthly_budget']:,.0f}/month) - from {act['investigation_id']}")
            df = pd.DataFrame(pl["changes"])
            df["change_%"] = (df["proposed_daily"] / df["current_daily"] - 1) * 100
            edited = st.data_editor(df[["campaign_id", "campaign", "current_daily", "proposed_daily", "change_%"]],
                                    disabled=["campaign_id", "campaign", "current_daily", "change_%"], hide_index=True,
                                    key=f"ed_{act['action_id']}", width="stretch")
            st.caption(f"Proposed total: ${edited['proposed_daily'].sum():,.2f}/day. Guardrails: +/-50% per campaign and total <= cap. "
                       f"Acting as **{user} ({role})**.")
            c1, c2, _ = st.columns([1, 1, 4])
            comment = st.text_input("Comment (optional)", key=f"c_{act['action_id']}")
            edits = dict(zip(edited["campaign_id"], edited["proposed_daily"]))
            try:
                if c1.button("Approve & apply", key=f"a_{act['action_id']}", type="primary"):
                    st.success(svc.decide(act["action_id"], user, role, "approve", edits, comment))
                    st.rerun()
                if c2.button("Reject", key=f"r_{act['action_id']}"):
                    svc.decide(act["action_id"], user, role, "reject", None, comment)
                    st.rerun()
            except (ApprovalError, PermissionError) as e:
                st.error(str(e))
    done = [a for a in svc.list_actions() if a["status"] != "pending_approval"]
    if done:
        st.markdown("**Decided actions**")
        st.dataframe(pd.DataFrame([{"action": a["action_id"], "status": a["status"], "created": a["created_at"],
                                    "edited": a["final_payload"] is not None and a["final_payload"] != a["payload"]} for a in done]),
                     hide_index=True, width="stretch")

with tab_hist:
    rows = audit.list_investigations(30)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    pick = st.selectbox("Inspect an investigation", [r["investigation_id"] for r in rows]) if rows else None
    if pick:
        inv = audit.get_investigation(pick)
        st.json({"question": inv["question"], "intent": inv["intent"], "status": inv["status"]})
        st.dataframe(pd.DataFrame([{k: c[k] for k in ("node", "tool", "status", "duration_ms", "error")} for c in inv["tool_calls"]]),
                     hide_index=True, width="stretch")
        for a in inv["actions"]:
            st.write("Action", a["action_id"], a["status"], audit.audit_trail_for_action(a["action_id"]))

with tab_defs:
    reg = load_registry()
    sel = st.selectbox("Metric", sorted(reg.metrics))
    st.json(reg.definition(sel))
