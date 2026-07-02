---
type: domain-model-source
source: 311_requests
extends: _base.operations.service_request
maps_to: fact_service_requests
from: bronze.chicago_service_requests_311
domain_source: "'chicago'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [request_id, "ABS(HASH(sr_number))"]
  - [request_type_id, "ABS(HASH(sr_type))"]
  - [status_id, "ABS(HASH(status))"]
  - [created_date, created_date]
  - [closed_date, closed_date]
  - [date_id, "CAST(DATE_FORMAT(created_date, 'yyyyMMdd') AS INT)"]
  - [year, "YEAR(created_date)"]
  - [street_address, street_address]
  - [zip_code, zip_code]
  - [ward, ward]
  - [community_area, community_area]
  - [latitude, latitude]
  - [longitude, longitude]
  - [days_to_close, "DATEDIFF(closed_date, created_date)"]
  - [sr_type, sr_type]
  - [status, status]
---

## 311 Requests
Constituent service requests since 12/18/2018 covering infrastructure, sanitation, trees, and more.
