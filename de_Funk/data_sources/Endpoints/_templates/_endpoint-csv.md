---
type: api-endpoint
provider: Provider Name
endpoint_id: endpoint_name

# API Configuration
endpoint_pattern: "/resource/{view_id}.csv"
method: GET
format: csv
auth: inherit
response_key: null

# Query Parameters
default_query:
  $limit: 50000
required_params: [view_id]

# Pagination
pagination_type: offset
bulk_download: true

# CSV Reading (Socrata-style)
# download_method: csv enables spark.read.csv() for raw files
# No json_structure needed - CSV is inherently flat
download_method: csv
download_method_comment: "Bulk CSV download, read with spark.read.csv()"

# View ID mapping (for multi-year datasets)
# Maps year to Socrata 4x4 view_id
# Table below is parsed automatically by MarkdownConfigLoader

# Metadata
domain: public_data
legal_entity_type: government
subject_entity_tags: [municipal]
data_tags: [records, historical]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Large dataset - use CSV bulk download"

# Storage Configuration
bronze: provider_name/table_name
partitions: [year]
write_strategy: append
key_columns: [record_id, date]
date_column: date

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  # Primary key
  - [record_id, string, id, false, "Unique record identifier"]

  # Date fields (Socrata uses ISO format or floating timestamps)
  - [date, date, date, false, "Record date", {transform: "to_date(yyyy-MM-dd)"}]
  - [created_at, timestamp, created_at, true, "Creation timestamp"]

  # Partition column (computed from date)
  - [year, int, _computed, false, "Year for partitioning", {expr: "extract(year from date)"}]

  # String fields
  - [category, string, category, true, "Category name"]
  - [description, string, description, true, "Description text"]

  # Numeric fields
  - [amount, double, amount, true, "Dollar amount", {coerce: double}]
  - [count, long, count, true, "Count value", {coerce: long}]

  # Location fields (common in Socrata)
  - [latitude, double, latitude, true, "Latitude", {coerce: double}]
  - [longitude, double, longitude, true, "Longitude", {coerce: double}]
---

## Description

Large dataset available via Socrata Open Data API with CSV bulk download.

## API Notes

- Socrata 4x4 view_id identifies the dataset
- CSV format is much faster than JSON for large datasets
- Use `$limit` and `$offset` for pagination, or download full CSV

### View ID Mapping

For multi-year datasets, each year may have a different view_id:

| Year | view_id | Format | Notes |
|------|---------|--------|-------|
| 2024 | xxxx-xxxx | CSV | current |
| 2023 | yyyy-yyyy | CSV | complete |
| 2022 | zzzz-zzzz | CSV | complete |

## Spark Reading Strategy

1. Download raw CSV to `storage/raw/provider/endpoint/`
2. `spark.read.csv()` with header=True, inferSchema=False
3. Apply type coercions via `try_cast()`
4. Parse date columns with Socrata-specific formats

## Homelab Usage

```bash
# Download and ingest
python -m scripts.ingest.run_bronze_ingestion --provider provider_name --endpoints endpoint_name

# Use cached CSV (skip download)
python -m scripts.ingest.run_bronze_ingestion --provider provider_name --use-raw-cache
```

## Known Quirks

1. **Floating timestamps**: Socrata may return timestamps as floats (epoch)
2. **Null representation**: Empty strings or "null" text
3. **Large file sizes**: May need chunked download for >100M records
4. **Rate limits**: Socrata has per-IP rate limits
