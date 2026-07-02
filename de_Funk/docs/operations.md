# Operations Guide

A practical, end-to-end walkthrough of the de_Funk data pipeline. This guide takes you from a fresh clone to a fully populated data warehouse with a running API server and Obsidian plugin. Every code block is something you can run.

---

## Prerequisites

Before anything else, make sure your environment is ready.

### System Requirements

| Dependency   | Version | Purpose                          |
|--------------|---------|----------------------------------|
| Python       | 3.10+   | Core runtime                     |
| Java         | 17+     | Apache Spark (Silver builds)     |
| Node.js      | 18+     | Obsidian plugin build toolchain  |
| DuckDB       | 0.9+    | Analytics queries (API backend)  |

### Install Python Dependencies

The project uses optional dependency groups defined in `pyproject.toml`. Pick the group that matches your use case, or install everything.

```bash
# Just the API server (FastAPI + uvicorn)
pip install -e ".[api]"

# Just the Spark pipeline (pyspark + delta-spark)
pip install -e ".[spark]"

# Everything (Spark, API, UI, dev tools)
pip install -e ".[all]"
```

The `-e` flag installs in editable mode so the `de_funk` package resolves from `src/de_funk/` without copying files.

### Configure API Keys

Copy the example environment file, then get your free keys.

```bash
cp .env.example .env
```

All three data providers offer **free API keys** — no credit card required.

#### 1. Alpha Vantage (securities data) — Required

1. Go to https://www.alphavantage.co/support/#api-key
2. Fill in the form (name, email, use case — "academic/personal" works)
3. Your key appears immediately on screen

```bash
# Paste into .env
ALPHA_VANTAGE_API_KEYS=your_key_here
```

Free tier: 25 requests/day, 5 requests/minute. You can provide multiple keys separated by commas for rotation.

#### 2. Chicago / Cook County Data Portal (municipal data) — Optional

1. Go to https://data.cityofchicago.org/profile/app_tokens
2. Create a Socrata account and generate an app token
3. The same token works for both Chicago and Cook County portals

```bash
CHICAGO_API_KEYS=your_app_token_here
COOK_COUNTY_API_KEYS=your_app_token_here    # Same Socrata token works
```

Without a token you can still query, just at lower rate limits.

### Verify Your Setup

Use `ConfigLoader` to confirm the framework can find everything it needs.

```python
from de_funk.config.loader import ConfigLoader

loader = ConfigLoader()
config = loader.load()

print(f"Repo root:       {config.repo_root}")
print(f"Connection type: {config.connection.type}")
print(f"Log level:       {config.log_level}")
```

Expected output (paths will vary):

```
Repo root:       /home/you/PycharmProjects/de_Funk
Connection type: duckdb
Log level:       INFO
```

If `ConfigLoader` cannot locate the repository root, it walks up the directory tree looking for a folder that contains `configs/`, `src/`, and `.git/`. You can also pass `repo_root` explicitly:

```python
loader = ConfigLoader(repo_root=Path("/home/you/PycharmProjects/de_Funk"))
```

To load just the storage configuration (used by pipeline scripts):

```python
storage_cfg = loader.load_storage()
print(storage_cfg["roots"]["bronze"])   # e.g. storage/bronze
print(storage_cfg["roots"]["silver"])   # e.g. /shared/storage/silver
```

---

## Step 1: Seed Foundation Data

Seeding is a one-time operation that populates foundational datasets. The calendar dimension and the geography seed are prerequisites for the rest of the pipeline.

### Seed the Calendar Dimension

The calendar seed generates one row per day from 2000 through 2050, with derived columns (day of week, fiscal quarter, is_trading_day, etc.).

```bash
python -m scripts.seed.seed_calendar --storage-path /shared/storage
```

This writes a Delta Lake table to `{storage_path}/bronze/seeds/calendar/`.

### Seed Geography Data

The geography seed loads reference data for Chicago community areas, wards, and Cook County townships. These provide the geographic dimension scaffolding that municipal and county models depend on.

```bash
python -m scripts.seed.seed_geography --storage-path /shared/storage
```

This writes to `{storage_path}/bronze/seeds/geography/`.

If you want to force a re-seed (overwrite existing data):

```bash
python -m scripts.seed.seed_geography --storage-path /shared/storage --force
```

### What the Output Looks Like

After seeding, the Bronze layer has this structure:

```
/shared/storage/bronze/
  seeds/
    calendar/
      _delta_log/           # Delta Lake transaction log
      part-00000-*.parquet  # Data files
    geography/
      _delta_log/
      part-00000-*.parquet
```

### Python Equivalent

Under the hood, the seed scripts spin up a Spark session and write DataFrames. If you want to do this programmatically:

```python
from de_funk.orchestration.common.spark_session import get_spark

spark = get_spark("Seeding")

# The seed scripts build a DataFrame and write it as Delta.
# Calendar: generates dates 2000-01-01 through 2050-12-31 with derived columns.
# Geography: loads Chicago community areas, wards, Cook County townships.

# To verify the seed landed:
df = spark.read.format("delta").load("/shared/storage/bronze/seeds/calendar")
print(f"Calendar rows: {df.count()}")   # ~18,628 rows (51 years * 365.25 days)

df = spark.read.format("delta").load("/shared/storage/bronze/seeds/geography")
print(f"Geography rows: {df.count()}")  # Community areas + wards + townships

spark.stop()
```

