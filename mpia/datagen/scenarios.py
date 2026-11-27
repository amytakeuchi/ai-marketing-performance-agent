"""Campaign catalogue and planted scenarios for the synthetic dataset.

Everything the agent is later expected to *discover* is declared here and exported to
data/ground_truth.json. The evaluation harness scores the agent against that file, so the
synthetic data is a labelled benchmark rather than a rigged demo.
"""
from __future__ import annotations

from datetime import date

START = date(2025, 11, 1)
END = date(2026, 10, 31)
DAILY_BUDGET_TOTAL = 1650.0  # ~ $50k / month across all paid campaigns

CVR_SCALE = 0.60  # calibrates blended ROAS to a realistic ~2.5-3 for e-commerce

DEVICES = {"mobile": 0.68, "desktop": 0.32}

LANDING_PAGES = [
    {"landing_page_id": "lp_home", "path": "/", "page_type": "home"},
    {"landing_page_id": "lp_collection_v2", "path": "/collections/new-arrivals", "page_type": "collection"},
    {"landing_page_id": "lp_bestseller", "path": "/products/bestseller", "page_type": "product"},
    {"landing_page_id": "lp_sale", "path": "/sale", "page_type": "promo"},
]

# elasticity < 1 => diminishing returns on spend (impressions ~ spend**elasticity)
CAMPAIGNS = [
    dict(campaign_id="META_PROSP_LAL", name="Meta | Prospecting | Lookalike 1%", platform="Meta Ads",
         funnel_stage="prospecting", base_spend=330, cpm=13.0, ctr=0.0125, c2s=0.88, atc=0.105, chk=0.56, pur=0.56,
         aov=82, new_rate=0.82, elasticity=0.80, overclaim=1.30, lps={"lp_home": .35, "lp_bestseller": .45, "lp_sale": .20}),
    dict(campaign_id="META_PROSP_INT", name="Meta | Prospecting | Interest Stack", platform="Meta Ads",
         funnel_stage="prospecting", base_spend=210, cpm=11.5, ctr=0.0105, c2s=0.87, atc=0.095, chk=0.55, pur=0.55,
         aov=79, new_rate=0.85, elasticity=0.75, overclaim=1.28, lps={"lp_home": .50, "lp_bestseller": .30, "lp_sale": .20}),
    dict(campaign_id="META_RETARG", name="Meta | Retargeting | Cart Abandoners", platform="Meta Ads",
         funnel_stage="retargeting", base_spend=130, cpm=17.0, ctr=0.021, c2s=0.90, atc=0.22, chk=0.62, pur=0.62,
         aov=88, new_rate=0.15, elasticity=0.55, overclaim=1.35, lps={"lp_bestseller": .55, "lp_collection_v2": .45}),
    dict(campaign_id="META_ADV_CAT", name="Meta | Advantage+ | Catalog", platform="Meta Ads",
         funnel_stage="prospecting", base_spend=240, cpm=12.5, ctr=0.0115, c2s=0.88, atc=0.115, chk=0.57, pur=0.57,
         aov=84, new_rate=0.70, elasticity=0.80, overclaim=1.25, lps={"lp_collection_v2": .50, "lp_bestseller": .30, "lp_home": .20}),
    dict(campaign_id="GOOG_BRAND", name="Google | Search | Brand", platform="Google Ads",
         funnel_stage="brand", base_spend=110, cpm=38.0, ctr=0.11, c2s=0.95, atc=0.20, chk=0.66, pur=0.66,
         aov=90, new_rate=0.35, elasticity=0.35, overclaim=1.12, lps={"lp_home": .80, "lp_bestseller": .20}),
    dict(campaign_id="GOOG_NONBRAND", name="Google | Search | Non-Brand", platform="Google Ads",
         funnel_stage="prospecting", base_spend=290, cpm=26.0, ctr=0.042, c2s=0.93, atc=0.12, chk=0.58, pur=0.58,
         aov=86, new_rate=0.75, elasticity=0.78, overclaim=1.15, lps={"lp_collection_v2": .45, "lp_bestseller": .35, "lp_home": .20}),
    dict(campaign_id="GOOG_SHOP", name="Google | Shopping | Core", platform="Google Ads",
         funnel_stage="prospecting", base_spend=270, cpm=19.0, ctr=0.018, c2s=0.92, atc=0.14, chk=0.60, pur=0.60,
         aov=83, new_rate=0.60, elasticity=0.78, overclaim=1.15, lps={"lp_collection_v2": .70, "lp_bestseller": .30}),
    dict(campaign_id="GOOG_PMAX", name="Google | Performance Max", platform="Google Ads",
         funnel_stage="prospecting", base_spend=240, cpm=15.0, ctr=0.0145, c2s=0.90, atc=0.11, chk=0.57, pur=0.57,
         aov=81, new_rate=0.65, elasticity=0.80, overclaim=1.18, lps={"lp_collection_v2": .35, "lp_home": .30, "lp_sale": .35}),
    dict(campaign_id="GOOG_YT", name="Google | YouTube | Awareness", platform="Google Ads",
         funnel_stage="prospecting", base_spend=70, cpm=7.5, ctr=0.0045, c2s=0.82, atc=0.06, chk=0.50, pur=0.50,
         aov=76, new_rate=0.90, elasticity=0.85, overclaim=1.40, lps={"lp_home": .85, "lp_sale": .15}),
    dict(campaign_id="GOOG_DISP_RT", name="Google | Display | Retargeting", platform="Google Ads",
         funnel_stage="retargeting", base_spend=60, cpm=6.0, ctr=0.0065, c2s=0.85, atc=0.17, chk=0.58, pur=0.58,
         aov=80, new_rate=0.18, elasticity=0.50, overclaim=1.45, lps={"lp_bestseller": .60, "lp_collection_v2": .40}),
]

