---
type: domain-model-table
table: fact_service_requests
extends: _base.operations.service_request._fact_service_requests
table_type: fact
primary_key: [request_id]
partition_by: [year]

schema:
  - [request_id, integer, false, "PK", {derived: "ABS(HASH(sr_number))"}]
  - [legal_entity_id, integer, false, "City of Chicago", {derived: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"}]
  - [request_type_id, integer, true, "FK to dim_request_type", {fk: dim_request_type.request_type_id, derived: "ABS(HASH(COALESCE(sr_type, 'UNKNOWN')))"}]
  - [status_id, integer, true, "FK to dim_status", {fk: dim_status.status_id, derived: "ABS(HASH(COALESCE(status, 'UNKNOWN')))"}]
  - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(DATE_FORMAT(created_date, 'yyyyMMdd') AS INT)"}]
  - [location_id, integer, true, "FK to geo_location._dim_location", {derived: "CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN ABS(HASH(CONCAT(CAST(latitude AS STRING), '_', CAST(longitude AS STRING)))) ELSE null END"}]
  - [created_date, timestamp, true, "Request created", {format: date}]
  - [closed_date, timestamp, true, "Request closed", {format: date}]
  - [year, integer, true, "Year created", {derived: "YEAR(created_date)"}]
  - [street_address, string, true, "Street address"]
  - [zip_code, string, true, "ZIP code"]
  - [ward, integer, true, "City ward"]
  - [community_area, integer, true, "Community area"]
  - [latitude, double, true, "Latitude", {format: decimal}]
  - [longitude, double, true, "Longitude", {format: decimal}]
  - [days_to_close, integer, true, "Days to close", {derived: "DATEDIFF('day', created_date, closed_date)", format: number}]

measures:
  - [request_count, count_distinct, request_id, "Total requests", {format: "#,##0"}]
  - [avg_days_to_close, avg, days_to_close, "Avg days to close", {format: "#,##0.1"}]
---

## Service Requests Fact Table

311 service requests since 12/18/2018. Extends `_base.operations.service_request._fact_service_requests`.
