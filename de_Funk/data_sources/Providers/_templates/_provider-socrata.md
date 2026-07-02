---
type: api-provider
provider_id: city_data_portal
provider: City Data Portal

# API Configuration
# Socrata uses SODA (Socrata Open Data API)
api_type: socrata
base_url: https://data.city.gov
homepage: https://data.city.gov

# Authentication
# Socrata supports app tokens (optional but recommended for higher rate limits)
auth_model: app-token
env_api_key: CITY_APP_TOKEN
env_api_key_comment: "Socrata app token for higher rate limits (optional)"

# Rate Limiting
# Without token: ~1 req/sec, With token: ~10 req/sec
rate_limit_per_sec: 5.0
rate_limit_comment: "With app token. Without: 0.5/sec"

# Default Headers
default_headers:
  X-App-Token: "${CITY_APP_TOKEN}"

# Provider-specific settings
provider_settings:
  save_raw: true
  save_raw_comment: "Save raw CSV downloads for Spark reading"
  default_limit: 50000
  default_limit_comment: "Records per API page"
  csv_chunk_size: 1000000
  csv_chunk_size_comment: "Records per CSV download chunk"

# Endpoints to ingest
endpoints:
  - dataset_one
  - dataset_two
endpoints_comment: "Socrata dataset identifiers"

# Models Fed
models:
  - city_model

# Metadata
category: public
legal_entity_type: government
data_domains: [municipal, finance, safety]
data_tags: [open-data, government]
status: active
bulk_download: true
last_verified:
last_reviewed:
notes: "Socrata Open Data Portal"
---

## Description

Open data portal powered by Socrata SODA API. Provides access to municipal datasets.

## API Notes

- **Socrata 4x4 IDs**: Each dataset has a unique identifier (e.g., `xxxx-xxxx`)
- **Dual Access**: JSON API for small queries, CSV bulk download for large datasets
- **SoQL**: Socrata Query Language for filtering/aggregation

### Rate Limits

| Access | Calls/Second | Notes |
|--------|--------------|-------|
| Anonymous | ~1 | IP-based throttling |
| App Token | ~10 | Recommended for bulk |

### Endpoint Pattern

```
JSON: https://data.city.gov/resource/{view_id}.json?$limit=50000&$offset=0
CSV:  https://data.city.gov/resource/{view_id}.csv
```

## Socrata-Specific Features

### Multi-Year Datasets

Some datasets have different view_ids per year. Define in endpoint markdown:

```markdown
| Year | view_id | Format | Notes |
|------|---------|--------|-------|
| 2024 | xxxx-xxxx | CSV | current |
| 2023 | yyyy-yyyy | CSV | complete |
```

### CSV vs JSON

| Criteria | Use JSON | Use CSV |
|----------|----------|---------|
| Records | < 100k | > 100k |
| Speed | Slower (paginated) | Faster (bulk) |
| Memory | Higher (in-memory) | Lower (streaming) |
| Spark | Python batching | `spark.read.csv()` |

### Date Formats

Socrata uses multiple date formats:
- ISO 8601: `2024-01-15T00:00:00.000`
- Floating timestamp: `1705276800` (epoch seconds)
- Date only: `2024-01-15`

## Homelab Usage

```bash
# Full ingestion with CSV bulk download
python -m scripts.ingest.run_bronze_ingestion \\
  --provider city_data_portal \\
  --endpoints dataset_one

# Use cached CSV (Spark native reading)
python -m scripts.ingest.run_bronze_ingestion \\
  --provider city_data_portal \\
  --use-raw-cache
```

## Python Provider Implementation

Socrata providers extend `SocrataBaseProvider`:

```python
from datapipelines.base.socrata_provider import SocrataBaseProvider

class CityDataProvider(SocrataBaseProvider):
    PROVIDER_NAME = "City Data Portal"

    def __init__(self, spark, docs_path, storage_path=None):
        super().__init__(
            provider_id="city_data_portal",
            spark=spark,
            docs_path=docs_path,
            storage_path=storage_path
        )
```

## Known Quirks

1. **Floating timestamps**: Some date fields are epoch floats
2. **Null handling**: Empty strings or literal "null"
3. **Schema changes**: Columns may be added/removed between years
4. **Large downloads**: May timeout - use chunked download
