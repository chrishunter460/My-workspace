---
type: domain-model-table
table: dim_employee_title
table_type: dimension
primary_key: [title_code]
transform: distinct
from: fact_payroll
group_by: [title_code, title]

schema:
  - [title_code, string, false, "Job title code (e.g. T1405)"]
  - [title, string, true, "Job title description"]

measures:
  - [title_count, count_distinct, title_code, "Number of job titles", {format: "#,##0"}]
---

## Employee Title Dimension

Distinct job titles extracted from the payroll silver table. Each `title_code` maps to a human-readable title description.
