---
title: Chart of Accounts — Corporate & Municipal
models: [corporate.finance, corporate.entity, municipal.finance]
filters:
  sector: {source: corporate.entity.sector, type: select, multi: false}
  ticker: {source: corporate.entity.ticker, type: select, multi: true, default: [AAPL, MSFT, GOOGL], context_filters: true}
  statement: {source: corporate.finance.statement_section, type: select, multi: false}
  year: {source: temporal.year, type: range, default: {from: 2005, to: 2025}}
  currency: {source: corporate.finance.reported_currency, type: select, multi: false}
controls:
  - id: budget-view
    dimensions: [municipal.finance.department_description, municipal.finance.account_description, municipal.finance.event_type]
---

# Chart of Accounts

Corporate financial statements (SEC/GAAP) and municipal budget data (Chicago/GASB) rendered as pivot tables with chart-of-accounts groupings.

---

## Income Statement — GAAP Summary by Sector

Standard presentation: rollup line items (Total Revenue → Net Income) by sector.

```de_funk
type: table.pivot
data:
  rows: corporate.finance.account_name
  cols: [temporal.year,corporate.entity.sector]
  measures:
    - [total_amount, corporate.finance.amount, sum, $B, Total]
  filters:
    - {field: corporate.finance.statement_section, op: eq, value: INCOME_STATEMENT}
    - {field: corporate.finance.report_type, op: eq, value: annual}
    - {field: corporate.finance.level, op: eq, value: 1}
  sort: {field: corporate.finance.display_order, dir: asc}
  layout: by_column
formatting:
  title: Income Statement — Standard (by Sector)
  format:
    total_amount: {format: $B, color: "#e3f2fd"}
  totals: {visible: true, color: "#bbdefb"}
```

---

## Balance Sheet — GAAP Summary by Sector

```de_funk
type: table.pivot
data:
  rows: corporate.finance.account_name
  cols: corporate.entity.sector
  measures:
    - [total_amount, corporate.finance.amount, sum, $, Balance]
  filters:
    - {field: corporate.finance.statement_section, op: eq, value: BALANCE_SHEET}
    - {field: corporate.finance.report_type, op: eq, value: annual}
    - {field: corporate.finance.level, op: eq, value: 1}
  sort: {field: corporate.finance.display_order, dir: asc}
formatting:
  title: Balance Sheet — Standard (by Sector)
  format:
    total_amount: {format: $B, color: "#e8f5e9"}
  totals: {visible: true, color: "#c8e6c9"}
```

---

## Cash Flow — GAAP Summary by Sector

```de_funk
type: table.pivot
data:
  rows: corporate.finance.account_name
  cols: corporate.entity.sector
  measures:
    - [total_amount, corporate.finance.amount, sum, $, Cash Flow]
  filters:
    - {field: corporate.finance.statement_section, op: eq, value: CASH_FLOW}
    - {field: corporate.finance.report_type, op: eq, value: annual}
    - {field: corporate.finance.level, op: eq, value: 1}
  sort: {field: corporate.finance.display_order, dir: asc}
formatting:
  title: Cash Flow — Standard (by Sector)
  format:
    total_amount: {format: $B, color: "#fff3e0"}
  totals: {visible: true, color: "#ffe0b2"}
```

---

## GAAP Category Breakdown

All accounts grouped by GAAP category across statement sections.

```de_funk
type: table.pivot
data:
  rows: corporate.finance.gaap_category
  cols: corporate.finance.statement_section
  measures:
    - [total_amount, corporate.finance.amount, sum, $B, Total]
    - [line_items, corporate.finance.statement_entry_id, count_distinct, number, Entries]
  filters:
    - {field: corporate.finance.report_type, op: eq, value: annual}
formatting:
  title: GAAP Category Summary — All Companies
  format:
    total_amount: {format: $B, color: "#f3e5f5"}
    line_items: {format: number, color: "#e0f2f1"}
```

---

## Income Statement — Detail by GAAP Category

Full account detail within each category, aggregated across all companies.

```de_funk
type: table.pivot
data:
  rows: corporate.finance.account_name
  cols: corporate.finance.gaap_category
  measures:
    - [total_amount, corporate.finance.amount, sum, $B, Total]
  filters:
    - {field: corporate.finance.statement_section, op: eq, value: INCOME_STATEMENT}
    - {field: corporate.finance.report_type, op: eq, value: annual}
  sort: {field: corporate.finance.display_order, dir: asc}
formatting:
  title: Income Statement — Detail by GAAP Category
  format:
    total_amount: {format: $B, color: "#e3f2fd"}
```