---

## Step 2: Bronze Ingestion

Bronze ingestion fetches data from the Chicago Data Portal and Cook County Data Portal (both Socrata APIs) and writes it to Delta Lake tables in `storage/bronze/`. Chicago datasets are large but the Socrata API supports efficient offset-based pagination.

### Providers

The pipeline uses two Socrata-based providers:

| Provider | Portal | Key Datasets |
|----------|--------|--------------|
| Chicago Data Portal | data.cityofchicago.org | Crimes, building permits, food inspections, business licenses, contracts, budget, CTA ridership, traffic, 311 requests |
| Cook County Data Portal | datacatalog.cookcountyil.gov | Property assessments, parcel sales, property locations |

### CLI Usage — Chicago

The Chicago provider uses `IngestorEngine` with `ChicagoProvider`. You can ingest all endpoints or specific ones:

```bash
# Ingest all Chicago endpoints (crimes, permits, inspections, licenses, etc.)
python -m scripts.ingest.run_chicago_ingestion --storage-path /shared/storage

# Ingest specific endpoints
python -m scripts.ingest.run_chicago_ingestion --endpoints crimes,food_inspections

# Ingest finance data
python -m scripts.ingest.run_chicago_ingestion \
    --endpoints contracts,budget_appropriations,budget_revenue,budget_positions

# Ingest regulatory + operations + transportation
python -m scripts.ingest.run_chicago_ingestion \
    --endpoints food_inspections,building_violations,business_licenses,311_requests,cta_l_ridership,traffic

# Load from existing raw CSVs (skip download) or preserve them for debugging
python -m scripts.ingest.run_chicago_ingestion --load-from-raw
python -m scripts.ingest.run_chicago_ingestion --preserve-raw
```

### CLI Usage — Cook County

```bash
# Ingest all Cook County endpoints (assessments, sales, property locations)
python -m scripts.ingest.run_cook_county_ingestion --storage-path /shared/storage

# Ingest specific endpoints
python -m scripts.ingest.run_cook_county_ingestion --endpoints assessments,parcel_sales

# Property sales only
python -m scripts.ingest.run_cook_county_ingestion --endpoints parcel_sales
```

### Endpoint Name Mapping

Chicago Data Portal endpoints:

| You Type | Bronze Table | Domain Model |
|----------|-------------|--------------|
| `crimes` | `chicago/crimes` | municipal.public_safety |
| `building_permits` | `chicago/building_permits` | municipal.housing |
| `food_inspections` | `chicago/food_inspections` | municipal.regulatory |
| `building_violations` | `chicago/building_violations` | municipal.regulatory |
| `business_licenses` | `chicago/business_licenses` | municipal.regulatory |
| `contracts` | `chicago/contracts` | municipal.finance |
| `budget_appropriations` | `chicago/budget_appropriations` | municipal.finance |
| `budget_revenue` | `chicago/budget_revenue` | municipal.finance |
| `budget_positions` | `chicago/budget_positions` | municipal.finance |
| `cta_l_ridership` | `chicago/cta_l_ridership` | municipal.transportation |
| `traffic` | `chicago/traffic` | municipal.transportation |
| `311_requests` | `chicago/311_requests` | municipal.operations |

Cook County Data Portal endpoints:

| You Type | Bronze Table | Domain Model |
|----------|-------------|--------------|
| `assessments` | `cook_county/assessments` | county.property |
| `parcel_sales` | `cook_county/parcel_sales` | county.property |
| `property_locations` | `cook_county/property_locations` | county.property |

### Python Equivalent

If you want to drive ingestion from Python code rather than the CLI:

```python
from de_funk.orchestration.common.spark_session import get_spark
from de_funk.pipelines.providers.chicago import create_chicago_provider
from de_funk.pipelines.providers.cook_county import create_cook_county_provider
from de_funk.pipelines.base.ingestor_engine import IngestorEngine
from de_funk.utils.repo import get_repo_root
from pathlib import Path
import json

repo_root = get_repo_root()
storage_path = Path("/shared/storage")
spark = get_spark(app_name="BronzeIngestion")

with open(repo_root / "configs" / "storage.json") as f:
    storage_cfg = json.load(f)
storage_cfg["roots"] = {
    k: str(storage_path / v.replace("storage/", ""))
    for k, v in storage_cfg["roots"].items()
}

# --- Chicago Data Portal ---
provider = create_chicago_provider(spark=spark, docs_path=repo_root, storage_path=storage_path)
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["crimes", "food_inspections", "building_permits"], silent=False)
print(f"Chicago errors: {results.total_errors}")

# --- Cook County Data Portal ---
provider = create_cook_county_provider(spark=spark, docs_path=repo_root, storage_path=storage_path)
engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["assessments", "parcel_sales"], silent=False)
print(f"Cook County errors: {results.total_errors}")

spark.stop()
```

