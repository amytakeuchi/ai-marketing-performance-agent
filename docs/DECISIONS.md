# Design decisions

**D1 - A constrained workflow agent, not a free-roaming one.** The LLM maps a question to a validated `Intent`; each intent
runs a fixed tool plan. Rationale: marketing numbers must be reproducible and auditable; free-form tool loops make every
answer a new, untestable program. Cost: cannot answer questions outside the five intents (it says so).

**D2 - The LLM never writes SQL or does arithmetic.** All SQL is compiled from the semantic layer with whitelisted
identifiers and bound parameters; the LLM's only structured output is an `Intent` (validated by pydantic and the registry).
Prompt injection can at worst mis-classify a question; it cannot reach the database or the action API.

**D3 - Ratio metrics are ratio-of-sums, defined once.** `metrics.yml` is the single source of truth; zero denominators return
NULL; every metric documents attribution, filters and limitations.

**D4 - Evidence-first answers.** Every finding cites evidence ids (tool, inputs, exact SQL). A grounding check verifies that
every number in generated prose appears in tool output; an LLM summary that fails is retried once, then replaced by the
deterministic template. Hypotheses, limitations and assumptions are separate sections - causes are never stated as facts.

**D5 - Validate before analysing.** Coverage, feed gaps, NULLs, de-duplicated rows, orphan orders and revenue reconciliation
run first. Hard failures stop the investigation with an explicit message; warnings flow into the answer's limitations.

**D6 - Exact decompositions.** Segment contributions split into rate and mix effects and sum exactly to the total change;
ROAS/CPA split into funnel-stage factors via log decomposition. Tests assert reconciliation error < 1e-9.

**D7 - Attribution is explicit.** ROAS uses order-level last-click revenue; platform-reported revenue is exposed separately as
`platform_reported_roas` because platforms over-claim. Nothing here is incrementality.

**D8 - Actions are proposals until a human decides.** Agent -> pending proposal -> authorised human (role check, optional
edits) -> deterministic guardrails (+/-50% per campaign, total <= cap) -> HMAC-signed token bound to the exact payload ->
mock API verifies the token independently, enforces an idempotency key, and writes a change log. The agent process cannot
call the API without an approval. In production the signer would be a separate service/IdP; here both share a secret.

**D9 - Least privilege in the database.** `analyst_ro` (read-only, marts only), `agent_rw` (audit schema), `mock_api_rw`
(mock platform only). Tested: the analytical role cannot write, or read raw/audit.

**D10 - Deterministic mode is first-class.** Without an API key the whole system runs (rule-based interpreter, template
narrative), so tests, evals and demos are free and reproducible. The LLM path is additive and falls back on any failure.
