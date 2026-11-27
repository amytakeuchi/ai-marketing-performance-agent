"""Central configuration. Reads env vars (optionally from a local .env file)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


PGHOST = env("PGHOST", "localhost")
PGPORT = env("PGPORT", "5432")
PGDATABASE = env("PGDATABASE", "marketing_dw")

ADMIN_USER = env("PG_ADMIN_USER", "postgres")
ADMIN_PASSWORD = env("PG_ADMIN_PASSWORD", "postgres")

ROLES = {
    "analyst_ro": env("ANALYST_RO_PASSWORD", "analyst_ro_dev"),
    "agent_rw": env("AGENT_RW_PASSWORD", "agent_rw_dev"),
    "mock_api_rw": env("MOCK_API_RW_PASSWORD", "mock_api_dev"),
}

MOCK_API_URL = env("MOCK_API_URL", "http://localhost:8000")
APPROVAL_SECRET = env("APPROVAL_SECRET", "change-me-in-real-life")

RAW_DIR = ROOT / "data" / "raw"
GROUND_TRUTH_PATH = ROOT / "data" / "ground_truth.json"
METRICS_YAML = ROOT / "mpia" / "semantic" / "metrics.yml"

# Warehouse covers 2025-11-01 .. 2026-10-31 (12 months of synthetic daily data)
DATA_START = "2025-11-01"
DATA_END = "2026-10-31"

ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-sonnet-5-5")


def llm_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and os.environ.get("MPIA_LLM", "on").lower() != "off"
