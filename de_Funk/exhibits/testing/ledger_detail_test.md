---
title: Ledger Detail Test
models: [municipal.finance]
filters:
  department:
    source: municipal.finance.organizational_unit
    type: select
    multi: true
    default: [D57 - Chicago Police Department, CHICAGO POLICE DEPARTMENT]
  year:
    source: temporal.year
    type: range
    default: {from: 2023, to: 2025}
---

# Ledger Detail Test

Combined payroll + payments in one tree with NULL auto-collapse. Payroll expands: department → entry type → job title (via dim_employee_title). Payments expand: department → entry type → contract description (via dim_contract). NULL levels auto-collapse: payments skip title, payroll skips contract_description. Filtered to Chicago Police Department (both naming variants) to demonstrate the disjoint multi-hop join.

```de_funk
type: table.pivot
data:
  rows:
    - municipal.finance.organizational_unit
    - municipal.finance.entry_type
    - municipal.finance.title
    - municipal.finance.contract_description
  cols: temporal.year
  measures:
    - [total, municipal.finance.transaction_amount, sum, $M, Amount]
  filters:
    - {field: municipal.finance.organizational_unit, op: in, value: [D57 - Chicago Police Department, CHICAGO POLICE DEPARTMENT]}
  totals: {rows: true}
formatting:
  title: Full Ledger — Chicago Police (Payroll + Payments)
```