### What the Output Looks Like

After ingesting Chicago and Cook County data, each endpoint becomes a Delta Lake table under `bronze/`:

```
/shared/storage/bronze/
  chicago/
    crimes/                         # case_number, date, iucr, block, ward, community_area, ...
    food_inspections/               # inspection_id, facility, result, violations, ...
    building_permits/               # permit_number, issue_date, work_description, ...
    business_licenses/              # license_number, business_activity, ...
    contracts/                      # contract_number, vendor, amount, ...
    budget_appropriations/          # department, fund, amount, ...
    budget_revenue/                 # fund, source, amount, ...
    311_requests/                   # sr_number, sr_type, created_date, ward, ...
    cta_l_ridership/                # station_id, date, rides, ...
    traffic/                        # segment_id, date, traffic_volume, ...
  cook_county/
    assessments/                    # pin, year, assessed_value, township_code, ...
    parcel_sales/                   # pin, sale_date, sale_price, deed_type, ...
```

Each directory contains a `_delta_log/` folder and one or more `.snappy.parquet` data files.

---

## Step 3: Silver Build

The Silver build transforms raw Bronze data into dimensional models (dimensional models (snowflake schema)). Each domain model reads from Bronze, applies graph-defined transformations, and writes dimension and fact tables to the Silver layer.

### CLI Usage

```bash
# Build all models (discovers builders from domains/, resolves dependencies automatically)
python -m scripts.build.build_models

# Build specific models (dependencies are auto-included)
python -m scripts.build.build_models --models municipal.public_safety municipal.finance

# Build all municipal + county models
python -m scripts.build.build_models \
    --models municipal.finance municipal.public_safety municipal.regulatory \
            municipal.transportation municipal.operations municipal.geospatial \
            county.property

# Dry run -- show the build order without actually building
python -m scripts.build.build_models --dry-run

# Restrict date range
python -m scripts.build.build_models --date-from 2020-01-01 --date-to 2024-12-31

# Point at shared NFS storage
python -m scripts.build.build_models --storage-root /shared/storage

# Skip dependency builds (assumes they already exist)
python -m scripts.build.build_models --models municipal.public_safety --skip-deps

# Verbose output (detailed logging per table)
python -m scripts.build.build_models --verbose
```

### Build Order

The builder discovers all domain configs in `domains/models/` and topologically sorts them by their `depends_on` declarations. A typical build order for municipal models:

```
temporal -> geospatial -> municipal.entity -> municipal.geospatial -> municipal.finance
temporal -> geospatial -> municipal.entity -> municipal.geospatial -> municipal.public_safety
temporal -> county.geospatial -> county.property
```

If you request `--models municipal.public_safety`, the builder automatically prepends its transitive dependencies (`temporal`, `geospatial`, `municipal.entity`, `municipal.geospatial`) unless you pass `--skip-deps`.

### Expected Output

```
======================================================================
  Building Silver Layer Models
======================================================================

  ✓ temporal: 1 dims, 0 facts (3.2s)
  ✓ geospatial: 1 dims, 0 facts (2.1s)
  ✓ municipal.entity: 1 dims, 0 facts (1.8s)
  ✓ municipal.geospatial: 4 dims, 0 facts (5.3s)
  ✓ municipal.finance: 6 dims, 3 facts (18.7s)
  ✓ municipal.public_safety: 2 dims, 2 facts (14.2s)
  ✓ municipal.regulatory: 2 dims, 3 facts (11.6s)
  ✓ municipal.operations: 2 dims, 1 facts (8.4s)
  ✓ municipal.transportation: 1 dims, 3 facts (9.1s)
  ✓ county.geospatial: 2 dims, 0 facts (3.0s)
  ✓ county.property: 3 dims, 2 facts (15.9s)

----------------------------------------------------------------------
  Complete: 11/11 models built (93.3s)
----------------------------------------------------------------------
```

### Python Equivalent

The build script is a thin CLI wrapper around `BuilderRegistry`. Here is the programmatic equivalent:

```python
from de_funk.orchestration.common.spark_session import get_spark
from de_funk.models.base.builder import BuilderRegistry, BuildContext
from de_funk.models.base.domain_builder import discover_domain_builders
from de_funk.config.loader import ConfigLoader
from de_funk.utils.repo import get_repo_root

repo_root = get_repo_root()
discover_domain_builders(repo_root)

# Get the topologically-sorted build order (includes transitive dependencies)
order = BuilderRegistry.get_build_order(["municipal.public_safety", "municipal.finance"])
print(f"Build order: {' -> '.join(order)}")
# e.g.: temporal -> geospatial -> municipal.entity -> municipal.geospatial
#        -> municipal.public_safety -> municipal.finance

spark = get_spark("SilverBuild")
loader = ConfigLoader(repo_root=repo_root)
context = BuildContext(
    spark=spark, storage_config=loader.load_storage(),
    repo_root=repo_root, date_from="2020-01-01", date_to="2024-12-31",
)

for model_name in order:
    builder = BuilderRegistry.get(model_name)(context)
    result = builder.build()
    print(f"{result.model_name}: {result.dimensions} dims, "
          f"{result.facts} facts ({result.duration_seconds:.1f}s)")

spark.stop()
```

