# MVP scope: what was built, where it lives, and where it deviates from the BRD

| # | MVP item | Implementation | Verified by |
|---|---|---|---|
| 1 | Synthetic marketing data | `mpia/datagen/` (seeded; planted scenarios + data-quality defects; `data/ground_truth.json`) | `tests/test_tools_ground_truth.py`, `evals/` |
| 2 | PostgreSQL warehouse | `sql/init/`, `mpia/db_init.py`, raw -> staging -> marts schemas, least-privilege roles | `tests/test_security_and_approvals.py` |
| 3 | dbt transformation | `dbt_project/` (6 staging views, 11 marts tables, 31 data tests incl. 3 deliberate warn-level detectors) | `dbt build` (45 pass, 3 expected warnings) |
| 4 | Metric definitions & semantic layer | `mpia/semantic/metrics.yml`, `registry.py`, `warehouse.py` | `tests/test_semantic.py`, `tests/test_calculations.py` |
| 5 | NL business-question interface | Streamlit UI `mpia/app/`, CLI `mpia/agent/cli.py` | `tests/test_app_smoke.py` |
| 6 | LLM request interpretation & tool selection | `mpia/agent/interpreter.py`, `llm.py` (Claude forced tool-call -> validated `Intent`; rule-based fallback) | `tests/test_llm_plumbing.py` (stubbed), `evals/` |
| 7 | LangGraph orchestration | `mpia/agent/graph.py` (interpret -> validate -> analyze -> narrate -> propose -> finalize) | `tests/test_graph_e2e.py` |
| 8 | SQL/Python analytical tools | `mpia/tools/` (validation, kpi, drivers, funnel, campaigns, budget, stats) | `tests/test_tools_ground_truth.py` |
| 9 | Campaign performance investigation | `analysis.kpi_investigation`, `underperformers` | e2e + evals |
| 10 | KPI comparison & driver analysis | `tools/kpi.py`, `tools/drivers.py` (exact rate/mix and log-factor decompositions) | reconciliation tests (error < 1e-9) |
| 11 | Evidence-based recommendations | `analysis.py`: every finding cites evidence ids; hypotheses and limitations are separate | grounding eval (numbers traceable) |
| 12 | Human approval interface | Streamlit "Approvals" tab, CLI `approve/reject`, `mpia/actions/service.py` | governance tests/evals |
| 13 | Mock marketing action API | `mpia/actions/mock_api.py` (HMAC approval token, idempotency, role-restricted DB) | governance tests/evals |
| 14 | Investigation logs & audit records | `mpia/audit/logger.py`, `audit.*` tables (investigations, tool calls with SQL, approvals, executions) | e2e tests |
| 15 | Automated tests & agent evaluation | `tests/` (281), `evals/` (benchmark, oracle, harness, report) | `make test`, `make eval` |

## Deviations from the original BRD (deliberate or forced)

- **Smaller dimensional model.** `dim_ad` and `dim_channel` were not built: the data has no ad-level or channel detail, so
  platform lives on `dim_campaign`/`dim_platform`. Adding them is easy but would be decoration.
- **Semantic layer is YAML + Python, not dbt metrics/MetricFlow.** Chosen so the agent can resolve synonyms, validate
  driver chains and compute ratios from additive components in one place. Trade-off: it is not consumable by BI tools.
- **A workflow agent, not an open-ended agent loop.** The LLM chooses an *intent*; each intent has a fixed, audited tool plan.
  This trades flexibility for predictability, testability and safety (see `DECISIONS.md` D1).
- **Approval is a durable Postgres state machine, not an in-memory LangGraph `interrupt`.** Pending actions survive restarts
  and can be decided from a different process (UI, CLI, API).
- **Not measured:** time saved vs a manual analyst (`docs/manual_baseline.md`), LLM-mode accuracy (never run against the
  live API in the environment this was built in), and any real-data performance.
- **BRD numbers are targets, not results.** E.g. "90% correct interpretation": see `EVAL_REPORT.md` for what was actually
  measured (including the 65% held-out first-run score).
