---
type: domain-model
model: municipal.regulatory
version: 3.0
description: "Municipal inspections, violations, and business licenses"
extends: [_base.regulatory.inspection]
depends_on: [temporal, municipal.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/regulatory/

graph:
  edges:
    # auto_edges inherited: date_id→calendar, location_id→location (all 3 facts)
    # Internal dimension edges
    - [inspection_to_facility, fact_food_inspections, dim_facility, [facility_id=facility_id], many_to_one, null]
    - [inspection_to_type, fact_food_inspections, dim_inspection_type, [inspection_type_id=inspection_type_id], many_to_one, null]

    # Building violations → geo
    - [violation_to_community_area, fact_building_violations, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [violation_to_ward, fact_building_violations, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]

    # Business licenses → geo
    - [license_to_community_area, fact_business_licenses, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [license_to_ward, fact_business_licenses, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]

    # Food inspections → geo (through dim_facility which has ward + community_area)
    - [facility_to_community_area, dim_facility, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [facility_to_ward, dim_facility, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_facility, dim_inspection_type] }
    2: { tables: [fact_food_inspections, fact_building_violations, fact_business_licenses] }

measures:
  simple:
    - [inspection_count, count, fact_food_inspections.inspection_id, "Inspections", {format: "#,##0"}]
    - [facility_count, count_distinct, dim_facility.facility_id, "Facilities", {format: "#,##0"}]
    - [violation_count, count, fact_building_violations.violation_id, "Violations", {format: "#,##0"}]
    - [license_count, count, fact_business_licenses.license_id, "Licenses", {format: "#,##0"}]
  computed:
    - [pass_rate, expression, "pass_count / inspection_count * 100", "Pass rate %", {format: "#,##0.0%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: regulatory
status: active
---

## Municipal Regulatory Model

Food inspections, building violations, and business licenses.

### Risk Levels

| Level | Description |
|-------|-------------|
| Risk 1 (High) | Full food prep |
| Risk 2 (Medium) | Limited food prep |
| Risk 3 (Low) | Prepackaged only |
