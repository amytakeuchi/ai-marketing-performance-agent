.PHONY: help install up setup db-init data load dbt seed api app ask test eval reset-audit clean
PY ?= python3

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

install:         ## install Python dependencies
	$(PY) -m pip install -r requirements.txt

up:              ## start Postgres in Docker (skip if you already have one; see .env.example)
	docker compose up -d --wait

setup: db-init data load dbt seed   ## build everything: roles/schemas -> synthetic data -> raw -> dbt -> mock budgets

db-init:         ## create schemas, least-privilege roles, audit + mock-API tables
	$(PY) -m mpia.db_init

data:            ## generate seeded synthetic data (+ ground truth)
	$(PY) -m mpia.datagen.generate --seed 42

load:            ## load CSVs into raw.*
	$(PY) -m mpia.datagen.load_raw

dbt:             ## dbt build: staging + marts + data tests
	cd dbt_project && dbt build --profiles-dir .

seed:            ## seed the mock marketing API's campaign budgets
	$(PY) -m mpia.actions.mock_api seed

api:             ## run the mock marketing API on :8000
	$(PY) -m uvicorn mpia.actions.mock_api:app --port 8000

app:             ## run the Streamlit UI on :8501 (start `make api` first for approvals)
	$(PY) -m streamlit run mpia/app/streamlit_app.py

ask:             ## make ask Q="Why did Meta ROAS decline in October compared with September?"  (for '$' amounts use the CLI directly)
	$(PY) -m mpia.agent.cli ask "$$Q"

test:            ## unit + integration tests (needs `make setup`)
	$(PY) -m pytest -q

eval:            ## run the evaluation harness -> docs/EVAL_REPORT.md
	$(PY) -m evals.run_evals

reset-audit:     ## clear audit records and re-seed mock budgets (clean demo state)
	$(PY) -c "from mpia import db; db.execute(None, 'TRUNCATE audit.executions, audit.approvals, audit.proposed_actions, audit.tool_calls, audit.investigations CASCADE')"
	$(PY) -m mpia.actions.mock_api seed

clean:           ## drop generated data
	rm -rf data/raw dbt_project/target dbt_project/logs
