---
type: domain-model-table
table: dim_status
extends: _base.operations.service_request._dim_status
table_type: dimension
transform: distinct
from: bronze.chicago_service_requests_311
group_by: [status]
primary_key: [status_id]
unique_key: [status_name]

schema:
  - [status_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(status, 'UNKNOWN')))"}]
  - [status_name, string, false, "Status name", {derived: "status"}]
  - [is_open, boolean, false, "Currently open", {derived: "status IN ('Open', 'In Progress')"}]
  - [is_closed, boolean, false, "Completed", {derived: "status = 'Completed'"}]
---

## Status Dimension

311 request status codes.
