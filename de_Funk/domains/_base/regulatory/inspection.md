---
type: domain-base
model: inspection
version: 1.1
description: "Regulatory inspections and violations - food safety, building code, business licensing"
extends: _base._base_.event

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [inspection_id, integer, nullable: false, description: "Primary key"]
  - [legal_entity_id, integer, nullable: true, description: "FK to owning jurisdiction"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [facility_id, integer, nullable: true, description: "FK to _dim_facility"]
  - [inspection_type_id, integer, nullable: true, description: "FK to _dim_inspection_type"]
  - [date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]
  - [location_id, integer, nullable: true, description: "FK to geo_location._dim_location"]
  - [inspection_date, date, nullable: false, description: "Date of inspection"]
  - [year, integer, nullable: false, description: "Inspection year (partition key)"]
  - [result, string, nullable: true, description: "Outcome (PASS, FAIL, CONDITIONAL, etc.)"]
  - [violations, string, nullable: true, description: "Violation details (free text)"]
  - [address, string, nullable: true, description: "Inspected location address"]
  - [ward, integer, nullable: true, description: "Political ward"]
  - [community_area, integer, nullable: true, description: "Community area / district"]
  - [latitude, double, nullable: true, description: "Location latitude"]
  - [longitude, double, nullable: true, description: "Location longitude"]

tables:
  _dim_facility:
    type: dimension
    primary_key: [facility_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [facility_id, integer, false, "PK", {derived: "ABS(HASH(facility_code))"}]
      - [facility_code, string, false, "Natural key (license number or ID)"]
      - [facility_name, string, true, "Establishment name"]
      - [facility_type, string, true, "Type of establishment"]
      - [risk_level, string, true, "Risk classification"]
      - [address, string, true, "Facility address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]

    measures:
      - [facility_count, count_distinct, facility_id, "Number of facilities", {format: "#,##0"}]

  _dim_inspection_type:
    type: dimension
    primary_key: [inspection_type_id]
    unique_key: [inspection_type_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [inspection_type_id, integer, false, "PK", {derived: "ABS(HASH(inspection_type_code))"}]
      - [inspection_type_code, string, false, "Inspection type code"]
      - [inspection_type_name, string, true, "Display name"]
      - [is_routine, boolean, true, "Scheduled routine inspection"]

    measures:
      - [type_count, count_distinct, inspection_type_id, "Inspection types", {format: "#,##0"}]

  _fact_inspections:
    type: fact
    primary_key: [inspection_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [inspection_id, integer, false, "PK", {derived: "ABS(HASH(source_id))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [facility_id, integer, true, "FK to _dim_facility", {fk: _dim_facility.facility_id}]
      - [inspection_type_id, integer, true, "FK to _dim_inspection_type", {fk: _dim_inspection_type.inspection_type_id}]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(inspection_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [inspection_date, date, false, "Inspection date"]
      - [year, integer, false, "Inspection year", {derived: "YEAR(inspection_date)"}]
      - [result, string, true, "Outcome"]
      - [violations, string, true, "Violation details"]
      - [address, string, true, "Inspected address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]

    measures:
      - [inspection_count, count_distinct, inspection_id, "Total inspections", {format: "#,##0"}]
      - [pass_count, expression, "SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END)", "Passed inspections", {format: "#,##0"}]
      - [fail_count, expression, "SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END)", "Failed inspections", {format: "#,##0"}]
      - [pass_rate, expression, "100.0 * SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)", "Pass rate %", {format: "#,##0.0%"}]

    python_measures:
      compliance_trend:
        function: "regulatory.measures.calculate_compliance_trend"
        description: "Rolling pass rate trend — detects improving or declining compliance by area"
        params:
          window_days: 365
          result_col: "result"
          partition_cols: [community_area]
        returns: [community_area, date_id, rolling_pass_rate, trend_direction, trend_slope]

      repeat_offender_score:
        function: "regulatory.measures.calculate_repeat_offender_score"
        description: "Facility-level risk score based on failure frequency and recency"
        params:
          lookback_days: 730
          decay_factor: 0.9
        returns: [facility_id, risk_score, failure_count, days_since_last_failure]

  _fact_violations:
    type: fact
    primary_key: [violation_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [violation_id, integer, false, "PK", {derived: "ABS(HASH(source_id))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(violation_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [violation_date, date, false, "Violation date"]
      - [year, integer, false, "Violation year", {derived: "YEAR(violation_date)"}]
      - [violation_type, string, true, "Type of violation"]
      - [status, string, true, "Violation status"]
      - [address, string, true, "Violation address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]

    measures:
      - [violation_count, count_distinct, violation_id, "Total violations", {format: "#,##0"}]

  _fact_licenses:
    type: fact
    primary_key: [license_id]
    partition_by: [year]

    # [column, type, nullable, description, {options}]
    schema:
      - [license_id, integer, false, "PK", {derived: "ABS(HASH(source_id))"}]
      - [legal_entity_id, integer, true, "FK to owning jurisdiction"]
      - [domain_source, string, false, "Origin domain"]
      - [business_name, string, true, "Licensed business name"]
      - [issue_date, date, false, "License issue date"]
      - [date_id, integer, false, "FK to calendar (issue date)", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(issue_date, 'yyyyMMdd') AS INT)"}]
      - [location_id, integer, true, "FK to geo_location._dim_location", {fk: "geo_location._dim_location.location_id", derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
      - [expiration_date, date, true, "License expiration"]
      - [year, integer, false, "Issue year", {derived: "YEAR(issue_date)"}]
      - [address, string, true, "Business address"]
      - [ward, integer, true, "Political ward"]
      - [community_area, integer, true, "Community area"]
      - [latitude, double, true, "Latitude"]
      - [longitude, double, true, "Longitude"]
      - [status, string, true, "License status"]
      - [license_type, string, true, "License category/description"]

    measures:
      - [license_count, count_distinct, license_id, "Total licenses", {format: "#,##0"}]
      - [active_license_count, expression, "SUM(CASE WHEN status IN ('AAI', 'ACTIVE') AND (expiration_date > CURRENT_DATE OR expiration_date IS NULL) THEN 1 ELSE 0 END)", "Active licenses", {format: "#,##0"}]

graph:
  # auto_edges inherited: date_id→calendar, location_id→location (all 3 facts)
  edges:
    - [inspection_to_facility, _fact_inspections, _dim_facility, [facility_id=facility_id], many_to_one, null]
    - [inspection_to_type, _fact_inspections, _dim_inspection_type, [inspection_type_id=inspection_type_id], many_to_one, null]

behaviors:
  - temporal        # Inherited from event
  - geo_locatable   # Inherited from event

domain: regulatory
tags: [base, template, regulatory, inspection, violation, license]
status: active
---

## Inspection Base Template

Regulatory compliance data covering inspections, violations, and business licensing. Supports multiple inspection domains (food safety, building code, etc.) via `inspection_type`.

### Inherited from Event Base

| Field | Nullable | Purpose |
|-------|----------|---------|
| `legal_entity_id` | yes | FK to jurisdiction (city, county) |
| `date_id` | no | FK to temporal.dim_calendar |
| `location_id` | yes | FK to geo_location._dim_location (from lat/lon) |

### Inspection Results

| Result | Description |
|--------|-------------|
| PASS | Compliant |
| FAIL | Non-compliant, action required |
| CONDITIONAL | Pass with conditions |
| NOT_READY | Facility not ready for inspection |
| OUT_OF_BUSINESS | No longer operating |

### Fact Tables

| Table | Purpose |
|-------|---------|
| `_fact_inspections` | Scheduled and ad-hoc inspections with results |
| `_fact_violations` | Building code, safety, and regulatory violations |
| `_fact_licenses` | Business license issuance and status tracking |

### Usage

```yaml
extends: _base.regulatory.inspection
```
