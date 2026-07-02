---
type: api-endpoint
provider: Provider Name
endpoint_id: endpoint_name

# API Configuration
endpoint_pattern: "/api/v1/resource"
method: GET
format: json
auth: inherit
response_key: null

# Query Parameters
default_query:
  param1: value1
required_params: [id]

# Pagination
pagination_type: none
bulk_download: false

# Spark JSON Reading
# object = flat JSON object, one record per file
# Use when API returns: {"field1": "value1", "field2": "value2", ...}
json_structure: object
json_structure_comment: "Flat object with fields. Direct struct access in Spark."

# Metadata
domain: domain_name
legal_entity_type: vendor
subject_entity_tags: [tag1]
data_tags: [reference, tag2]
status: active
update_cadence: daily
last_verified:
last_reviewed:
notes: "One API call per entity"

# Storage Configuration
bronze: provider_name/table_name
partitions: []
write_strategy: upsert
key_columns: [primary_key]
date_column: null

# Schema
# Format: [field_name, type, source_field, nullable, description, {options}]
schema:
  # Primary key
  - [id, string, Id, false, "Unique identifier"]

  # String fields
  - [name, string, Name, true, "Entity name"]

  # Numeric fields (require coercion from string)
  - [amount, double, Amount, true, "Amount value", {coerce: double}]
  - [count, long, Count, true, "Count value", {coerce: long}]

  # Generated fields
  - [entity_type, string, _generated, false, "Entity type constant", {default: "type_value"}]
---

## Description

Brief description of what this endpoint provides.

## API Notes

- Note about authentication
- Note about rate limits
- Note about response format

### Example Response

```json
{
  "Id": "12345",
  "Name": "Example Entity",
  "Amount": "1000.50",
  "Count": "42"
}
```

## Homelab Usage

```bash
# Example ingestion command
python -m scripts.ingest.run_bronze_ingestion --provider provider_name --endpoints endpoint_name
```

## Known Quirks

1. **Quirk 1**: Description
2. **Quirk 2**: Description
