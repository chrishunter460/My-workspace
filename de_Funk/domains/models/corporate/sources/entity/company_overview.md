---
type: domain-model-source
source: company_overview
extends: _base.entity.company
maps_to: dim_company
from: bronze.alpha_vantage_company_overview
domain_source: "'alpha_vantage'"

aliases:
  - [company_id, "ABS(HASH(CONCAT('COMPANY_', ticker)))"]
  - [ticker, ticker]
  - [company_name, company_name]
  - [cik, cik]
  - [asset_type, asset_type]
  - [exchange_code, exchange_code]
  - [sector, sector]
  - [industry, industry]
  - [country, country]
  - [currency, currency]
  - [address, address]
  - [official_site, official_site]
  - [fiscal_year_end, fiscal_year_end]
  - [is_active, "true"]
  - [shares_outstanding, shares_outstanding]
  - [shares_float, shares_float]
  - [beta, beta]
  - [pe_ratio, pe_ratio]
  - [eps, eps]
  - [dividend_yield, dividend_yield]
  - [profit_margin, profit_margin]
  - [revenue_ttm, revenue_ttm]
  - [week_52_high, week_52_high]
  - [week_52_low, week_52_low]
---

## Company Overview
Company reference data: name, sector, industry, exchange, CIK for SEC linkage. Includes financial snapshot (market cap, shares outstanding, key ratios) from Alpha Vantage COMPANY_OVERVIEW.
