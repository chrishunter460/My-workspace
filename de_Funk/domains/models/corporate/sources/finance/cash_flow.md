---
type: domain-model-source
source: cash_flow
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_cash_flow
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
  # Operating Activities
  - [operating_cashflow, OPERATING_CASHFLOW]
  - [profit_loss, PROFIT_LOSS]
  - [depreciation_depletion_amortization, DEPRECIATION_DEPLETION_AMORTIZATION]
  - [change_in_operating_assets, CHANGE_IN_OPERATING_ASSETS]
  - [change_in_operating_liabilities, CHANGE_IN_OPERATING_LIABILITIES]
  - [change_in_receivables, CHANGE_IN_RECEIVABLES]
  - [change_in_inventory, CHANGE_IN_INVENTORY]
  - [payments_for_operating_activities, PAYMENTS_FOR_OPERATING_ACTIVITIES]
  - [proceeds_from_operating_activities, PROCEEDS_FROM_OPERATING_ACTIVITIES]
  # Investing Activities
  - [cashflow_from_investment, CASHFLOW_FROM_INVESTMENT]
  - [capital_expenditures, CAPITAL_EXPENDITURES]
  # Financing Activities
  - [cashflow_from_financing, CASHFLOW_FROM_FINANCING]
  - [dividend_payout, DIVIDEND_PAYOUT]
  - [dividend_payout_common, DIVIDEND_PAYOUT_COMMON]
  - [dividend_payout_preferred, DIVIDEND_PAYOUT_PREFERRED]
  - [proceeds_from_common_stock, PROCEEDS_FROM_COMMON_STOCK]
  - [proceeds_from_preferred_stock, PROCEEDS_FROM_PREFERRED_STOCK]
  - [proceeds_from_treasury_stock, PROCEEDS_FROM_TREASURY_STOCK]
  - [payments_for_repurchase_common, PAYMENTS_FOR_REPURCHASE_COMMON]
  - [payments_for_repurchase_preferred, PAYMENTS_FOR_REPURCHASE_PREFERRED]
  - [payments_for_repurchase_equity, PAYMENTS_FOR_REPURCHASE_EQUITY]
  - [proceeds_from_repurchase_equity, PROCEEDS_FROM_REPURCHASE_EQUITY]
  - [proceeds_from_long_term_debt, PROCEEDS_FROM_LONG_TERM_DEBT]
  - [proceeds_from_short_term_debt, PROCEEDS_FROM_SHORT_TERM_DEBT]
  # Net Cash Change
  - [change_in_exchange_rate, CHANGE_IN_EXCHANGE_RATE]
  - [net_change_in_cash, NET_CHANGE_IN_CASH]
  - [net_income, NET_INCOME]
---

## Cash Flow
Operating, investing, and financing cash flows from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
