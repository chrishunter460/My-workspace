---
type: domain-model
model: municipal.entity
version: 3.0
description: "Municipal government entities - cities, counties, townships, special districts"
extends: [_base.entity.municipality]
depends_on: [temporal, geospatial]

storage:
  format: delta
  silver:
    root: storage/silver/municipal/{entity}/entity/

graph:
  edges:
    - [municipality_to_geography, dim_municipality, geospatial.dim_geography, [geography_id=geography_id], many_to_one, geospatial]

build:
  optimize: true
  phases:
    1: { tables: [dim_municipality] }

measures:
  simple:
    - [municipality_count, count_distinct, dim_municipality.municipality_id, "Number of municipalities", {format: "#,##0"}]

metadata:
  domain: municipal
  subdomain: entity
  owner: data_engineering
status: active
---

## Municipal Entity Model

Municipality identity data. This is the "who" for all municipal domains.

### Relationship to Other Municipal Models

All municipal domain models (finance, public_safety, regulatory, housing, operations, transportation) depend on this model. Fact tables set `legal_entity_id = ABS(HASH(CONCAT('CITY_', 'Chicago')))` which FKs to `dim_municipality.municipality_id`.

### Seeded Dimension

`dim_municipality` is a seeded dimension — rows are defined in the table file's `data:` section rather than loaded from bronze. Each municipality in the federation gets one row.