---

## Income Statement (Great Tables)

```de_funk
type: table.pivot
data:
  rows: corporate.finance.account_name
  cols: corporate.entity.sector
  measures:
    - [total_amount, corporate.finance.amount, sum, $B, Amount]
  filters:
    - {field: corporate.finance.statement_section, op: eq, value: INCOME_STATEMENT}
    - {field: corporate.finance.report_type, op: eq, value: annual}
    - {field: corporate.finance.level, op: eq, value: 1}
  sort: {field: corporate.finance.display_order, dir: asc}
formatting:
  title: Income Statement
  subtitle: Annual Filing Data — GAAP Standard Presentation
  format:
    total_amount: {format: $B, color: "#e3f2fd"}
  totals: {visible: true, color: "#1565c0", label: "Total"}
```

---

## Municipal — Appropriations by Department & Year

Total appropriations by department, pivoted by fiscal year.

```de_funk
type: table.pivot
data:
  rows: municipal.finance.department_description
  cols: municipal.finance.fiscal_year
  measures:
    - [total, municipal.finance.amount, sum, $, Appropriated]
  filters:
    - {field: municipal.finance.event_type, op: eq, value: APPROPRIATION}
formatting:
  title: Chicago Appropriations by Department & Year
  format:
    total: {format: $M, color: "#e8eaf6"}
  totals: {visible: true, color: "#c5cae9"}
  defaults: {max_row_width: "250px", max_col_width: "90px"}
```

---

## Municipal — Appropriations by Spending Category & Year

Broad spending categories (account descriptions) across fiscal years.

```de_funk
type: table.pivot
data:
  rows: municipal.finance.account_description
  cols: municipal.finance.fiscal_year
  measures:
    - [total, municipal.finance.amount, sum, $, Appropriated]
  filters:
    - {field: municipal.finance.event_type, op: eq, value: APPROPRIATION}
formatting:
  title: Appropriations by Spending Category & Year
  format:
    total: {format: $M, color: "#e3f2fd"}
  totals: {visible: true, color: "#bbdefb"}
  defaults: {max_row_width: "280px", max_col_width: "90px"}
```

---

## Municipal — Department × Category Breakdown

Department with spending category sub-grouping — appropriations only.

```de_funk
type: table.pivot
data:
  rows: municipal.finance.department_description
  cols: municipal.finance.event_type
  measures:
    - [total, municipal.finance.amount, sum, $, Total]
    - [line_items, municipal.finance.statement_entry_id, count_distinct, number, Items]
  filters:
    - {field: municipal.finance.event_type, op: eq, value: APPROPRIATION}
formatting:
  title: Department Budget Breakdown
  format:
    total: {format: $M, color: "#e8eaf6"}
    line_items: {format: number, color: "#e0f2f1"}
  totals: {visible: true, color: "#c5cae9"}
  defaults: {max_row_width: "250px"}
```

---

## Municipal — Budget KPI Cards

```de_funk
type: cards.metric
data:
  metrics:
    - [total_budget, municipal.finance.amount, sum, $B, Total Budget]
    - [line_items, municipal.finance.statement_entry_id, count_distinct, number, Line Items]
    - [accounts, municipal.finance.account_id, count_distinct, number, Accounts]
    - [departments, municipal.finance.department_code, count_distinct, number, Departments]
formatting:
  format:
    total_budget: $B
    line_items: number
    accounts: number
    departments: number
```

---

## Municipal — Configurable Budget Pivot

Use the **budget-view** control in the sidebar to switch the row dimension (Department, Spending Category, or Fund).

```de_funk
type: table.pivot
data:
  rows: municipal.finance.department_description
  cols: municipal.finance.fiscal_year
  measures:
    - [total, municipal.finance.amount, sum, $M, Appropriated]
  filters:
    - {field: municipal.finance.event_type, op: eq, value: APPROPRIATION}
  totals: {rows: true}
formatting:
  title: Budget Explorer
  subtitle: Select a dimension from the sidebar to change grouping
  format:
    total: {format: $M, color: "#e8eaf6"}
  totals: {visible: true, color: "#c5cae9"}
  defaults: {max_row_width: "280px", max_col_width: "90px"}
config:
  config_ref: budget-view
```
