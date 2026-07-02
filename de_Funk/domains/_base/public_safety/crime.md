---
type: domain-base
model: crime
version: 3.1
description: "Base template for crime/incident data across jurisdictions"
extends: _base._base_.event

canonical_fields:
  - [incident_id, integer, false, "PK - incident surrogate"]
  - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [case_number, string, true, "Police case number"]
  - [crime_type_id, integer, false, "FK to _dim_crime_type"]
  - [location_type_id, integer, true, "FK to _dim_location_type"]
  - [date_id, integer, false, "FK to dim_calendar"]
  - [location_id, integer, true, "FK to geo_location._dim_location"]
  - [year, integer, false, "Incident year (partition key)"]
  - [block, string, true, "Block-level address"]
  - [beat, string, true, "Police beat"]
  - [district, string, true, "Police district"]
  - [ward, integer, true, "Political ward"]
  - [community_area, integer, true, "Community area number"]
  - [latitude, double, true, "Latitude"]
  - [longitude, double, true, "Longitude"]
  - [arrest_made, boolean, true, "Whether arrest was made"]
  - [domestic, boolean, true, "Domestic-related"]

tables:
  _dim_crime_type:
    type: dimension
    primary_key: [crime_type_id]
    schema:
      - [crime_type_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(iucr_code, '_', COALESCE(fbi_code, 'UNK'))))"}]
      - [iucr_code, string, true, "Illinois Uniform Crime Reporting code"]
      - [fbi_code, string, true, "FBI UCR code"]
      - [primary_type, string, false, "Primary crime type"]
      - [description, string, true, "Detailed description"]
      - [crime_category, string, true, "VIOLENT, PROPERTY, OTHER"]
      - [crime_subcategory, string, true, "Subcategory"]
      - [is_index_crime, boolean, true, "FBI Part I crime", {default: false}]

  _dim_location_type:
    type: dimension
    primary_key: [location_type_id]
    schema:
      - [location_type_id, integer, false, "PK", {derived: "ABS(HASH(location_description))"}]
      - [location_description, string, false, "Location description"]
      - [location_category, string, true, "Grouped category"]

  _fact_crimes:
    type: fact
    primary_key: [incident_id]
    partition_by: [year]
    schema:
      - [incident_id, integer, false, "PK", {derived: "ABS(HASH(case_number))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [crime_type_id, integer, false, "FK to _dim_crime_type", {fk: _dim_crime_type.crime_type_id}]
      - [location_type_id, integer, true, "FK to _dim_location_type", {fk: _dim_location_type.location_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [case_number, string, true, "Police case number"]
      - [year, integer, false, "Incident year"]
      - [block, string, true, "Block-level address"]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [arrest_made, boolean, true, "Arrest made", {default: false}]
      - [domestic, boolean, true, "Domestic-related", {default: false}]
    measures:
      - [crime_count, count_distinct, incident_id, "Total crimes", {format: "#,##0"}]
      - [arrest_count, expression, "SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END)", "Crimes with arrest", {format: "#,##0"}]
      - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)", "Arrest rate %", {format: "#,##0.0%"}]

  _fact_arrests:
    type: fact
    primary_key: [arrest_id]
    partition_by: [year]
    schema:
      - [arrest_id, integer, false, "PK"]
      - [incident_id, integer, true, "FK to _fact_crimes (nullable — not all arrests link to a crime report)"]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [crime_type_id, integer, false, "FK to _dim_crime_type", {fk: _dim_crime_type.crime_type_id}]
      - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [beat, string, true, "Police beat"]
      - [district, string, true, "Police district"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [year, integer, false, "Arrest year"]
    measures:
      - [total_arrests, count_distinct, arrest_id, "Total arrests", {format: "#,##0"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location (both facts)
  edges:
    - [crime_to_type, _fact_crimes, _dim_crime_type, [crime_type_id=crime_type_id], many_to_one, null]
    - [crime_to_location_type, _fact_crimes, _dim_location_type, [location_type_id=location_type_id], many_to_one, null]
    - [arrest_to_crime, _fact_arrests, _fact_crimes, [incident_id=incident_id], many_to_one, null]
    - [arrest_to_crime_type, _fact_arrests, _dim_crime_type, [crime_type_id=crime_type_id], many_to_one, null]

subsets:
  discriminator: _dim_crime_type.crime_category
  description: "Crimes can be subset by category for focused analysis"
  values:
    VIOLENT:
      description: "Homicide, assault, battery, robbery"
      filter: "crime_category = 'VIOLENT'"
    PROPERTY:
      description: "Theft, burglary, motor vehicle theft"
      filter: "crime_category = 'PROPERTY'"
    OTHER:
      description: "All remaining crime types"
      filter: "crime_category = 'OTHER'"

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event
  - subsettable     # Has subsets: block (crime_category discriminator)

domain: public_safety
tags: [base, template, public_safety, crime]
status: active
---

## Base Crime Template

Reusable template for crime/public safety data. Two separate fact tables for distinct concepts:

- **`_fact_crimes`** — Reported incidents (a crime report filed by police)
- **`_fact_arrests`** — Actions taken (a person arrested, may or may not link to a crime report)

Not every crime leads to an arrest. Not every arrest ties to a single crime report. The `incident_id` FK on arrests is nullable for this reason.

### Crime Categories

```
VIOLENT: HOMICIDE, ASSAULT, BATTERY, ROBBERY
PROPERTY: THEFT, BURGLARY, MOTOR VEHICLE THEFT
OTHER: All remaining types
```

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to jurisdiction (city, county) |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (from lat/lon) |

### Models Using This Base

- `chicago_public_safety` — Chicago crime data (extends with Chicago-specific geography)
