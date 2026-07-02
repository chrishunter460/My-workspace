---
type: domain-model
model: municipal.operations
version: 3.0
description: "Municipal 311 service requests"
extends: [_base.operations.service_request]
depends_on: [temporal, municipal.geospatial]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/municipal/{entity}/operations/

graph:
  edges:
    - [request_to_type, fact_service_requests, dim_request_type, [request_type_id=request_type_id], many_to_one, null]
    - [request_to_status, fact_service_requests, dim_status, [status_id=status_id], many_to_one, null]
    - [request_to_community_area, fact_service_requests, municipal.geospatial.dim_community_area, [community_area=area_number], many_to_one, municipal.geospatial, optional: true]
    - [request_to_ward, fact_service_requests, municipal.geospatial.dim_ward, [ward=ward_number], many_to_one, municipal.geospatial, optional: true]

build:
  partitions: [year]
  optimize: true
  phases:
    1: { tables: [dim_request_type, dim_status] }
    2: { tables: [fact_service_requests] }

measures:
  simple:
    - [request_count, count, fact_service_requests.request_id, "Total requests", {format: "#,##0"}]
    - [avg_days_to_close, avg, fact_service_requests.days_to_close, "Avg days to close", {format: "#,##0.1"}]
  computed:
    - [completion_rate, expression, "(request_count - open_request_count) / request_count * 100", "Completion rate", {format: "#,##0.0%"}]

federation:
  enabled: true
  union_key: domain_source

metadata:
  domain: municipal
  subdomain: operations
status: active
---

## Municipal Operations Model

311 service requests.

### Request Taxonomy

INFRASTRUCTURE, SANITATION, TREES, BUILDINGS, ANIMALS, OTHER