UNATTRIBUTED = dict(campaign_id="UNATTRIBUTED", name="Unattributed / Direct / Organic",
                    platform="Non-paid", funnel_stage="unattributed")

# --- Planted scenarios (ground truth for evaluation) --------------------------------------
SCENARIOS = {
    "S1_meta_lal_creative_fatigue": dict(
        description="Meta Lookalike campaign: budget +45% and CTR decays linearly to -50% over October "
                    "(creative fatigue). Click-through rate is the dominant ROAS driver.",
        campaign_id="META_PROSP_LAL", start="2026-10-01", end="2026-10-31",
        spend_multiplier=1.45, ctr_decay_to=0.50, expected_dominant_factor="CTR",
    ),
    "S2_meta_adv_cpm_spike": dict(
        description="Meta Advantage+ Catalog: CPM +22% from 2026-10-10 (auction pressure). Secondary driver.",
        campaign_id="META_ADV_CAT", start="2026-10-10", end="2026-10-31", cpm_multiplier=1.22,
    ),
    "S3_mobile_checkout_bug": dict(
        description="Mobile checkout->purchase rate on lp_collection_v2 drops 45% from 2026-10-15 "
                    "(broken payment button). Still ongoing at end of data.",
        landing_page_id="lp_collection_v2", device="mobile", stage="checkout_to_purchase",
        start="2026-10-15", end="2026-10-31", rate_multiplier=0.55,
    ),
    "S4_brand_search_saturated": dict(
        description="Google Brand Search has the highest average ROAS but strongly diminishing returns "
                    "(spend elasticity 0.35). It captures existing demand, so the optimizer holds it flat by policy.",
        campaign_id="GOOG_BRAND", elasticity=0.35,
    ),
    "DQ_duplicates": dict(description="12 duplicated rows in raw.ad_performance (de-duplicated in staging)."),
    "DQ_null_clicks": dict(description="8 ad rows with NULL clicks."),
    "DQ_missing_days": dict(description="GOOG_YT ad-platform feed missing 2026-09-14..2026-09-16 "
                                         "(orders/sessions exist, spend rows do not)."),
    "DQ_orphan_orders": dict(description="6 orders reference unknown campaign CMP_LEGACY_X (mapped to UNATTRIBUTED)."),
}
