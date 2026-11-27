-- Schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS mock_ads;

-- Least-privilege runtime roles (passwords injected by mpia.db_init)
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analyst_ro') THEN CREATE ROLE analyst_ro LOGIN PASSWORD '{analyst_ro_pw}'; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_rw')   THEN CREATE ROLE agent_rw   LOGIN PASSWORD '{agent_rw_pw}';   END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mock_api_rw') THEN CREATE ROLE mock_api_rw LOGIN PASSWORD '{mock_api_rw_pw}'; END IF;
END $$;

-- analyst_ro: read-only on marts (analytical tools can never touch raw, audit, or mock_ads)
GRANT USAGE ON SCHEMA marts TO analyst_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO analyst_ro;

-- agent_rw: audit trail only
GRANT USAGE ON SCHEMA audit TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO agent_rw;
GRANT USAGE ON SCHEMA marts TO agent_rw;

-- mock_api_rw: mock ad platform only
GRANT USAGE ON SCHEMA mock_ads TO mock_api_rw;
