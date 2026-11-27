"""Structured intent (the only thing an LLM is allowed to produce for routing) + period/defaults logic."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from ..semantic.registry import MetricRegistry

IntentName = Literal["kpi_investigation", "underperformers", "budget_allocation", "funnel_dropoff",
                     "metric_definition", "unsupported"]
PLATFORMS = ("Meta Ads", "Google Ads")


class Intent(BaseModel):
    intent: IntentName
    metric: str | None = Field(default=None, description="Metric name from the semantic layer, e.g. roas")
    platform: Literal["Meta Ads", "Google Ads"] | None = None
    current_start: str | None = Field(default=None, description="ISO date")
    current_end: str | None = None
    baseline_start: str | None = None
    baseline_end: str | None = None
    budget_amount: float | None = Field(default=None, description="Total monthly budget in USD")
    clarification: str | None = Field(default=None, description="Question to ask the user if the request is ambiguous")
    unsupported_reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)

    @property
    def current(self) -> tuple[str, str] | None:
        return (self.current_start, self.current_end) if self.current_start and self.current_end else None

    @property
    def baseline(self) -> tuple[str, str] | None:
        return (self.baseline_start, self.baseline_end) if self.baseline_start and self.baseline_end else None


def month_bounds(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def prev_month(y: int, m: int) -> tuple[int, int]:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def latest_full_month(as_of: date) -> tuple[int, int]:
    if as_of.day == calendar.monthrange(as_of.year, as_of.month)[1]:
        return as_of.year, as_of.month
    return prev_month(as_of.year, as_of.month)


def _is_full_month(s: date, e: date) -> bool:
    return s.day == 1 and s.year == e.year and s.month == e.month and e.day == calendar.monthrange(e.year, e.month)[1]


def finalize_intent(it: Intent, registry: MetricRegistry, data_range: tuple[str, str]) -> Intent:
    """Apply defaults, validate against the semantic layer, and turn ambiguity into a clarification."""
    it = it.model_copy(deep=True)
    as_of = date.fromisoformat(data_range[1])

    if it.intent in ("unsupported",):
        return it
    if it.intent == "metric_definition":
        if not it.metric or it.metric not in registry.metrics:
            it.clarification = "Which metric would you like defined? Available: " + ", ".join(sorted(registry.metrics))
        return it

    if it.metric and it.metric not in registry.metrics:
        it.clarification = (f"I don't have a governed definition for '{it.metric}'. "
                            f"Available metrics: {', '.join(sorted(registry.metrics))}.")
        return it
    if it.intent == "kpi_investigation" and not it.metric:
        it.metric = "roas"
        it.assumptions.append("No metric was named, so I assumed ROAS (return on ad spend) as 'performance'.")

    if it.intent == "budget_allocation":
        if not it.budget_amount:
            it.clarification = "What total monthly budget should I plan for (e.g. $50,000)?"
            return it
        it.current_start = it.current_end = it.baseline_start = it.baseline_end = None
        return it

    # periods
    if it.current is None:
        y, m = latest_full_month(as_of)
        s, e = month_bounds(y, m)
        it.current_start, it.current_end = str(s), str(e)
        it.assumptions.append(f"No period was given, so I used the latest complete month ({calendar.month_name[m]} {y}).")
    cs, ce = date.fromisoformat(it.current_start), date.fromisoformat(it.current_end)
    if cs > ce:
        cs, ce = ce, cs
        it.current_start, it.current_end = str(cs), str(ce)
    if it.baseline is None:
        if _is_full_month(cs, ce):
            py, pm = prev_month(cs.year, cs.month)
            bs, be = month_bounds(py, pm)
        else:
            n = (ce - cs).days + 1
            be, bs = cs - timedelta(days=1), cs - timedelta(days=n)
        it.baseline_start, it.baseline_end = str(bs), str(be)
        it.assumptions.append(f"Compared against the immediately preceding period ({bs} to {be}).")
    return it
