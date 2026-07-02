---
type: domain-model
model: corporate.entity
version: 3.0
description: "Corporate legal entities - SEC-registered companies with CIK identifiers"
extends: [_base.entity.company]
depends_on: [temporal]

sources_from: sources/entity/

hooks:
  after_build:
    - {fn: de_funk.hooks.corporate.cik_enrichment.fix_company_ids}

storage:
  format: delta
  silver:
    root: storage/silver/corporate/entity/

graph:
  edges: []

build:
  sort_by: [company_id]
  optimize: true
  phases:
    1: { tables: [dim_company] }

measures:
  simple:
    - [company_count, count_distinct, dim_company.company_id, "Number of companies", {format: "#,##0"}]

metadata:
  domain: corporate
  subdomain: entity
  owner: data_engineering
status: active
---

## Corporate Entity Model

Company identity data: ticker, CIK, sector, industry, exchange. This is the "who" — the legal entity itself.

### Relationship to Finance

Financial reporting (income statements, balance sheets, cash flows, earnings) lives in `corporate.finance`, which depends on this model. The `legal_entity_id` on financial facts FKs to `dim_company.company_id`.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| company_overview | alpha_vantage_company_overview | SEC-registered company reference data |
