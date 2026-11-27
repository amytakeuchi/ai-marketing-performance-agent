-- State of the *mock* ad platform. Nothing here touches a real advertising account.
CREATE TABLE IF NOT EXISTS mock_ads.campaign_budgets (
    campaign_id         TEXT PRIMARY KEY,
    daily_budget        NUMERIC(12,2) NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by          TEXT
);

CREATE TABLE IF NOT EXISTS mock_ads.budget_change_log (
    change_id           BIGSERIAL PRIMARY KEY,
    action_id           TEXT NOT NULL,
    campaign_id         TEXT NOT NULL,
    old_daily_budget    NUMERIC(12,2),
    new_daily_budget    NUMERIC(12,2) NOT NULL,
    approved_by         TEXT NOT NULL,
    applied_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mock_ads.idempotency_keys (
    idempotency_key     TEXT PRIMARY KEY,
    action_id           TEXT NOT NULL,
    response            JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA mock_ads TO mock_api_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA mock_ads TO mock_api_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA mock_ads TO agent_rw;
GRANT USAGE ON SCHEMA mock_ads TO agent_rw;
