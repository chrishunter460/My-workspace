---
type: domain-base
model: service_request
version: 1.1
description: "Constituent service requests (311-type) - intake, routing, resolution tracking"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [request_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning jurisdiction"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [request_type_id, integer, nullable: false, description: "FK to _dim_request_type"]
  - [status_id, integer, nullable: true, description: "FK to _dim_status"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (created date)"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location"]
  - [created_date, date, nullable: false, description: "Request creation date"]
  - [closed_date, date, nullable: true, description: "Request close date"]
  - [year, integer, nullable: false, description: "Creation year (partition key)"]
  - [street_address, string, nullable: true, description: "Request location address"]
  - [zip_code, string, nullable: true, description: "ZIP code"]
  - [ward, integer, nullable: true, description: "Political ward"]
  - [community_area, integer, nullable: true, description: "Community area / district"]
  - [latitude, double, nullable: true, description: "Request latitude"]
  - [longitude, double, nullable: true, description: "Request longitude"]
  - [days_to_close, integer, nullable: true, description: "Days between creation and close"]

tables:
  _dim_request_type:
    type: dimension
    primary_key: [request_type_id]
    unique_key: [request_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [request_type_id, integer, false, "PK", {derived: "ABS(HASH(request_type_code))"}]
      - [request_type_code, string, false, "Service request type code"]
      - [request_type_name, string, true, "Display name"]
      - [request_category, string, true, "INFRASTRUCTURE, SANITATION, VEGETATION, BUILDINGS, ANIMALS, OTHER"]

    measures:
      - [type_count, count_distinct, request_type_id, "Request types", {format: "#,##0"}]

  _dim_status:
    type: dimension
    primary_key: [status_id]
    unique_key: [status_name]

    # [column, type, nullable, description, {options}]
    schema:
      - [status_id, integer, false, "PK", {derived: "ABS(HASH(status_name))"}]
      - [status_name, string, false, "Status label"]
      - [is_open, boolean, false, "Request is open/in-progress", {derived: "status_name IN ('Open', 'In Progress')"}]
      - [is_closed, boolean, false, "Request is closed", {derived: "status_name IN ('Closed', 'Completed')"}]

    measures:
      - [status_count, count_distinct, status_id, "Status codes", {format: "#,##0"}]

  _fact_service_requests:
    type: fact
    primary_key: [request_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [request_id, integer, false, "PK", {derived: "ABS(HASH(source_id))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [request_type_id, integer, false, "FK to _dim_request_type", {fk: _dim_request_type.request_type_id}]
      - [status_id, integer, true, "FK to _dim_status", {fk: _dim_status.status_id}]
      - [date_id, integer, false, "FK to calendar (created)", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(created_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [created_date, date, false, "Request creation date"]
      - [closed_date, date, true, "Request close date"]
      - [year, integer, false, "Creation year", {derived: "YEAR(created_date)"}]
      - [street_address, string, true, "Location address"]
      - [zip_code, string, true, "ZIP code"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [days_to_close, integer, true, "Resolution time (days)", {derived: "DATEDIFF(closed_date, created_date)"}]

    measures:
      - [request_count, count_distinct, request_id, "Total requests", {format: "#,##0"}]
      - [avg_days_to_close, avg, days_to_close, "Avg resolution time (days)", {format: "#,##0.0"}]
      - [open_request_count, expression, "SUM(CASE WHEN closed_date IS NULL THEN 1 ELSE 0 END)", "Open requests", {format: "#,##0"}]
      - [closed_request_count, expression, "SUM(CASE WHEN closed_date IS NOT NULL THEN 1 ELSE 0 END)", "Closed requests", {format: "#,##0"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location
  edges:
    - [request_to_type, _fact_service_requests, _dim_request_type, [request_type_id=request_type_id], many_to_one, null]
    - [request_to_status, _fact_service_requests, _dim_status, [status_id=status_id], many_to_one, null]

subsets:
  discriminator: _dim_request_type.request_category
  description: "Service requests can be subset by category"
  values:
    INFRASTRUCTURE:
      description: "Potholes, street lights, sidewalks"
      filter: "request_category = 'INFRASTRUCTURE'"
    SANITATION:
      description: "Garbage, recycling, graffiti"
      filter: "request_category = 'SANITATION'"
    VEGETATION:
      description: "Tree trimming, debris, weed complaints"
      filter: "request_category = 'VEGETATION'"
    BUILDINGS:
      description: "Vacant buildings, code violations"
      filter: "request_category = 'BUILDINGS'"
    ANIMALS:
      description: "Stray animals, rodent complaints"
      filter: "request_category = 'ANIMALS'"
    OTHER:
      description: "General complaints, information requests"
      filter: "request_category = 'OTHER'"

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event
  - subsettable     # Has subsets: block (request_category discriminator)

domain: operations
tags: [base, template, operations, 311, service-request]
status: active
---

## Service Request Base Template

Constituent service requests (311-type systems). Tracks intake, routing, and resolution with time-to-close metrics.

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to jurisdiction (city, county) |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (from lat/lon) |

### Request Categories

| Category | Examples |
|----------|----------|
| INFRASTRUCTURE | Potholes, street lights, sidewalks |
| SANITATION | Garbage, recycling, graffiti |
| VEGETATION | Tree trimming, debris, weed complaints |
| BUILDINGS | Vacant buildings, code violations |
| ANIMALS | Stray animals, rodent complaints |
| OTHER | General complaints, information requests |

### Resolution Tracking

`days_to_close` is derived at build time: `DATEDIFF(closed_date, created_date)`. Open requests have `NULL` for both `closed_date` and `days_to_close`.

### Usage

```yaml
extends: _base.operations.service_request
```
