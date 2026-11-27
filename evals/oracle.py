"""Independent calculation oracle: recomputes KPIs with plain pandas straight from the raw CSVs.
It shares NO code with dbt, the semantic layer or the tools, so agreement is meaningful evidence of correctness."""
from __future__ import annotations

import pandas as pd

from mpia import config


class Oracle:
    def __init__(self):
        R = config.RAW_DIR
        camp = pd.read_csv(R / "campaigns.csv")
        ad = pd.read_csv(R / "ad_performance.csv", parse_dates=["date"]).drop_duplicates(["date", "campaign_id"])
        web = pd.read_csv(R / "web_analytics.csv", parse_dates=["date"])
        orders = pd.read_csv(R / "orders.csv", parse_dates=["order_ts"])
        orders["date"] = orders.order_ts.dt.normalize()
        orders["campaign_id"] = orders.campaign_id.where(orders.campaign_id.isin(camp.campaign_id), "UNATTRIBUTED")
        self.camp, self.ad, self.web, self.orders = camp, ad, web, orders

    def components(self, start: str, end: str, platform: str | None = None, campaign_id: str | None = None) -> dict:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        ids = self.camp
        if platform:
            ids = ids[ids.platform == platform]
        if campaign_id:
            ids = ids[ids.campaign_id == campaign_id]
        ids = set(ids.campaign_id)
        ad = self.ad[(self.ad.date.between(s, e)) & self.ad.campaign_id.isin(ids)]
        web = self.web[(self.web.date.between(s, e)) & self.web.campaign_id.isin(ids)]
        od = self.orders[(self.orders.date.between(s, e)) & self.orders.campaign_id.isin(ids)]
        return dict(spend=ad.spend.sum(), impressions=ad.impressions.sum(), clicks=ad.clicks.sum(),
                    sessions=web.sessions.sum(), orders=len(od), revenue=od.revenue.sum(),
                    new_customers=int(od.is_new_customer.sum()),
                    platform_reported_revenue=ad.platform_reported_revenue.sum())

    def metric(self, name: str, start: str, end: str, platform: str | None = None, campaign_id: str | None = None):
        c = self.components(start, end, platform, campaign_id)
        d = lambda n, m: (c[n] / c[m]) if c[m] else None  # noqa: E731
        return {"spend": c["spend"], "impressions": c["impressions"], "clicks": c["clicks"], "conversions": c["orders"],
                "revenue": c["revenue"], "roas": d("revenue", "spend"), "ctr": d("clicks", "impressions"),
                "cpc": d("spend", "clicks"), "cpa": d("spend", "orders"), "cac": d("spend", "new_customers"),
                "conversion_rate": d("orders", "sessions"), "aov": d("revenue", "orders"),
                "cpm": (c["spend"] / c["impressions"] * 1000) if c["impressions"] else None,
                "platform_reported_roas": d("platform_reported_revenue", "spend")}[name]

    def naive_mean_of_daily_roas(self, start: str, end: str, platform: str | None = None, campaign_id: str | None = None) -> float:
        """The classic mistake the semantic layer prevents: averaging daily ratios instead of ratio-of-sums."""
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        ids = set(self.camp[(self.camp.platform == platform) if platform else self.camp.campaign_id.notna()].campaign_id)
        if campaign_id:
            ids = {campaign_id}
        ad = self.ad[self.ad.date.between(s, e) & self.ad.campaign_id.isin(ids)].groupby("date").spend.sum()
        rev = self.orders[self.orders.date.between(s, e) & self.orders.campaign_id.isin(ids)].groupby("date").revenue.sum()
        return float((rev.reindex(ad.index).fillna(0) / ad).mean())
