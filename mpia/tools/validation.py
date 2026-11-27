"""Data-quality checks run before every investigation (BRD: validate before analyzing)."""
from __future__ import annotations

from .. import db
from ..semantic.warehouse import Warehouse
from .base import ToolResult


def validate_data(wh: Warehouse, start: str, end: str, platform: str | None = None) -> ToolResult:
    role = wh.role
    plat_sql = "AND platform = %(platform)s" if platform else ""
    params = {"start": start, "end": end, **({"platform": platform} if platform else {})}
    sqls: list[str] = []
    checks: list[dict] = []

    def run(sql: str, p: dict | None = None):
        sqls.append(" ".join(sql.split()))
        return db.query(role, sql, p if p is not None else params)

    lo, hi = wh.data_range()
    cov = run(f"""SELECT count(DISTINCT date_day) AS days, min(date_day) AS first_day, max(date_day) AS last_day,
                         coalesce(sum(spend), 0) AS spend
                  FROM marts.mart_campaign_daily
                  WHERE date_day BETWEEN %(start)s AND %(end)s AND is_paid {plat_sql}""")[0]
    expected_days = (db.query(role, "SELECT (%(e)s::date - %(s)s::date + 1) AS n", {"s": start, "e": end})[0]["n"])
    covered = int(cov["days"])
    if covered == 0 or float(cov["spend"]) == 0:
        checks.append({"name": "coverage", "status": "fail",
                       "detail": f"No paid-media data for {start}..{end} (warehouse covers {lo}..{hi})."})
    elif covered < expected_days:
        checks.append({"name": "coverage", "status": "warn",
                       "detail": f"Data present for {covered} of {expected_days} days in range.", "value": covered})
    else:
        checks.append({"name": "coverage", "status": "pass",
                       "detail": f"All {expected_days} days in {start}..{end} have data (warehouse covers {lo}..{hi}).",
                       "value": covered})

    gaps = run(f"""SELECT campaign_id, min(date_day) AS first_day, max(date_day) AS last_day, count(*) AS days
                   FROM marts.mart_campaign_daily
                   WHERE date_day BETWEEN %(start)s AND %(end)s AND is_paid AND NOT has_ad_data {plat_sql}
                   GROUP BY campaign_id ORDER BY campaign_id""")
    if gaps:
        gdesc = "; ".join(f"{g['campaign_id']} {g['first_day']}..{g['last_day']} ({g['days']} d)" for g in gaps)
        checks.append({"name": "ad_feed_gaps", "status": "warn", "value": sum(g["days"] for g in gaps),
                       "detail": f"Ad-platform feed missing while orders/sessions exist: {gdesc}. "
                                 "Spend is understated on those days, so ROAS/CPA for those campaign-days are unreliable.",
                       "rows": [{k: str(v) for k, v in g.items()} for g in gaps]})
    else:
        checks.append({"name": "ad_feed_gaps", "status": "pass", "detail": "No ad-feed gaps in range.", "value": 0})

    nulls = run(f"""SELECT count(*) AS n FROM marts.mart_campaign_daily
                    WHERE date_day BETWEEN %(start)s AND %(end)s AND is_paid AND clicks_missing {plat_sql}""")[0]["n"]
    checks.append({"name": "null_clicks", "status": "warn" if nulls else "pass", "value": int(nulls),
                   "detail": (f"{nulls} campaign-day rows have NULL clicks; click-based metrics (CTR, CPC) ignore them."
                              if nulls else "No NULL click values in range.")})

    dups = run(f"""SELECT count(*) AS n FROM marts.mart_campaign_daily
                   WHERE date_day BETWEEN %(start)s AND %(end)s AND is_paid AND had_duplicate {plat_sql}""")[0]["n"]
    checks.append({"name": "duplicates_removed", "status": "warn" if dups else "pass", "value": int(dups),
                   "detail": (f"{dups} campaign-days had duplicated feed rows that staging already de-duplicated."
                              if dups else "No duplicated feed rows in range.")})

    orph = run("""SELECT count(*) AS n, coalesce(sum(revenue), 0) AS rev FROM marts.fact_orders
                  WHERE date_day BETWEEN %(start)s AND %(end)s AND is_orphan_campaign""",
               {"start": start, "end": end})[0]
    checks.append({"name": "orphan_orders", "status": "warn" if orph["n"] else "pass", "value": int(orph["n"]),
                   "detail": (f"{orph['n']} orders (${float(orph['rev']):,.0f}) reference an unknown campaign id and are "
                              "treated as unattributed." if orph["n"] else "All orders map to a known campaign.")})

    rec = run("""SELECT (SELECT coalesce(sum(revenue), 0) FROM marts.mart_campaign_daily
                         WHERE date_day BETWEEN %(start)s AND %(end)s) AS mart_rev,
                        (SELECT coalesce(sum(revenue), 0) FROM marts.fact_orders
                         WHERE date_day BETWEEN %(start)s AND %(end)s) AS order_rev""",
              {"start": start, "end": end})[0]
    diff = abs(float(rec["mart_rev"]) - float(rec["order_rev"]))
    checks.append({"name": "revenue_reconciliation", "status": "pass" if diff < 0.01 else "fail", "value": round(diff, 2),
                   "detail": ("Mart revenue reconciles to the order system "
                              f"(${float(rec['order_rev']):,.0f})." if diff < 0.01 else
                              f"Mart revenue differs from order system by ${diff:,.2f}.")})

    statuses = {c["status"] for c in checks}
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return ToolResult("validate_data", {"start": start, "end": end, "platform": platform},
                      {"status": overall, "checks": checks, "warehouse_range": [lo, hi]}, sql=sqls)
