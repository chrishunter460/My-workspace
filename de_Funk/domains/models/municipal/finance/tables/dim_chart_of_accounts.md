---
type: domain-model-table
table: dim_chart_of_accounts
extends: _base.accounting.chart_of_accounts._dim_chart_of_accounts
table_type: dimension
transform: distinct
from: fact_budget_events
union_from: [fact_budget_events, fact_ledger_entries]
group_by: [account_code]
primary_key: [account_id]
unique_key: [account_code]

# [column, type, nullable, description, {options}]
schema:
  - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
  - [account_code, string, false, "Natural key", {derived: "account_code"}]
  - [account_name, string, false, "Display name", {derived: "account_description"}]
  - [account_type, string, false, "Classification", {derived: "CASE WHEN event_type = 'REVENUE' THEN 'REVENUE' WHEN event_type = 'POSITION' THEN 'EXPENSE' ELSE 'EXPENSE' END"}]
  - [account_subtype, string, true, "Sub-classification", {derived: "CASE WHEN event_type = 'POSITION' THEN 'OPERATING' ELSE null END"}]
  - [parent_account_id, integer, true, "No hierarchy in source", {derived: "CAST(null AS INT)"}]
  - [level, integer, false, "Flat hierarchy", {derived: "1"}]
  - [statement_section, string, true, "Financial statement", {derived: "CASE WHEN event_type = 'REVENUE' THEN 'INCOME_STATEMENT' ELSE 'INCOME_STATEMENT' END"}]
  - [cash_flow_category, string, true, "Cash flow bucket (not available from budget data)", {derived: "CAST(null AS STRING)"}]
  - [normal_balance, string, true, "Balance direction", {derived: "CASE WHEN event_type = 'REVENUE' THEN 'CREDIT' ELSE 'DEBIT' END"}]
  - [is_contra, boolean, true, "No contra accounts in budget data", {derived: "false"}]
  - [is_rollup, boolean, true, "No rollup distinction in budget data", {derived: "false"}]
  - [format_type, string, true, "Display format", {derived: "'CURRENCY'"}]
  - [fund_type, string, true, "Municipal fund type (derived from fund dimension)", {derived: "CAST(null AS STRING)"}]
  - [gasb_category, string, true, "Municipal GASB category", {derived: "'GOVERNMENTAL'"}]
  - [is_active, boolean, false, "Currently used", {default: true}]

measures:
  - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
  - [expense_account_count, expression, "SUM(CASE WHEN account_type = 'EXPENSE' THEN 1 ELSE 0 END)", "Expense accounts", {format: "#,##0"}]
  - [revenue_account_count, expression, "SUM(CASE WHEN account_type = 'REVENUE' THEN 1 ELSE 0 END)", "Revenue accounts", {format: "#,##0"}]
---

## Chart of Accounts Dimension

Extends `_base.accounting.chart_of_accounts._dim_chart_of_accounts`. Distinct accounts discovered from **canonicalized budget events**.

### Notes

- Accounts come from all three budget event types (APPROPRIATION, REVENUE, POSITION)
- `account_type` is inferred from the `event_type` of the source budget event:
  - REVENUE events → REVENUE accounts
  - APPROPRIATION and POSITION events → EXPENSE accounts
- Hierarchy is flat (level=1) — Chicago's budget data doesn't provide parent-child account relationships
- `account_code` maps to different source fields by event type:
  - APPROPRIATION: `appropriation_account`
  - REVENUE: `revenue_source_code`
  - POSITION: `title_code`
