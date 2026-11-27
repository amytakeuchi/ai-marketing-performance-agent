from __future__ import annotations

import calendar
from datetime import date


def money(v: float, d: int = 0) -> str:
    return f"${v:,.{d}f}"


def pct(v: float | None, signed: bool = True, d: int = 1) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.{d}f}%" if signed else f"{v * 100:.{d}f}%"


def value(unit: str, v: float | None) -> str:
    if v is None:
        return "n/a"
    if unit == "currency":
        return money(v, 2 if abs(v) < 100 else 0)
    if unit == "percent":
        return f"{v * 100:.2f}%"
    if unit == "ratio":
        return f"{v:.2f}"
    return f"{v:,.0f}"


def period_label(p: tuple[str, str] | list[str]) -> str:
    s, e = date.fromisoformat(p[0]), date.fromisoformat(p[1])
    if s.day == 1 and s.year == e.year and s.month == e.month and e.day == calendar.monthrange(e.year, e.month)[1]:
        return f"{calendar.month_abbr[s.month]} {s.year}"
    return f"{p[0]} to {p[1]}"
