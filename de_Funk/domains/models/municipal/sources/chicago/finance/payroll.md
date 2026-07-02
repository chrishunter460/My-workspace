---
type: domain-model-source
source: fmps_payroll
extends: _base.accounting.ledger_entry
maps_to: fact_payroll
from: bronze.chicago_fmps_payroll
entry_type: PAYROLL
domain_source: "'chicago'"
aliases:
  # Standard ledger_entry fields
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [entry_id, "ABS(HASH(record_id))"]
  - [source_id, record_id]
  - [payee, employee]
  - [transaction_amount, "CAST(amount AS DOUBLE)"]
  # Derive transaction_date from payroll_year + payroll_period (biweekly: period N ≈ day N*15)
  - [transaction_date, "date_add(make_date(payroll_year, 1, 1), payroll_period * 15)"]
  - [date_id, "CAST(DATE_FORMAT(date_add(make_date(payroll_year, 1, 1), payroll_period * 15), 'yyyyMMdd') AS INT)"]
  - [organizational_unit, department]
  - [expense_category, pay_element]
  - [fund_code, fund_code]
  - [description, "CONCAT(pay_element, ' - ', title)"]
  # Account mapping — uses same appropriation codes as budget
  - [account_code, appropriation_code]
  - [account_id, "ABS(HASH(COALESCE(appropriation_code, 'UNCLASSIFIED')))"]
  # Payroll-specific columns
  - [title_code, title_code]
  - [title, title]
  - [pay_element, pay_element]
  - [payroll_year, "CAST(payroll_year AS INT)"]
  - [payroll_period, "CAST(payroll_period AS INT)"]
---

## Payroll Source

Chicago employee payroll costing from FMPS. Maps to `fact_ledger_entries` as `entry_type = 'PAYROLL'`.

### Temporal Mapping

Payroll periods are biweekly (1-24 per year). The `date_id` is derived by approximating the period end date: `year-01-01 + (period * 15 days)`. This places each pay period roughly in the correct half-month for calendar joins.

### Budget-vs-Actual

The `appropriation_code` field uses the same account codes as `budget_appropriations`, enabling:

```sql
-- Budget vs actual payroll by department
SELECT dept, 
  SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount END) as actual,
  SUM(CASE WHEN event_type = 'APPROPRIATION' THEN amount END) as budgeted
FROM (
  SELECT organizational_unit as dept, entry_type, null as event_type, transaction_amount as amount
  FROM fact_ledger_entries WHERE entry_type = 'PAYROLL'
  UNION ALL
  SELECT department_description, null, event_type, amount
  FROM fact_budget_events WHERE event_type = 'APPROPRIATION'
)
GROUP BY dept
```