### What the Output Looks Like

After building, the Silver layer has this structure (paths from `configs/storage.json`):

```
/shared/storage/silver/
  temporal/
    dims/dim_calendar/                    # Calendar dimension
  municipal/chicago/
    geospatial/dims/
      dim_community_area/                 # 77 community areas
      dim_ward/                           # 50 city wards
      dim_patrol_district/                # 22 patrol districts
      dim_patrol_area/                    # ~280 patrol areas (beats)
    finance/
      dims/{dim_department, dim_vendor, dim_contract, dim_fund, dim_chart_of_accounts}/
      facts/{fact_ledger_entries, fact_budget_events, fact_property_tax}/
    public_safety/
      dims/{dim_crime_type, dim_location_type}/
      facts/{fact_crimes, fact_arrests}/
    regulatory/
      dims/{dim_facility, dim_inspection_type}/
      facts/{fact_food_inspections, fact_building_violations, fact_business_licenses}/
    operations/
      dims/{dim_request_type, dim_status}/
      facts/fact_service_requests/
    transportation/
      dims/dim_transit_station/
      facts/{fact_rail_ridership, fact_bus_ridership, fact_traffic}/
  county/cook_county/
    geospatial/dims/{dim_township, dim_municipality_boundary}/
    property/
      dims/{dim_parcel, dim_property_class, dim_tax_district}/
      facts/{fact_assessed_values, fact_parcel_sales}/
```

### Rebuild a Single Model

If you need to rebuild just one model (for example after fixing a bug in its config):

```bash
python -m scripts.build.rebuild_model --model municipal.public_safety
```

---

## Step 4: Start the API Server

The API server is a FastAPI application that the Obsidian plugin queries to render exhibits. It reads Silver layer Delta tables via DuckDB.

### Start the Server

```bash
# Default: bind to 0.0.0.0:8765
python -m scripts.serve.run_api

# Development mode with auto-reload
python -m scripts.serve.run_api --port 8765 --reload

# Multiple workers (production)
python -m scripts.serve.run_api --workers 4
```

### Verify It Is Running

Open a browser to the auto-generated API docs:

```
http://localhost:8765/api/docs
```

Or check the health endpoint from the command line:

```bash
curl http://localhost:8765/api/health
```

Expected response:

```json
{"status": "ok"}
```

### API Endpoints

| Endpoint                        | Method | Purpose                                             |
|---------------------------------|--------|-----------------------------------------------------|
| `/api/health`                   | GET    | Liveness check                                      |
| `/api/domains`                  | GET    | Full field catalog for all domains                  |
| `/api/dimensions/{ref}`         | GET    | Distinct values for a field (sidebar dropdowns)     |
| `/api/query`                    | POST   | Execute exhibit queries (table data, charts, etc.)  |
| `/api/docs`                     | GET    | Interactive Swagger UI                              |
| `/api/redoc`                    | GET    | ReDoc documentation                                 |

### Python Equivalent

You can also start the server directly from Python:

```python
import uvicorn
from de_funk.api.main import create_app

app = create_app()
uvicorn.run(app, host="0.0.0.0", port=8765)
```

Or import the app factory with custom paths:

```python
from pathlib import Path
from de_funk.api.main import create_app

app = create_app(
    storage_root=Path("/shared/storage/silver"),
    domains_root=Path("/home/you/PycharmProjects/de_Funk/domains"),
)
```

### Required Configuration

The server reads `configs/storage.json` at startup and requires these keys under the `api` section:

```json
{
  "api": {
    "duckdb_memory_limit": "3GB",
    "max_sql_rows": 30000,
    "max_dimension_values": 10000,
    "max_response_mb": 4.0
  }
}
```

If any of these are missing, the server will refuse to start with a clear error message.

---

## Step 5: Query Data

Once the pipeline is complete and the API server is running, you can query data through the API or directly via DuckDB.

### Query via the API

The `/api/query` endpoint accepts a JSON body that describes what to fetch. The `type` field determines which handler processes the request.

```python
import requests

# Crime counts by community area
response = requests.post("http://localhost:8765/api/query", json={
    "type": "table.data",
    "rows": ["municipal.geospatial.community_name"],
    "measures": [
        {"key": "municipal.public_safety.crime_count", "agg": "count_distinct", "format": "#,##0"}
    ],
    "filters": [
        {"field": "municipal.public_safety.year", "operator": "eq", "value": 2024}
    ]
})

data = response.json()
print(f"Rows returned: {len(data.get('rows', []))}")
```

```python
import requests

# Budget by department
response = requests.post("http://localhost:8765/api/query", json={
    "type": "table.data",
    "rows": ["municipal.finance.department_description"],
    "measures": [
        {"key": "municipal.finance.total_budget", "agg": "sum", "format": "$#,##0.00"},
        {"key": "municipal.finance.appropriation_total", "agg": "sum", "format": "$#,##0.00"}
    ],
    "filters": [
        {"field": "municipal.finance.fiscal_year", "operator": "eq", "value": 2024}
    ]
})

data = response.json()
print(f"Departments: {len(data.get('rows', []))}")
```

