---
type: domain-model-table
table: dim_request_type
extends: _base.operations.service_request._dim_request_type
table_type: dimension
transform: distinct
from: bronze.chicago_service_requests_311
group_by: [sr_type]
primary_key: [request_type_id]
unique_key: [sr_type]

schema:
  - [request_type_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(sr_type, 'UNKNOWN')))"}]
  - [sr_type, string, false, "Request type name"]
  - [sr_short_code, string, true, "Short code"]
  - [request_category, string, true, "Category", {derived: "CASE WHEN sr_type LIKE '%Pothole%' OR sr_type LIKE '%Street%' THEN 'INFRASTRUCTURE' WHEN sr_type LIKE '%Graffiti%' OR sr_type LIKE '%Garbage%' OR sr_type LIKE '%Sanitation%' THEN 'SANITATION' WHEN sr_type LIKE '%Tree%' THEN 'TREES' WHEN sr_type LIKE '%Building%' THEN 'BUILDINGS' WHEN sr_type LIKE '%Rodent%' OR sr_type LIKE '%Animal%' THEN 'ANIMALS' ELSE 'OTHER' END"}]
---

## Request Type Dimension

Distinct 311 request types with taxonomy categorization.
