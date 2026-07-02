---
type: domain-model-table
table: fact_ledger_entries
extends: _base.accounting.ledger_entry._fact_ledger_entries
table_type: fact
primary_key: [entry_id]
partition_by: [date_id]
persist: true

# Union from silver source tables (not bronze)
# These are built in phase 1, fact_ledger_entries in phase 2
union_from: [fact_payments, fact_payroll]

# Canonical ledger columns (from base template, listed for resolver indexing)
schema:
  - [entry_id, integer, false, "PK"]
  - [legal_entity_id, integer, true, "FK to entity"]
  - [date_id, integer, false, "FK to calendar"]
  - [entry_type, string, false, "VENDOR_PAYMENT or PAYROLL"]
  - [domain_source, string, false, "Origin domain"]
  - [source_id, string, false, "Original source ID — key back to source table"]
  - [payee, string, false, "Who received payment"]
  - [transaction_amount, double, false, "Amount"]
  - [transaction_date, date, false, "Transaction date"]
  - [organizational_unit, string, true, "Department"]
  - [expense_category, string, true, "Classification"]
  - [fund_code, string, true, "Fund code"]
  - [description, string, true, "Transaction description"]

additional_schema:
  - [vendor_id, integer, true, "FK to dim_vendor", {fk: dim_vendor.vendor_id, derived: "ABS(HASH(COALESCE(payee, 'UNKNOWN')))"}]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]
  - [account_code, string, true, "Account code for chart of accounts"]
  - [account_id, integer, true, "FK to dim_chart_of_accounts", {fk: dim_chart_of_accounts.account_id}]
---

## Ledger Entries Fact

Union of `payments` and `payroll` silver tables. Contains only canonical ledger columns — no source-specific fields.

### Entry Types

| entry_type | Source Table | payee | expense_category |
|-----------|-------------|-------|-----------------|
| VENDOR_PAYMENT | payments | vendor name | procurement type |
| PAYROLL | payroll | employee name | pay element |

### Source Detail via Graph

Source-specific detail is reachable through multi-hop joins using `source_id`:
- Contract info: `fact_ledger_entries → payments → dim_contract`
- Job title: `fact_ledger_entries → payroll → dim_employee_title`
- Pay element: `fact_ledger_entries → payroll → dim_pay_element`