```python
import requests

# Average parcel sale price by township
response = requests.post("http://localhost:8765/api/query", json={
    "type": "table.data",
    "rows": ["county.geospatial.township_name"],
    "measures": [
        {"key": "county.property.avg_sale_price", "agg": "avg", "format": "$#,##0"},
        {"key": "county.property.sale_count", "agg": "count", "format": "#,##0"}
    ],
    "filters": [
        {"field": "county.property.year", "operator": "gte", "value": 2020}
    ]
})
```

### Fetch Dimension Values

The `/api/dimensions/{ref}` endpoint returns distinct values for filter dropdowns:

```python
import requests

# Get all community area names
response = requests.get("http://localhost:8765/api/dimensions/municipal.geospatial/community_name")
values = response.json()["values"]
print(f"Community areas: {values[:5]}")
# e.g. ['ALBANY PARK', 'ARCHER HEIGHTS', 'ARMOUR SQUARE', 'ASHBURN', 'AUBURN GRESHAM']

# Get all city departments
response = requests.get("http://localhost:8765/api/dimensions/municipal.finance/department_description")
departments = response.json()["values"]
print(f"Departments: {departments[:5]}")

# Get ward numbers
response = requests.get("http://localhost:8765/api/dimensions/municipal.geospatial/ward_number")
wards = response.json()["values"]
print(f"Wards: {wards[:10]}")
```

### Get the Field Catalog

To see all available domains, tables, and fields:

```python
import requests

response = requests.get("http://localhost:8765/api/domains")
catalog = response.json()
for domain, fields in catalog.items():
    print(f"\n{domain}:")
    for field_name in list(fields.keys())[:5]:
        print(f"  {field_name}")
```

---

## Step 6: Full Pipeline Script

For production or cluster environments, the shell script `scripts/spark-cluster/run_pipeline.sh` orchestrates the entire pipeline in one command: seed, ingest Chicago and Cook County data, build Silver models.

### Prerequisites

1. A running Spark cluster (`./scripts/spark-cluster/start-master.sh` + `./scripts/spark-cluster/start-all-workers.sh`)
2. NFS mounted at `/shared/storage`
3. API keys in `.env`

### Run It

```bash
# Full pipeline (seed + ingest + Silver build)
./scripts/spark-cluster/run_pipeline.sh

# Skip seeding (already done)
./scripts/spark-cluster/run_pipeline.sh --skip-seed

# Silver build only (Bronze already populated)
./scripts/spark-cluster/run_pipeline.sh --skip-seed --skip-ingestion

# Bronze ingestion only
./scripts/spark-cluster/run_pipeline.sh --skip-seed --skip-silver
```

### All Flags

| Flag                | Effect                                |
|---------------------|---------------------------------------|
| `--storage-path`    | Override storage root (default: `/shared/storage`) |
| `--skip-seed`       | Skip calendar and geography seeding   |
| `--skip-ingestion`  | Skip Bronze ingestion                 |
| `--skip-silver`     | Skip Silver model builds              |
| `--force-seed`      | Force re-seed even if data exists     |

The script checks that the Spark master is reachable before proceeding. If the cluster is not running, it exits with instructions.

---

## Step 7: Building the Obsidian Plugin

The Obsidian plugin renders de_funk exhibit blocks inside your vault. It communicates with the API server over HTTP.

```bash
cd obsidian-plugin

# Install dependencies
npm install

# Development mode (watches for changes, rebuilds automatically)
npm run dev

# Production build
npm run build

# Build and deploy to your Obsidian vault
npm run deploy
```

The deploy script copies the built `main.js`, `manifest.json`, and `styles.css` into your vault's `.obsidian/plugins/de-funk/` directory.

The plugin requires the API server to be running at `http://localhost:8765` (configurable in plugin settings).

---

## Step 8: Testing

### Unit Tests

Fast, isolated tests with no external dependencies. Uses DuckDB in-memory mode.

```bash
pytest tests/unit/ -v
```

### Integration Tests

Tests that exercise the full stack (Spark, Delta Lake, model builds).

```bash
pytest tests/integration/ -v
```

### All Tests

```bash
pytest tests/ -v
```

### Run a Specific Test File

```bash
pytest tests/unit/test_measure_framework.py -v
```

### Test Coverage

```bash
pytest tests/ --cov=de_funk --cov-report=term-missing
```

---

## Step 9: Maintenance

### Clear Storage

Remove Bronze and/or Silver data. Always preview with `--dry-run` first.

```bash
# Show what would be deleted (both layers)
python -m scripts.maintenance.clear_storage --dry-run

# Clear Bronze only
python -m scripts.maintenance.clear_storage --bronze --dry-run
python -m scripts.maintenance.clear_storage --bronze -y    # skip confirmation prompt

# Clear Silver only
python -m scripts.maintenance.clear_storage --silver --dry-run
python -m scripts.maintenance.clear_storage --silver -y

# Clear both layers
python -m scripts.maintenance.clear_storage -y
```

