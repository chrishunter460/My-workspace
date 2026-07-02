---
type: domain-base
model: event
version: 2.0
description: "Root template for any timestamped occurrence - transaction, incident, measurement"

# CANONICAL FIELDS - the most fundamental attributes of any event
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [event_id, integer, nullable: false, description: "Surrogate primary key"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning legal entity (company, municipality, county)"]
  - [event_date, date, nullable: false, description: "When the event occurred"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar (YYYYMMDD)"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location (nullable — not all events have geography)"]
  - [event_type, string, nullable: false, description: "Discriminator for what kind of event"]
  - [domain_source, string, nullable: false, description: "Which domain/organization produced this event"]
  - [source_id, string, nullable: false, description: "Original identifier from source system"]

tables:
  _fact_event:
    type: fact
    primary_key: [event_id]
    partition_by: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [event_id, integer, false, "PK - surrogate", {derived: "ABS(HASH(CONCAT(event_type, '_', source_id)))"}]
      - [legal_entity_id, integer, true, "FK to owning legal entity", {fk: "_dim_legal_entity.legal_entity_id"}]
      - [date_id, integer, false, "FK to temporal.dim_calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(event_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [event_type, string, false, "Discriminator"]
      - [domain_source, string, false, "Origin domain"]
      - [source_id, string, false, "Original ID from source"]
      - [event_date, date, false, "Event date"]

    measures:
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]

auto_edges:
  # [fk_column, target, on, type, cross_model]
  # Applied to every fact table whose schema contains fk_column.
  # Edge name is auto-generated: {fact_name}_to_{target_short_name}
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
  - [location_id, geo_location._dim_location, [location_id=location_id], many_to_one, geo_location, optional: true]

graph:
  edges: []

behaviors:
  - temporal        # auto_edges: date_id → calendar
  - geo_locatable   # auto_edges: location_id → geo_location

domain: _base
tags: [base, template, event, root]
status: active
---

## Event Base Template

The most fundamental fact template. Every timestamped occurrence in the system is an event.

### What Extends This

| Template | event_type | Example source_id |
|----------|------------|-------------------|
| `_base.accounting.financial_event` | PAYMENT, BUDGET, STATEMENT | composite key |
| `_base.public_safety.crime` | CRIME, ARREST | case_number |
| `_base.regulatory.inspection` | FOOD_INSPECTION, VIOLATION | inspection_id |
| `_base.operations.service_request` | 311_REQUEST | sr_number |
| `_base.housing.permit` | BUILDING_PERMIT | permit_number |
| `_base.transportation.transit` | RIDERSHIP | station + date |
| `_base.transportation.traffic` | TRAFFIC_OBS | segment + timestamp |

### Key Design

All event PKs are integers: `ABS(HASH(CONCAT(event_type, '_', source_id)))`

The `event_type` prefix in the hash ensures uniqueness across unions of different source types.

### legal_entity_id Pattern

Every event can optionally FK to the legal entity that owns or produced it. This enables cross-domain federation by entity:

| Domain | legal_entity_id derivation |
|--------|---------------------------|
| Municipal (Chicago) | `ABS(HASH(CONCAT('CITY_', 'Chicago')))` |
| County (Cook County) | `ABS(HASH(CONCAT('COUNTY_', 'Cook County')))` |
| Corporate | `ABS(HASH(CONCAT('COMPANY_', ticker)))` |
| Securities (market data) | nullable - linked via security_id -> company |

The field is nullable because some events (e.g., market prices) relate to entities indirectly through other FKs rather than directly.

### location_id Pattern

Every event can optionally FK to a geographic location via `location_id`. This works like `date_id` — a standard FK that enables geographic analysis across all event types:

| Domain | location_id derivation |
|--------|----------------------|
| Crime / 311 / Permits | `ABS(HASH(CONCAT(latitude, '_', longitude)))` |
| Financial events | nullable — no geographic component |
| Transit ridership | Derived from station lat/lon |
| Traffic observations | Derived from segment centroid |

The field is nullable because not all events have a geographic component (e.g., financial transactions, market data). Sources that lack lat/lon set `location_id` to null.

### date_id Pattern

All facts FK to `temporal.dim_calendar` via integer `date_id` (YYYYMMDD format). Facts store `date_id`, not raw date columns, for join efficiency. The raw `event_date` is kept for derivation but should not be used for joins.
