---
type: domain-base
model: ledger_entry
version: 1.0
description: "Financial ledger entries - payments, payroll, contracts. Supports multi-source unions."
extends: _base.accounting.financial_event

# CANONICAL FIELDS
# Inherited from financial_event: event_id (→ entry_id), legal_entity_id,
#   date_id, amount (→ transaction_amount), event_type (→ entry_type), reported_currency
# Adds: payee, source tracking, categorization fields
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [entry_id, integer, nullable: false, description: "Primary key"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [entry_type, string, nullable: false, description: "VENDOR_PAYMENT, PAYROLL"]
  - [domain_source, string, nullable: false, description: "Origin domain (chicago, cook_county, etc.)"]
  - [source_id, string, nullable: false, description: "Original ID from source system"]
  - [payee, string, nullable: false, description: "Entity receiving payment"]
  - [transaction_amount, "decimal(18,2)", nullable: false, description: "Monetary value"]
  - [transaction_date, date, nullable: false, description: "Date of transaction"]
  - [organizational_unit, string, nullable: true, description: "Department/agency (null if unavailable)"]
  - [expense_category, string, nullable: true, description: "How expense is classified (null if unavailable)"]
  - [fund_code, string, nullable: true, description: "Fund the expense is charged to (null if unavailable)"]
  - [description, string, nullable: true, description: "Free-text description of transaction"]

tables:
  _fact_ledger_entries:
    type: fact
    primary_key: [entry_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
      - [legal_entity_id, integer, true, "FK to owning legal entity"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(transaction_date, 'yyyyMMdd') AS INT)"}]
      - [entry_type, string, false, "Source discriminator"]
      - [domain_source, string, false, "Origin domain"]
      - [source_id, string, false, "Original source ID"]
      - [payee, string, false, "Who received payment"]
      - [transaction_amount, "decimal(18,2)", false, "Amount"]
      - [transaction_date, date, false, "Transaction date"]
      - [organizational_unit, string, true, "Department (null if not available)"]
      - [expense_category, string, true, "Classification (null if not available)"]
      - [fund_code, string, true, "Fund code (null if not available)"]
      - [description, string, true, "Transaction description"]

    measures:
      - [total_amount, sum, transaction_amount, "Total transaction amount", {format: "$#,##0.00"}]
      - [entry_count, count_distinct, entry_id, "Number of entries", {format: "#,##0"}]
      - [avg_amount, avg, transaction_amount, "Average transaction", {format: "$#,##0.00"}]
      - [payee_count, count_distinct, payee, "Unique payees", {format: "#,##0"}]
      - [payroll_total, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN transaction_amount ELSE 0 END)", "Payroll total", {format: "$#,##0.00"}]
      - [vendor_total, expression, "SUM(CASE WHEN entry_type = 'VENDOR_PAYMENT' THEN transaction_amount ELSE 0 END)", "Vendor payment total", {format: "$#,##0.00"}]

    python_measures:
      # Inherited from _base.accounting.financial_event, params overridden for ledger schema
      net_present_value:
        params:
          amount_col: "transaction_amount"
          date_col: "transaction_date"

      spending_velocity:
        params:
          amount_col: "transaction_amount"
          date_col: "transaction_date"
          partition_cols: [domain_source, entry_type]

graph:
  # auto_edges inherited: date_id→calendar
  edges: []

behaviors:
  - temporal        # Inherited from event → financial_event

domain: accounting
tags: [base, template, accounting, ledger]
status: active
---

## Ledger Entry Base Template

Categorized financial transactions with payee, department, and expense classification. Extends `financial_event` (the generic base) to add recording-level detail.

### Inheritance Chain

```
_base._base_.event
└── _base.accounting.financial_event       ← NPV, spending_velocity defined here
    └── _base.accounting.ledger_entry      ← YOU ARE HERE (adds payee, categorization)
        └── _base.accounting.financial_statement  ← periodic aggregation by chart of accounts
```

Each source endpoint (payments, salaries, contracts) maps to this schema via aliases. Supports multi-source unions via federation.

### Nullable Field Contract

Fields marked `nullable: true` are optional. Sources that lack a field must explicitly handle it:

| Pattern | When | Example |
|---------|------|---------|
| `"null"` | Source truly lacks field | `organizational_unit: "null"` |
| `"'STATIC'"` | Use constant | `expense_category: "'SALARY'"` |
| `"other_col"` | Use fallback column | `organizational_unit: "company_name"` |
| `"COALESCE(...)"` | Try multiple | `"COALESCE(dept, division, 'UNKNOWN')"` |

### Expense vs Revenue Categorization

Expense/revenue classification operates at **two levels** of the accounting hierarchy:

**Level 1 — Ledger Entry (this template):** The `entry_type` discriminator classifies by *transaction origin*:

| entry_type | Classification | Example |
|-----------|---------------|---------|
| `VENDOR_PAYMENT` | Expense | Paying a supplier |
| `PAYROLL` | Expense | Employee salaries |

Computed measures filter on `entry_type` (e.g., `payroll_total`, `vendor_total`). This is a flat, operational classification — it tells you *what kind of payment* but not the GAAP accounting category.

**Level 2 — Financial Statement (child template):** The `account_id` FK links to `_dim_chart_of_accounts`, which has `account_type` enum: `[ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY]`. This is the GAAP-standard classification. Computed measures use:

```sql
SUM(CASE WHEN coa.account_type = 'EXPENSE' THEN amount ELSE 0 END)
```

**In practice:** Ledger entries get loaded with `entry_type` at ingestion time. Financial statements (which extend ledger entries) add `account_id` to classify each amount by its chart-of-accounts category. The two levels are complementary, not competing.

### Federation

When multiple domain-models extend this base, a federation view unions them:

```sql
SELECT * FROM accounting.v_all_ledger_entries
-- Unions: chicago_ledger, cook_county_ledger, corporate_ledger
```

### Usage

```yaml
extends: _base.accounting.ledger_entry
```