### Delta Lake Maintenance

Delta Lake tables accumulate old data files over time. Run VACUUM to reclaim disk space and OPTIMIZE to compact small files for better query performance.

```bash
# Show table stats (no changes)
python -m scripts.maintenance.delta_maintenance --stats-only

# Vacuum Bronze tables (remove files older than 7 days)
python -m scripts.maintenance.delta_maintenance --vacuum

# Optimize Bronze tables (compact small files, Z-ORDER where applicable)
python -m scripts.maintenance.delta_maintenance --optimize

# Both vacuum and optimize
python -m scripts.maintenance.delta_maintenance --all

# Specific table only
python -m scripts.maintenance.delta_maintenance --table chicago_crimes --all

# Silver layer instead of Bronze
python -m scripts.maintenance.delta_maintenance --layer silver --all

# Preview only
python -m scripts.maintenance.delta_maintenance --all --dry-run

# Custom retention (default is 168 hours = 7 days)
python -m scripts.maintenance.delta_maintenance --vacuum --retention-hours 48
```

### Reset and Rebuild a Model

To reset a model's Silver tables and rebuild from Bronze:

```bash
python -m scripts.maintenance.reset_model --model municipal.public_safety
python -m scripts.build.build_models --models municipal.public_safety --skip-deps
```

### Inspect Silver Tables

View what is in the Silver layer without modifying anything:

```bash
python -m scripts.maintenance.inspect_silver
```

---

## Step 10: Diagnostics and Debugging

The `scripts/diagnostics/` directory contains focused diagnostic scripts for investigating issues.

### Check Data Layers

Scan Bronze and Silver directories and report on table contents (row counts, columns, format).

```bash
python -m scripts.diagnostics.check_data_layers
python -m scripts.diagnostics.check_data_layers --storage-path /shared/storage
```

### Storage Summary

A clean overview of all tables, their sizes, row counts, and last-modified dates.

```bash
python -m scripts.diagnostics.storage_summary
python -m scripts.diagnostics.storage_summary --bronze-only
python -m scripts.diagnostics.storage_summary --silver-only
```

### Bronze-Specific Diagnostics

```bash
python -m scripts.diagnostics.verify_bronze_data           # Data integrity
python -m scripts.diagnostics.check_bronze_counts           # Row counts per table
python -m scripts.diagnostics.diagnose_bronze_accumulation  # Duplicates, schema drift
python -m scripts.diagnostics.diagnose_bronze_data          # Raw data inspection
```

### Silver-Specific Diagnostics

```bash
python -m scripts.diagnostics.diagnose_silver_data   # NULL gaps, missing joins
python -m scripts.diagnostics.print_table_schemas     # All Silver schemas
python -m scripts.diagnostics.check_view_columns      # DuckDB view columns
```

### Model and Query Debugging

```bash
python -m scripts.diagnostics.debug_node_config       # YAML front matter parsing
python -m scripts.diagnostics.debug_measure_execution  # Measure calculation
python -m scripts.diagnostics.explore_tables           # Interactive table explorer
```

---

## Step 11: Configuration Reference

### Config Files

| File                        | Location      | Purpose                                                     |
|-----------------------------|---------------|-------------------------------------------------------------|
| `.env`                      | repo root     | API keys and environment overrides (never committed)        |
| `configs/storage.json`      | `configs/`    | Runtime config: connection backend, API query limits, storage paths, domain root overrides, table mappings |
| `configs/run_config.json`   | `configs/`    | Pipeline orchestration: provider configs, named run profiles, retry/batch settings, scheduled jobs |
| `configs/cluster.yaml`      | `configs/`    | Infrastructure: Spark cluster topology, Airflow scheduler, NFS mounts, forecasting models |

### storage.json — Runtime Configuration

Despite the name, `configs/storage.json` is the **central runtime config** for the entire system — not just storage. It controls the default backend, API query limits, storage format, path routing, and table discovery.

```json
{
  "connection": {"type": "duckdb"},
  "api": {
    "duckdb_memory_limit": "3GB",
    "max_sql_rows": 30000,
    "max_dimension_values": 10000,
    "max_response_mb": 4.0
  },
  "defaults": {"format": "delta"},
  "roots": {
    "bronze": "storage/bronze",
    "silver": "/shared/storage/silver"
  },
  "domain_roots": {
    "municipal.finance": "municipal/chicago/finance",
    "municipal.public_safety": "municipal/chicago/public_safety",
    "county.property": "county/cook_county/property"
  },
  "tables": {
    "calendar_seed": {"root": "bronze", "rel": "seeds/calendar", "partitions": []},
    "dim_calendar": {"root": "silver", "rel": "temporal/dims/dim_calendar"},
    "dim_community_area": {"root": "silver", "rel": "municipal/chicago/geospatial/dims/dim_community_area"},
    "fact_crimes": {"root": "silver", "rel": "municipal/chicago/public_safety/facts/fact_crimes"},
    "fact_budget_events": {"root": "silver", "rel": "municipal/chicago/finance/facts/fact_budget_events"},
    "fact_parcel_sales": {"root": "silver", "rel": "county/cook_county/property/facts/fact_parcel_sales"}
  }
}
```

