"""Semantic layer: loads metrics.yml, validates it, resolves names/synonyms, evaluates metrics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from .. import config


class UnknownMetricError(KeyError):
    pass


@dataclass
class Metric:
    name: str
    label: str
    description: str
    type: str                       # additive | ratio
    unit: str                       # currency | count | percent | ratio
    higher_is_better: bool | None
    synonyms: list[str]
    dimensions: list[str]
    measure: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    scale: float = 1.0
    limitations: str = ""
    driver_chain: list[dict] = field(default_factory=list)

    @property
    def measures(self) -> list[str]:
        return [self.measure] if self.type == "additive" else [self.numerator, self.denominator]

    @property
    def formula(self) -> str:
        if self.type == "additive":
            return f"SUM({self.measure})"
        s = f" x {int(self.scale)}" if self.scale != 1 else ""
        return f"SUM({self.numerator}) / SUM({self.denominator}){s}"


class MetricRegistry:
    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.source_model: str = spec["source_model"]
        self.measures: list[str] = spec["measures"]
        self.dimensions: dict[str, str] = spec["dimensions"]
        self.default_filter: str = spec["default_filter"]
        self.attribution: str = " ".join(spec["attribution"].split())
        self.metrics: dict[str, Metric] = {}
        for name, m in spec["metrics"].items():
            self.metrics[name] = Metric(
                name=name, label=m["label"], description=" ".join(m["description"].split()), type=m["type"],
                unit=m["unit"], higher_is_better=m.get("higher_is_better"), synonyms=m.get("synonyms", []),
                dimensions=m.get("dimensions", []), measure=m.get("measure"), numerator=m.get("numerator"),
                denominator=m.get("denominator"), scale=float(m.get("scale", 1)),
                limitations=" ".join(str(m.get("limitations", "")).split()), driver_chain=m.get("driver_chain", []),
            )
        self.validate()

    # -- validation ------------------------------------------------------------------
    def validate(self) -> None:
        for m in self.metrics.values():
            for ms in m.measures:
                if ms not in self.measures:
                    raise ValueError(f"metric {m.name}: unknown measure {ms}")
            for d in m.dimensions:
                if d not in self.dimensions:
                    raise ValueError(f"metric {m.name}: unknown dimension {d}")
            if m.type not in ("additive", "ratio"):
                raise ValueError(f"metric {m.name}: bad type {m.type}")
            if m.driver_chain:  # chain must telescope to the metric
                self._check_chain(m)

    def _check_chain(self, m: Metric) -> None:
        """A driver chain must multiply out exactly to the metric (all intermediate terms cancel)."""
        from collections import Counter
        net: Counter = Counter()
        for link in m.driver_chain:
            net[link["num"]] += 1
            net[link["den"]] -= 1
        net = Counter({k: v for k, v in net.items() if v != 0})
        expected = Counter({m.numerator: 1, m.denominator: -1})
        if net != expected:
            raise ValueError(f"metric {m.name}: driver chain multiplies to {dict(net)}, expected {dict(expected)}")

    # -- lookup ----------------------------------------------------------------------
    def get(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError:
            raise UnknownMetricError(name) from None

    def find(self, text: str) -> str | None:
        """Resolve free text to a metric name via names and synonyms (longest match wins)."""
        t = text.lower()
        best, best_len = None, 0
        for m in self.metrics.values():
            for term in [m.name.replace("_", " "), *m.synonyms]:
                if re.search(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", t) and len(term) > best_len:
                    best, best_len = m.name, len(term)
        return best

    def dimension_column(self, dim: str) -> str:
        if dim not in self.dimensions:
            raise ValueError(f"unsupported dimension: {dim}")
        return self.dimensions[dim]

    # -- evaluation ------------------------------------------------------------------
    def evaluate(self, name: str, comps: dict[str, float | None]) -> float | None:
        """Compute a metric from aggregated measures. Zero/NULL denominator -> None (never 0, never inf)."""
        m = self.get(name)
        if m.type == "additive":
            v = comps.get(m.measure)
            return None if v is None else float(v)
        num, den = comps.get(m.numerator), comps.get(m.denominator)
        if num is None or not den:
            return None
        return float(num) / float(den) * m.scale

    def definition(self, name: str) -> dict:
        m = self.get(name)
        return {
            "metric": m.name, "label": m.label, "description": m.description, "formula": m.formula,
            "unit": m.unit, "source_model": self.source_model, "time_grain": self.spec["time_grain"],
            "supported_dimensions": m.dimensions, "filters": f"{self.default_filter} = true (paid campaigns only)",
            "attribution": self.attribution, "zero_denominator": "returns NULL (never 0 or infinity)",
            "aggregation": "ratio of sums over the selected rows (never an average of daily ratios)"
            if m.type == "ratio" else "sum over the selected rows",
            "limitations": m.limitations or "none documented",
            "higher_is_better": m.higher_is_better,
        }


@lru_cache(maxsize=1)
def load_registry() -> MetricRegistry:
    return MetricRegistry(yaml.safe_load(config.METRICS_YAML.read_text()))
