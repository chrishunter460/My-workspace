---
type: api-endpoint
provider:                               # Chicago Data Portal | Cook County Data Portal
endpoint_id:                            # Unique identifier (e.g., "crimes", "building_permits")

# API Configuration
endpoint_pattern: /resource/{resource_id}.json  # Replace {resource_id} with 4x4 code (e.g., ijzp-q8t2)
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000                         # Socrata default batch size
  $order:                               # Optional: date_column DESC
required_params: []

# Pagination
pagination_type: offset                 # Socrata uses offset pagination
bulk_download: true
download_method: csv                    # Use 'csv' for large datasets (>6M records), 'json' for smaller

# Metadata
domain:                                 # public-safety | finance | housing | transportation | etc.
legal_entity_type: municipal            # municipal | county
subject_entity_tags: []                 # [municipal, individual, property, corporate]
data_tags: []                           # [time-series, geospatial, reference, daily]
status: active
update_cadence: daily                   # daily | weekly | monthly | irregular
last_verified:
last_reviewed:
notes: ""

# Storage Configuration
bronze:                                 # Bronze table name (e.g., "chicago_crimes")
partitions: [year]                      # Common: [year] for time-series data
write_strategy: append                  # append (preserves data) | upsert (merge) | overwrite
key_columns: []                         # Primary key for deduplication (e.g., [id])
date_column:                            # Date column for incremental loads

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Types: string | long | double | boolean | date | timestamp | int
# Options: {transform: "...", coerce: "...", expr: "...", default: ...}
#
# Common Socrata transforms:
#   - Timestamps: {transform: "to_timestamp(yyyy-MM-dd'T'HH:mm:ss)"}
#   - Dates: {transform: "to_date(yyyy-MM-dd)"}
#   - Numeric strings: {coerce: double} or {coerce: long}

schema:
  - [id, string, id, false, "Unique identifier"]
  # Add fields here...
---

## Description

What data this endpoint provides. Include data source, coverage dates, and any limitations.

## Request Notes

- **Resource ID**: `xxxx-xxxx`
- **API Docs**: https://dev.socrata.com/foundry/{domain}/xxxx-xxxx
- **Rate Limits**: Socrata allows 1000 requests/hour without app token

## Homelab Usage

```bash
# Full ingest
./scripts/test/test_pipeline.sh --profile dev

# This endpoint only
python -m scripts.ingest.run_bronze_ingestion --endpoints endpoint_id
```

## Known Quirks

- Data quirks, schema changes, null handling notes
