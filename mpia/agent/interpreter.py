"""Request interpretation. Two interchangeable interpreters produce the same validated `Intent`:
  * RuleInterpreter  - deterministic keyword/regex parser (offline, free, the eval baseline)
  * LLMInterpreter   - Claude tool-use (forced `emit_intent` call); falls back to rules on any failure
The LLM only ever returns a structured Intent. It never writes SQL and never sees query results."""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from ..semantic.registry import MetricRegistry
from .intents import Intent, finalize_intent, latest_full_month, month_bounds

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9
_MONTH_RE = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b(?:\s+(?:of\s+)?(20\d{2}))?", re.I)
_MAY_OK = re.compile(r"(?:in|of|during|for|from|to|and|vs\.?|versus|than|with|between|since)\s+may\b|\bmay\s+20\d{2}", re.I)

PLATFORM_WORDS = {"Meta Ads": ["meta", "facebook", "instagram", "fb "], "Google Ads": ["google", "youtube", "adwords"]}
ACTION_WORDS = re.compile(r"\b(pause|stop|turn off|shut down|delete|launch|create (?:a )?campaign|increase (?:the )?budget (?:of|for|on)|"
                          r"set (?:the )?budget|approve|execute|apply)\b", re.I)


def _find_months(text: str, as_of: date) -> list[tuple[int, int]]:
    out = []
    for m in _MONTH_RE.finditer(text):
        word = m.group(1).lower()
        if word == "may" and not (m.group(2) or _MAY_OK.search(text)):
            continue
        month = MONTHS[word]
        if m.group(2):
            year = int(m.group(2))
        else:
            year = as_of.year if date(as_of.year, month, 1) <= as_of else as_of.year - 1
        out.append((year, month))
    return out


def parse_periods(text: str, as_of: date) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
    t = text.lower()
    months = _find_months(text, as_of)
    if len(months) >= 2:
        a, b = sorted(months[:2])           # chronologically earlier / later
        (cs, ce), (bs, be) = month_bounds(*b), month_bounds(*a)
        return (str(cs), str(ce)), (str(bs), str(be))
    if len(months) == 1:
        cs, ce = month_bounds(*months[0])
        return (str(cs), str(ce)), None
    if re.search(r"\blast week\b", t):
        return (str(as_of - timedelta(days=6)), str(as_of)), None
    m = re.search(r"last\s+(\d+)\s+(day|days|week|weeks)", t)
    if m:
        n = int(m.group(1)) * (7 if m.group(2).startswith("week") else 1)
        return (str(as_of - timedelta(days=n - 1)), str(as_of)), None
    if re.search(r"\b(last|this|latest|most recent|past)\s+month\b", t):
        y, mo = latest_full_month(as_of)
        cs, ce = month_bounds(y, mo)
        return (str(cs), str(ce)), None
    return None, None


def _platform(text: str) -> str | None:
    t = " " + text.lower() + " "
    hits = [p for p, words in PLATFORM_WORDS.items() if any(w in t for w in words)]
    return hits[0] if len(hits) == 1 else None


def _budget(text: str) -> float | None:
    m = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)(?:\s*([km])\b)?", text, re.I) or \
        re.search(r"\b(\d[\d,]*(?:\.\d+)?)\s*([km])\b", text, re.I)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    mult = {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
    return v * mult


class RuleInterpreter:
    name = "rules"

    def __init__(self, registry: MetricRegistry):
        self.registry = registry

    def interpret(self, question: str, data_range: tuple[str, str]) -> Intent:
        q, t = question.strip(), question.lower()
        as_of = date.fromisoformat(data_range[1])
        platform = _platform(q)
        cur, base = parse_periods(q, as_of)
        metric = self.registry.find(q)
        kw = dict(platform=platform, metric=metric,
                  current_start=cur[0] if cur else None, current_end=cur[1] if cur else None,
                  baseline_start=base[0] if base else None, baseline_end=base[1] if base else None)

        if ACTION_WORDS.search(t):
            return Intent(intent="unsupported", unsupported_reason=(
                "I can analyse performance and *propose* budget changes for human approval, but I can't pause, "
                "launch, delete or directly change campaigns, and I can't approve actions on anyone's behalf."))
        if re.search(r"\b(define|definition|how (?:do you|is|are) .*(?:calculat|comput|defin)|what does .* mean|what is (?:the )?(?:\w+ )?(?:roas|ctr|cpc|cpa|cac|aov|cpm))", t) \
                or (metric and re.search(r"\bmeans?\b|\bstands? for\b|\bmeaning\b", t)):
            return Intent(intent="metric_definition", metric=metric)
        if re.search(r"\b(budget|allocate|allocation|reallocate|redistribute|spread|distribute|divide|shift (?:the )?spend|split)\b", t):
            return Intent(intent="budget_allocation", budget_amount=_budget(q), platform=platform)
        if re.search(r"\b(funnel|drop[- ]?off|drop off|abandon\w*|check(?:ing)?[ -]?out|losing (?:people|users|visitors|customers|shoppers))\b|"
                     r"where (?:are|do) (?:users|visitors|customers|shoppers) ", t):
            return Intent(intent="funnel_dropoff", platform=platform,
                          **{k: v for k, v in kw.items() if k.startswith(("current", "baseline"))})
        if re.search(r"\b(under[- ]?perform\w*|worst|weakest|lowest[- ]performing|poor(?:ly)? performing|wast\w+|bleed\w*|losing money|"
                     r"should (?:i|we) (?:cut|drop|reduce|scale back)|which (?:\w+ ){0,2}campaigns?)\b", t):
            return Intent(intent="underperformers", **{k: v for k, v in kw.items() if k != "metric"})
        if re.search(r"\b(why|what happened|what changed|going on|decline[ds]?|drop(?:ped)?|dip(?:ped|s)?|tank(?:ed|s)?|fell|fall|spik\w+|"
                     r"surg\w+|plung\w+|increase[ds]?|rise|rose|go(?:es)? (?:up|down)|went (?:up|down)|worse|better|lower|higher|trend\w*|"
                     r"change[ds]?|compare[ds]?|versus|vs\.?|how (?:is|are|did|much|many)|performance|converting)\b", t):
            return Intent(intent="kpi_investigation", **kw)
        return Intent(intent="unsupported", unsupported_reason=(
            "That doesn't look like a marketing-performance question I can answer from the warehouse. "
            "Try asking why a KPI changed, which campaigns underperform, where users drop off, or how to allocate a budget."))


def interpret(question: str, registry: MetricRegistry, data_range: tuple[str, str], llm=None) -> tuple[Intent, str, list[str]]:
    """Returns (finalized intent, interpreter used, notes)."""
    notes: list[str] = []
    intent = None
    used = "rules"
    if llm is not None:
        try:
            raw = llm.interpret(question, {"as_of": data_range[1], "data_range": data_range,
                                           "metrics": {n: m.synonyms for n, m in registry.metrics.items()}})
            intent = Intent(**raw)
            if intent.metric and intent.metric not in registry.metrics:
                notes.append(f"LLM proposed unknown metric '{intent.metric}'; falling back to rules.")
                intent = None
            else:
                used = "llm"
        except Exception as e:  # any API/validation failure -> deterministic fallback
            notes.append(f"LLM interpretation failed ({type(e).__name__}); used rule-based interpreter.")
            intent = None
    if intent is None:
        intent = RuleInterpreter(registry).interpret(question, data_range)
        used = "rules"
    return finalize_intent(intent, registry, data_range), used, notes
