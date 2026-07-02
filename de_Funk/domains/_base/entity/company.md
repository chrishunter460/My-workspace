---
type: domain-base
model: company
version: 1.0
description: "Public and private corporations - SEC registrants, market-listed entities"
extends: _base.entity.legal

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [company_id, integer, nullable: false, description: "Primary key"]
  - [ticker, string, nullable: false, description: "Primary ticker symbol"]
  - [company_name, string, nullable: false, description: "Legal company name"]
  - [cik, string, nullable: true, description: "SEC Central Index Key"]
  - [asset_type, string, nullable: true, description: "Stock, ETF, Mutual Fund"]
  - [exchange_code, string, nullable: true, description: "Primary exchange (NYSE, NASDAQ)"]
  - [sector, string, nullable: true, description: "GICS Sector"]
  - [industry, string, nullable: true, description: "GICS Industry"]
  - [country, string, nullable: true, description: "Country of incorporation"]
  - [currency, string, nullable: true, description: "Reporting currency"]
  - [address, string, nullable: true, description: "Headquarters address"]
  - [official_site, string, nullable: true, description: "Website URL"]
  - [fiscal_year_end, string, nullable: true, description: "Fiscal year end month"]
  - [is_active, boolean, nullable: false, description: "Currently operating"]

tables:
  _dim_company:
    type: dimension
    primary_key: [company_id]
    unique_key: [ticker]

    # [column, type, nullable, description, {options}]
    schema:
      - [company_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT('COMPANY_', ticker)))"}]
      - [ticker, string, false, "Primary ticker"]
      - [company_name, string, false, "Legal name"]
      - [cik, string, true, "SEC CIK"]
      - [asset_type, string, true, "Asset classification"]
      - [exchange_code, string, true, "Primary exchange"]
      - [sector, string, true, "GICS Sector"]
      - [industry, string, true, "GICS Industry"]
      - [country, string, true, "Country", {default: "US"}]
      - [currency, string, true, "Reporting currency", {default: "USD"}]
      - [address, string, true, "Headquarters address"]
      - [official_site, string, true, "Website URL"]
      - [fiscal_year_end, string, true, "Fiscal year end month"]
      - [is_active, boolean, false, "Currently operating", {default: true}]

    measures:
      - [company_count, count_distinct, company_id, "Number of companies", {format: "#,##0"}]

behaviors: []  # Pure entity — reference dimension only

domain: entity
tags: [base, template, entity, company, corporate]
status: active
---

## Company Base Template

Public and private corporations with SEC registration, market listing, and sector classification. Extends `_base.entity.legal` with corporate-specific fields.

### Inherited from Legal Entity

| Field | From |
|-------|------|
| legal_entity_id | `_base.entity.legal` |
| tax_id (EIN) | `_base.entity.legal` |
| jurisdiction | `_base.entity.legal` |
| incorporation_state | `_base.entity.legal` |

### Company-Specific Fields

| Field | Purpose |
|-------|---------|
| ticker | Links to securities model via `ABS(HASH(ticker))` |
| cik | Links to SEC EDGAR filings |
| sector / industry | GICS classification |
| exchange_code | Primary listing exchange |

### Usage

```yaml
extends: _base.entity.company
```
