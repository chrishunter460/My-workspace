---
type: domain-model
model: municipal.finance
version: 4.0
description: "Municipal payments, payroll, contracts, and budget data"

extends:
  - _base.accounting.ledger_entry
  - _base.accounting.ledger_source
  - _base.accounting.financial_statement
  - _base.accounting.fund
  - _base.accounting.chart_of_accounts

depends_on: [temporal, municipal.entity]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/finance/

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]

    # Ledger → source tables (via source_id natural key)
    - [ledger_to_payments, fact_ledger_entries, fact_payments, [source_id=source_id], many_to_one, null]
    - [ledger_to_payroll, fact_ledger_entries, fact_payroll, [source_id=source_id], many_to_one, null]

    # Ledger → calendar (cross-model)
    - [entry_to_calendar, fact_ledger_entries, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

    # Ledger → dimensions (direct FK)
    - [entry_to_vendor, fact_ledger_entries, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [entry_to_department, fact_ledger_entries, dim_department, [department_id=org_unit_id], many_to_one, null]
    - [entry_to_account, fact_ledger_entries, dim_chart_of_accounts, [account_id=account_id], many_to_one, null]
    - [entry_to_contract, fact_ledger_entries, dim_contract, [contract_number=contract_number], many_to_one, null]

    # Source → source-specific dimensions (multi-hop from ledger)
    - [payment_to_contract, fact_payments, dim_contract, [contract_number=contract_number], many_to_one, null]
    - [payroll_to_title, fact_payroll, dim_employee_title, [title_code=title_code], many_to_one, null]
    - [payroll_to_pay_element, fact_payroll, dim_pay_element, [pay_element=pay_element], many_to_one, null]

    # Budget → dimensions
    - [budget_to_calendar, fact_budget_events, temporal.dim_calendar, [period_end_date_id=date_id], many_to_one, temporal]
    - [budget_to_department, fact_budget_events, dim_department, [department_description=org_unit_code], many_to_one, null]
    - [budget_to_fund, fact_budget_events, dim_fund, [fund_code=fund_code], many_to_one, null]
    - [budget_to_account, fact_budget_events, dim_chart_of_accounts, [account_id=account_id], many_to_one, null]

    # Entity → municipality (cross-model)
    - [entry_to_municipality, fact_ledger_entries, municipal.entity.dim_municipality, [legal_entity_id=municipality_id], many_to_one, municipal.entity]
    - [budget_to_municipality, fact_budget_events, municipal.entity.dim_municipality, [legal_entity_id=municipality_id], many_to_one, municipal.entity]

    # Dimension → dimension
    - [contract_to_vendor, dim_contract, dim_vendor, [vendor_id=vendor_id], many_to_one, null]
    - [contract_to_department, dim_contract, dim_department, [department_id=org_unit_id], many_to_one, null]

  paths:
    payment_contract_detail:
      description: "Ledger → payment source → contract"
      steps:
        - {from: fact_ledger_entries, to: payments, via: source_id}
        - {from: payments, to: dim_contract, via: contract_number}
    payroll_title_detail:
      description: "Ledger → payroll source → job title"
      steps:
        - {from: fact_ledger_entries, to: payroll, via: source_id}
        - {from: payroll, to: dim_employee_title, via: title_code}
    budget_to_account_fund:
      description: "Budget line item → account classification + fund"
      steps:
        - {from: fact_budget_events, to: dim_chart_of_accounts, via: account_id}
        - {from: fact_budget_events, to: dim_fund, via: fund_id}

build:
  partitions: [date_id]
  optimize: true
  phases:
    1:
      description: "Silver source tables from bronze"
      tables: [fact_payments, fact_payroll]
      persist: true
    2:
      description: "Fact tables from silver intermediates"
      tables: [fact_ledger_entries, fact_budget_events]
      persist: true
    3:
      description: "Dimensions from facts, source tables, and bronze"
      tables: [dim_employee_title, dim_pay_element, dim_vendor, dim_department, dim_contract, dim_fund, dim_chart_of_accounts]
      persist: true

measures:
  simple:
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payment amount", {format: "$#,##0.00"}]
    - [payment_count, count_distinct, fact_ledger_entries.entry_id, "Number of entries", {format: "#,##0"}]
    - [vendor_count, count_distinct, dim_vendor.vendor_id, "Unique vendors", {format: "#,##0"}]
    - [avg_payment, avg, fact_ledger_entries.transaction_amount, "Average payment", {format: "$#,##0.00"}]
    - [total_budget, sum, fact_budget_events.amount, "Total budget amount", {format: "$#,##0.00"}]
    - [budget_line_count, count_distinct, fact_budget_events.statement_entry_id, "Budget line items", {format: "#,##0"}]
    - [department_count, count_distinct, dim_department.org_unit_id, "City departments", {format: "#,##0"}]
    - [contract_count, count_distinct, dim_contract.contract_id, "Total contracts", {format: "#,##0"}]
    - [employee_count, count_distinct, payroll.payee, "Unique employees", {format: "#,##0"}]
    - [title_count, count_distinct, dim_employee_title.title_code, "Unique job titles", {format: "#,##0"}]

  computed:
    - [payments_per_vendor, expression, "SUM(fact_ledger_entries.transaction_amount) / NULLIF(COUNT(DISTINCT dim_vendor.vendor_id), 0)", "Average payments per vendor", {format: "$#,##0.00"}]
    - [budget_surplus, expression, "SUM(CASE WHEN fact_budget_events.event_type = 'REVENUE' THEN fact_budget_events.amount ELSE 0 END) - SUM(CASE WHEN fact_budget_events.event_type = 'APPROPRIATION' THEN fact_budget_events.amount ELSE 0 END)", "Revenue minus appropriations", {format: "$#,##0.00"}]
    - [vendor_payment_pct, expression, "SUM(CASE WHEN fact_ledger_entries.entry_type = 'VENDOR_PAYMENT' THEN fact_ledger_entries.transaction_amount ELSE 0 END) / NULLIF(SUM(fact_ledger_entries.transaction_amount), 0)", "Vendor payments as % of total", {format: "0.00%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: finance
status: active
---

## Municipal Finance Model

Payments, payroll, contracts, and budget data for City of Chicago.

### Architecture

```
sources/                        tables/
  payments.md ──→ fact_payments ─────────────┐
                  (contract_number,          ├→ fact_ledger_entries ──→ dim_vendor
                   voucher_number)           │  (canonical cols only)  ──→ dim_department
                                             │                         ──→ dim_chart_of_accounts
  payroll.md ───→ payroll ──────────────────┘
                  (title_code, title,             ──→ dim_employee_title
                   pay_element)                   ──→ dim_pay_element

  contracts.md ──→ dim_contract (from bronze)

  budget_*.md ───→ fact_budget_events ──→ dim_fund
```

### Source Detail via Graph

Source-specific detail is reachable through multi-hop joins:
- `fact_ledger_entries → fact_payments → dim_contract` (via source_id)
- `fact_ledger_entries → payroll → dim_employee_title` (via source_id)
- `fact_ledger_entries → payroll → dim_pay_element` (via source_id)
