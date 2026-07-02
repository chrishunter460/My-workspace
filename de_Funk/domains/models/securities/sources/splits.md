---
type: domain-model-source
source: splits
extends: _base.finance.corporate_action
maps_to: fact_splits
from: bronze.alpha_vantage_splits
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [split_id, "ABS(HASH(CONCAT(ticker, '_', CAST(effective_date AS STRING))))"]
  - [security_id, "ABS(HASH(ticker))"]
  - [ticker, ticker]
  - [action_type, "'SPLIT'"]
  - [effective_date, effective_date]
  - [effective_date_id, "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"]
  - [split_factor, split_factor]
---

## Splits
Historical stock splits with effective date and split ratio.
