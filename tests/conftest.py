import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CUR = ("2026-10-01", "2026-10-31")
BASE = ("2026-09-01", "2026-09-30")


def _db_ready() -> bool:
    try:
        from mpia import db
        db.query("analyst_ro", "SELECT 1 FROM marts.mart_campaign_daily LIMIT 1")
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    if _db_ready():
        return
    skip = pytest.mark.skip(reason="warehouse not ready - run `make setup` first")
    for it in items:
        if "db" in it.keywords:
            it.add_marker(skip)


@pytest.fixture(scope="session")
def wh():
    from mpia.semantic.warehouse import Warehouse
    return Warehouse()


@pytest.fixture(scope="session")
def oracle():
    from evals.oracle import Oracle
    return Oracle()


@pytest.fixture()
def api():
    """Mock marketing API running in-process, seeded fresh for each test that uses it."""
    from fastapi.testclient import TestClient
    from mpia.actions.mock_api import create_app, seed_budgets
    seed_budgets()
    return TestClient(create_app())


@pytest.fixture()
def deps(api):
    from mpia.actions.service import ActionService
    from mpia.agent.graph import Deps
    return Deps(llm=None, actions=ActionService(api))
