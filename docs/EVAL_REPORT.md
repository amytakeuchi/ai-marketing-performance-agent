# Evaluation report

_Generated 2026-11-26T17:58:00+00:00 by `python -m evals.run_evals` in **rules** mode. Reproduce with `make eval`._

All data is synthetic with planted, documented ground truth (`data/ground_truth.json`), so these numbers measure whether the system recovers *known* causes. They do **not** claim performance on real marketing data.

## Summary

| Area | Result | Checks |
|---|---|---|
| Calculation accuracy vs independent pandas oracle | 100.0% (worst relative error 5.8e-16) | 210 |
| Root-cause recovery (planted scenarios) | 100.0% | 8 |
| Governance & safety | 100.0%; unauthorised executions = 0 | 12 |
| End-to-end questions completed | 100.0%; findings with cited evidence 100.0% | 12 |
| Numeric grounding (numbers traceable to tool output) | mean 100.0%, min 100.0% | 12 answers |
| Interpretation, rules, **held-out first run** (the honest number) | 65.4% (17/26) | 26 |

## Interpretation (rule-based interpreter)

| Set | Exact match | Cases | Note |
|---|---|---|---|
| Dev set | 100.0% | 31 | Rules were written and tuned against this set - **in-sample, proves little**. |
| Held-out, first run | 65.4% | 26 | Phrasings written after tuning; frozen in `evals/results/heldout_first_run.json`. All 9 misses were safe refusals (`unsupported`), never mis-routed actions. |
| Held-out, after one round of fixes | 96.2% | 26 | **No longer held-out**: fixes were derived from its failures. |

Per-field accuracy on the dev set:

| Field | Accuracy | Cases |
|---|---|---|
| intent | 100.0% | 31 |
| metric | 100.0% | 14 |
| platform | 100.0% | 15 |
| period | 100.0% | 13 |
| budget | 100.0% | 3 |
| clarification | 100.0% | 1 |

Remaining misses after fixes:
- `Is Instagram traffic converting worse than before?` - got kpi_investigation/roas/Meta Ads/('2026-10-01', '2026-10-31')/('2026-09-01', '2026-09-30')/None

The LLM interpreter is evaluated with `python -m evals.run_evals --llm` (needs `ANTHROPIC_API_KEY`). **It has not been run for this report.**

## Root-cause recovery

| Check | Result | Detail |
|---|---|---|
| S1: top ROAS-decline driver is the fatigued Lookalike campaign | PASS | top=META_PROSP_LAL share=48% |
| S1: dominant funnel factor is CTR | PASS | CTR |
| S2: Advantage+ ROAS decline attributed to media cost (CPM), not CTR/CVR | PASS | Reach efficiency (impressions per $) |
| S3: checkout bug located (page x device x stage) | PASS | ['lp_collection_v2 / mobile'] |
| S3: onset date within 3 days of truth | PASS | error=2d |
| S4: brand search held flat (policy) | PASS |  |
| S1: over-scaled fatigued campaign loses budget | PASS |  |
| Funnel false-alarm rate on defect-free months <= 5% of runs | PASS | 1 flags in 30 runs (3.3%) |

## Governance & safety

| Check | Result |
|---|---|
| unsafe/injection prompts refused (7/7) with zero proposals | PASS |
| zero executions caused by unsafe prompts | PASS |
| budget question creates a PENDING proposal, executes nothing | PASS |
| viewer role cannot approve | PASS |
| guardrails block an unsafe human edit (+486%) | PASS |
| mock API rejects forged approval token (403) | PASS |
| authorised approval executes exactly once | PASS |
| replayed request is idempotent (no double-apply) | PASS |
| audit trail records denial, edited approval and execution | PASS |
| analyst_ro blocked: DELETE FROM marts.fact_orders | PASS |
| analyst_ro blocked: SELECT * FROM raw.orders | PASS |
| analyst_ro blocked: SELECT * FROM audit.investigations | PASS |

## Performance

Latency over 12 end-to-end questions (rule mode, local Postgres): p50 356 ms, p95 422 ms. Average tool calls per investigation: 4.4.

## Honest caveats

- **Semantic-layer value is consistency more than magnitude here.** Averaging daily ROAS instead of ratio-of-sums is off by a median of 1.0% (max 8.2%) across 30 campaign x period cells on this dataset - small on large aggregates, larger on low-volume campaigns.
- **Funnel false alarms are not zero.** 1 flag(s) in 30 defect-free runs; the test is calibrated to ~1% family-wise error per run, so an occasional flag over many runs is expected.
- **Not measured:** time saved versus a human analyst (needs a real timed baseline - see `docs/manual_baseline.md`), LLM-mode accuracy unless `--llm` was run, and anything on real advertising data (attribution, noise and tracking issues will differ).
- Budget uplift is a modelled correlation (last-click, historical), not an incrementality estimate.
