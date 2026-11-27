"""Grounding check: every number in generated prose must be traceable to tool output.
Used to validate LLM-written summaries (reject -> retry -> deterministic fallback) and, in evals, to
measure how much of the final answer is supported by evidence."""
from __future__ import annotations

import re
from typing import Any

_REF = re.compile(r"\[E\d+(?:\s*,\s*E\d+)*\]")
_DATE = re.compile(r"\b20\d{2}-\d{2}(?:-\d{2})?\b")
_YEAR = re.compile(r"\b20\d{2}\b")
_NUM = re.compile(r"(?<![\w.])[-+\u2212]?\$?\d[\d,]*(?:\.\d+)?%?")


def _flatten(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten(v, out)
    elif isinstance(obj, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", obj):   # numbers embedded in strings (dates, labels)
            out.append(float(m.group()))


def evidence_numbers(evidence: list[dict]) -> list[float]:
    nums: list[float] = []
    for e in evidence:
        _flatten(e.get("data"), nums)
        _flatten(e.get("inputs"), nums)
    expanded = []
    for n in nums:
        expanded += [n, abs(n), n * 100, abs(n) * 100]
    return expanded


def ungrounded_numbers(text: str, evidence: list[dict]) -> list[str]:
    allowed = evidence_numbers(evidence)
    t = _DATE.sub(" ", _REF.sub(" ", text))
    t = _YEAR.sub(" ", t)
    bad = []
    for m in _NUM.finditer(t):
        tok = m.group()
        clean = tok.replace(",", "").replace("$", "").replace("%", "").replace("\u2212", "-").lstrip("+-")
        try:
            v = float(clean)
        except ValueError:
            continue
        has_sym = "$" in tok or "%" in tok
        if not has_sym and "." not in clean and v <= 10:      # small counts / ordinals ("top 3", "2 factors")
            continue
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        tol_abs = {0: 0.51, 1: 0.051}.get(decimals, 0.0051)
        if not any(abs(v - a) <= max(tol_abs, 0.01 * abs(a)) for a in allowed):
            bad.append(tok)
    return bad


def grounding_rate(text: str, evidence: list[dict]) -> float:
    toks = [m.group() for m in _NUM.finditer(_YEAR.sub(" ", _DATE.sub(" ", _REF.sub(" ", text))))]
    if not toks:
        return 1.0
    return 1 - len(ungrounded_numbers(text, evidence)) / len(toks)
