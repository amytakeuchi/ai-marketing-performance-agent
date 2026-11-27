"""Read-only warehouse access. All SQL is compiled from the semantic layer with whitelisted
identifiers and bound parameters - there is no code path that executes LLM-written SQL."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from .. import db
from .registry import MetricRegistry, load_registry

FUNNEL_DIMS = {"platform": "platform", "campaign_id": "campaign_id", "campaign": "campaign_name",
               "landing_page": "landing_page_id", "device": "device", "funnel_stage": "funnel_stage",
               "week": "date_trunc('week', date_day)::date", "month": "date_trunc('month', date_day)::date"}
FUNNEL_DIMS["date"] = "date_day"
FUNNEL_FILTER_COLS = {"landing_page": "landing_page_id", "device": "device", "campaign_id": "campaign_id",
                      "funnel_stage": "funnel_stage", "platform": "platform"}
FUNNEL_MEASURES = ["sessions", "add_to_carts", "checkouts", "purchases"]


def _clean(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return v


def render_sql(sql: str, params: dict) -> str:
    """Human-readable SQL with parameters inlined (for evidence/audit display only)."""
    out = sql
    for k, v in params.items():
        lit = "ARRAY[" + ", ".join(f"'{x}'" for x in v) + "]" if isinstance(v, (list, tuple)) else \
              (f"'{v}'" if isinstance(v, (str, date)) else str(v))
        out = out.replace(f"%({k})s", lit)
    return " ".join(out.split())


class Warehouse:
    def __init__(self, registry: MetricRegistry | None = None, role: str = "analyst_ro"):
        self.registry = registry or load_registry()
        self.role = role

    # ------------------------------------------------------------------
    def _where(self, start, end, platform, campaign_ids, extra_cols=False):
        clauses = ["date_day BETWEEN %(start)s AND %(end)s", self.registry.default_filter]
        params: dict = {"start": start, "end": end}
        if platform:
            clauses.append("platform = %(platform)s")
            params["platform"] = platform
        if campaign_ids:
            clauses.append("campaign_id = ANY(%(cids)s)")
            params["cids"] = list(campaign_ids)
        return " AND ".join(clauses), params

    def components(self, group_by: list[str], start: str, end: str, platform: str | None = None,
                   campaign_ids: list[str] | None = None, measures: list[str] | None = None):
        """Aggregate additive measures from the semantic source model. Returns (rows, sql_text)."""
        measures = measures or self.registry.measures
        bad = [m for m in measures if m not in self.registry.measures]
        if bad:
            raise ValueError(f"unknown measures: {bad}")
        cols = [self.registry.dimension_column(d) for d in group_by]
        select = ", ".join([*cols, *[f"SUM({m}) AS {m}" for m in measures]])
        where, params = self._where(start, end, platform, campaign_ids)
        sql = f"SELECT {select} FROM {self.registry.source_model} WHERE {where}"
        if cols:
            sql += f" GROUP BY {', '.join(cols)} ORDER BY {', '.join(cols)}"
        rows = db.query(self.role, sql, params)
        rows = [{k: _clean(v) for k, v in r.items()} for r in rows]
        return rows, render_sql(sql, params)

    def funnel_components(self, group_by: list[str], start: str, end: str, platform: str | None = None,
                          campaign_ids: list[str] | None = None, filters: dict | None = None):
        cols = []
        for d in group_by:
            if d not in FUNNEL_DIMS:
                raise ValueError(f"unsupported funnel dimension: {d}")
            cols.append(FUNNEL_DIMS[d])
        select_dims = [f"{FUNNEL_DIMS[d]} AS {d}" for d in group_by]
        select = ", ".join([*select_dims, *[f"SUM({m}) AS {m}" for m in FUNNEL_MEASURES]])
        clauses = ["date_day BETWEEN %(start)s AND %(end)s", "platform <> 'Non-paid'"]
        params: dict = {"start": start, "end": end}
        if platform:
            clauses.append("platform = %(platform)s")
            params["platform"] = platform
        if campaign_ids:
            clauses.append("campaign_id = ANY(%(cids)s)")
            params["cids"] = list(campaign_ids)
        for i, (k, v) in enumerate((filters or {}).items()):
            if k not in FUNNEL_FILTER_COLS:
                raise ValueError(f"unsupported funnel filter: {k}")
            clauses.append(f"{FUNNEL_FILTER_COLS[k]} = %(f{i})s")
            params[f"f{i}"] = v
        sql = f"SELECT {select} FROM marts.mart_web_funnel_daily WHERE {' AND '.join(clauses)}"
        if group_by:
            sql += f" GROUP BY {', '.join(str(i + 1) for i in range(len(group_by)))} ORDER BY 1"
        rows = db.query(self.role, sql, params)
        rows = [{k: _clean(v) for k, v in r.items()} for r in rows]
        return rows, render_sql(sql, params)

    def data_range(self) -> tuple[str, str]:
        r = db.query(self.role, "SELECT min(date_day) AS lo, max(date_day) AS hi FROM marts.mart_campaign_daily")[0]
        return _clean(r["lo"]), _clean(r["hi"])

    def metric_value(self, metric: str, start: str, end: str, platform=None, campaign_ids=None):
        rows, sql = self.components([], start, end, platform, campaign_ids)
        comps = rows[0] if rows else {}
        return self.registry.evaluate(metric, comps), comps, sql
