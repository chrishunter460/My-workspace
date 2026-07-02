---
type: domain-base
model: geo_location
version: 1.0
description: "Point locations - addresses, coordinates, named places"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [location_id, integer, nullable: false, description: "Primary key"]
  - [location_type, string, nullable: false, description: "ADDRESS, COORDINATE, PLACE"]
  - [location_name, string, nullable: true, description: "Named place or address"]
  - [latitude, double, nullable: true, description: "WGS84 latitude"]
  - [longitude, double, nullable: true, description: "WGS84 longitude"]
  - [city, string, nullable: true, description: "City name"]
  - [state, string, nullable: true, description: "State/province"]
  - [zip_code, string, nullable: true, description: "Postal code"]
  - [country, string, nullable: true, description: "Country code"]

tables:
  _dim_location:
    type: dimension
    primary_key: [location_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [location_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(location_type, '_', COALESCE(location_name, CAST(latitude AS STRING)))))"}]
      - [location_type, string, false, "Classification"]
      - [location_name, string, true, "Display name or address"]
      - [latitude, double, true, "WGS84 latitude"]
      - [longitude, double, true, "WGS84 longitude"]
      - [city, string, true, "City"]
      - [state, string, true, "State"]
      - [zip_code, string, true, "Postal code"]
      - [country, string, true, "Country", {default: "US"}]

    measures:
      - [location_count, count_distinct, location_id, "Number of locations", {format: "#,##0"}]

behaviors: []  # Pure entity — target of auto_edges, not source

domain: geography
tags: [base, template, geography, location]
status: active
---

## Geo Location Base Template

Point locations with coordinates and address components. For boundary/polygon data, see `geo_spatial.md`.

### Usage

```yaml
extends: _base.geography.geo_location
```
