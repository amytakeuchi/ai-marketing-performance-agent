# Business Requirements Document (BRD)
## Marketing Performance Intelligence Agent

**Document version:** 1.0  
**Status:** Initial product specification  
**Project type:** Enterprise AI / Marketing Analytics  
**Primary users:** Marketing Managers, Growth Managers, Marketing Analysts

---

## 1. Executive Summary

The Marketing Performance Intelligence Agent is an AI-powered marketing analytics application that enables marketing teams to investigate campaign performance, identify the drivers of KPI changes, and develop evidence-based optimization recommendations using structured marketing data.

Users can ask business questions in natural language, such as:

- Why did our Meta Ads ROAS decline by 20% this month?
- Which campaigns contributed most to the increase in customer acquisition cost?
- Which channels are generating the highest-value new customers?
- Where are users dropping off in our conversion funnel?
- How should we redistribute our $50,000 marketing budget?

The application will combine a governed marketing data warehouse, a centralized semantic layer, deterministic analytical tools, and an LLM-powered agent.

The agent will retrieve and analyze data, explain its findings, and generate recommendations. Any external marketing action will require explicit human approval.

The initial version will use synthetic marketing data and mock integrations rather than live advertising accounts.

## 2. Business Problem

Marketing teams frequently need to investigate performance across multiple platforms and data sources.

Common challenges include:

1. Fragmented data across advertising platforms, website analytics, CRM and e-commerce systems.
2. Inconsistent KPI definitions, particularly ROAS, CAC, CPA and conversions.
3. Time-consuming manual investigation of performance changes.
4. Difficulty identifying which campaigns, channels or audience segments contribute to changes.
5. Reporting workflows that require analysts to repeatedly write SQL, manipulate spreadsheets and prepare presentations.
6. Difficulty converting analytical findings into specific optimization actions.

Existing dashboards can show what happened, but they do not necessarily explain why it happened or guide users through the next analytical steps.

The proposed product aims to make marketing performance investigations faster, more consistent and more accessible to nontechnical users.

## 3. Product Vision

Build an AI marketing analyst that allows business users to investigate marketing performance through natural language while maintaining reliable metric definitions, transparent analytical evidence and human control over business actions.

### Product principles

- Business metrics must have centralized and documented definitions.
- All numerical calculations must be performed by deterministic SQL or Python functions.
- The LLM must not invent data, metric definitions or analytical conclusions.
- Every major conclusion must be supported by retrieved data.
- Users must be able to inspect the evidence behind recommendations.
- External actions must require authorized human approval.
- The system must record investigation and execution history.

## 4. Target Users

### Primary user: Marketing Manager

Responsibilities:
- Monitor campaign and channel performance.
- Understand changes in marketing KPIs.
- Identify underperforming campaigns.
- Allocate marketing budgets.
- Communicate performance and recommendations to stakeholders.

Pain points:
- Needs analysts to investigate complex questions.
- Spends time navigating multiple dashboards.
- Finds it difficult to identify the underlying drivers of performance changes.
- Needs evidence before making budget decisions.

### Secondary user: Marketing Analyst

Responsibilities:
- Analyze campaign performance.
- Investigate KPI changes.
- Prepare reports.
- Support marketing optimization decisions.

Pain points:
- Repeatedly writes similar SQL queries.
- Manually combines data from multiple sources.
- Repeats the same analytical workflows.

### Future user: Marketing Director

Responsibilities:
- Monitor overall marketing effectiveness.
- Evaluate channel investment.
- Review recommendations and business outcomes.

## 5. Business Objectives

| Objective | Intended outcome |
|---|---|
| Reduce investigation time | Automate repetitive data retrieval and analysis |
| Improve analytical consistency | Standardize KPI definitions through the semantic layer |
| Improve decision quality | Provide evidence-backed explanations |
| Increase analytical accessibility | Enable natural-language interaction |
| Support optimization | Generate actionable budget and campaign recommendations |
| Maintain governance | Require approval before external actions |

### Proposed success measures

These are targets to validate, not achieved results.

- At least 90% correct interpretation of benchmark business requests.
- At least 95% successful retrieval of required data in supported test cases.
- 100% calculation accuracy for deterministic analytical test cases.
- At least 90% evidence-grounded conclusions in the evaluation set.
- 100% enforcement of human approval for protected actions.
- Demonstrate a measurable reduction in investigation time versus a manual baseline.

