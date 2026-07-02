---
type: domain-model-source
source: income_statement
extends: _base.accounting.financial_statement
maps_to: fact_financial_statements
from: bronze.alpha_vantage_income_statement
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
  # Revenue
  - [total_revenue, TOTAL_REVENUE]
  - [non_interest_income, NON_INTEREST_INCOME]
  - [net_interest_income, NET_INTEREST_INCOME]
  - [interest_income, INTEREST_INCOME]
  - [investment_income_net, INVESTMENT_INCOME_NET]
  - [other_non_operating_income, OTHER_NON_OPERATING_INCOME]
  # Cost of Revenue
  - [cost_of_revenue, COST_OF_REVENUE]
  - [cost_of_goods_sold, COST_OF_GOODS_SOLD]
  # Gross Profit
  - [gross_profit, GROSS_PROFIT]
  # Operating Expenses
  - [operating_expenses, OPERATING_EXPENSES]
  - [sg_and_a, SG_AND_A]
  - [research_and_development, RESEARCH_AND_DEVELOPMENT]
  - [depreciation, DEPRECIATION]
  - [depreciation_and_amortization, DEPRECIATION_AND_AMORTIZATION]
  # Operating Income
  - [operating_income, OPERATING_INCOME]
  # Non-Operating Items
  - [interest_expense, INTEREST_EXPENSE]
  - [interest_and_debt_expense, INTEREST_AND_DEBT_EXPENSE]
  # Pre-Tax Income
  - [income_before_tax, INCOME_BEFORE_TAX]
  - [income_tax_expense, INCOME_TAX_EXPENSE]
  # Net Income & Subtotals
  - [net_income_from_continuing_ops, NET_INCOME_FROM_CONTINUING_OPS]
  - [comprehensive_income, COMPREHENSIVE_INCOME]
  - [ebit, EBIT]
  - [ebitda, EBITDA]
  - [net_income, NET_INCOME]
---

## Income Statement
Revenue, expenses, profit metrics from annual and quarterly SEC filings. Unpivoted into row-per-line-item for fact_financial_statements.
