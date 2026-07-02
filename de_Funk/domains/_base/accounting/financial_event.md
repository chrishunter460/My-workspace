---
type: domain-base
model: financial_event
version: 4.0
description: "Base for all financial occurrences — any event involving money, an entity, and a date"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# The universal financial event: something financial happened to an entity on a date.
# All accounting templates inherit these core fields.
# Inherited from event: event_id, legal_entity_id, date_id, location_id (always null for financial events)
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [event_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: false, description: "FK to entity involved"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location (inherited from event, always null for financial events)"]
  - [amount, "decimal(18,2)", nullable: false, description: "Monetary value"]
  - [event_type, string, nullable: false, description: "Event classification (PAYMENT, BUDGET, STATEMENT, etc.)"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [reported_currency, string, nullable: true, description: "Currency (USD, EUR, etc.)"]

tables:
  _fact_financial_events:
    type: fact
    primary_key: [event_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [event_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(event_type, '_', source_id)))"}]
      - [legal_entity_id, integer, false, "FK to entity"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [amount, "decimal(18,2)", false, "Monetary value"]
      - [event_type, string, false, "Event classification"]
      - [domain_source, string, false, "Origin domain"]
      - [reported_currency, string, true, "Currency", {default: "'USD'"}]

    measures:
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0.00"}]
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]
      - [avg_amount, avg, amount, "Average event amount", {format: "$#,##0.00"}]
      - [entity_count, count_distinct, legal_entity_id, "Entities involved", {format: "#,##0"}]

    python_measures:
      net_present_value:
        function: "accounting.measures.calculate_npv"
        description: "NPV of cash flows discounted to earliest date"
        params:
          discount_rate: 0.05
          amount_col: "amount"
          date_col: "date_id"
        returns: [legal_entity_id, event_type, npv]

      spending_velocity:
        function: "accounting.measures.calculate_spending_velocity"
        description: "Rolling spend rate — trailing 30/90/365-day totals and trend"
        params:
          amount_col: "amount"
          date_col: "date_id"
          windows: [30, 90, 365]
          partition_cols: [legal_entity_id, event_type]
        returns: [legal_entity_id, event_type, date_id, spend_30d, spend_90d, spend_365d, trend]

graph:
  # auto_edges inherited: date_id→calendar (no location_id on financial events)
  edges: []

behaviors:
  - temporal        # Inherited from event

domain: accounting
tags: [base, template, accounting, financial_event]
status: active
---

## Financial Event Base Template

The root of the accounting hierarchy. A financial event is any occurrence involving money, an entity, and a date. All accounting templates inherit from this.

### Inheritance Chain

```
_base._base_.event
└── _base.accounting.financial_event       ← YOU ARE HERE (NPV, spending_velocity defined)
    └── _base.accounting.ledger_entry      ← adds payee, categorization, source tracking
        └── _base.accounting.financial_statement  ← adds account structure, report periods
```

### Real-World Flow

1. **Financial event occurs** — money moves, a budget is allocated, a statement is filed
2. **Gets recorded as a ledger entry** — categorized with payee, department, expense type
3. **Entries aggregate into financial statements** — periodic summaries by chart of accounts

### Budgets Are Financial Statements

Budget data flows through `_fact_financial_statements` with `report_type = 'budget'`. There is no separate budget table at the base level. Budget-specific columns (fiscal_year, department_code, fund_code) belong at the model level, not the base. This enables budget-vs-actual analysis via a single table:

```sql
-- Budget vs actual revenue: same table, same schema, filter by report_type
SELECT report_type, SUM(amount) as total
FROM _fact_financial_statements
WHERE legal_entity_id = ABS(HASH(CONCAT('CITY_', 'Chicago')))
  AND report_type IN ('annual', 'budget')
GROUP BY report_type;
```

### Python Measures (Inherited by ALL Accounting Templates)

| Measure | Description | Defined Here |
|---------|-------------|:---:|
| `net_present_value` | NPV of cash flows discounted to earliest date | **yes** |
| `spending_velocity` | Rolling 30/90/365-day spend rate with trend | **yes** |

These are the foundational financial measures. `ledger_entry` and `financial_statement` inherit them and override column params to match their schemas.

### Usage

```yaml
extends: _base.accounting.financial_event
```
