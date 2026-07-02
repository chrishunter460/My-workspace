---
type: domain-base
model: chart_of_accounts
version: 1.0
description: "Chart of accounts - hierarchical expense/revenue classification"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [account_id, integer, nullable: false, description: "Primary key"]
  - [account_code, string, nullable: false, description: "Account code (e.g., 5000, SALARY)"]
  - [account_name, string, nullable: false, description: "Account name"]
  - [account_type, string, nullable: false, description: "ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY"]
  - [account_subtype, string, nullable: true, description: "Sub-classification: current, non_current, operating, non_operating"]
  - [parent_account_id, integer, nullable: true, description: "Parent account for hierarchy"]
  - [level, integer, nullable: false, description: "Hierarchy level (1=top)"]
  - [statement_section, string, nullable: true, description: "Which financial statement: balance_sheet, income_statement, cash_flow"]
  - [cash_flow_category, string, nullable: true, description: "Cash flow classification: operating, investing, financing"]
  - [normal_balance, string, nullable: true, description: "Natural balance direction: debit or credit"]
  - [is_contra, boolean, nullable: true, description: "Contra account (reverses normal balance)"]
  - [is_rollup, boolean, nullable: true, description: "Summary/rollup account vs leaf account"]
  - [format_type, string, nullable: true, description: "Display format: currency, percentage, ratio"]
  - [fund_type, string, nullable: true, description: "Municipal only: GENERAL, SPECIAL_REVENUE, ENTERPRISE, etc."]
  - [gasb_category, string, nullable: true, description: "Municipal GASB classification (null for corporate)"]
  - [is_active, boolean, nullable: false, description: "Currently in use"]

tables:
  _dim_chart_of_accounts:
    type: dimension
    primary_key: [account_id]
    unique_key: [account_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
      - [account_code, string, false, "Natural key"]
      - [account_name, string, false, "Display name"]
      - [account_type, string, false, "Classification", {enum: [ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY]}]
      - [account_subtype, string, true, "Sub-classification", {enum: [CURRENT, NON_CURRENT, OPERATING, NON_OPERATING, CONTRA]}]
      - [parent_account_id, integer, true, "Self-referencing FK", {fk: _dim_chart_of_accounts.account_id}]
      - [level, integer, false, "Hierarchy depth", {default: 1}]
      - [statement_section, string, true, "Financial statement", {enum: [BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW]}]
      - [cash_flow_category, string, true, "Cash flow bucket", {enum: [OPERATING, INVESTING, FINANCING]}]
      - [normal_balance, string, true, "Natural balance direction", {enum: [DEBIT, CREDIT]}]
      - [is_contra, boolean, true, "Contra account flag", {default: false}]
      - [is_rollup, boolean, true, "Summary/rollup account", {default: false}]
      - [format_type, string, true, "Display format", {enum: [CURRENCY, PERCENTAGE, RATIO, INTEGER]}]
      - [fund_type, string, true, "Municipal fund classification (null for corporate)"]
      - [gasb_category, string, true, "Municipal GASB category (null for corporate)"]
      - [is_active, boolean, false, "Currently used", {default: true}]

    measures:
      - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
      - [expense_account_count, expression, "SUM(CASE WHEN account_type = 'EXPENSE' THEN 1 ELSE 0 END)", "Expense accounts", {format: "#,##0"}]
      - [revenue_account_count, expression, "SUM(CASE WHEN account_type = 'REVENUE' THEN 1 ELSE 0 END)", "Revenue accounts", {format: "#,##0"}]

behaviors: []  # Pure entity — classification dimension only

domain: accounting
tags: [base, template, accounting, chart_of_accounts]
status: active
---

## Chart of Accounts Base Template

Hierarchical classification of financial accounts. Extends `_base._base_.entity` with accounting-specific fields.

### Account Types

| Type | Description | Example |
|------|-------------|---------|
| ASSET | Owned resources | Cash, Receivables |
| LIABILITY | Owed obligations | Payables, Bonds |
| REVENUE | Income sources | Taxes, Fees, Grants |
| EXPENSE | Spending categories | Salaries, Contracts, Supplies |
| EQUITY | Net position | Fund Balance |

### Hierarchy

Accounts form a tree via `parent_account_id`:

```
EXPENSE (level 1)
  PERSONNEL (level 2)
    SALARIES (level 3)
    BENEFITS (level 3)
  CONTRACTUAL (level 2)
    PROFESSIONAL_SERVICES (level 3)
    UTILITIES (level 3)
```

### Financial Statement Mapping

Every account maps to a financial statement via `statement_section`:

| statement_section | Contains | Example Accounts |
|---|---|---|
| BALANCE_SHEET | Assets, liabilities, equity | Cash, Payables, Fund Balance |
| INCOME_STATEMENT | Revenue and expenses | Tax Revenue, Salaries, Contracts |
| CASH_FLOW | Cash flow activities | Operating Cash, CapEx, Financing |

### Normal Balance & Contra Accounts

`normal_balance` determines sign convention. `is_contra` reverses it:

| account_type | normal_balance | is_contra | Example |
|---|---|---|---|
| ASSET | DEBIT | false | Cash, Receivables |
| ASSET | CREDIT | true | Allowance for Doubtful Accounts |
| LIABILITY | CREDIT | false | Payables, Bonds |
| REVENUE | CREDIT | false | Tax Revenue |
| EXPENSE | DEBIT | false | Salaries |

### Municipal Extensions

`fund_type` and `gasb_category` are null for corporate models but populated for government GAAP:

| fund_type | Description | gasb_category |
|---|---|---|
| GENERAL | Unrestricted operating | GOVERNMENTAL |
| SPECIAL_REVENUE | Legally restricted | GOVERNMENTAL |
| ENTERPRISE | Self-sustaining | PROPRIETARY |
| CAPITAL | Capital projects | GOVERNMENTAL |
| DEBT_SERVICE | Debt repayment | GOVERNMENTAL |

### Expense vs Revenue Determination

The `account_type` enum is the canonical answer to "is this an expense or revenue?" Every financial statement line item FKs to this dimension via `account_id`. Classification is definitive:

- `account_type = 'EXPENSE'` → spending
- `account_type = 'REVENUE'` → income
- `account_type = 'ASSET'` / `'LIABILITY'` / `'EQUITY'` → balance sheet items

This applies uniformly to both corporate (SEC filings) and municipal (government GAAP) models. See `_base.accounting.ledger_entry` for the operational-level classification via `entry_type`.

### Usage

```yaml
extends: _base.accounting.chart_of_accounts
```