**Sections:**

| Key | What it controls |
|-----|-----------------|
| `connection` | Default backend (`duckdb` for interactive queries, `spark` for builds). Pipeline scripts override this automatically. |
| `api` | Query guardrails: DuckDB memory ceiling, max rows per query, max dimension dropdown values, max response payload size. The API server refuses to start if any are missing. |
| `defaults` | Storage format (always `delta` — provides ACID, time travel, schema evolution). |
| `roots` | Base filesystem paths for Bronze and Silver layers. Can be relative (to repo root) or absolute (e.g., NFS mount). |
| `domain_roots` | Path overrides for domains whose Silver path doesn't follow the canonical `{silver}/{domain.replace('.','/')}` convention. |
| `tables` | Explicit path mappings for individual tables, used by `StorageRouter` to resolve logical names like `fact_crimes` to physical Delta Lake paths. |

### run_config.json — Pipeline Orchestration

Controls how the ingestion pipeline runs: which providers to call, what endpoints to hit, batch sizes, retry behavior, and named profiles for common scenarios. Read by `IngestorEngine` and the pipeline scripts.

**Key sections:**

| Key | What it controls |
|-----|-----------------|
| `defaults` | Global defaults: `storage_path`, `days` of history, `dry_run`, `log_level`, whether to `build_silver` after ingestion. |
| `providers` | Per-provider config. Each provider (`alpha_vantage`, `chicago`, `cook_county`) lists its `endpoints`, `rate_limit_per_sec`, and `enabled` flag. |
| `silver_models` | Which Silver models to build after ingestion. |
| `cluster` | Spark master URL, fallback-to-local behavior, task batch size. |
| `retry` | Max retries, delay, exponential backoff for failed API calls. |
| `profiles` | **Named run profiles** — the most useful part. Use `--profile` to activate. |

**Profiles** are pre-configured pipeline runs. The Chicago-relevant ones:

```
--profile dev_municipal     Chicago + Cook County, 10k records/endpoint, debug logging
--profile chicago_only      Just Chicago crimes, full bulk ingestion
--profile municipal_only    Chicago crimes + Cook County parcel_sales
--profile municipal_all     All Chicago + Cook County endpoints, full ingestion
--profile silver_only       Build Silver models from existing Bronze (no ingestion)
```

### cluster.yaml — Infrastructure Configuration

Defines the physical Spark cluster, Airflow scheduler, NFS shared storage, and forecasting settings. Read by `scripts/spark-cluster/` setup scripts and the scheduler.

**Key sections:**

| Key | What it controls |
|-----|-----------------|
| `cluster` | Head node + worker nodes: hostnames, IPs, cores, memory per worker. |
| `spark` | Master port, UI port, default session config (driver/executor memory, shuffle partitions), Delta Lake package version. |
| `airflow` | Airflow UI port and Python venv path (uses separate 3.12 venv). |
| `storage` | NFS server config: mount point (`/shared/storage`), server IP, export path. Also local fallback paths for development. |
| `scheduler.jobs` | Scheduled pipeline jobs: daily price ingestion, daily Silver rebuild, weekly forecasts — each with cron-style schedule and settings. |
| `ingestion` | Default batch size, auto-compact after ingestion, rate limiting, retry config. |
| `pipeline` | Default max tickers, per-model overrides, market cap ranking toggle. |
| `forecasting` | Min data points, default horizon, available forecast models (ARIMA, Prophet, ETS) with their hyperparameters. |

This file is specific to your cluster topology. If running locally (no Spark cluster), the pipeline scripts auto-detect and fall back to local Spark (`spark.master = local[*]`).

### Environment Variables

All environment variables are optional -- they override file-based config.

| Variable                    | Default     | Purpose                                     |
|-----------------------------|-------------|---------------------------------------------|
| `ALPHA_VANTAGE_API_KEYS`   | (none)      | Alpha Vantage API key(s), comma-separated   |
| `CHICAGO_API_KEYS`         | (none)      | Chicago Data Portal app token               |
| `COOK_COUNTY_API_KEYS`     | (none)      | Cook County Data Portal app token           |
| `CONNECTION_TYPE`          | `duckdb`    | Default backend: `duckdb` or `spark`        |
| `SPARK_DRIVER_MEMORY`      | `4g`        | Spark driver memory allocation              |
| `SPARK_EXECUTOR_MEMORY`    | `4g`        | Spark executor memory allocation            |
| `SPARK_SHUFFLE_PARTITIONS` | `200`       | Spark shuffle partition count               |
| `DUCKDB_MEMORY_LIMIT`     | `4GB`       | DuckDB memory ceiling                       |
| `DUCKDB_THREADS`           | `4`         | DuckDB thread count                         |
| `LOG_LEVEL`                | `INFO`      | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Config Precedence

When the same setting is defined in multiple places, the highest-priority source wins:

