---
type: domain-model-source
source: budget_revenue
extends: _base.accounting.financial_statement
maps_to: fact_budget_events
from: bronze.chicago_budget_revenue
event_type: REVENUE
domain_source: "'chicago'"
aliases:
  # Maps to financial_statement base schema
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [statement_entry_id, "ABS(HASH(CONCAT('REVENUE', '_', CAST(year AS INT), '_', '', '_', COALESCE(revenue_source,''))))"]
  - [account_id, "ABS(HASH(COALESCE(revenue_source, 'UNCLASSIFIED')))"]
  - [period_end_date_id, "CAST(CONCAT(CAST(CAST(year AS INT) AS STRING), '1231') AS INT)"]
  - [period_start_date_id, "CAST(CONCAT(CAST(CAST(year AS INT) AS STRING), '0101') AS INT)"]
  - [report_type, "'budget'"]
  - [amount, "CAST(amount AS DOUBLE)"]
  - [reported_currency, "'USD'"]
  # Budget-specific (model-level additional_schema)
  - [fiscal_year, "CAST(year AS INT)"]
  - [department_code, department_number]
  - [department_description, department_description]
  - [fund_code, fund_code]
  - [fund_description, fund_description]
  - [account_code, revenue_source]
  - [account_description, revenue_source]
  - [description, "null"]
---

## Budget Revenue Source

Annual revenue estimates by fund and revenue source. Maps to `fact_budget_events` which extends the financial_statement base with `report_type = 'budget'`.
