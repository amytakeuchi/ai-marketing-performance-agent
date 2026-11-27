"""KPI comparison between two periods (FR: compare current vs baseline)."""
from __future__ import annotations

from ..semantic.warehouse import Warehouse
from .base import ToolResult, pct_change


def _period_block(wh: Warehouse, metric: str, period, platform, campaign_ids):
    start, end = period
    value, comps, sql = wh.metric_value(metric, start, end, platform, campaign_ids)
    return {"start": start, "end": end, "value": value, "components": comps}, sql


def compare_kpi(wh: Warehouse, metric: str, current: tuple[str, str], baseline: tuple[str, str],
                platform: str | None = None, campaign_ids: list[str] | None = None) -> ToolResult:
    m = wh.registry.get(metric)
    cur, sql_c = _period_block(wh, metric, current, platform, campaign_ids)
    base, sql_b = _period_block(wh, metric, baseline, platform, campaign_ids)
    pc = pct_change(cur["value"], base["value"])
    if pc is None:
        direction = "unknown"
    elif abs(pc) < 0.01:
        direction = "flat"
    else:
        up = pc > 0
        good = (up and m.higher_is_better) or (not up and m.higher_is_better is False)
        direction = "improved" if good else "declined" if m.higher_is_better is not None else ("increased" if up else "decreased")
    data = {
        "metric": metric, "label": m.label, "unit": m.unit, "higher_is_better": m.higher_is_better,
        "platform": platform, "current": cur, "baseline": base,
        "abs_change": None if None in (cur["value"], base["value"]) else cur["value"] - base["value"],
        "pct_change": pc, "direction": direction,
    }
    return ToolResult("compare_kpi", {"metric": metric, "current": list(current), "baseline": list(baseline),
                                      "platform": platform}, data, sql=[sql_c, sql_b])


def kpi_timeseries(wh: Warehouse, metric: str, start: str, end: str, platform: str | None = None,
                   grain: str = "week", campaign_ids: list[str] | None = None) -> ToolResult:
    rows, sql = wh.components([grain], start, end, platform, campaign_ids)
    series = [{"period": r[wh.registry.dimension_column(grain)],
               "value": wh.registry.evaluate(metric, r)} for r in rows]
    return ToolResult("kpi_timeseries", {"metric": metric, "start": start, "end": end, "platform": platform,
                                         "grain": grain}, {"metric": metric, "series": series}, sql=[sql])
