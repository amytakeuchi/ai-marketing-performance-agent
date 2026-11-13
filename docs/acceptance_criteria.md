# Acceptance Criteria
## Marketing Performance Intelligence Agent

## Epic 1: Marketing Data Foundation

### AC-01: Unified marketing data

Given marketing data from Meta Ads, Google Ads, website analytics and e-commerce orders,

When the data pipeline runs,

Then:
- Data is loaded into the appropriate PostgreSQL source tables.
- Source identifiers and reporting dates are preserved.
- Data is transformed into documented dbt staging and mart models.
- Fact table grains are documented.
- Primary and foreign key relationships are tested.
- Data can be queried by platform, campaign and date.

### AC-02: Data quality validation

Given marketing data containing missing values, duplicate records or invalid values,

When data validation runs,

Then:
- Duplicate records are identified according to each model's grain.
- Required fields are tested for null values.
- Negative spend, invalid dates and impossible metric values are flagged.
- Referential integrity is tested.
- Invalid data is not silently included in trusted analytical results.
- Validation failures are visible to the agent.

### AC-03: Semantic metric definitions

Given a request for ROAS,

When the agent resolves the metric,

Then:
- It retrieves the approved ROAS definition.
- The definition identifies the numerator and denominator.
- The definition specifies the attribution basis.
- The definition identifies supported dimensions.
- The system handles zero denominators safely.
- The same metric definition is used across supported investigations.

The same requirements apply to other registered metrics.

## Epic 2: Natural-Language Interface

### AC-04: Submit a business question

Given a user submits a supported marketing question,

When the application receives the request,

Then:
- The request receives a unique identifier.
- The original question is preserved.
- The agent begins an investigation.
- The user can see the investigation status.
- The final answer is associated with the original request.

### AC-05: Interpret a business question

Given the question:

"Why did Meta Ads ROAS decline in October compared with September?"

When the agent interprets it,

Then the structured interpretation includes:
- Platform: Meta.
- Metric: ROAS.
- Current period: October.
- Comparison period: September.
- Analysis objective: Identify drivers of change.

If the year is ambiguous or cannot be reliably inferred, the agent asks for clarification.

### AC-06: Handle ambiguous requests

Given a user asks:

"Why is performance declining?"

When the agent cannot identify the KPI or relevant time period,

Then:
- It asks a concise clarification question.
- It does not execute an unsupported investigation.
- It retains the original user request.

## Epic 3: Performance Investigation

### AC-07: Compare KPI performance

Given known campaign performance data for two periods,

When the agent performs a comparison,

Then:
- It calculates the current value.
- It calculates the previous-period value.
- It calculates absolute change.
- It calculates percentage change when the denominator is valid.
- It reports the comparison periods.
- It uses deterministic SQL/Python calculations.

Example test:

Previous-period ROAS: 2.0x  
Current-period ROAS: 1.6x

Expected result:
- Absolute change: -0.4x.
- Relative change: -20%.

### AC-08: Identify campaign contributors

Given a known change in total advertising spend or attributed revenue,

When the agent performs campaign driver analysis,

Then:
- It calculates campaign-level changes.
- It identifies the largest contributors to the overall change.
- It distinguishes absolute contribution from percentage change.
- It identifies campaigns with insufficient volume.
- It avoids claiming causation from simple correlation.
- It includes supporting figures.

### AC-09: Investigate the conversion funnel

Given valid funnel data,

When the agent analyzes funnel performance,

Then:
- It retrieves impressions, clicks, sessions, add-to-carts and purchases where available.
- It calculates defined stage-to-stage conversion rates.
- It identifies the largest drop-off.
- It distinguishes advertising platform events from website events and actual orders.
- It flags missing or incompatible stages.

### AC-10: Evidence-backed explanation

Given an investigation has completed,

When the agent produces a response,

Then:
- Major findings include supporting metrics.
- Findings reference the analyzed time period and dimensions.
- Metric definitions are consistent with the semantic layer.
- Missing data and assumptions are disclosed.
- Unsupported explanations are not presented as established facts.

## Epic 4: Recommendations

### AC-11: Generate recommendations

Given a completed investigation,

When the agent generates recommendations,

Then:
- Each recommendation is linked to at least one finding.
- Supporting evidence is displayed.
- The recommendation identifies its assumptions.
- Risks and limitations are communicated.
- The agent does not guarantee future performance.

### AC-12: Budget allocation proposal

Given a marketing manager specifies a total budget of $50,000,

When the agent generates a budget proposal,

Then:
- The proposed allocation totals exactly $50,000.
- Every allocation is non-negative.
- Campaign and channel constraints are respected.
- Current and proposed allocations are shown.
- The reasoning is documented.
- Forecasted results, if any, are explicitly labeled as estimates.
- No external action is executed.

## Epic 5: Approval and Execution

### AC-13: Approve a recommendation

Given an authorized user reviews a proposed action,

When the user approves it,

Then:
- The system records the approving user and timestamp.
- Approval is linked to the exact recommendation version and parameters.
- The action becomes eligible for execution.
- The application verifies authorization before execution.

### AC-14: Edit a recommendation

Given a user edits an approved-action proposal,

When the proposed parameters change,

Then:
- A new proposal version is created.
- The previous approval is invalidated.
- The updated proposal requires a new approval.
- The previous version remains in the audit history.

### AC-15: Reject a recommendation

Given a user rejects a proposed action,

When rejection is recorded,

Then:
- The status becomes rejected.
- No execution call is made.
- The rejection is recorded.
- The user can inspect the rejected proposal.

### AC-16: Execute an approved action

Given an authorized user has approved a valid proposal,

When the action execution tool is invoked,

Then:
- The approval is verified by the backend.
- The approved parameters are checked against the execution request.
- The mock API receives the action.
- The execution result is recorded.
- Duplicate requests are prevented through idempotency.
- Failed actions are reported accurately.

### AC-17: Prevent unauthorized execution

Given an action has not been approved or the user lacks permission,

When an execution request is submitted,

Then:
- The backend rejects the request.
- The mock API does not execute the action.
- The failed attempt is logged.
- The user receives a clear error message.

## Epic 6: Governance and Evaluation

### AC-18: Investigation history

Given a completed investigation,

When a user opens its history,

Then the application displays:
- Original request.
- Interpreted request.
- Metrics and filters.
- Data references.
- Key findings.
- Recommendation.
- Approval status.
- Execution status.

### AC-19: Agent evaluation

Given a benchmark containing known expected outcomes,

When the evaluation suite runs,

Then:
- Intent interpretation is scored.
- Tool selection is scored.
- Data retrieval is tested.
- Numerical calculations are compared with expected results.
- Recommendation grounding is assessed.
- Approval enforcement is tested.
- Results are saved for comparison across versions.

### AC-20: Error handling

Given a database, LLM or tool failure,

When the investigation cannot proceed,

Then:
- The error is captured.
- Retry behavior is bounded.
- No fabricated result is returned.
- The user receives an understandable explanation.
- Protected actions are not executed.

## Global Definition of Done

A feature is complete only when:

1. Its requirements are implemented.
2. Its acceptance criteria are satisfied.
3. Unit tests are written and pass.
4. Relevant integration tests are written and pass.
5. Error and edge cases are considered.
6. Documentation is updated.
7. The feature does not violate security or approval requirements.
8. Actual test results are reported.

A feature must not be marked complete merely because the application runs successfully.