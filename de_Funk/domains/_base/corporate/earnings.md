---
type: domain-base
model: earnings
version: 1.0
description: "Earnings reports - EPS actuals, analyst estimates, and surprise metrics"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [earnings_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: false, description: "FK to reporting entity (company)"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [report_date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (report date)"]
  - [fiscal_date_ending, date, nullable: true, description: "Fiscal period end date"]
  - [reported_eps, double, nullable: true, description: "Reported earnings per share"]
  - [estimated_eps, double, nullable: true, description: "Analyst consensus estimate EPS"]
  - [surprise_eps, double, nullable: true, description: "EPS surprise (reported - estimated)"]
  - [surprise_percentage, double, nullable: true, description: "Surprise as percentage"]

tables:
  _fact_earnings:
    type: fact
    primary_key: [earnings_id]
    partition_by: [report_date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [earnings_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(legal_entity_id, '_', report_date_id)))"}]
      - [legal_entity_id, integer, false, "FK to reporting entity"]
      - [domain_source, string, false, "Origin domain"]
      - [report_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [fiscal_date_ending, date, true, "Fiscal period end"]
      - [reported_eps, double, true, "Reported EPS"]
      - [estimated_eps, double, true, "Consensus estimate EPS"]
      - [surprise_eps, double, true, "EPS surprise"]
      - [surprise_percentage, double, true, "Surprise %"]

    measures:
      - [avg_eps, avg, reported_eps, "Average EPS", {format: "$#,##0.00"}]
      - [avg_surprise_pct, avg, surprise_percentage, "Avg surprise %", {format: "#,##0.00%"}]
      - [earnings_count, count_distinct, earnings_id, "Earnings reports", {format: "#,##0"}]
      - [beat_count, expression, "SUM(CASE WHEN surprise_eps > 0 THEN 1 ELSE 0 END)", "Earnings beats", {format: "#,##0"}]
      - [beat_rate, expression, "100.0 * SUM(CASE WHEN surprise_eps > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)", "Beat rate %", {format: "#,##0.0%"}]

    python_measures:
      eps_trend:
        function: "corporate.measures.calculate_eps_trend"
        description: "Rolling EPS trend — QoQ and YoY growth with linear regression slope"
        params:
          window_quarters: 8
          partition_cols: [legal_entity_id]
        returns: [legal_entity_id, report_date_id, eps_qoq_growth, eps_yoy_growth, eps_trend_slope]

      estimate_accuracy:
        function: "corporate.measures.calculate_estimate_accuracy"
        description: "Rolling analyst estimate accuracy — mean absolute error and bias direction"
        params:
          window_quarters: 8
          partition_cols: [legal_entity_id]
        returns: [legal_entity_id, report_date_id, mae, bias, accuracy_pct]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [earnings_to_calendar, _fact_earnings, temporal.dim_calendar, [report_date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal        # Inherited from event

domain: corporate
tags: [base, template, corporate, earnings, eps]
status: active
---

## Earnings Base Template

Quarterly earnings reports with actual EPS, analyst estimates, and surprise metrics. One row per entity per reporting period.

### Distinct from Financial Statements

| | Earnings | Financial Statements |
|---|---------|---------------------|
| **Grain** | 1 row per entity per quarter | N rows per entity per quarter (one per account) |
| **Source** | Analyst-facing (earnings calls) | GAAP-filed (SEC 10-Q/10-K) |
| **Fields** | EPS, estimates, surprise | Account-by-account amounts |
| **Use Case** | Analyst tracking, earnings calendar | Financial analysis, ratio computation |

### Relationship to Entity

The `legal_entity_id` FK links to the reporting entity. Source aliases map it:

```yaml
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
```

### Usage

```yaml
extends: _base.corporate.earnings
```
