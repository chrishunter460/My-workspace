---
type: domain-model-table
table: dim_fund
extends: _base.accounting.fund._dim_fund
table_type: dimension
transform: distinct
from: fact_budget_events
group_by: [fund_code]
primary_key: [fund_id]
unique_key: [fund_code]

# [column, type, nullable, description, {options}]
schema:
  - [fund_id, integer, false, "PK", {derived: "ABS(HASH(fund_code))"}]
  - [fund_code, string, false, "Natural key", {derived: "fund_code"}]
  - [fund_description, string, false, "Display name", {derived: "fund_description"}]
  - [fund_type, string, false, "Classification", {derived: "'OTHER'"}]
  - [is_active, boolean, false, "Currently used", {default: true}]

measures:
  - [fund_count, count_distinct, fund_id, "Number of funds", {format: "#,##0"}]
---

## Fund Dimension

Extends `_base.accounting.fund._dim_fund`. Distinct funds discovered from **canonicalized budget events** (not raw bronze).

### Notes

- `fund_type` defaults to `'OTHER'` — Chicago's fund classification doesn't directly map to GASB fund types. A future enrichment could classify based on fund_description patterns.
- Funds appear in both APPROPRIATION and REVENUE events; `distinct` over `fund_code` deduplicates.
