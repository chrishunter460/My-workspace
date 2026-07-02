---
type: domain-model-source
source: balance_sheet
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_balance_sheet
transform: unpivot
domain_source: "'alpha_vantage'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [account_code, line_item_code]
  - [account_id, "ABS(HASH(line_item_code))"]
  - [statement_entry_id, "ABS(HASH(CONCAT(ticker, CAST(fiscal_date_ending AS STRING), line_item_code)))"]
  - [period_end_date_id, "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"]
  - [period_start_date_id, "CAST(DATE_FORMAT(fiscal_date_ending, 'yyyyMMdd') AS INT)"]
  - [report_type, report_type]
  - [amount, value]
  - [reported_currency, reported_currency]

unpivot_aliases:
  # Current Assets
  - [total_assets, TOTAL_ASSETS]
  - [total_current_assets, TOTAL_CURRENT_ASSETS]
  - [cash_and_equivalents, CASH_AND_EQUIVALENTS]
  - [cash_and_short_term_investments, CASH_AND_SHORT_TERM_INVESTMENTS]
  - [short_term_investments, SHORT_TERM_INVESTMENTS]
  - [current_net_receivables, CURRENT_NET_RECEIVABLES]
  - [inventory, INVENTORY]
  - [other_current_assets, OTHER_CURRENT_ASSETS]
  # Non-Current Assets
  - [total_non_current_assets, TOTAL_NON_CURRENT_ASSETS]
  - [property_plant_equipment, PROPERTY_PLANT_EQUIPMENT]
  - [accumulated_depreciation, ACCUMULATED_DEPRECIATION]
  - [goodwill, GOODWILL]
  - [intangible_assets, INTANGIBLE_ASSETS]
  - [intangible_assets_ex_goodwill, INTANGIBLE_ASSETS_EX_GOODWILL]
  - [long_term_investments, LONG_TERM_INVESTMENTS]
  - [investments, INVESTMENTS]
  - [other_non_current_assets, OTHER_NON_CURRENT_ASSETS]
  # Current Liabilities
  - [total_liabilities, TOTAL_LIABILITIES]
  - [total_current_liabilities, TOTAL_CURRENT_LIABILITIES]
  - [accounts_payable, ACCOUNTS_PAYABLE]
  - [current_debt, CURRENT_DEBT]
  - [short_term_debt, SHORT_TERM_DEBT]
  - [current_long_term_debt, CURRENT_LONG_TERM_DEBT]
  - [deferred_revenue, DEFERRED_REVENUE]
  - [other_current_liabilities, OTHER_CURRENT_LIABILITIES]
  # Non-Current Liabilities
  - [total_non_current_liabilities, TOTAL_NON_CURRENT_LIABILITIES]
  - [long_term_debt, LONG_TERM_DEBT]
  - [long_term_debt_noncurrent, LONG_TERM_DEBT_NONCURRENT]
  - [short_long_term_debt_total, SHORT_LONG_TERM_DEBT_TOTAL]
  - [capital_lease_obligations, CAPITAL_LEASE_OBLIGATIONS]
  - [other_non_current_liabilities, OTHER_NON_CURRENT_LIABILITIES]
  # Shareholders' Equity
  - [total_shareholder_equity, TOTAL_SHAREHOLDER_EQUITY]
  - [common_stock, COMMON_STOCK]
  - [retained_earnings, RETAINED_EARNINGS]
  - [treasury_stock, TREASURY_STOCK]
  - [shares_outstanding, SHARES_OUTSTANDING]
---

## Balance Sheet
Assets, liabilities, equity from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
