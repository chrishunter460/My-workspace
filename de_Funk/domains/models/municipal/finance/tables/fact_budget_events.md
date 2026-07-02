---
type: domain-model-table
table: fact_budget_events
extends: _base.accounting.financial_statement._fact_financial_statements
table_type: fact
primary_key: [statement_entry_id]
partition_by: [period_end_date_id]
persist: true

# Budget line items ARE financial statement entries with report_type = 'budget'.
# They use the same base schema (statement_entry_id, legal_entity_id, account_id,
# period_end_date_id, report_type, amount, reported_currency) plus budget-specific
# additional columns at the model level.

# Sources auto-discovered: any sources/*.md with maps_to: fact_budget_events
# Currently: budget_appropriations (APPROPRIATION) + budget_revenue (REVENUE) + budget_positions (POSITION)

# Base financial_statement fields (inherited from extends, listed here for resolver indexing)
# [column, type, nullable, description, {options}]
schema:
  - [statement_entry_id, integer, false, "PK", {}]
  - [legal_entity_id, integer, false, "FK to reporting entity"]
  - [account_id, integer, false, "FK to chart of accounts", {fk: dim_chart_of_accounts.account_id}]
  - [period_end_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_start_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, false, "budget"]
  - [amount, double, false, "Line item value", {format: $}]
  - [reported_currency, string, true, "Reporting currency"]

# Budget-specific columns beyond base financial_statement schema
# [column, type, nullable, description, {options}]
additional_schema:
  - [event_type, string, false, "APPROPRIATION, REVENUE, POSITION"]
  - [fiscal_year, integer, false, "Budget year", {derived: "YEAR(period_end_date_id)"}]
  - [domain_source, string, false, "Origin domain"]
  - [department_code, string, true, "Department code (nullable for revenue sources)"]
  - [department_description, string, true, "Department name (nullable for revenue sources)"]
  - [fund_code, string, true, "Fund code (nullable for position sources)"]
  - [fund_description, string, true, "Fund name (nullable for position sources)"]
  - [account_code, string, true, "Raw account code (also used to derive account_id)"]
  - [account_description, string, true, "Account/title name"]
  - [description, string, true, "Line-item description"]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "CASE WHEN department_code IS NOT NULL THEN ABS(HASH(department_code)) ELSE null END"}]
  - [fund_id, integer, true, "FK to dim_fund", {fk: dim_fund.fund_id, derived: "CASE WHEN fund_code IS NOT NULL THEN ABS(HASH(fund_code)) ELSE null END"}]

measures:
  - [total_budget, sum, amount, "Total budgeted amount", {format: "$#,##0.00"}]
  - [line_item_count, count_distinct, statement_entry_id, "Budget line items", {format: "#,##0"}]
  - [appropriation_total, expression, "SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Total appropriations", {format: "$#,##0.00"}]
  - [revenue_total, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END)", "Total revenue", {format: "$#,##0.00"}]
  - [position_total, expression, "SUM(CASE WHEN event_type = 'POSITION' THEN amount ELSE 0 END)", "Total position salaries", {format: "$#,##0.00"}]
  - [budget_surplus, expression, "SUM(CASE WHEN event_type = 'REVENUE' THEN amount ELSE 0 END) - SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
---

## Budget Events Fact

Budget line items stored as financial statement entries with `report_type = 'budget'`. Extends `_base.accounting.financial_statement._fact_financial_statements` — same PK, same account_id FK, same period dates.

### Why Not a Separate Table?

Budgets and actuals share the same dimensions (chart of accounts, calendar, legal entity). Keeping them in the same table enables budget-vs-actual analysis via a `report_type` filter:

```sql
SELECT report_type, SUM(amount)
FROM fact_budget_events  -- which IS a financial_statements table with report_type = 'budget'
UNION ALL
SELECT 'annual', SUM(amount)
FROM fact_financial_statements
WHERE report_type = 'annual'
```

### Budget-Specific Columns

| Column | Nullable | Why Nullable |
|--------|----------|--------------|
| `department_code` | yes | Revenue sources don't have departments |
| `fund_code` | yes | Position sources don't have funds |
| `account_code` | yes | Derived from source-specific fields (appropriation_account, revenue_source_code, title_code) |

### Source Mapping

| Source | event_type | account_code from |
|--------|-----------|-------------------|
| budget_appropriations | APPROPRIATION | appropriation_account |
| budget_revenue | REVENUE | revenue_source_code |
| budget_positions | POSITION | title_code |
