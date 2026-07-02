---
type: domain-model-source
source: earnings
extends: _base.corporate.earnings
maps_to: fact_earnings
from: bronze.alpha_vantage_earnings
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [earnings_id, "ABS(HASH(CONCAT(ticker, '_', CAST(reported_date AS STRING))))"]
  - [report_date_id, "CAST(REGEXP_REPLACE(CAST(reported_date AS STRING), '-', '') AS INT)"]
  - [fiscal_date_ending, fiscal_date_ending]
  - [reported_eps, reported_eps]
  - [estimated_eps, estimated_eps]
  - [surprise_eps, surprise]
  - [surprise_percentage, surprise_percentage]
---

## Earnings
Quarterly reported EPS, estimated EPS, and surprise metrics.
