---
type: domain-model-table
table: dim_financial_account
extends: _base.accounting.chart_of_accounts._dim_chart_of_accounts
table_type: dimension
static: true
primary_key: [account_id]
unique_key: [account_code]

# [column, type, nullable, description, {options}]
schema:
  - [account_id, integer, false, "PK", {derived: "ABS(HASH(account_code))"}]
  - [account_code, string, false, "Line item code (e.g., TOTAL_REVENUE)"]
  - [account_name, string, false, "Display name"]
  - [account_type, string, false, "Classification", {enum: [ASSET, LIABILITY, REVENUE, EXPENSE, EQUITY, CASH_FLOW]}]
  - [account_subtype, string, true, "Sub-classification (current, non_current, operating)"]
  - [parent_account_id, integer, true, "Hierarchy parent", {fk: dim_financial_account.account_id}]
  - [level, integer, true, "Hierarchy depth"]
  - [statement_section, string, false, "Financial statement", {enum: [BALANCE_SHEET, INCOME_STATEMENT, CASH_FLOW]}]
  - [gaap_category, string, true, "GAAP classification grouping"]
  - [cash_flow_category, string, true, "Cash flow bucket", {enum: [OPERATING, INVESTING, FINANCING]}]
  - [normal_balance, string, true, "Balance direction", {enum: [DEBIT, CREDIT]}]
  - [is_contra, boolean, true, "Contra account flag", {default: false}]
  - [is_rollup, boolean, true, "Summary/rollup account", {default: false}]
  - [format_type, string, true, "Display format", {enum: [CURRENCY, PERCENTAGE, RATIO, INTEGER], default: "CURRENCY"}]
  - [display_order, integer, true, "Sort order within statement"]

