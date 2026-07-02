---
type: domain-model-table
table: dim_pay_element
table_type: dimension
primary_key: [pay_element]
transform: distinct
from: fact_payroll
group_by: [pay_element]

schema:
  - [pay_element, string, false, "Pay category (REGULAR SALARY, OVERTIME, etc.)"]

measures:
  - [pay_element_count, count_distinct, pay_element, "Number of pay categories", {format: "#,##0"}]
---

## Pay Element Dimension

Distinct pay categories extracted from the payroll silver table. Small cardinality (~20 values): REGULAR SALARY, OVERTIME, HOLIDAY PAY, etc.
