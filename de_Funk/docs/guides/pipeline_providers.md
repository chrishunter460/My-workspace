---
type: reference
description: "Guide for adding data providers and running the ingestion pipeline"
---

# Pipeline & Providers Guide

> How to add a new data source, configure endpoints, and run the full pipeline: Download → Bronze → Silver.

## Architecture

```
data_sources/Providers/*.md       data_sources/Endpoints/*/*.md
         │                                  │
         ▼                                  ▼
    ProviderConfig                    EndpointConfig
         │                                  │
         └──────────┬───────────────────────┘
                    ▼
         create_socrata_provider(provider_id)
                    │
                    ▼
           SocrataBaseProvider
           ├── download_all_csv()  → Raw CSVs
           └── IngestorEngine.run() → Bronze Delta
                    │
                    ▼
              BuildSession.build() → Silver Delta
```

## Adding a New Socrata Provider

All Socrata-based providers (Chicago, Cook County, etc.) are now **config-driven** — no Python subclass needed. Just add markdown files:

### Step 1: Provider Config

Create `data_sources/Providers/My Portal.md`:

```yaml
---
type: api-provider
provider_id: my_portal
provider: My Data Portal

api_type: soda
base_url: https://data.myportal.org
homepage: https://data.myportal.org

auth:
  type: app_token
  env_key: MY_PORTAL_APP_TOKEN

rate_limit_per_sec: 5.0
---

## My Data Portal

Description of the data source.
```

### Step 2: Endpoint Configs

Create one file per endpoint in `data_sources/Endpoints/My Portal/Category/Dataset Name.md`:

```yaml
---
type: api-endpoint
provider: My Data Portal
endpoint_id: my_dataset

endpoint_pattern: /resource/xxxx-yyyy.json
method: GET
format: json

pagination_type: offset
bulk_download: true
download_method: csv

domain: my_domain
status: active

bronze: my_portal
partitions: []
write_strategy: overwrite
key_columns: [id]

schema:
  - [id, string, id, false, "Primary key"]
  - [name, string, name, true, "Display name"]
  - [value, double, value, true, "Metric value"]
---
```

### Step 3: Run Ingestion

```python
from de_funk.pipelines.base.socrata_provider import create_socrata_provider
from de_funk.pipelines.base.ingestor_engine import IngestorEngine

provider = create_socrata_provider(
    "my_portal",
    spark=spark,
    docs_path=repo_root,
    storage_path=storage_path,
)

# Download raw CSVs first
provider.download_all_csv()

# Then ingest to Bronze
engine = IngestorEngine(provider, storage_cfg)
results = engine.run()
print(f"{results.total_records:,} records, {results.total_errors} errors")
```

## Adding a Non-Socrata Provider

For APIs that aren't Socrata (REST, GraphQL, etc.), extend `BaseProvider`:

```python
from de_funk.pipelines.base.provider import BaseProvider

class MyProvider(BaseProvider):
    PROVIDER_NAME = "My Custom API"

    def _setup(self):
        """Initialize API client."""
        self.client = MyAPIClient(self.api_key)

    def list_work_items(self, **kwargs):
        """Return list of things to fetch."""
        return ["dataset_a", "dataset_b"]

    def fetch(self, work_item, **kwargs):
        """Fetch data for one work item. Returns list of dicts."""
        return self.client.get(work_item)

    def normalize(self, records, work_item):
        """Convert list of dicts to Spark DataFrame."""
        return self.spark.createDataFrame(records)

    def get_table_name(self, work_item):
        """Bronze table name for this work item."""
        return f"my_provider/{work_item}"
```

See `AlphaVantageProvider` for a full example of a custom provider.

## Pipeline Operations

### Download Only (Raw CSVs)

```python
provider = create_socrata_provider("chicago", ...)
results = provider.download_all_csv()
# CSVs saved to /shared/storage/raw/chicago/
```

### Bronze Only (Raw → Delta)

```python
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["crimes", "arrests"])
```

### Silver Build (Bronze → Dimensional)

```python
from de_funk.app import DeFunk

app = DeFunk.from_config("configs")
session = app.build_session(spark=spark)

# Build specific models
for model in ["temporal", "municipal.entity", "municipal.public_safety"]:
    builder = BuilderRegistry.all()[model]
    result = builder(session).build()
    print(result)
```

### Full Pipeline (Download → Bronze → Silver)

```python
# 1. Download
provider = create_socrata_provider("chicago", spark=spark, docs_path=repo_root,
                                    storage_path=storage_path)
provider.download_all_csv()

# 2. Bronze
engine = IngestorEngine(provider, storage_cfg)
engine.run()

# 3. Silver
app = DeFunk.from_config("configs")
session = app.build_session(spark=spark)
for model in build_order:
    BuilderRegistry.all()[model](session).build()
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `0 endpoints discovered` | Provider name mismatch | Check `provider:` in endpoint .md matches provider .md `provider:` field |
| `HTTP 403` on CSV download | API token missing or expired | Set `MY_PORTAL_APP_TOKEN` in `.env` |
| `HTTP 400` on CSV download | Dataset is non-tabular (KMZ, shapefile) | Find the tabular version of the dataset |
| `field larger than field limit` | Large geometry in CSV, Python csv.reader can't handle | Use `download_method: csv` + Spark reads (bypasses Python csv) |
| `Path does not exist` during Silver build | Bronze table not ingested | Run ingestion for that endpoint first |
| Row count mismatch after rebuild | DISTINCT/GROUP BY variance | Normal for aggregation tables — source data freshness differs |

## Configuration Files

| File | What It Controls |
|---|---|
| `configs/storage.json` | Bronze/Silver root paths, DuckDB memory, API limits |
| `configs/run_config.json` | Provider list, endpoints, rate limits, build order, profiles |
| `data_sources/Providers/*.md` | Provider base URLs, auth, rate limits |
| `data_sources/Endpoints/*/*.md` | Endpoint resource IDs, schemas, write strategies |
| `.env` | API keys (`CHICAGO_APP_TOKEN`, `ALPHA_VANTAGE_API_KEY`) |
