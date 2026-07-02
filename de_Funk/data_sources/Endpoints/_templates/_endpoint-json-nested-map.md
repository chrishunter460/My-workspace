---
type: api-endpoint
provider: Provider Name
endpoint_id: endpoint_name

# API Configuration
endpoint_pattern: "/api/v1/timeseries"
method: GET
format: json
auth: inherit
# IMPORTANT: response_key tells Spark which nested field contains the map
response_key: "Data Series"

# Query Parameters
default_query:
  outputsize: full
required_params: [symbol]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
# nested_map = Keys are dates/IDs, values are objects
# Use when API returns: {"Data Series": {"2024-01-15": {...}, "2024-01-14": {...}}}
# Spark will explode the map into (key, value) rows
json_structure: nested_map
json_structure_comment: "Date/ID strings as keys → data objects as values. Requires explode() in Spark."

# Metadata
domain: timeseries
legal_entity_type: vendor
subject_entity_tags: [tag1]
data_tags: [time-series, daily]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "Full history in single call"

# Storage Configuration
bronze: provider_name/table_name
partitions: [year]
write_strategy: append
key_columns: [symbol, date]
date_column: date

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  # The map key becomes a column (use _key as source)
  - [date, date, _key, false, "Date from response dict key", {transform: "to_date(yyyy-MM-dd)"}]

  # Symbol comes from request parameter
  - [symbol, string, _param, false, "Symbol from request param"]

  # Partition columns (computed from date)
  - [year, int, _computed, false, "Year extracted from date", {expr: "extract(year from date)"}]
  - [month, int, _computed, false, "Month extracted from date", {expr: "extract(month from date)"}]

  # Data fields from the nested object (require coercion from string)
  - [open, double, "1. open", true, "Opening value", {coerce: double}]
  - [high, double, "2. high", true, "High value", {coerce: double}]
  - [low, double, "3. low", true, "Low value", {coerce: double}]
  - [close, double, "4. close", true, "Closing value", {coerce: double}]
  - [volume, double, "5. volume", true, "Volume", {coerce: double}]

  # Computed field
  - [midpoint, double, _computed, true, "Midpoint", {expr: "(high + low) / 2"}]
---

## Description

Time-series endpoint where the response contains a nested map with date/ID keys.

## API Notes

- Response is a nested structure with dates as keys
- All numeric values returned as strings
- Single API call returns full history

### Example Response

```json
{
  "Meta Data": {
    "1. Information": "Daily Data",
    "2. Symbol": "AAPL"
  },
  "Data Series": {
    "2024-01-15": {
      "1. open": "185.00",
      "2. high": "187.50",
      "3. low": "184.25",
      "4. close": "186.75",
      "5. volume": "52341200"
    },
    "2024-01-14": {
      "1. open": "183.00",
      "2. high": "184.50",
      "3. low": "182.25",
      "4. close": "183.75",
      "5. volume": "48123400"
    }
  }
}
```

## Spark Reading Strategy

1. `spark.read.json()` reads all files
2. Extract `response_key` field ("Data Series")
3. `explode(map)` converts to (date, struct) rows
4. Flatten struct fields
5. Apply field mappings and type coercions

## Homelab Usage

```bash
python -m scripts.ingest.run_bronze_ingestion --provider provider_name --endpoints endpoint_name
```

## Known Quirks

1. **All values are strings**: Must coerce to numeric types
2. **Date as dict key**: Extracted via `_key` source marker
3. **Full history is large**: Watch memory during bulk ingestion
