---
type: domain-base
model: permit
version: 1.1
description: "Building permits - construction, renovation, demolition with cost and fee tracking"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [permit_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning jurisdiction"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [permit_number, string, nullable: true, description: "Official permit number"]
  - [permit_type_id, integer, nullable: false, description: "FK to _dim_permit_type"]
  - [work_type_id, integer, nullable: true, description: "FK to _dim_work_type"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (issue date)"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location"]
  - [issue_date, date, nullable: false, description: "Permit issue date"]
  - [year, integer, nullable: false, description: "Issue year (partition key)"]
  - [address, string, nullable: true, description: "Construction address"]
  - [ward, integer, nullable: true, description: "Political ward"]
  - [community_area, integer, nullable: true, description: "Community area / district"]
  - [latitude, double, nullable: true, description: "Location latitude"]
  - [longitude, double, nullable: true, description: "Location longitude"]
  - [total_fee, "decimal(18,2)", nullable: true, description: "Total permit fees"]
  - [estimated_cost, "decimal(18,2)", nullable: true, description: "Estimated construction cost"]

tables:
  _dim_permit_type:
    type: dimension
    primary_key: [permit_type_id]
    unique_key: [permit_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [permit_type_id, integer, false, "PK", {derived: "ABS(HASH(permit_type_code))"}]
      - [permit_type_code, string, false, "Permit type code"]
      - [permit_type_name, string, true, "Display name"]
      - [permit_category, string, true, "NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER", {enum: [NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER]}]

    measures:
      - [permit_type_count, count_distinct, permit_type_id, "Permit types", {format: "#,##0"}]

  _dim_work_type:
    type: dimension
    primary_key: [work_type_id]
    unique_key: [work_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [work_type_id, integer, false, "PK", {derived: "ABS(HASH(work_type_code))"}]
      - [work_type_code, string, false, "Work type code"]
      - [work_type_name, string, true, "Display name"]
      - [work_category, string, true, "RESIDENTIAL, COMMERCIAL, INDUSTRIAL, OTHER", {enum: [RESIDENTIAL, COMMERCIAL, INDUSTRIAL, OTHER]}]

    measures:
      - [work_type_count, count_distinct, work_type_id, "Work types", {format: "#,##0"}]

  _fact_permits:
    type: fact
    primary_key: [permit_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [permit_id, integer, false, "PK", {derived: "ABS(HASH(permit_number))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [permit_number, string, true, "Official permit number"]
      - [permit_type_id, integer, false, "FK to _dim_permit_type", {fk: _dim_permit_type.permit_type_id}]
      - [work_type_id, integer, true, "FK to _dim_work_type", {fk: _dim_work_type.work_type_id}]
      - [date_id, integer, false, "FK to calendar (issue date)", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(issue_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [issue_date, date, false, "Permit issue date"]
      - [year, integer, false, "Issue year", {derived: "YEAR(issue_date)"}]
      - [address, string, true, "Construction address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [total_fee, "decimal(18,2)", true, "Total permit fees"]
      - [estimated_cost, "decimal(18,2)", true, "Estimated construction cost"]

    measures:
      - [permit_count, count_distinct, permit_id, "Total permits", {format: "#,##0"}]
      - [total_fees, sum, total_fee, "Total permit fees", {format: "$#,##0.00"}]
      - [total_estimated_cost, sum, estimated_cost, "Total estimated cost", {format: "$#,##0.00"}]
      - [avg_estimated_cost, avg, estimated_cost, "Avg estimated cost", {format: "$#,##0.00"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location
  edges:
    - [permit_to_type, _fact_permits, _dim_permit_type, [permit_type_id=permit_type_id], many_to_one, null]
    - [permit_to_work_type, _fact_permits, _dim_work_type, [work_type_id=work_type_id], many_to_one, null]

subsets:
  discriminator: _dim_permit_type.permit_category
  description: "Permits can be subset by category"
  values:
    NEW_CONSTRUCTION:
      description: "New building construction"
      filter: "permit_category = 'NEW_CONSTRUCTION'"
    ALTERATION:
      description: "Renovation, remodeling, addition"
      filter: "permit_category = 'ALTERATION'"
    DEMOLITION:
      description: "Building demolition"
      filter: "permit_category = 'DEMOLITION'"
    OTHER:
      description: "Electrical, plumbing, mechanical"
      filter: "permit_category = 'OTHER'"

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event
  - subsettable     # Has subsets: block (permit_category discriminator)

domain: housing
tags: [base, template, housing, permit, construction]
status: active
---

## Permit Base Template

Building and construction permits with permit type classification, work type taxonomy, and cost/fee tracking.

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to jurisdiction (city, county) |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (from lat/lon) |

### Permit Categories

| Category | Description |
|----------|-------------|
| NEW_CONSTRUCTION | New building construction |
| ALTERATION | Renovation, remodeling, addition |
| DEMOLITION | Building demolition |
| OTHER | Electrical, plumbing, mechanical |

### Usage

```yaml
extends: _base.housing.permit
```
