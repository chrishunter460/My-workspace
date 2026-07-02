---
type: api-endpoint
provider: Chicago Data Portal
endpoint_id: fmps_payroll

# API Configuration
endpoint_pattern: /resource/{view_id}.json
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
required_params: [view_id]

# Pagination
pagination_type: offset
bulk_download: true
download_method: csv

# Metadata
domain: finance
legal_entity_type: municipal
subject_entity_tags: [municipal]
data_tags: [payroll, employees, compensation, annual]
status: active
update_cadence: annual
last_verified:
last_reviewed:
notes: "Employee payroll costing from FMPS. Biweekly pay periods (1-24). One row per employee per pay period per pay element."

# Storage Configuration
bronze: chicago
partitions: [payroll_year]
write_strategy: upsert
key_columns: [record_id]
date_column: null

# Schema
schema:
  - [record_id, string, record_id, false, "Composite key (employee + year + sequence)"]
  - [payroll_year, int, payroll_year, false, "Payroll year", {coerce: int}]
  - [payroll_period, int, payroll_period, false, "Biweekly pay period (1-24)", {coerce: int}]
  - [employee_dataset_id, string, employee_dataset_id, false, "Anonymized employee ID"]
  - [employee, string, employee, true, "Employee ID + name"]
  - [department_code, string, department_code, true, "Department code (e.g. D54)"]
  - [department, string, department, true, "Department code + name"]
  - [department_function, string, department_function, true, "Functional grouping"]
  - [fund_code, string, fund_code, true, "Fund code"]
  - [fund, string, fund, true, "Fund code + name"]
  - [fund_type, string, fund_type, true, "Fund type (e.g. CORPORATE FUND)"]
  - [appropriation_code, string, appropriation_code, true, "Appropriation account code (e.g. A0005)"]
  - [appropriation, string, appropriation, true, "Appropriation code + description"]
  - [title_code, string, title_code, true, "Job title code (e.g. T1405)"]
  - [title, string, title, true, "Job title code + description"]
  - [pay_element, string, pay_element, true, "Pay category (REGULAR SALARY, OVERTIME, etc.)"]
  - [amount, double, amount, true, "Pay amount for this period", {coerce: double}]
---

## Description

Employee Payroll Data from the Financial Management and Purchasing System (FMPS Payroll Costing). Each row represents one employee's pay for one pay element in one biweekly period. Covers regular salary, overtime, and other pay elements.

The `appropriation_code` field uses the same account codes as the budget appropriations dataset, enabling direct budget-vs-actual comparison.

## Available Years

| Year | view_id | Format | Notes |
|----|----|----|-----|
| 2023-present | dawh-m56b | JSON | Single dataset with payroll_year filter |

## Known Quirks

- `payroll_period` is biweekly (1-24), not monthly
- `employee` field combines anonymized ID + name (e.g. "C1081EDB5EEAE1 - TACCAD, CLARIBEL")
- Department and fund fields embed codes in display names (e.g. "D54 - Department of Planning and Development")
- Code-only fields (`department_code`, `fund_code`, `appropriation_code`, `title_code`) are cleaner for joining
