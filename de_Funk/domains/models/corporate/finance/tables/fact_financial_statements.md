---
type: domain-model-table
table: fact_financial_statements
table_type: fact
extends: _base.accounting.financial_statement._fact_financial_statements
primary_key: [statement_entry_id]
partition_by: [period_end_date_id]

# Unpivot config lives in sources: income_statement.md, balance_sheet.md, cash_flow.md
transform: unpivot

# [column, type, nullable, description, {options}]
schema:
  - [statement_entry_id, integer, false, "PK — HASH(ticker + date + account)", {}]
  - [legal_entity_id, integer, false, "Company hash (legacy)", {}]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [account_id, integer, false, "FK to dim_financial_account", {fk: dim_financial_account.account_id}]
  - [account_code, string, false, "Line item code (TOTAL_REVENUE, NET_INCOME, etc.)"]
  - [period_start_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [period_end_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
  - [report_type, string, false, "annual or quarterly"]
  - [amount, double, false, "Line item value", {format: $}]
  - [reported_currency, string, true, "Reporting currency"]

measures:
  - [entry_count, count_distinct, statement_entry_id, "Statement entries", {format: "#,##0"}]
  - [total_amount, sum, amount, "Total amount", {format: "$#,##0"}]
---

## Financial Statements Fact

Normalized financial statement data. Each row is one line item for one company in one reporting period. Built by unpivoting wide source tables (income_statement, balance_sheet, cash_flow) into row-per-line-item format.

### Unpivot Transform

Source columns are mapped to account codes via `unpivot_aliases` in each source file (income_statement.md, balance_sheet.md, cash_flow.md). For example, the `totalRevenue` column from bronze becomes a row where `account_code = 'TOTAL_REVENUE'` and `amount` = the revenue value.

### Query Pattern

```sql
-- Get all income statement items for AAPL, 2024 annual
SELECT fa.account_name, fs.amount
FROM fact_financial_statements fs
JOIN dim_financial_account fa ON fs.account_id = fa.account_id
JOIN dim_company c ON fs.company_id = c.company_id
WHERE c.ticker = 'AAPL'
  AND fa.statement_type = 'INCOME_STATEMENT'
  AND fs.report_type = 'annual'
ORDER BY fa.display_order;
```
