---
type: domain-model-source
source: budget_positions
extends: _base.accounting.financial_statement
maps_to: fact_budget_events
from: bronze.chicago_budget_positions_salaries
event_type: POSITION
domain_source: "'chicago'"
aliases:
  # Maps to financial_statement base schema
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [statement_entry_id, "ABS(HASH(CONCAT('POSITION', '_', CAST(year AS INT), '_', COALESCE(department_code,''), '_', COALESCE(title_code,''))))"]
  - [account_id, "ABS(HASH(COALESCE(title_code, 'UNCLASSIFIED')))"]
  - [period_end_date_id, "CAST(CONCAT(CAST(CAST(year AS INT) AS STRING), '1231') AS INT)"]
  - [period_start_date_id, "CAST(CONCAT(CAST(CAST(year AS INT) AS STRING), '0101') AS INT)"]
  - [report_type, "'budget'"]
  - [amount, "CAST(amount AS DOUBLE)"]
  - [reported_currency, "'USD'"]
  # Budget-specific (model-level additional_schema)
  - [fiscal_year, "CAST(year AS INT)"]
  - [department_code, department_code]
  - [department_description, department_description]
  - [fund_code, "null"]
  - [fund_description, "null"]
  - [account_code, title_code]
  - [account_description, title_description]
  - [description, "CONCAT(title_description, ' (', budgeted_unit, ' units)')"]
---

## Budget Positions Source

Annual budgeted employee positions with title and salary allocation. Maps to `fact_budget_events` which extends the financial_statement base with `report_type = 'budget'`.
