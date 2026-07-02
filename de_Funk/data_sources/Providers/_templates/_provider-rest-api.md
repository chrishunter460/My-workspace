---
type: api-provider
provider_id: provider_name
provider: Provider Display Name

# API Configuration
api_type: rest
base_url: https://api.example.com
homepage: https://example.com/docs

# Authentication
# Options: api-key, oauth2, basic, none
auth_model: api-key
env_api_key: PROVIDER_API_KEYS
env_api_key_comment: "Comma-separated list of API keys for rotation"

# Rate Limiting
rate_limit_per_sec: 1.0
rate_limit_comment: "Conservative rate to stay within limits"

# Default Headers (if API key goes in header)
default_headers: {}
# Or for header-based auth:
# default_headers:
#   X-Api-Key: "${PROVIDER_API_KEY}"

# Provider-specific settings
# These are accessible via provider.get_provider_setting('key')
provider_settings:
  save_raw: true
  save_raw_comment: "Save raw API responses for reprocessing"
  custom_setting: value
  custom_setting_comment: "Description of custom setting"

# Endpoints to ingest (list of endpoint_ids)
endpoints:
  - endpoint_one
  - endpoint_two
  - endpoint_three
endpoints_comment: "Available endpoints for this provider"

# Models Fed (Silver layer models populated by this provider)
models:
  - model_one
  - model_two

# Metadata
category: commercial
legal_entity_type: vendor
data_domains: [domain1, domain2]
data_tags: [tag1, tag2]
status: active
bulk_download: false
last_verified:
last_reviewed:
notes:
---

## Description

Brief description of the data provider and what data they offer.

## API Notes

- Authentication method
- Response format (JSON/CSV)
- Any special considerations

### Rate Limits

| Tier | Calls/Minute | Calls/Day | Cost |
|------|--------------|-----------|------|
| Free | X | Y | $0 |
| Paid | X | Unlimited | $Z/mo |

### Key Endpoints by Category

| Category | Endpoints | Bronze Tables |
|----------|-----------|---------------|
| Category1 | endpoint_one | table_one |
| Category2 | endpoint_two | table_two |

## Homelab Usage Notes

- Recommended ingestion cadence
- Data quality notes
- Any preprocessing required

### Raw Data Storage

When `save_raw: true`, raw API responses are saved to:
```
storage/raw/{provider_id}/{endpoint_id}/{identifier}.json
```

This enables:
- Reprocessing without API calls
- Debugging data issues
- Spark native JSON reading

## Python Provider Implementation

```python
from datapipelines.providers.{provider_name} import create_{provider_name}_provider

provider = create_{provider_name}_provider(spark, repo_root, storage_path)
provider.set_identifiers(["ID1", "ID2"])

# Use with IngestorEngine
from datapipelines.base.ingestor_engine import IngestorEngine
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["endpoint_one"])
```

## Known Quirks

1. **Quirk 1**: Description and workaround
2. **Quirk 2**: Description and workaround
