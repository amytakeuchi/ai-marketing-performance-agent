CREATE TABLE IF NOT EXISTS audit.investigations (
    investigation_id  TEXT PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    requested_by      TEXT NOT NULL,
    question          TEXT NOT NULL,
    interpreter       TEXT,
    intent            JSONB,
    status            TEXT NOT NULL DEFAULT 'running',  -- running | completed | blocked | unsupported | error
    answer            JSONB,
    duration_ms       INTEGER
);

CREATE TABLE IF NOT EXISTS audit.tool_calls (
    call_id           BIGSERIAL PRIMARY KEY,
    investigation_id  TEXT NOT NULL REFERENCES audit.investigations(investigation_id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    node              TEXT NOT NULL,
    tool              TEXT NOT NULL,
    inputs            JSONB,
    output_summary    JSONB,
    sql_executed      JSONB,
    status            TEXT NOT NULL,                    -- ok | error
    error             TEXT,
    duration_ms       INTEGER
);

CREATE TABLE IF NOT EXISTS audit.proposed_actions (
    action_id         TEXT PRIMARY KEY,
    investigation_id  TEXT REFERENCES audit.investigations(investigation_id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_type       TEXT NOT NULL,
    payload           JSONB NOT NULL,                   -- as proposed by the agent
    final_payload     JSONB,                            -- as approved (after human edits)
    status            TEXT NOT NULL DEFAULT 'pending_approval'  -- pending_approval | approved | rejected | executed | execution_failed
);

CREATE TABLE IF NOT EXISTS audit.approvals (
    approval_id       BIGSERIAL PRIMARY KEY,
    action_id         TEXT NOT NULL REFERENCES audit.proposed_actions(action_id),
    decided_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by        TEXT NOT NULL,
    role              TEXT NOT NULL,
    decision          TEXT NOT NULL,                    -- approved | rejected | denied
    edited            BOOLEAN NOT NULL DEFAULT FALSE,
    comment           TEXT
);

CREATE TABLE IF NOT EXISTS audit.executions (
    execution_id      BIGSERIAL PRIMARY KEY,
    action_id         TEXT NOT NULL REFERENCES audit.proposed_actions(action_id),
    executed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key   TEXT NOT NULL,
    http_status       INTEGER,
    response          JSONB
);

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA audit TO agent_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit TO agent_rw;
