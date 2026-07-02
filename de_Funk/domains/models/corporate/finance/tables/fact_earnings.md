---
type: domain-model-table
table: fact_earnings
table_type: fact
extends: _base.corporate.earnings._fact_earnings
primary_key: [earnings_id]
partition_by: [report_date_id]

schema:
  - [earnings_id, integer, false, "PK"]
  - [company_id, integer, false, "FK to dim_company", {fk: dim_company.company_id}]
  - [report_date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
  - [fiscal_date_ending, date, true, "Fiscal period end"]
  - [reported_eps, double, true, "Reported EPS"]
  - [estimated_eps, double, true, "Estimated EPS"]
  - [surprise_eps, double, true, "EPS surprise"]
  - [surprise_percentage, double, true, "Surprise %"]

measures:
  - [avg_eps, avg, reported_eps, "Average EPS", {format: "$#,##0.00"}]
  - [avg_surprise_pct, avg, surprise_percentage, "Avg surprise %", {format: "#,##0.00%"}]
---

## Earnings Fact Table

Quarterly earnings reports and EPS data.
