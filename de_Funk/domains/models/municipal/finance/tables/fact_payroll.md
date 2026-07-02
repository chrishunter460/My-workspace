---
type: domain-model-table
table: fact_payroll
extends: _base.accounting.ledger_source._ledger_source
table_type: fact
primary_key: [entry_id]
partition_by: [date_id]
persist: true

# Sources auto-discovered: any sources/*.md with maps_to: payroll

additional_schema:
  - [title_code, string, true, "Job title code (e.g. T1405)"]
  - [title, string, true, "Job title description (e.g. CITY PLANNER V)"]
  - [pay_element, string, true, "Pay category (REGULAR SALARY, OVERTIME, etc.)"]
  - [payroll_year, integer, true, "Payroll year"]
  - [payroll_period, integer, true, "Biweekly pay period (1-24)"]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]

measures:
  - [payroll_total, sum, transaction_amount, "Total payroll", {format: "$#,##0.00"}]
  - [payroll_count, count_distinct, entry_id, "Number of payroll entries", {format: "#,##0"}]
  - [employee_count, count_distinct, payee, "Unique employees", {format: "#,##0"}]
  - [title_count, count_distinct, title_code, "Unique job titles", {format: "#,##0"}]
---

## Payroll

Silver table for employee payroll transactions from FMPS. Extends the ledger source base with payroll-specific columns (`title_code`, `title`, `pay_element`, `payroll_year`, `payroll_period`). The `source_id` (record_id) is the natural key that links back from `fact_ledger_entries`.

### Title and Pay Element Linkage

Job title detail is reachable via: `fact_ledger_entries → payroll → dim_employee_title`
Pay element breakdown via: `fact_ledger_entries → payroll → dim_pay_element`
