---
type: domain-model
model: municipal.housing
version: 3.0
description: "Municipal building permits and zoning data"
extends: [_base.housing.permit, _base.geography.geo_spatial]
depends_on: [temporal, municipal.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/housing/

graph:
  edges:
    - [permit_to_type, fact_building_permits, dim_permit_type, [permit_type_id=permit_type_id], many_to_one, null]
    - [permit_to_work_type, fact_building_permits, dim_work_type, [work_type_id=work_type_id], many_to_one, null]
    - [permit_to_community_area, fact_building_permits, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [permit_to_ward, fact_building_permits, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_permit_type, dim_work_type, dim_zoning_district] }
    2: { tables: [fact_building_permits] }

measures:
  simple:
    - [permit_count, count, fact_building_permits.permit_id, "Number of permits", {format: "#,##0"}]
    - [total_fees, sum, fact_building_permits.total_fee, "Total permit fees", {format: "$#,##0"}]
    - [total_estimated_cost, sum, fact_building_permits.estimated_cost, "Total estimated cost", {format: "$#,##0"}]
    - [avg_permit_fee, avg, fact_building_permits.total_fee, "Average permit fee", {format: "$#,##0.00"}]
  computed:
    - [avg_project_cost, expression, "total_estimated_cost / permit_count", "Average project cost", {format: "$#,##0"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: housing
status: active
---

## Municipal Housing Model

Building permits and zoning data.

### Permit Types

- NEW CONSTRUCTION, RENOVATION/ALTERATION, DEMOLITION, ELECTRICAL, PLUMBING

### Zoning Categories

| Category | Description |
|----------|-------------|
| R | Residential |
| B | Business |
| C | Commercial |
| M | Manufacturing |
| PD | Planned Development |