## 6. Scope

### MVP: Included

1. Synthetic marketing data generation.
2. PostgreSQL data warehouse.
3. dbt data transformation.
4. Centralized marketing metric definitions and semantic layer.
5. Natural-language business question interface.
6. LLM-powered request interpretation and tool selection.
7. LangGraph workflow orchestration.
8. SQL/Python analytical tools.
9. Campaign performance investigation.
10. KPI comparison and driver analysis.
11. Evidence-based recommendations.
12. Human approval interface.
13. Mock marketing action API.
14. Investigation logs and audit records.
15. Automated tests and agent evaluation.

### Out of scope for MVP

- Live Meta Ads or Google Ads account connections.
- Direct modification of real advertising campaigns.
- Autonomous budget execution.
- Production customer personal data.
- Advanced multi-agent collaboration.
- Real-time streaming analytics.
- Full multi-tenant enterprise SaaS infrastructure.
- Complex marketing mix modeling and incrementality measurement.

These can be future extensions.

## 7. Core Product Use Cases

### Use Case 1: Marketing Performance Investigation

Example request:

"Why did Meta Ads ROAS decline by 20% in October compared with September?"

Expected process:
1. Interpret platform, KPI and date range.
2. Resolve the approved ROAS definition.
3. Retrieve relevant campaign performance data.
4. Compare current and previous periods.
5. Identify campaign-level and funnel-level contributors.
6. Explain findings with supporting evidence.
7. Present limitations and potential causes that cannot be verified.

Expected output:
- KPI comparison.
- Campaign contribution analysis.
- Supporting metrics.
- Evidence-based explanation.
- Recommended next steps.

### Use Case 2: Campaign Optimization

Example request:

"Which campaigns are underperforming and should be investigated?"

Expected process:
1. Retrieve campaign performance.
2. Compare campaigns using consistent metrics.
3. Identify campaigns with declining ROAS, high CPA or other relevant performance issues.
4. Consider spend levels and conversion volume.
5. Generate a prioritized investigation list.

Expected output:
- Campaign ranking.
- Performance metrics.
- Reasons for prioritization.
- Data limitations.
- Recommended investigation actions.

### Use Case 3: Budget Allocation Recommendation

Example request:

"Recommend how to redistribute our $50,000 marketing budget to improve ROAS."

Expected process:
1. Retrieve campaign-level performance and spend.
2. Analyze historical performance and constraints.
3. Estimate candidate budget allocations.
4. Explain assumptions and uncertainty.
5. Create a proposed budget change.
6. Request human approval.
7. Execute only against the mock marketing API after approval.

Expected output:
- Current versus proposed allocation.
- Expected outcomes and assumptions.
- Risks and limitations.
- Approval status.
- Execution record if approved.

The MVP must not treat historical ROAS as a guaranteed prediction of future incremental returns.

### Use Case 4: Conversion Funnel Investigation

Example request:

"Where are users dropping off between ad clicks and purchases?"

Expected process:
1. Retrieve impressions, clicks, sessions, add-to-carts and purchases.
2. Calculate conversion rates between defined funnel stages.
3. Compare platforms, campaigns and landing pages.
4. Identify significant drop-offs.
5. Recommend additional investigation.

Expected output:
- Funnel visualization.
- Stage conversion rates.
- Segment breakdown.
- Potential explanations and supporting evidence.

## 8. Data Requirements

### Data sources

The MVP will simulate data from:

- Meta Ads
- Google Ads
- Website analytics
- E-commerce orders
- Customer acquisition records

### Core warehouse tables

Fact tables:

- fact_ad_performance
- fact_web_analytics
- fact_orders
- fact_customer_acquisition

Dimension tables:

- dim_date
- dim_platform
- dim_channel
- dim_campaign
- dim_ad
- dim_landing_page
- dim_customer

Every fact table must have a documented grain, primary key or unique-key strategy, relationships and data quality tests.

### Data requirements

