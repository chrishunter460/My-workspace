---
type: domain-base
model: financial_statement
version: 1.0
description: "Periodic financial reporting - income statements, balance sheets, cash flows, budgets structured by chart of accounts"
extends: _base.accounting.ledger_entry

# CANONICAL FIELDS
# Inherited from financial_event → ledger_entry:
#   event_id → entry_id → statement_entry_id (PK)
#   date_id → date_id → period_end_date_id (FK to calendar)
#   event_type → entry_type → report_type (annual, quarterly, budget)
#   amount → transaction_amount → amount (line item value)
#   legal_entity_id (FK to entity)
#   reported_currency
# Additional fields specific to periodic financial reporting:
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [statement_entry_id, integer, nullable: false, description: "Primary key (maps to ledger entry_id)"]
  - [legal_entity_id, integer, nullable: false, description: "FK to reporting entity (company or municipality)"]
  - [account_id, integer, nullable: false, description: "FK to chart of accounts line item"]
  - [period_end_date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (period end, maps to ledger date_id)"]
  - [period_start_date_id, integer, nullable: true, description: "FK to temporal.dim_calendar (period start)"]
  - [report_type, string, nullable: false, description: "annual, quarterly, budget (maps to ledger entry_type)"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [amount, double, nullable: false, description: "Line item value (maps to ledger transaction_amount)"]
  - [reported_currency, string, nullable: true, description: "Reporting currency (USD, EUR, etc.)"]

tables:
  _fact_financial_statements:
    type: fact
    primary_key: [statement_entry_id]
    partition_by: [period_end_date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [statement_entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(legal_entity_id, '_', account_id, '_', period_end_date_id, '_', report_type)))"}]
      - [legal_entity_id, integer, false, "FK to reporting entity"]
      - [account_id, integer, false, "FK to chart of accounts", {derived: "ABS(HASH(account_code))"}]
      - [period_end_date_id, integer, false, "FK to calendar (period end)", {fk: temporal.dim_calendar.date_id}]
      - [period_start_date_id, integer, true, "FK to calendar (period start)", {fk: temporal.dim_calendar.date_id}]
      - [report_type, string, false, "annual or quarterly"]
      - [domain_source, string, false, "Origin domain"]
      - [amount, double, false, "Line item value"]
      - [reported_currency, string, true, "Reporting currency"]

    measures:
      # Simple aggregations (work on any financial_statement fact)
      - [entry_count, count_distinct, statement_entry_id, "Statement entries", {format: "#,##0"}]
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0"}]
      - [avg_line_item, avg, amount, "Average line item", {format: "$#,##0.00"}]
      - [entity_count, count_distinct, legal_entity_id, "Reporting entities", {format: "#,##0"}]
      - [period_count, count_distinct, period_end_date_id, "Reporting periods", {format: "#,##0"}]

      # Account-type measures (JOIN to chart of accounts via account_type — works for corporate AND municipal)
      - [total_revenue_by_type, expression, "SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount ELSE 0 END)", "Revenue (all accounts)", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [total_expenses_by_type, expression, "SUM(CASE WHEN coa.account_type = 'EXPENSE' THEN fs.amount ELSE 0 END)", "Expenses (all accounts)", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [net_position, expression, "SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount WHEN coa.account_type = 'EXPENSE' THEN -fs.amount ELSE 0 END)", "Revenue minus expenses", {format: "$#,##0", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]
      - [expense_ratio, expression, "SUM(CASE WHEN coa.account_type = 'EXPENSE' THEN fs.amount ELSE 0 END) / NULLIF(SUM(CASE WHEN coa.account_type = 'REVENUE' THEN fs.amount ELSE 0 END), 0)", "Expense-to-revenue ratio", {format: "#,##0.00", joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"}]

    python_measures:
      # Inherited from _base.accounting.ledger_entry, params overridden for statement schema
      net_present_value:
        params:
          amount_col: "amount"
          date_col: "period_end_date_id"

      # Inherited, override for statement columns
      spending_velocity:
        params:
          amount_col: "amount"
          date_col: "period_end_date_id"
          partition_cols: [legal_entity_id, report_type]

      # Financial statement-specific measures below
      npv_by_category:
        function: "accounting.measures.calculate_npv_by_category"
        description: "NPV grouped by account type (revenue, expense, asset, liability)"
        params:
          discount_rate: 0.05
          category_col: "account_type"
          amount_col: "amount"
        returns: [legal_entity_id, account_type, npv]
        joins: "_fact_financial_statements fs JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id"

      cagr:
        function: "accounting.measures.calculate_cagr"
        description: "Compound annual growth rate of amounts between earliest and latest periods"
        params:
          amount_col: "amount"
          date_col: "period_end_date_id"
        returns: [legal_entity_id, account_type, cagr_pct]

      yoy_growth:
        function: "accounting.measures.calculate_yoy_growth"
        description: "Year-over-year growth rate per entity per account type"
        params:
          amount_col: "amount"
          date_col: "period_end_date_id"
          partition_cols: [legal_entity_id, account_id]
        returns: [legal_entity_id, account_id, period_end_date_id, amount, prior_amount, yoy_growth_pct]

      budget_variance:
        function: "accounting.measures.calculate_budget_variance"
        description: "Variance between budget and actual amounts for same entity/account"
        params:
          budget_report_type: "budget"
          actual_report_types: ["annual", "quarterly"]
        returns: [legal_entity_id, account_id, budget_amount, actual_amount, variance, variance_pct]

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [statement_to_period_end, _fact_financial_statements, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [statement_to_period_start, _fact_financial_statements, temporal.dim_calendar, [period_start_date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal        # Inherited from event → financial_event → ledger_entry

domain: accounting
tags: [base, template, accounting, financial_statement, SEC]
status: active
---

## Financial Statement Base Template

Periodic financial reporting data — income statements, balance sheets, cash flows, and budgets. Each row is one line item for one entity in one reporting period. The `report_type` discriminator distinguishes actuals from budgets.

### Inheritance Chain

```
_base._base_.event
└── _base.accounting.financial_event       ← NPV, spending_velocity defined here
    └── _base.accounting.ledger_entry      ← adds payee, categorization
        └── _base.accounting.financial_statement  ← adds account structure, CAGR, YoY, budget variance
```

Financial statements ARE structured ledger entries — periodic summaries organized by chart of accounts. The column mapping from ledger to statement:

| ledger_entry field | financial_statement field | Notes |
|-------------------|-------------------------|-------|
| `entry_id` | `statement_entry_id` | PK |
| `date_id` | `period_end_date_id` | FK to calendar |
| `entry_type` | `report_type` | annual, quarterly, budget |
| `transaction_amount` | `amount` | Line item value |
| *(new)* | `account_id` | FK to chart of accounts |
| *(new)* | `period_start_date_id` | Period start date |
| *(new)* | `reported_currency` | Currency |

### What Extends This

This is the leaf of the accounting hierarchy — no other base templates extend it. Concrete domain-models extend this directly:

| Domain Model | report_type values | Use case |
|-------------|-------------------|----------|
| `corporate/company` | `annual`, `quarterly` | SEC filings (10-K, 10-Q) |
| `municipal/finance` | `annual`, `budget` | Municipal financial reporting |

### Shared Measures

The account-type measures (`total_revenue_by_type`, `total_expenses_by_type`, `net_position`, `expense_ratio`) work across ANY implementing model because they rely on `account_type` from the chart of accounts, not specific account codes. This enables:

- Compare Chicago's budgeted revenue vs Apple's reported revenue — same measure, different `legal_entity_id`
- Budget-vs-actual analysis — filter `report_type IN ('annual', 'budget')` for the same entity

### Relationship to Chart of Accounts

Financial statements are structured by a chart of accounts. The `account_id` FK links each line item to a classification in `_base.accounting.chart_of_accounts`. The implementing model provides the concrete account dimension:

- **Corporate models**: `dim_financial_account` with SEC line items (TOTAL_REVENUE, NET_INCOME, etc.)
- **Municipal models**: Government accounting chart (GAAP fund-based accounts)

### Relationship to Entity

The `legal_entity_id` FK is generic. Source aliases map it to the concrete entity:

```yaml
# Corporate: legal_entity_id maps to company_id
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]

# Municipal: legal_entity_id maps to municipality_id
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', municipality_name)))"]
```

### Python Measures

**Inherited from `financial_event` → `ledger_entry`** (param overrides only):

| Measure | Origin | Overridden Params |
|---------|--------|-------------------|
| `net_present_value` | `financial_event` | `amount_col: "amount"`, `date_col: "period_end_date_id"` |
| `spending_velocity` | `financial_event` | `amount_col: "amount"`, `partition_cols: [legal_entity_id, report_type]` |

**Defined at this level** (inherited by all implementing models):

| Measure | Description | Key Params |
|---------|-------------|------------|
| `npv_by_category` | NPV grouped by account type (revenue, expense, etc.) | `discount_rate: 0.05` |
| `cagr` | Compound annual growth rate between earliest and latest periods | `amount_col: "amount"` |
| `yoy_growth` | Year-over-year growth per entity per account | Partitions by entity + account |
| `budget_variance` | Variance between budget and actual for same entity/account | Requires `report_type` filter |

NPV is defined once at `financial_event` and flows through the chain: `financial_event` → `ledger_entry` → `financial_statement`. Each level overrides column params to match its schema. No duplication.

### Budget Integration Pattern

Budget data is modeled as financial statements — **not** as a separate base template. Budget line items extend `_fact_financial_statements` with `report_type = 'budget'`. This enables budget-vs-actual comparison using the same chart of accounts structure.

**How it works:**
1. Budget sources set `report_type` to `'budget'` and `event_type` to the budget grain (`APPROPRIATION`, `REVENUE`, `POSITION`)
2. Actual financial data sets `report_type` to `'annual'` or `'quarterly'`
3. Both share the same `account_id` FK to `_dim_chart_of_accounts`
4. Same `legal_entity_id` identifies the reporting entity

**Budget-vs-actual query:**
```sql
SELECT coa.account_name,
       SUM(CASE WHEN fs.report_type = 'budget' THEN fs.amount ELSE 0 END) as budget,
       SUM(CASE WHEN fs.report_type = 'annual' THEN fs.amount ELSE 0 END) as actual,
       SUM(CASE WHEN fs.report_type = 'annual' THEN fs.amount ELSE 0 END)
         - SUM(CASE WHEN fs.report_type = 'budget' THEN fs.amount ELSE 0 END) as variance
FROM _fact_financial_statements fs
JOIN _dim_chart_of_accounts coa ON fs.account_id = coa.account_id
GROUP BY coa.account_name;
```

The `budget_variance` python measure automates this pattern. Budget events do NOT need a separate base — they ARE financial statements, classified by `report_type`.

### Unpivot Transform

Source data typically arrives as wide tables (one column per line item). Sources use `transform: unpivot` with `unpivot_aliases:` to convert columns into rows:

```yaml
transform: unpivot
unpivot_aliases:
  - [totalRevenue, TOTAL_REVENUE]
  - [netIncome, NET_INCOME]
```

### Usage

```yaml
extends: _base.accounting.financial_statement
```
