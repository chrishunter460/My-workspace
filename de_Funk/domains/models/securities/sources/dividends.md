---
type: domain-model-source
source: dividends
extends: _base.finance.corporate_action
maps_to: fact_dividends
from: bronze.alpha_vantage_dividends
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [dividend_id, "ABS(HASH(CONCAT(ticker, '_', CAST(ex_dividend_date AS STRING))))"]
  - [security_id, "ABS(HASH(ticker))"]
  - [ticker, ticker]
  - [action_type, "'DIVIDEND'"]
  - [effective_date, ex_dividend_date]
  - [effective_date_id, "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"]
  - [ex_dividend_date, ex_dividend_date]
  - [dividend_amount, dividend_amount]
  - [record_date, record_date]
  - [payment_date, payment_date]
  - [declaration_date, declaration_date]
  - [dividend_type, "'TBD'"]
---

## Dividends
Historical dividend payments including ex-date, payment date, and amount.