1. Explicit parameters passed to `ConfigLoader.load(connection_type="spark")`
2. Environment variables (`CONNECTION_TYPE=spark`)
3. Config files (`configs/storage.json`)
4. Default constants (`de_funk.config.constants`)

---

## Step 12: Scripts Reference

All scripts use `python -m scripts.{category}.{name}` syntax for consistent import handling.

```
scripts/
  serve/
    run_api.py                      # Start FastAPI server
  build/
    build_models.py                 # Build all Silver models
    rebuild_model.py                # Rebuild a single model
  ingest/
    run_bronze_ingestion.py         # Bronze data ingestion (Alpha Vantage)
    run_chicago_ingestion.py        # Bronze ingestion (Chicago Data Portal)
    run_cook_county_ingestion.py    # Bronze ingestion (Cook County Data Portal)
  seed/
    seed_calendar.py                # Seed calendar dimension (2000-2050)
    seed_geography.py               # Seed geographic data (community areas, wards, townships)
    seed_synthetic_bronze.py        # Generate synthetic Bronze data for testing
  maintenance/
    clear_storage.py                # Clear Bronze and/or Silver layers
    clear_bronze.py                 # Clear Bronze only
    clear_silver.py                 # Clear Silver only
    reset_model.py                  # Reset a model's Silver tables
    delta_maintenance.py            # VACUUM + OPTIMIZE Delta tables
    inspect_silver.py               # Inspect Silver tables
    clear_and_refresh.py            # Full reset and rebuild
  diagnostics/
    check_data_layers.py            # Verify Bronze/Silver state
    storage_summary.py              # Table overview (sizes, row counts)
    check_bronze_counts.py          # Bronze row counts per table
    verify_bronze_data.py           # Bronze data integrity
    diagnose_bronze_data.py         # Detailed Bronze inspection
    diagnose_bronze_accumulation.py # Duplicate/schema drift detection
    diagnose_silver_data.py         # Silver data issues
    print_table_schemas.py          # Print all Silver schemas
    check_view_columns.py           # DuckDB view column definitions
    explore_tables.py               # Interactive table explorer
    debug_node_config.py            # Debug model config parsing
    debug_measure_execution.py      # Debug measure calculations
    show_tables.py                  # List all accessible tables
  spark-cluster/
    init-cluster.sh                 # Initialize Spark cluster
    start-master.sh                 # Start Spark master
    start-all-workers.sh            # Start Spark workers
    stop-cluster.sh                 # Stop Spark cluster
    run_pipeline.sh                 # Full pipeline orchestration
    submit-job.sh                   # Submit a job to the cluster
```

---

## Troubleshooting

### Server will not start

Check that `configs/storage.json` exists and has all required keys under the `api` section: `duckdb_memory_limit`, `max_sql_rows`, `max_dimension_values`, `max_response_mb`. The server logs which keys are missing.

### Exhibits show "Query error"

Check the API server logs (terminal output or `logs/de_funk.log`). Common causes:

- **Field reference does not exist**: Typo in the domain or field name. Use `GET /api/domains` to see valid references.
- **Missing join edge**: The query requires joining two tables that have no declared edge. Add an explicit edge in the model's `model.md` YAML front matter.
- **Silver table is empty**: The model has not been built, or the build produced zero rows. Run `python -m scripts.build.build_models --models <domain>`.

### Filters are not cascading

Verify that `context_filters: true` is set on the dependent filter in the exhibit's frontmatter. Check the browser console Network tab for the API response to `/api/dimensions/` to see if filters are being passed.

### DuckDB out of memory

Increase `duckdb_memory_limit` in `configs/storage.json`, or add a `limit` clause to exhibit blocks to restrict result set size.

### Stale data after rebuild

Restart the API server after rebuilding models. DuckDB views are created at server startup and do not auto-refresh when the underlying Delta tables change.

### Bronze ingestion returns zero rows

The Socrata API may return empty results if your `$where` clause references columns that do not exist in the dataset, or if the dataset ID in the provider config is incorrect. Check the API server logs for the actual SoQL query being sent:

```bash
# Check what the provider is requesting
python -m scripts.diagnostics.diagnose_bronze_data
```

Without a Socrata app token, you are limited to lower throughput. Add your token to `.env` for better performance on large datasets like crimes (8M+ rows).

### Spark session errors during build

If you see "No active SparkSession" or "Delta table not found" errors during a multi-model build, the builder framework handles this by re-registering the session via JVM bridge calls between builds. If it persists, try building models individually:

```bash
python -m scripts.build.build_models --models temporal
python -m scripts.build.build_models --models municipal.geospatial --skip-deps
python -m scripts.build.build_models --models municipal.public_safety --skip-deps
python -m scripts.build.build_models --models municipal.finance --skip-deps
python -m scripts.build.build_models --models county.property --skip-deps
```

### Cannot import de_funk

Make sure you installed the package in editable mode:

```bash
pip install -e ".[all]"
```

This registers `de_funk` as a package pointing at `src/de_funk/`. Without it, Python cannot resolve `from de_funk.config import ConfigLoader`.
