---
type: domain-model-table
table: dim_department
extends: _base.entity.organizational_entity._dim_org_unit
table_type: dimension
transform: distinct
from: fact_ledger_entries
union_from: [fact_ledger_entries, fact_budget_events]
group_by: [organizational_unit]
primary_key: [org_unit_id]
unique_key: [org_unit_code]

# [column, type, nullable, description, {options}]
schema:
  - [org_unit_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]
  - [org_unit_code, string, false, "Natural key", {derived: "COALESCE(organizational_unit, 'UNKNOWN')"}]
  - [org_unit_name, string, false, "Display name", {derived: "COALESCE(organizational_unit, 'UNKNOWN')"}]
  - [org_unit_type, string, false, "Type", {derived: "'DEPARTMENT'"}]
  - [parent_org_unit_id, integer, true, "No hierarchy in source", {derived: "CAST(null AS INT)"}]
  - [legal_entity_id, integer, false, "City of Chicago", {derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [is_active, boolean, false, "Operational", {default: true}]

# Enrichment: budget vs actual spending (materialized at build time)
enrich:
  - from: fact_ledger_entries
    join: [organizational_unit = org_unit_code]
    # [column, type, nullable, description, {options}]
    columns:
      - [total_paid, "decimal(18,2)", true, "Total actual spending", {derived: "SUM(transaction_amount)", format: $}]
      - [payment_count, integer, true, "Number of payments", {derived: "COUNT(DISTINCT entry_id)", format: number}]
      - [first_payment_date, date, true, "Earliest payment", {derived: "MIN(transaction_date)", format: date}]
      - [last_payment_date, date, true, "Most recent payment", {derived: "MAX(transaction_date)", format: date}]

  - from: fact_budget_events
    join: [department_description = org_unit_code]
    filter: "event_type = 'APPROPRIATION'"
    columns:
      - [total_appropriated, "decimal(18,2)", true, "Total budgeted", {derived: "SUM(amount)", format: $}]
      - [budget_line_count, integer, true, "Budget line items", {derived: "COUNT(DISTINCT statement_entry_id)", format: number}]

  - from: fact_budget_events
    join: [department_description = org_unit_code]
    filter: "event_type = 'POSITION'"
    columns:
      - [total_personnel_budget, "decimal(18,2)", true, "Budgeted personnel costs", {derived: "SUM(amount)", format: $}]

  - derived:
      - [budget_variance, "decimal(18,2)", true, "Budget minus actual", {derived: "COALESCE(total_appropriated, 0) - COALESCE(total_paid, 0)", format: $}]
      - [budget_utilization_pct, "decimal(5,4)", true, "% of budget used", {derived: "COALESCE(total_paid, 0) / NULLIF(total_appropriated, 0)", format: "%"}]
      - [personnel_pct, "decimal(5,4)", true, "Personnel as % of budget", {derived: "COALESCE(total_personnel_budget, 0) / NULLIF(total_appropriated, 0)", format: "%"}]

measures:
  - [department_count, count_distinct, org_unit_id, "Number of departments", {format: "#,##0"}]
  - [over_budget_count, expression, "SUM(CASE WHEN budget_variance < 0 THEN 1 ELSE 0 END)", "Departments over budget", {format: "#,##0"}]
  - [avg_utilization, avg, budget_utilization_pct, "Avg budget utilization", {format: "0.0%"}]
---

## Department Dimension

Extends `_base.entity.organizational_entity._dim_org_unit`. Distinct departments discovered from ledger entries.

### Budget-vs-Actual Enrichment

Each department is enriched with pre-computed accrual metrics at build time:

| Column | Source | Meaning |
|--------|--------|---------|
| total_paid | fact_ledger_entries | Actual cash out the door |
| total_appropriated | fact_budget_events (APPROPRIATION) | Authorized spending limit |
| total_personnel_budget | fact_budget_events (POSITION) | Budgeted salary costs |
| budget_variance | derived | Positive = under budget, negative = over |
| budget_utilization_pct | derived | How much of the budget has been spent |
| personnel_pct | derived | What fraction of budget is personnel |

### Example Query

```sql
-- Departments over budget
SELECT org_unit_name, total_paid, total_appropriated, budget_variance
FROM dim_department
WHERE budget_variance < 0
ORDER BY budget_variance ASC;
```
