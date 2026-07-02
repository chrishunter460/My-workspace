---
type: api-endpoint
provider:                               # Chicago Data Portal | Cook County Data Portal
endpoint_id:                            # Unique identifier (e.g., "traffic_congestion_segments")

# API Configuration
endpoint_pattern: /resource/{view_id}.json      # Uses {view_id} placeholder - resolved from table below
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000                         # Socrata default batch size
required_params: [view_id]              # REQUIRED for multi-year endpoints

# Pagination
pagination_type: offset                 # Socrata uses offset pagination
bulk_download: true
download_method: csv                    # Use 'csv' for large datasets (>6M records), 'json' for smaller

# Metadata
domain:                                 # public-safety | finance | housing | transportation | etc.
legal_entity_type: municipal            # municipal | county
subject_entity_tags: []                 # [municipal, individual, property, corporate]
data_tags: []                           # [time-series, geospatial, reference]
status: active
update_cadence: irregular               # Often irregular for archived datasets
last_verified:
last_reviewed:
notes: "Multiple view_ids for different date ranges."

# Storage Configuration
bronze:                                 # Bronze table name (e.g., "chicago_traffic_congestion")
partitions: [year]                      # Partition by year for multi-year data
write_strategy: append                  # append (preserves data) | upsert (merge) | overwrite
key_columns: []                         # Primary key for deduplication
date_column:                            # Date column for partitioning

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
# Types: string | long | double | boolean | date | timestamp | int
# Options: {transform: "...", coerce: "...", expr: "...", default: ...}

schema:
  - [id, string, id, false, "Unique identifier"]
  # Add fields here...
---

## Description

What data this endpoint provides. Include data source, coverage dates, and why multiple view_ids exist.

## Available Years

**IMPORTANT**: The Year column must be a simple 4-digit year (e.g., `2024`, `2018`) for the parser to extract view_ids correctly. Do NOT use ranges like "2018-2023" or "May 2023 - current".

| Year | view_id | Format | Notes |
|------|---------|--------|-------|
| 2024 | xxxx-xxxx | JSON | Current year data |
| 2023 | yyyy-yyyy | JSON | Previous year |
| 2018 | zzzz-zzzz | JSON | Historical archive |

## Request Notes

- **API Docs**: https://dev.socrata.com/foundry/{domain}/xxxx-xxxx
- **Rate Limits**: Socrata allows 1000 requests/hour without app token
- Each view_id is fetched separately and combined with `year` column for partitioning

## Homelab Usage

```bash
# Full ingest (processes all years)
./scripts/test/test_pipeline.sh --profile dev

# This endpoint only
python -m scripts.ingest.run_bronze_ingestion --endpoints endpoint_id
```

## Known Quirks

- Different view_ids may have slightly different schemas
- Historical archives may stop updating
- Data quirks, schema changes, null handling notes