data:
  # ═══════════════════════════════════════════════════════════════════
  # INCOME STATEMENT — GAAP Presentation Order (ASC 220)
  # ═══════════════════════════════════════════════════════════════════

  # ── Revenue ──
  - {account_code: TOTAL_REVENUE, account_name: "Total Revenue", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 100}
  - {account_code: NON_INTEREST_INCOME, account_name: "Non-Interest Income", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 101}
  - {account_code: NET_INTEREST_INCOME, account_name: "Net Interest Income", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 102}
  - {account_code: INTEREST_INCOME, account_name: "Interest Income", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 103}
  - {account_code: INVESTMENT_INCOME_NET, account_name: "Investment Income (Net)", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 104}
  - {account_code: OTHER_NON_OPERATING_INCOME, account_name: "Other Non-Operating Income", account_type: REVENUE, gaap_category: "Revenue", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 105}

  # ── Cost of Revenue ──
  - {account_code: COST_OF_REVENUE, account_name: "Cost of Revenue", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Cost of Goods Sold", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 200}
  - {account_code: COST_OF_GOODS_SOLD, account_name: "Cost of Goods Sold", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Cost of Goods Sold", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 201}

  # ── Gross Profit ──
  - {account_code: GROSS_PROFIT, account_name: "Gross Profit", account_type: REVENUE, gaap_category: "Gross Profit", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 300}

  # ── Operating Expenses ──
  - {account_code: OPERATING_EXPENSES, account_name: "Operating Expenses", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Operating Expenses", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 400}
  - {account_code: SG_AND_A, account_name: "Selling, General & Administrative", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Operating Expenses", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 401}
  - {account_code: RESEARCH_AND_DEVELOPMENT, account_name: "Research & Development", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Operating Expenses", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 402}
  - {account_code: DEPRECIATION, account_name: "Depreciation", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Operating Expenses", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 403}
  - {account_code: DEPRECIATION_AND_AMORTIZATION, account_name: "Depreciation & Amortization", account_type: EXPENSE, account_subtype: OPERATING, gaap_category: "Operating Expenses", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 404}

  # ── Operating Income ──
  - {account_code: OPERATING_INCOME, account_name: "Operating Income", account_type: REVENUE, account_subtype: OPERATING, gaap_category: "Operating Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 500}

  # ── Non-Operating Items ──
  - {account_code: INTEREST_EXPENSE, account_name: "Interest Expense", account_type: EXPENSE, account_subtype: NON_OPERATING, gaap_category: "Non-Operating Items", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 600}
  - {account_code: INTEREST_AND_DEBT_EXPENSE, account_name: "Interest & Debt Expense", account_type: EXPENSE, account_subtype: NON_OPERATING, gaap_category: "Non-Operating Items", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 601}

  # ── Pre-Tax Income ──
  - {account_code: INCOME_BEFORE_TAX, account_name: "Income Before Tax", account_type: REVENUE, gaap_category: "Pre-Tax Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 700}
  - {account_code: INCOME_TAX_EXPENSE, account_name: "Income Tax Expense", account_type: EXPENSE, account_subtype: TAX, gaap_category: "Pre-Tax Income", statement_section: INCOME_STATEMENT, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 701}

  # ── Net Income & Subtotals ──
  - {account_code: NET_INCOME_FROM_CONTINUING_OPS, account_name: "Net Income from Continuing Operations", account_type: REVENUE, gaap_category: "Net Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 800}
  - {account_code: COMPREHENSIVE_INCOME, account_name: "Comprehensive Income", account_type: REVENUE, gaap_category: "Net Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 810}
  - {account_code: EBIT, account_name: "EBIT", account_type: REVENUE, gaap_category: "Net Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 820}
  - {account_code: EBITDA, account_name: "EBITDA", account_type: REVENUE, gaap_category: "Net Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 830}
  - {account_code: NET_INCOME, account_name: "Net Income", account_type: REVENUE, gaap_category: "Net Income", statement_section: INCOME_STATEMENT, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 900}

  # ═══════════════════════════════════════════════════════════════════
  # BALANCE SHEET — GAAP Presentation Order (ASC 210)
  # ═══════════════════════════════════════════════════════════════════

  # ── Current Assets ──
  - {account_code: TOTAL_ASSETS, account_name: "Total Assets", account_type: ASSET, gaap_category: "Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 1000}
  - {account_code: TOTAL_CURRENT_ASSETS, account_name: "Total Current Assets", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 1100}
  - {account_code: CASH_AND_EQUIVALENTS, account_name: "Cash and Equivalents", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1101}
  - {account_code: CASH_AND_SHORT_TERM_INVESTMENTS, account_name: "Cash & Short-Term Investments", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1102}
  - {account_code: SHORT_TERM_INVESTMENTS, account_name: "Short-Term Investments", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1103}
  - {account_code: CURRENT_NET_RECEIVABLES, account_name: "Accounts Receivable (Net)", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1104}
  - {account_code: INVENTORY, account_name: "Inventory", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1105}
  - {account_code: OTHER_CURRENT_ASSETS, account_name: "Other Current Assets", account_type: ASSET, account_subtype: CURRENT, gaap_category: "Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1106}

  # ── Non-Current Assets ──
  - {account_code: TOTAL_NON_CURRENT_ASSETS, account_name: "Total Non-Current Assets", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 1200}
  - {account_code: PROPERTY_PLANT_EQUIPMENT, account_name: "Property, Plant & Equipment", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1201}
  - {account_code: ACCUMULATED_DEPRECIATION, account_name: "Accumulated Depreciation", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_contra: true, format_type: CURRENCY, level: 3, display_order: 1202}
  - {account_code: GOODWILL, account_name: "Goodwill", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1203}
  - {account_code: INTANGIBLE_ASSETS, account_name: "Intangible Assets", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1204}
  - {account_code: INTANGIBLE_ASSETS_EX_GOODWILL, account_name: "Intangible Assets (Ex-Goodwill)", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1205}
  - {account_code: LONG_TERM_INVESTMENTS, account_name: "Long-Term Investments", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1206}
  - {account_code: INVESTMENTS, account_name: "Investments", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1207}
  - {account_code: OTHER_NON_CURRENT_ASSETS, account_name: "Other Non-Current Assets", account_type: ASSET, account_subtype: NON_CURRENT, gaap_category: "Non-Current Assets", statement_section: BALANCE_SHEET, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 1208}

  # ── Current Liabilities ──
  - {account_code: TOTAL_LIABILITIES, account_name: "Total Liabilities", account_type: LIABILITY, gaap_category: "Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 2000}
  - {account_code: TOTAL_CURRENT_LIABILITIES, account_name: "Total Current Liabilities", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 2100}
  - {account_code: ACCOUNTS_PAYABLE, account_name: "Accounts Payable", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2101}
  - {account_code: CURRENT_DEBT, account_name: "Current Portion of Debt", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2102}
  - {account_code: SHORT_TERM_DEBT, account_name: "Short-Term Debt", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2103}
  - {account_code: CURRENT_LONG_TERM_DEBT, account_name: "Current Long-Term Debt", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2104}
  - {account_code: DEFERRED_REVENUE, account_name: "Deferred Revenue", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2105}
  - {account_code: OTHER_CURRENT_LIABILITIES, account_name: "Other Current Liabilities", account_type: LIABILITY, account_subtype: CURRENT, gaap_category: "Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2106}

  # ── Non-Current Liabilities ──
  - {account_code: TOTAL_NON_CURRENT_LIABILITIES, account_name: "Total Non-Current Liabilities", account_type: LIABILITY, account_subtype: NON_CURRENT, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 2200}
  - {account_code: LONG_TERM_DEBT, account_name: "Long-Term Debt", account_type: LIABILITY, account_subtype: NON_CURRENT, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2201}
  - {account_code: LONG_TERM_DEBT_NONCURRENT, account_name: "Long-Term Debt (Non-Current)", account_type: LIABILITY, account_subtype: NON_CURRENT, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2202}
  - {account_code: SHORT_LONG_TERM_DEBT_TOTAL, account_name: "Total Debt (Short + Long)", account_type: LIABILITY, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 2, display_order: 2203}
  - {account_code: CAPITAL_LEASE_OBLIGATIONS, account_name: "Capital Lease Obligations", account_type: LIABILITY, account_subtype: NON_CURRENT, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2204}
  - {account_code: OTHER_NON_CURRENT_LIABILITIES, account_name: "Other Non-Current Liabilities", account_type: LIABILITY, account_subtype: NON_CURRENT, gaap_category: "Non-Current Liabilities", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 3, display_order: 2205}

  # ── Shareholders' Equity ──
  - {account_code: TOTAL_SHAREHOLDER_EQUITY, account_name: "Total Shareholder Equity", account_type: EQUITY, gaap_category: "Shareholders' Equity", statement_section: BALANCE_SHEET, normal_balance: CREDIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 3000}
  - {account_code: COMMON_STOCK, account_name: "Common Stock", account_type: EQUITY, gaap_category: "Shareholders' Equity", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 3001}
  - {account_code: RETAINED_EARNINGS, account_name: "Retained Earnings", account_type: EQUITY, gaap_category: "Shareholders' Equity", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: CURRENCY, level: 2, display_order: 3002}
  - {account_code: TREASURY_STOCK, account_name: "Treasury Stock", account_type: EQUITY, gaap_category: "Shareholders' Equity", statement_section: BALANCE_SHEET, normal_balance: DEBIT, is_contra: true, format_type: CURRENCY, level: 2, display_order: 3003}
  - {account_code: SHARES_OUTSTANDING, account_name: "Shares Outstanding", account_type: EQUITY, gaap_category: "Shareholders' Equity", statement_section: BALANCE_SHEET, normal_balance: CREDIT, format_type: INTEGER, level: 2, display_order: 3004}

  # ═══════════════════════════════════════════════════════════════════
  # CASH FLOW STATEMENT — GAAP Presentation Order (ASC 230)
  # ═══════════════════════════════════════════════════════════════════

  # ── Operating Activities ──
  - {account_code: OPERATING_CASHFLOW, account_name: "Cash from Operations", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 4000}
  - {account_code: PROFIT_LOSS, account_name: "Profit / Loss", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4001}
  - {account_code: DEPRECIATION_DEPLETION_AMORTIZATION, account_name: "Depreciation, Depletion & Amortization", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4002}
  - {account_code: CHANGE_IN_OPERATING_ASSETS, account_name: "Change in Operating Assets", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4003}
  - {account_code: CHANGE_IN_OPERATING_LIABILITIES, account_name: "Change in Operating Liabilities", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4004}
  - {account_code: CHANGE_IN_RECEIVABLES, account_name: "Change in Receivables", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4005}
  - {account_code: CHANGE_IN_INVENTORY, account_name: "Change in Inventory", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4006}
  - {account_code: PAYMENTS_FOR_OPERATING_ACTIVITIES, account_name: "Payments for Operating Activities", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4007}
  - {account_code: PROCEEDS_FROM_OPERATING_ACTIVITIES, account_name: "Proceeds from Operating Activities", account_type: CASH_FLOW, gaap_category: "Operating Activities", statement_section: CASH_FLOW, cash_flow_category: OPERATING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 4008}

  # ── Investing Activities ──
  - {account_code: CASHFLOW_FROM_INVESTMENT, account_name: "Cash from Investing", account_type: CASH_FLOW, gaap_category: "Investing Activities", statement_section: CASH_FLOW, cash_flow_category: INVESTING, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 5000}
  - {account_code: CAPITAL_EXPENDITURES, account_name: "Capital Expenditures", account_type: CASH_FLOW, gaap_category: "Investing Activities", statement_section: CASH_FLOW, cash_flow_category: INVESTING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 5001}

  # ── Financing Activities ──
  - {account_code: CASHFLOW_FROM_FINANCING, account_name: "Cash from Financing", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 6000}
  - {account_code: DIVIDEND_PAYOUT, account_name: "Dividends Paid", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6001}
  - {account_code: DIVIDEND_PAYOUT_COMMON, account_name: "Dividends Paid (Common)", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 6002}
  - {account_code: DIVIDEND_PAYOUT_PREFERRED, account_name: "Dividends Paid (Preferred)", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 3, display_order: 6003}
  - {account_code: PROCEEDS_FROM_COMMON_STOCK, account_name: "Proceeds from Common Stock", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6010}
  - {account_code: PROCEEDS_FROM_PREFERRED_STOCK, account_name: "Proceeds from Preferred Stock", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6011}
  - {account_code: PROCEEDS_FROM_TREASURY_STOCK, account_name: "Proceeds from Treasury Stock", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6012}
  - {account_code: PAYMENTS_FOR_REPURCHASE_COMMON, account_name: "Share Repurchases (Common)", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6020}
  - {account_code: PAYMENTS_FOR_REPURCHASE_PREFERRED, account_name: "Share Repurchases (Preferred)", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6021}
  - {account_code: PAYMENTS_FOR_REPURCHASE_EQUITY, account_name: "Equity Repurchases", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6022}
  - {account_code: PROCEEDS_FROM_REPURCHASE_EQUITY, account_name: "Proceeds from Equity Repurchase", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6023}
  - {account_code: PROCEEDS_FROM_LONG_TERM_DEBT, account_name: "Proceeds from Long-Term Debt", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6030}
  - {account_code: PROCEEDS_FROM_SHORT_TERM_DEBT, account_name: "Proceeds from Short-Term Debt", account_type: CASH_FLOW, gaap_category: "Financing Activities", statement_section: CASH_FLOW, cash_flow_category: FINANCING, normal_balance: DEBIT, format_type: CURRENCY, level: 2, display_order: 6031}

  # ── Net Cash Change ──
  - {account_code: CHANGE_IN_EXCHANGE_RATE, account_name: "Effect of Exchange Rate Changes", account_type: CASH_FLOW, gaap_category: "Exchange Rate", statement_section: CASH_FLOW, normal_balance: DEBIT, format_type: CURRENCY, level: 1, display_order: 7000}
  - {account_code: NET_CHANGE_IN_CASH, account_name: "Net Change in Cash", account_type: CASH_FLOW, gaap_category: "Net Cash Change", statement_section: CASH_FLOW, normal_balance: DEBIT, is_rollup: true, format_type: CURRENCY, level: 1, display_order: 7100}

measures:
  - [account_count, count_distinct, account_id, "Financial accounts", {format: "#,##0"}]
---

## Financial Account Dimension

Chart of accounts for SEC financial statement line items following US GAAP presentation order (ASC 210, 220, 230). Static dimension — accounts are seeded from the `data:` section.

### GAAP Categories

| Category | Statement | Standard |
|----------|-----------|----------|
| Revenue | Income Statement | ASC 606 |
| Cost of Goods Sold | Income Statement | ASC 330 |
| Operating Expenses | Income Statement | ASC 220 |
| Non-Operating Items | Income Statement | ASC 220 |
| Current Assets | Balance Sheet | ASC 210 |
| Non-Current Assets | Balance Sheet | ASC 350/360 |
| Current Liabilities | Balance Sheet | ASC 210 |
| Non-Current Liabilities | Balance Sheet | ASC 470 |
| Shareholders' Equity | Balance Sheet | ASC 505 |
| Operating Activities | Cash Flow | ASC 230 |
| Investing Activities | Cash Flow | ASC 230 |
| Financing Activities | Cash Flow | ASC 230 |

### Hierarchy

Accounts have `parent_account_id` and `level` fields forming a tree. Level 1 = statement totals, Level 2 = category subtotals, Level 3 = detail line items. Use `is_rollup = true` to identify summary accounts.
