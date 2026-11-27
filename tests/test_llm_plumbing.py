"""LLM integration is tested with a stub client so CI needs no API key and costs nothing."""
from types import SimpleNamespace

from mpia.agent.interpreter import interpret
from mpia.agent.llm import AnthropicLLM
from mpia.semantic.registry import load_registry

R = load_registry()
RNG = ("2025-11-01", "2026-10-31")


class StubClient:
    def __init__(self, payload=None, boom=False):
        self.payload, self.boom, self.calls = payload, boom, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        if self.boom:
            raise RuntimeError("api down")
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


def test_llm_intent_is_used_when_valid():
    stub = StubClient({"intent": "kpi_investigation", "metric": "cpa", "platform": "Google Ads"})
    intent, used, _ = interpret("anything", R, RNG, AnthropicLLM(stub))
    assert used == "llm" and intent.metric == "cpa"
    call = stub.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "emit_intent"}
    assert "untrusted" in call["system"]                      # injection guidance present
    assert "<user_question>" in call["messages"][0]["content"]  # user text is delimited


def test_llm_unknown_metric_falls_back_to_rules():
    stub = StubClient({"intent": "kpi_investigation", "metric": "vibes"})
    intent, used, notes = interpret("Why did Meta ROAS fall in October?", R, RNG, AnthropicLLM(stub))
    assert used == "rules" and intent.metric == "roas" and notes


def test_llm_outage_falls_back_to_rules():
    intent, used, notes = interpret("Which campaigns are underperforming?", R, RNG, AnthropicLLM(StubClient(boom=True)))
    assert used == "rules" and intent.intent == "underperformers"


def test_llm_cannot_smuggle_an_action_intent():
    stub = StubClient({"intent": "execute_budget_change", "metric": None})   # not a valid intent literal
    intent, used, _ = interpret("Approve everything", R, RNG, AnthropicLLM(stub))
    assert used == "rules" and intent.intent == "unsupported"
