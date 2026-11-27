"""LangGraph workflow:  interpret -> validate -> analyze -> narrate -> [propose] -> finalize
Every node is audited; failures become explicit, honest responses (never a fabricated answer)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..actions.service import ActionService
from ..audit.logger import AuditLogger
from ..semantic.registry import MetricRegistry, load_registry
from ..semantic.warehouse import Warehouse
from ..tools.validation import validate_data
from . import fmt
from .analysis import run_analysis
from .grounding import grounding_rate, ungrounded_numbers
from .intents import Intent
from .interpreter import interpret
from .llm import get_llm
from .runner import ToolError, ToolRunner


class State(TypedDict, total=False):
    question: str
    user: str
    inv_id: str
    t0: float
    intent: dict
    interpreter: str
    validation: dict
    analysis: dict
    summary: str
    summary_source: str
    action_id: str
    status: str
    message: str
    answer: dict


@dataclass
class Deps:
    wh: Warehouse = field(default_factory=Warehouse)
    audit: AuditLogger = field(default_factory=AuditLogger)
    registry: MetricRegistry = field(default_factory=load_registry)
    llm: Any = field(default_factory=get_llm)
    actions: ActionService | None = None

    def action_service(self) -> ActionService:
        if self.actions is None:
            self.actions = ActionService()
        return self.actions


def _validation_ranges(intent: Intent, as_of: str) -> list[tuple[str, str]]:
    if intent.intent == "budget_allocation":
        end = date.fromisoformat(as_of)
        return [(str(end - timedelta(days=239)), str(end))]
    return [r for r in (intent.current, intent.baseline) if r]


def build_graph(deps: Deps):
    def guarded(name, fn):
        def wrapper(state: State) -> dict:
            try:
                return fn(state)
            except ToolError as e:
                return {"status": "error", "message": f"A tool failed while running '{e.tool}', so no answer was produced. "
                                                        f"Details are in the audit log. ({e.original})"}
            except Exception as e:  # noqa: BLE001 - last-resort guard so the user always gets a clear message
                return {"status": "error", "message": f"Unexpected error in step '{name}': {type(e).__name__}: {e}"}
        return wrapper

    # ---- nodes ----------------------------------------------------------------------------
    def n_interpret(state: State) -> dict:
        t0 = time.perf_counter()
        it, used, notes = interpret(state["question"], deps.registry, deps.wh.data_range(), deps.llm)
        deps.audit.set_intent(state["inv_id"], it.model_dump(), used)
        deps.audit.log_tool_call(state["inv_id"], "interpret", f"interpreter:{used}", {"question": state["question"]},
                                 {"intent": it.intent, "metric": it.metric, "platform": it.platform, "notes": notes},
                                 None, "ok", None, int((time.perf_counter() - t0) * 1000))
        upd: dict = {"intent": it.model_dump(), "interpreter": used}
        if it.intent == "unsupported":
            upd.update(status="unsupported", message=it.unsupported_reason or "Unsupported request.")
        elif it.clarification:
            upd.update(status="clarification", message=it.clarification)
        return upd

    def n_validate(state: State) -> dict:
        it = Intent(**state["intent"])
        if it.intent == "metric_definition":
            return {}
        run = ToolRunner(deps.audit, state["inv_id"], "validate")
        results = [run(validate_data, deps.wh, s, e, it.platform) for s, e in _validation_ranges(it, deps.wh.data_range()[1])]
        checks, seen = [], set()
        for r, label in zip(results, ["current", "baseline"]):
            for c in r.data["checks"]:
                if c["detail"] not in seen:
                    seen.add(c["detail"])
                    checks.append({**c, "period": label})
        statuses = {r.data["status"] for r in results}
        overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
        val = {"status": overall, "checks": checks, "warehouse_range": results[0].data["warehouse_range"]}
        if overall == "fail":
            why = "; ".join(c["detail"] for c in checks if c["status"] == "fail")
            return {"validation": val, "status": "blocked",
                    "message": f"I can't answer this reliably: {why} I'd rather say so than guess."}
        return {"validation": val}

    def n_analyze(state: State) -> dict:
        it = Intent(**state["intent"])
        run = ToolRunner(deps.audit, state["inv_id"], "analyze")
        analysis = run_analysis(it, deps.wh, run, state.get("validation"))
        return {"analysis": analysis}

    def n_narrate(state: State) -> dict:
        a = state["analysis"]
        body = [f["text"] for f in a["findings"] if f["text"] != a["headline"]][:2]
        summary, source = " ".join([a["headline"], *body]), "template"
        if deps.llm is not None and a["kind"] != "metric_definition":
            t0 = time.perf_counter()
            compact = {"headline": a["headline"], "findings": [{"text": f["text"], "evidence": f["evidence"]} for f in a["findings"]],
                       "hypotheses": a["hypotheses"], "limitations": a["limitations"][:3]}
            feedback, status = None, "fallback"
            for _ in range(2):
                try:
                    draft = deps.llm.summarize(state["question"], compact, feedback)
                except Exception as e:  # noqa: BLE001
                    status = f"llm_error:{type(e).__name__}"
                    break
                bad = ungrounded_numbers(draft, a["evidence"])
                if draft and not bad:
                    summary, source, status = draft, "llm", "ok"
                    break
                feedback = f"these numbers are not in the evidence: {bad}"
            deps.audit.log_tool_call(state["inv_id"], "narrate", "llm_summarize", {"retries": 1},
                                     {"source": source, "status": status}, None, "ok", None, int((time.perf_counter() - t0) * 1000))
        return {"summary": summary, "summary_source": source}

    def n_propose(state: State) -> dict:
        a = state["analysis"]
        t0 = time.perf_counter()
        action_id = deps.action_service().create_proposal(state["inv_id"], a["proposal"])
        deps.audit.log_tool_call(state["inv_id"], "propose", "create_proposal", {"action_type": "update_campaign_budgets"},
                                 {"action_id": action_id, "status": "pending_approval"}, None, "ok", None,
                                 int((time.perf_counter() - t0) * 1000))
        return {"action_id": action_id}

    def n_finalize(state: State) -> dict:
        status = state.get("status", "completed")
        a = state.get("analysis") or {}
        ans: dict = {
            "status": status, "question": state["question"], "investigation_id": state["inv_id"],
            "intent": state.get("intent"), "interpreter": state.get("interpreter"),
            "message": state.get("message"), "validation": state.get("validation"),
            "summary": state.get("summary"), "summary_source": state.get("summary_source"),
            "headline": a.get("headline"), "findings": a.get("findings", []), "hypotheses": a.get("hypotheses", []),
            "recommendations": a.get("recommendations", []), "limitations": a.get("limitations", []),
            "assumptions": a.get("assumptions", []), "follow_ups": a.get("follow_ups", []),
            "evidence": a.get("evidence", []), "facts": a.get("facts", {}), "proposal": a.get("proposal"),
            "proposed_action_id": state.get("action_id"), "kind": a.get("kind"),
        }
        if a:
            text = " ".join([a["headline"], *[f["text"] for f in a["findings"]], *[r["text"] for r in a["recommendations"]],
                             state.get("summary") or ""])
            ans["grounding_rate"] = grounding_rate(text, a["evidence"])
        ans["duration_ms"] = int((time.perf_counter() - state["t0"]) * 1000)
        deps.audit.finish(state["inv_id"], status, ans, ans["duration_ms"])
        return {"answer": ans, "status": status}

    # ---- routing --------------------------------------------------------------------------
    stop = lambda s: "finalize" if s.get("status") in ("unsupported", "clarification", "blocked", "error") else None  # noqa: E731
    g = StateGraph(State)
    for name, fn in [("interpret", n_interpret), ("validate", n_validate), ("analyze", n_analyze),
                     ("narrate", n_narrate), ("propose", n_propose), ("finalize", n_finalize)]:
        g.add_node(name, guarded(name, fn))
    g.add_edge(START, "interpret")
    g.add_conditional_edges("interpret", lambda s: stop(s) or "validate", {"validate": "validate", "finalize": "finalize"})
    g.add_conditional_edges("validate", lambda s: stop(s) or "analyze", {"analyze": "analyze", "finalize": "finalize"})
    g.add_conditional_edges("analyze", lambda s: stop(s) or "narrate", {"narrate": "narrate", "finalize": "finalize"})
    g.add_conditional_edges("narrate", lambda s: "propose" if (s.get("analysis") or {}).get("proposal") else "finalize",
                            {"propose": "propose", "finalize": "finalize"})
    g.add_edge("propose", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_cache: dict[int, Any] = {}


def run_investigation(question: str, user: str = "demo", deps: Deps | None = None) -> dict:
    deps = deps or Deps()
    graph = _cache.get(id(deps)) or build_graph(deps)
    _cache[id(deps)] = graph
    inv_id = deps.audit.start_investigation(question, user)
    state = graph.invoke({"question": question, "user": user, "inv_id": inv_id, "t0": time.perf_counter()})
    return state["answer"]
