---
type: domain-model
model: municipal.public_safety
version: 3.0
description: "Municipal crime and arrest data"
extends: _base.public_safety.crime
depends_on: [temporal, geospatial, municipal.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/public_safety/

graph:
  edges:
    # auto_edges inherited: date_id→calendar, location_id→location (both facts)
    # Base edges inherited: crime_to_type, crime_to_location_type, arrest_to_crime, arrest_to_crime_type
    # Chicago-specific geo edges
    - [crime_to_community_area, fact_crimes, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [crime_to_ward, fact_crimes, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]
    - [crime_to_district, fact_crimes, municipal.geospatial.dim_patrol_district, [district=district_number], many_to_one, municipal.geospatial, optional: true]
    - [arrest_to_community_area, fact_arrests, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [arrest_to_ward, fact_arrests, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]
    - [arrest_to_district, fact_arrests, municipal.geospatial.dim_patrol_district, [district=district_number], many_to_one, municipal.geospatial, optional: true]

  paths:
    arrest_to_crime_neighborhood:
      description: "Arrest → originating crime → community area"
      steps:
        - {from: fact_arrests, to: fact_crimes, via: incident_id}
        - {from: fact_crimes, to: municipal.geospatial.dim_community_area, via: community_area}
    crime_type_by_district:
      description: "Crime classification across patrol districts"
      steps:
        - {from: fact_crimes, to: dim_crime_type, via: crime_type_id}
        - {from: fact_crimes, to: municipal.geospatial.dim_patrol_district, via: district}

build:
  partitions: [year]
  sort_by: [date_id, incident_id]
  optimize: true
  phases:
    1: { tables: [dim_crime_type, dim_location_type] }
    2: { tables: [fact_crimes, fact_arrests] }

measures:
  simple:
    - [crime_count, count_distinct, fact_crimes.incident_id, "Total crime incidents", {format: "#,##0"}]
    - [arrest_count, count, fact_crimes.incident_id, "Crimes with arrest", {filters: ["arrest_made = true"]}]
    - [domestic_crime_count, count, fact_crimes.incident_id, "Domestic crimes", {filters: ["domestic = true"]}]
    - [total_arrests, count_distinct, fact_arrests.arrest_id, "Total arrest records", {format: "#,##0"}]
  computed:
    - [arrest_rate, expression, "arrest_count / crime_count * 100", "Arrest rate %", {format: "#,##0.1%"}]
    - [domestic_rate, expression, "domestic_crime_count / crime_count * 100", "Domestic rate %", {format: "#,##0.1%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: public_safety
status: active
---

## Chicago Public Safety Model

Crime and arrest data for the City of Chicago, extending `_base.public_safety.crime`.

### Data Sources

| Source | Bronze Table | Description |
|--------|--------------|-------------|
| Crimes | chicago_crimes | Incidents 2001-present |
| Arrests | chicago_arrests | Arrest records |
| IUCR Codes | chicago_iucr_codes | Crime classification |

### Crime Taxonomy

Standard taxonomy from base: VIOLENT, PROPERTY, OTHER.
Chicago uses dual classification: IUCR (state) + FBI UCR (federal).

### Privacy Notes

- Addresses at block level only
- Most recent 7 days excluded