- At least 12 months of synthetic daily marketing data.
- Multiple advertising platforms.
- Multiple campaigns per platform.
- Campaign-level variation in spend, impressions, clicks and conversions.
- Website sessions and conversion funnel events.
- Order-level revenue and customer acquisition information.
- Controlled scenarios representing campaign performance changes.
- Intentionally introduced data quality issues for testing.

## 9. Semantic Layer Requirements

The application must maintain centralized definitions of important marketing metrics.

Initial metrics:

- Total Ad Spend
- Impressions
- Clicks
- CTR
- CPC
- Conversions
- CPA
- Revenue
- ROAS
- CAC
- Conversion Rate

Each metric must document:

- Business name and description.
- Calculation formula.
- Source model or data source.
- Aggregation behavior.
- Supported dimensions.
- Time grain.
- Attribution methodology, where relevant.
- Filters and exclusions.
- Null and zero-denominator behavior.
- Known limitations.

The LLM must retrieve these definitions instead of independently inventing formulas.

## 10. Functional Requirements

**FR-01: Natural-language interface**

Users can submit marketing performance questions in natural language.

**FR-02: Request interpretation**

The application identifies the KPI, date range, platform, campaign, dimensions and business objective.

**FR-03: Metric resolution**

The agent retrieves the approved semantic definition for each requested KPI.

**FR-04: Data retrieval**

The agent retrieves data using approved, validated analytical tools.

**FR-05: Data validation**

The system checks data availability, freshness, missing values, duplicate records and aggregation consistency.

**FR-06: KPI analysis**

The system calculates marketing performance metrics using deterministic SQL/Python functions.

**FR-07: Driver analysis**

The system identifies campaigns, channels or other segments contributing to observed changes.

**FR-08: Evidence-based explanations**

The agent produces findings supported by data and clearly communicates uncertainty.

**FR-09: Recommendations**

The agent proposes optimization opportunities based on retrieved evidence and stated constraints.

**FR-10: Human approval**

Users can approve, edit or reject proposed external actions.

**FR-11: Action execution**

Only authorized and approved actions can be executed through the mock marketing API.

**FR-12: Audit logging**

The system records requests, tool calls, data references, results, recommendations, approvals and execution outcomes.

**FR-13: Error handling**

The system handles missing information, invalid requests, failed queries and LLM/tool failures without fabricating results.

**FR-14: Evaluation**

The application includes benchmark requests with expected outputs and automated evaluation.

## 11. Nonfunctional Requirements

### Reliability
- Failed tool calls must be handled explicitly.
- The agent must not silently continue with incomplete or invalid data.
- Protected actions must never execute without verified approval.
- Duplicate execution requests must be prevented using idempotency controls.

### Security
- Database access must be read-only for analytical tools.
- Credentials must be stored in environment variables or a secret manager.
- The application must validate user permissions before actions.
- User inputs and retrieved data must not be treated as trusted system instructions.

### Transparency
- Display metric definitions and reporting periods.
- Show relevant supporting data and calculations.
- Identify assumptions and data limitations.
- Record the analysis and approval history.

### Maintainability
- Separate data, analytics, orchestration, API and UI modules.
- Keep metric definitions centralized.
- Maintain automated unit and integration tests.
- Use Git for version control.

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Inconsistent attribution | Explicit attribution rules and separate source-reported metrics |
| Double-counted revenue | Define canonical order-level revenue and avoid summing duplicated platform attribution |
| Incorrect KPI calculations | Centralized metric definitions and deterministic tests |
| Incorrect LLM tool selection | Structured inputs, tool constraints and benchmark evaluation |
| Unsupported recommendations | Require supporting data and explain limitations |
| Unsafe execution | Human approval, authorization and idempotency |
| Incomplete data | Data validation and explicit uncertainty |
| Overcomplicated architecture | Deliver a limited MVP before advanced features |

## 13. Definition of MVP Success

The MVP is considered successful when a marketing manager can:

1. Submit a supported natural-language marketing question.
2. Receive the correct interpretation of the request.
3. Retrieve the correct data and metric definitions.
4. Receive numerically accurate KPI analysis.
5. Understand the key drivers of the observed change.
6. Review an evidence-based recommendation.
7. Approve, edit or reject a proposed action.
8. Verify that only an approved action was executed.
9. Inspect the investigation and execution history.

The final evaluation must report measured performance, actual limitations and manual comparison results.