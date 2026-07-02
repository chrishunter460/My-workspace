---
title: Chart of Accounts Explorer
models:
  - corporate.finance
  - corporate.entity
  - municipal.finance
filters:
  sector:
    source: corporate.entity.sector
    type: select
    multi: false
  ticker:
    source: corporate.entity.ticker
    type: select
    multi: true
    default:
      - AAPL
      - MSFT
      - GOOGL
    context_filters: true
  year:
    source: temporal.year
    type: range
    default:
      from: 2010
      to: 2025
controls:
  - id: corporate-coa
    dimensions:
      - corporate.finance.account_name
      - corporate.finance.gaap_category
      - corporate.finance.statement_section
      - corporate.finance.account_type
      - corporate.entity.sector
      - corporate.entity.industry
    cols:
      - temporal.year
      - corporate.entity.sector
      - corporate.entity.ticker
      - corporate.finance.statement_section
      - corporate.finance.report_type
      - corporate.finance.reported_currency
    measures:
      - - corporate.finance.amount
        - $B
      - - corporate.finance.statement_entry_id
        - number
        - count_distinct
      - - corporate.entity.revenue_ttm
        - $B
      - - corporate.entity.eps
        - $2
    sort_order:
      - asc
      - desc
    current:
      sort_order: asc
      measures:
        - corporate.finance.amount
      dimensions:
        - corporate.finance.gaap_category
        - corporate.finance.account_type
  - id: municipal-coa
    dimensions:
      - municipal.finance.department_description
      - municipal.finance.account_description
      - municipal.finance.fund_description
      - municipal.finance.gasb_category
      - municipal.finance.event_type
      - municipal.finance.account_type
    cols:
      - temporal.year
      - municipal.finance.event_type
      - municipal.finance.fund_description
      - municipal.finance.department_description
    measures:
      - - municipal.finance.amount
        - $M
      - - municipal.finance.statement_entry_id
        - number
        - count_distinct
      - - municipal.finance.account_id
        - number
        - count_distinct
    sort_order:
      - asc
      - desc
    current:
      cols:
        - temporal.year
      dimensions:
        - municipal.finance.account_type
        - municipal.finance.department_description
---

# Chart of Accounts Explorer

Fully configurable pivot tables for corporate (SEC/GAAP) and municipal (Chicago/GASB) chart of accounts. Use the sidebar controls to swap rows, columns, and measures on the fly.

---

## Corporate Chart of Accounts

```de_funk
type: table.pivot
data:
  filters:
    - {field: corporate.finance.report_type, op: eq, value: annual}
    - {field: corporate.finance.level, op: eq, value: 1}
  sort: {field: corporate.finance.display_order, dir: asc}
  totals: {rows: true}
formatting:
  title: Corporate — GAAP Chart of Accounts
  subtitle: Select rows, columns, and measures from the sidebar
  totals: {visible: true, color: "#bbdefb"}
  defaults: {max_row_width: "280px", max_col_width: "100px"}
config:
  config_ref: corporate-coa
```

---

## Municipal Chart of Accounts

```de_funk
type: table.pivot
data:
  filters:
    - {field: municipal.finance.event_type, op: eq, value: APPROPRIATION}
  totals: {rows: true}
formatting:
  title: Municipal — GASB Chart of Accounts
  subtitle: Select rows, columns, and measures from the sidebar
  totals: {visible: true, color: "#c5cae9"}
  defaults: {max_row_width: "280px", max_col_width: "90px"}
config:
  config_ref: municipal-coa
```
