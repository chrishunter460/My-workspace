---
type: api-endpoint
provider:                               # Must match a provider note (e.g., "Alpha Vantage")
endpoint_id:                            # Unique code identifier (e.g., "company_overview")

# API Configuration
endpoint_pattern:                       # URL path template (e.g., "/resource/{view_id}.json")
method: GET                             # HTTP method
format: json                            # json | csv | xml | geojson
auth: inherit                           # inherit | none | api-key | basic
response_key:                           # JSON key containing data (null = entire response)

# Query Parameters
default_query: {}                       # Default query params (e.g., {function: OVERVIEW})
required_params: []                     # Required parameters (e.g., [symbol])

# Pagination
pagination_type: none                   # none | offset | cursor | page
multiple_endpoints: false               # Whether multiple sources required for full data
bulk_download: false                    # Whether bulk downloads are available

# Metadata
domain:                                 # finance | securities | geospatial | housing | etc.
legal_entity_type:                      # municipal | county | federal | vendor
subject_entity_tags: []                 # Who is the data about [corporate, municipal, property]
data_tags: []                           # Descriptive tags [time-series, public, daily, reference]
status: active                          # active | flaky | deprecated
update_cadence: irregular               # daily | weekly | monthly | quarterly | annual | irregular
last_verified:
last_reviewed:
notes:

# ============================================
# STORAGE CONFIGURATION
# (Replaces storage.json entries for this endpoint)
# ============================================
bronze:                                 # Bronze table name (e.g., "company_reference")
partitions: []                          # Partition columns (e.g., [asset_type])
write_strategy: append                  # append (preserves data) | upsert (merge) | overwrite
key_columns: []                         # Primary key columns for deduplication (e.g., [ticker])
date_column:                            # Date column for incremental loads

# ============================================
# SCHEMA DEFINITION
# ============================================
# Format: [field_name, type, source_field, nullable, description, {options}]
#
# Basic format: [name, type, source, nullable, description]
# Enhanced format adds options dict as 6th element
#
# Types: string | long | double | boolean | date | timestamp | int
#
# Source field values:
#   - API field name (e.g., "Symbol", "MarketCapitalization")
#   - "_generated" for fields set by pipeline (e.g., report_type)
#   - "_computed" for fields calculated from expression
#   - "_key" for dict key extraction (nested responses)
#   - "_param" for request parameter injection
#   - "_na" for unavailable fields (set default)
#
# Options (optional dict as 6th element):
#   - transform: String transform (e.g., "zfill(10)", "to_date(yyyy-MM-dd)")
#   - coerce: Type coercion for numeric strings (e.g., "double", "long")
#   - expr: Expression for computed fields (e.g., "(high + low + close) / 3")
#   - default: Default value when source is null

schema:
  # Basic fields
  - [ticker, string, Symbol, false, "Stock ticker"]

  # With transform (pad CIK to 10 digits)
  - [cik, string, CIK, true, "SEC identifier", {transform: "zfill(10)"}]

  # With coercion (convert string to numeric)
  - [market_cap, double, MarketCapitalization, true, "Market cap", {coerce: double}]

  # Computed field (calculated from other fields)
  - [vwap, double, _computed, true, "VWAP approximation", {expr: "(high + low + close) / 3"}]

  # Generated with default
  - [is_active, boolean, _generated, false, "Active status", {default: true}]
---

## Description

What data this endpoint returns.

## Schema

```dataview
TABLE
  s[0] AS Field,
  s[1] AS Type,
  s[2] AS Source,
  s[3] AS Nullable,
  s[4] AS Description,
  s[5] AS Options
FROM ""
FLATTEN schema AS s
WHERE file.path = this.file.path

```



## Request Notes

Query params, limits, filters, authentication details.

## Homelab Usage

Cron jobs, ingest scripts, storage paths, recommended refresh cadence.

## Known Quirks

Downtime patterns, format changes, schema drift, error handling notes.
