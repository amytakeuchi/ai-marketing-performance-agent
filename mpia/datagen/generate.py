"""Seeded synthetic marketing data generator.

Usage: python -m mpia.datagen.generate [--seed 42]
Writes CSVs to data/raw/ and the ground truth to data/ground_truth.json.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .. import config
from . import scenarios as sc


def _season(d: date) -> tuple[float, float]:
    """(spend multiplier, conversion-rate multiplier) for holiday / seasonal effects."""
    if date(2025, 11, 20) <= d <= date(2025, 12, 2):
        return 1.35, 1.25
    if date(2025, 12, 3) <= d <= date(2025, 12, 24):
        return 1.10, 1.08
    if d.month == 1:
        return 0.92, 0.95
    return 1.0, 1.0


def generate(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    days = [sc.START + timedelta(days=i) for i in range((sc.END - sc.START).days + 1)]
    scale = sc.DAILY_BUDGET_TOTAL / sum(c["base_spend"] for c in sc.CAMPAIGNS)
    s1 = sc.SCENARIOS["S1_meta_lal_creative_fatigue"]
    s2 = sc.SCENARIOS["S2_meta_adv_cpm_spike"]
    s3 = sc.SCENARIOS["S3_mobile_checkout_bug"]
    d = lambda s: date.fromisoformat(s)  # noqa: E731

    ad_rows, web_rows, order_rows = [], [], []
    customers: list[str] = []
    cust_first: dict[str, tuple] = {}
    order_seq = 0

    def new_order(ts, campaign_id, revenue, is_new):
        nonlocal order_seq
        order_seq += 1
        if is_new or not customers:
            cid = f"C{len(customers) + 1:06d}"
            customers.append(cid)
            cust_first[cid] = (ts, campaign_id)
            is_new = True
        else:
            cid = customers[rng.integers(len(customers))]
        order_rows.append(dict(order_id=f"ORD-{order_seq:07d}", order_ts=ts, customer_id=cid,
                               campaign_id=campaign_id, revenue=round(float(revenue), 2), is_new_customer=is_new))

    # weekly pacing multipliers give spend variation (needed to identify response curves)
    weeks = sorted({d_.isocalendar()[:2] for d_ in days})
    pacing = {(c["campaign_id"], w): float(rng.lognormal(0, 0.15)) for c in sc.CAMPAIGNS for w in weeks}

    for c in sc.CAMPAIGNS:
        base = c["base_spend"] * scale
        for day in days:
            spend_m, cvr_m = _season(day)
            wk = day.isocalendar()[:2]
            weekend = day.weekday() >= 5
            spend_mult = spend_m * pacing[(c["campaign_id"], wk)] * (0.93 if weekend else 1.0)
            cpm = c["cpm"]
            ctr = c["ctr"] * float(rng.lognormal(0, 0.05))
            if c["campaign_id"] == s1["campaign_id"] and d(s1["start"]) <= day <= d(s1["end"]):
                spend_mult *= s1["spend_multiplier"]
                prog = (day - d(s1["start"])).days / max((d(s1["end"]) - d(s1["start"])).days, 1)
                ctr *= 1 - prog * (1 - s1["ctr_decay_to"])
            if c["campaign_id"] == s2["campaign_id"] and d(s2["start"]) <= day <= d(s2["end"]):
                cpm *= s2["cpm_multiplier"]
            spend = base * spend_mult * float(rng.lognormal(0, 0.06))
            rel = spend / base
            impressions = int(spend / cpm * 1000 * rel ** (c["elasticity"] - 1))
            clicks = int(rng.binomial(impressions, min(ctr, 0.5)))
            sessions_total = int(rng.binomial(clicks, c["c2s"]))

            # spread sessions across landing page x device cells
            cell_p, cells = [], []
            for lp in c["lps"]:
                for dev, share in sc.DEVICES.items():
                    cells.append((lp, dev))
                    cell_p.append(c["lps"][lp] * share)
            counts = rng.multinomial(sessions_total, np.array(cell_p) / sum(cell_p))
            purchases_total = 0
            for (lp, dev), n_sess in zip(cells, counts):
                atc_rate = c["atc"] * sc.CVR_SCALE * cvr_m * (0.90 if dev == "mobile" else 1.20)
                pur_rate = c["pur"]
                if (lp == s3["landing_page_id"] and dev == s3["device"] and d(s3["start"]) <= day <= d(s3["end"])):
                    pur_rate *= s3["rate_multiplier"]
                atc = int(rng.binomial(n_sess, min(atc_rate, 0.9)))
                chk = int(rng.binomial(atc, c["chk"]))
                pur = int(rng.binomial(chk, min(pur_rate, 0.95)))
                purchases_total += pur
                web_rows.append(dict(date=day, campaign_id=c["campaign_id"], landing_page_id=lp, device=dev,
                                     sessions=int(n_sess), add_to_carts=atc, checkouts=chk, purchases=pur))

            # order rows (last-click attribution = campaign that drove the session)
            aov = c["aov"] * (0.92 if date(2025, 11, 20) <= day <= date(2025, 12, 2) else 1.0)
            for _ in range(purchases_total):
                ts = pd.Timestamp(day) + pd.Timedelta(seconds=int(rng.integers(0, 86400)))
                rev = float(rng.lognormal(np.log(aov) - 0.45 ** 2 / 2, 0.45))
                new_order(ts, c["campaign_id"], rev, bool(rng.random() < c["new_rate"]))

            over = c["overclaim"] * float(rng.lognormal(0, 0.08))
            plat_conv = int(round(purchases_total * over))
            ad_rows.append(dict(date=day, campaign_id=c["campaign_id"], impressions=impressions, clicks=clicks,
                                spend=round(spend, 2), platform_reported_conversions=plat_conv,
                                platform_reported_revenue=round(plat_conv * aov * float(rng.lognormal(0, 0.05)), 2)))

    # unattributed (direct/organic) orders ~ 12% on top of attributed
    attributed = len(order_rows)
    for _ in range(int(attributed * 0.12)):
        day = days[rng.integers(len(days))]
        ts = pd.Timestamp(day) + pd.Timedelta(seconds=int(rng.integers(0, 86400)))
        new_order(ts, "UNATTRIBUTED", float(rng.lognormal(np.log(85) - 0.45 ** 2 / 2, 0.45)), bool(rng.random() < 0.5))

    ad = pd.DataFrame(ad_rows)
    web = pd.DataFrame(web_rows)
    orders = pd.DataFrame(order_rows).sort_values("order_ts").reset_index(drop=True)

    # ---- planted data-quality defects -------------------------------------------------
    gap = ((ad.campaign_id == "GOOG_YT") & (ad.date >= date(2026, 9, 14)) & (ad.date <= date(2026, 9, 16)))
    ad = ad[~gap].reset_index(drop=True)
    null_idx = rng.choice(ad.index, size=8, replace=False)
    ad["clicks"] = ad["clicks"].astype("Int64")
    ad.loc[null_idx, "clicks"] = pd.NA
    dup_idx = rng.choice(ad.index, size=12, replace=False)
    ad = pd.concat([ad, ad.loc[dup_idx]], ignore_index=True).sort_values(["date", "campaign_id"]).reset_index(drop=True)
    orphan_idx = rng.choice(orders[orders.campaign_id != "UNATTRIBUTED"].index, size=6, replace=False)
    orders.loc[orphan_idx, "campaign_id"] = "CMP_LEGACY_X"

    customers_df = pd.DataFrame(
        [dict(customer_id=cid, first_order_ts=ts, acquisition_campaign_id=cmp) for cid, (ts, cmp) in cust_first.items()]
    )
    campaigns_df = pd.DataFrame([
        dict(campaign_id=c["campaign_id"], campaign_name=c["name"], platform=c["platform"], funnel_stage=c["funnel_stage"])
        for c in sc.CAMPAIGNS
    ])
    lp_df = pd.DataFrame(sc.LANDING_PAGES)
    return dict(ad_performance=ad, web_analytics=web, orders=orders, customers=customers_df,
                campaigns=campaigns_df, landing_pages=lp_df)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    tables = generate(args.seed)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(config.RAW_DIR / f"{name}.csv", index=False)
        print(f"{name:15s} {len(df):>8,d} rows")
    gt = {"seed": args.seed, "data_start": str(sc.START), "data_end": str(sc.END),
          "scenarios": sc.SCENARIOS, "campaigns": [c["campaign_id"] for c in sc.CAMPAIGNS]}
    config.GROUND_TRUTH_PATH.write_text(json.dumps(gt, indent=2, default=str))
    print(f"ground truth -> {config.GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
