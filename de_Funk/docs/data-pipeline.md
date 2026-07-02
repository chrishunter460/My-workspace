# Data Pipeline Walkthrough

A hands-on guide to the de_Funk ingestion and build pipeline. Every code block is runnable. Follow along from raw API data all the way to queryable Silver dimensional tables.

```
External APIs ──► Raw (JSON/CSV) ──► Bronze (Delta) ──► Silver (Delta) ──► DuckDB (views)
                  cached responses    schema-normalized   snowflake schemas       interactive queries
                  optional staging    ACID + time travel   partitioned        BI + notebooks
```

**Key principle**: Configuration lives in markdown files with YAML front matter. Endpoint schemas, provider settings, and model definitions are all defined in markdown — the code reads from these files at runtime. One source of truth, zero duplication.

---

## Part 1: Bronze Layer — Fetching Raw Data

The Bronze layer stores raw API responses with minimal transformation. Data flows through four components:

```
Provider → Facet → IngestorEngine → BronzeSink → Delta Lake
```

### 1.1 Provider Registry — Discovering Data Sources

The `ProviderRegistry` auto-discovers all available providers by scanning subdirectories under `src/de_funk/pipelines/providers/`.

```python
from de_funk.pipelines.providers.registry import ProviderRegistry

# Trigger auto-discovery (scans providers/ directory)
ProviderRegistry.discover()

# List available providers
providers = ProviderRegistry.list_available()
print(providers)
# → ['alpha_vantage', 'chicago', 'cook_county']

# Get metadata for the Chicago provider
info = ProviderRegistry.get_info("chicago")
print(info.name)           # → 'chicago'
print(info.models)         # → ['municipal.finance', 'municipal.public_safety', 'municipal.regulatory',
                           #     'municipal.housing', 'municipal.operations', 'municipal.transportation']
print(info.bronze_tables)  # → ['chicago/crimes', 'chicago/building_permits', 'chicago/food_inspections',
                           #     'chicago/business_licenses', 'chicago/contracts', 'chicago/budget_appropriations',
                           #     'chicago/cta_l_ridership_daily', 'chicago/traffic', ...]

# Find which providers feed a specific model
feeds_public_safety = ProviderRegistry.get_providers_for_model("municipal.public_safety")
print(feeds_public_safety)
# → ['chicago']
```

**Discovery algorithm**: For each subdirectory in `providers/`, the registry looks for `{name}_provider.yaml` (preferred, explicit metadata) or `{name}_ingestor.py` (fallback, convention-based). YAML files define `models`, `bronze_tables`, `module_path`, and `class_name`.

### 1.2 Creating a Provider Instance

Each provider extends `BaseProvider` and loads its configuration from markdown files in `data_sources/`.

**Chicago Data Portal** (Socrata API, offset pagination):

```python
from de_funk.pipelines.providers.chicago.chicago_provider import (
    create_chicago_provider
)

provider = create_chicago_provider(
    spark=spark,
    docs_path=repo_root / "data_sources",
    storage_path=Path("/shared/storage"),  # enables raw CSV staging
    preserve_raw=True                      # keep CSV files for verification
)

# List available work items (active endpoints)
items = provider.list_work_items()
print(items)
# → ['budget_appropriations', 'budget_revenue', 'budget_positions', 'contracts',
#     'payments', 'crimes', 'arrests', 'building_permits', 'food_inspections',
#     'building_violations', 'business_licenses', 'cta_l_ridership',
#     'cta_bus_ridership', 'traffic', 'service_requests_311', ...]
```

**Cook County Data Portal** (also Socrata, with PIN-based property lookups):

```python
from de_funk.pipelines.providers.cook_county.cook_county_provider import (
    create_cook_county_provider
)

provider = create_cook_county_provider(
    spark=spark,
    docs_path=repo_root / "data_sources",
    storage_path=Path("/shared/storage")
)

items = provider.list_work_items()
print(items)
# → ['assessed_values', 'parcel_sales', 'neighborhoods', 'townships',
#     'municipalities', 'parcel_universe']

# Cook County also supports PIN-based lookups
for batch in provider.fetch_parcel_data(pins=["17321110370000", "17321110380000"]):
    print(f"  Batch: {len(batch)} records")
```

Other providers (e.g., Alpha Vantage for securities data) follow the same interface but use REST APIs with API key authentication instead of Socrata.

### 1.3 Provider Interface

All providers implement the same abstract interface defined in `BaseProvider`:

```python
from de_funk.pipelines.base.provider import BaseProvider

class BaseProvider(ABC):
    """Configuration loaded from markdown documentation files."""

    def __init__(self, provider_id: str, spark=None, docs_path=None):
        # Loads provider config and endpoint configs from markdown
        ...

    @abstractmethod
    def list_work_items(self, **kwargs) -> List[str]:
        """List available work items for ingestion."""
        ...

    @abstractmethod
    def fetch(self, work_item: str, max_records=None, **kwargs) -> Generator[List[Dict], None, None]:
        """Fetch data for a work item, yielding batches of raw records."""
        ...

    @abstractmethod
    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize raw records to a typed Spark DataFrame."""
        ...

    @abstractmethod
    def get_table_name(self, work_item: str) -> str:
        """Get the Bronze table name for a work item."""
        ...

    # These read from endpoint markdown automatically:
    def get_partitions(self, work_item: str) -> Optional[List[str]]: ...
    def get_key_columns(self, work_item: str) -> List[str]: ...
    def get_write_strategy(self, work_item: str) -> str: ...
    def get_date_column(self, work_item: str) -> Optional[str]: ...
```

The `fetch()` method is a generator. It yields batches of raw dicts so the `IngestorEngine` can write incrementally without loading the full dataset into memory.

Chicago and Cook County both extend `SocrataBaseProvider`, which provides Socrata-specific features: offset pagination, CSV bulk downloads, multi-year view IDs, date format normalization (US, ISO, month name formats), and column name normalization ("Case Number" -> "case_number").

### 1.4 Facet System — Transforming Raw API Responses

Facets sit between raw API responses and typed Spark DataFrames. The `Facet` base class reads its schema from endpoint markdown front matter — no code changes needed when adding fields.

```python
from de_funk.pipelines.base.facet import Facet

facet = Facet(
    spark,
    provider_id="chicago",
    endpoint_id="crimes"
)

# The facet loads schema from:
# data_sources/Endpoints/Chicago Data Portal/Public Safety/Crimes.md

# Normalize raw API response → typed DataFrame
raw_batches = [[
    {"case_number": "JG123456", "date": "2024-06-15T10:30:00.000",
     "primary_type": "THEFT", "description": "OVER $500",
     "iucr": "0820", "fbi_code": "06", "arrest": "false",
     "domestic": "false", "beat": "0835", "district": "008",
     "ward": "18", "community_area": "66", "year": "2024",
     "block": "048XX S WESTERN AVE",
     "latitude": "41.807", "longitude": "-87.683",
     "location_description": "STREET"}
]]

df = facet.normalize(raw_batches)
df.printSchema()
# root
#  |-- case_number: string
#  |-- date: timestamp
#  |-- primary_type: string
#  |-- description: string
#  |-- iucr: string
#  |-- fbi_code: string
#  |-- arrest: boolean
#  |-- domestic: boolean
#  |-- beat: string
#  |-- district: string
#  |-- ward: integer
#  |-- community_area: integer
#  |-- year: integer
#  |-- latitude: double
#  |-- longitude: double
#  |-- location_description: string
```

**The normalization pipeline** (7 steps, all automatic):

```
1. Clean raw data       → _clean_raw_value() strips whitespace, converts "N/A" → None
2. Pre-coerce types     → coerce_rules from markdown (e.g., ward: "int", latitude: "double")
3. Create DataFrame     → spark.createDataFrame(rows)
4. Apply postprocess    → subclass hook for custom transforms
5. Apply computed fields → SQL expressions from markdown (e.g., TO_DATE(timestamp))
6. Apply Spark casts    → TRY_CAST for safe type conversion
7. Apply final columns  → enforce column order from markdown schema
```

**Socrata date handling**: The `SocrataBaseProvider` normalizes multiple date formats that appear in Chicago and Cook County data:

```python
# Handled automatically by _safe_parse_date():
# "2024-06-15T10:30:00.000" → 2024-06-15     (ISO timestamp)
# "01/16/2025"              → 2025-01-16     (US date)
# "October 01 2019"         → 2019-10-01     (Month name)
# "2020"                    → 2020-01-01     (Year only)
# Uses try_to_timestamp → returns NULL for malformed dates instead of errors
```

**Writing a custom facet** (only needed for provider-specific cleaning):

```python
class SocrataFacet(Facet):
    """Socrata returns geospatial objects that need JSON serialization."""

    def postprocess(self, df):
        """Custom transforms after initial normalization."""
        from pyspark.sql import functions as F
        # Derive year partition from date column if not present
        if 'year' not in df.columns and 'date' in df.columns:
            df = df.withColumn("year", F.year(F.col("date")))
        return df
```

### 1.5 IngestorEngine — Orchestrating Fetch + Write

The `IngestorEngine` decouples API fetching from Delta Lake writes using a `ThreadPoolExecutor`. This overlaps I/O operations for 2-3x throughput.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Fetch Thread  │───►│  In-Memory Queue │───►│  Writer Thread  │
│   (API calls)   │    │  (bounded, ~2)   │    │  (Delta writes) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Basic usage** (Chicago Data Portal):

```python
from de_funk.pipelines.base.ingestor_engine import IngestorEngine

engine = IngestorEngine(
    provider=provider,
    storage_cfg=storage_cfg,
    max_pending_writes=2,   # Backpressure: blocks fetch if 2 writes pending
    writer_threads=2        # Number of Delta writer threads
)

# Run ingestion for specific work items
results = engine.run(
    work_items=["crimes", "building_permits", "food_inspections"],
    write_batch_size=500_000,  # Records buffered before each Delta write
    max_records=None,          # None = fetch everything
    async_writes=True          # Overlap fetch + write (default)
)
```

**Expected output**:

```
============================================================
INGESTOR ENGINE: CHICAGO
============================================================
  Work items: 3
  Mode: async (chunked)
  Batch size: 500,000 records

[1/3] crimes... ✓ 8,234,567 records
[2/3] building_permits... ✓ 1,456,231 records
[3/3] food_inspections... ✓ 248,903 records

============================================================
INGESTION SUMMARY
============================================================
  Work items: 3/3 completed
  Records: 9,939,701
  Errors: 0
  Time: 312.4s
  Throughput: 31,817 records/sec
============================================================
```

**Inspecting results**:

```python
print(results.completed_work_items)  # → 3
print(results.total_records)         # → 9,939,701
print(results.total_errors)          # → 0
print(results.elapsed_seconds)       # → 312.4

# Per-item results
for name, result in results.results.items():
    print(f"  {name}: {result.record_count:,} records, success={result.success}")
# → crimes: 8,234,567 records, success=True
# → building_permits: 1,456,231 records, success=True
# → food_inspections: 248,903 records, success=True
```

**Factory shortcut** (creates engine for any provider):

```python
from de_funk.pipelines.base.ingestor_engine import create_engine

engine = create_engine(
    provider_name="chicago",       # or "cook_county", "alpha_vantage"
    storage_cfg=storage_cfg,
    spark=spark,
    docs_path=repo_root / "data_sources"
)

results = engine.run(work_items=["crimes", "building_permits"])
```

**Two ingestion paths** (auto-selected per work item):

| Path | When Used | How It Works |
|------|-----------|-------------|
| **BULK** (Spark-native) | Provider has `get_raw_path()` and no `max_records` limit | Populates raw cache (JSON/CSV files), Spark reads all at once, single Delta write. 10-50x faster. |
| **INCREMENTAL** (streaming) | Fallback, or when `max_records` is set | Fetches in batches via `provider.fetch()`, normalizes, async Delta writes in chunks. |

Chicago endpoints with `download_method: csv` (like crimes, building_permits) use the BULK path by default. Endpoints with JSON pagination use the INCREMENTAL path.

### 1.6 BronzeSink — Writing to Delta Lake

`BronzeSink` handles all Delta Lake writes with ACID guarantees, schema evolution, and multiple write strategies.

```python
from de_funk.pipelines.ingestors.bronze_sink import BronzeSink

sink = BronzeSink(storage_cfg)
# storage_cfg must have: {"roots": {"bronze": "/shared/storage/bronze"}, ...}
```

**Three write strategies**:

```python
# 1. append_immutable — for time-series data (crimes, ridership, traffic)
# Deduplicates new records against existing data using key columns.
# O(1) memory: reads only the date range that overlaps with new data.
sink.append_immutable(
    df,
    table="chicago/crimes",
    key_columns=["case_number", "date"],
    partitions=["year"],
    date_column="date"
)

# 2. upsert — for reference/dimension data (community areas, wards)
# Read-Merge-Overwrite: reads existing, unions with new, deduplicates, overwrites.
# Prevents file accumulation from Delta MERGE operations.
sink.upsert(
    df,
    table="chicago/community_areas",
    key_columns=["area_number"],
    update_existing=True  # New data overwrites existing for same key
)

# 3. overwrite — full table replacement
sink.overwrite(
    df,
    table="cook_county/neighborhoods",
    partitions=None
)
```

**smart_write** reads the strategy from `storage.json` config:

```python
# Reads write_strategy, key_columns, partitions, date_column from storage.json
# and calls the appropriate method automatically
sink.smart_write(df, table="chicago_crimes")
```

**Schema evolution** happens automatically:

```python
# New columns added seamlessly (mergeSchema: true)
# Type incompatibilities trigger automatic retry with overwriteSchema: true
# Column casting matches existing schema types before merge to prevent conflicts
```

**Check if data exists**:

```python
exists = sink.exists("chicago/crimes")
print(exists)  # → True (checks for _delta_log directory)
```

### 1.7 StreamingBronzeWriter — Memory-Safe Batch Writes

For large datasets, `StreamingBronzeWriter` accumulates records in a buffer and auto-flushes when `batch_size` is reached. First flush overwrites, subsequent flushes append.

```python
# Create via BronzeSink (recommended)
def create_df(records):
    return provider.normalize(records, "crimes")

with sink.streaming_writer(
    table="chicago/crimes",
    df_factory=create_df,
    batch_size=500_000,
    partitions=["year"]
) as writer:
    for batch in provider.fetch("crimes"):
        writer.add_batch(batch)
    # Auto-flushes remaining records on context exit

print(f"Written: {writer.total_records:,} records in {writer.batches_written} batches")
# → Written: 8,234,567 records in 17 batches
```

**Properties available during/after writing**:

```python
writer.total_records    # Records already flushed to Delta
writer.buffered_records # Records in current buffer (not yet written)
writer.batches_written  # Number of flush operations completed
```

---

## Part 2: Silver Layer — Building Dimensional Models

The Silver layer contains dimensional snowflake schemas built from Bronze data. Each domain model is defined in a markdown file with YAML front matter.

```
Bronze (raw snapshots) ──► GraphBuilder (transforms) ──► ModelWriter (Delta) ──► Silver (snowflake schemas)
```

### 2.1 Domain Config Loading

Model configurations live in `domains/models/` as markdown files with YAML front matter.

```python
from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader

# Factory function auto-detects v4 structure
loader = get_domain_loader(repo_root / "domains")
# → DomainConfigLoaderV4

# List all available models
models = loader.list_models()
print(models)
# → ['corporate.entity', 'corporate.finance', 'county.geospatial',
#     'county.property', 'municipal.entity', 'municipal.finance',
#     'municipal.geospatial', 'municipal.housing', 'municipal.operations',
#     'municipal.public_safety', 'municipal.regulatory', 'municipal.transportation',
#     'securities.master', 'securities.stocks', 'temporal']

# Load a model's full config
config = loader.load_model_config("municipal.public_safety")

print(config.keys())
# → dict_keys(['type', 'model', 'version', 'description', 'extends',
#     'depends_on', 'storage', 'graph', 'build', 'measures', 'tables',
#     'sources', ...])

print(config["depends_on"])
# → ['temporal', 'geospatial', 'municipal.geospatial']
```

**Config discovery**: `DomainConfigLoaderV4` scans the directory for:

```
domains/
├── _model_guides_/     # Reference docs (skipped)
├── _base/              # Base templates (for extends)
└── models/
    └── municipal/
        ├── public_safety/
        │   ├── model.md         # type: domain-model — main config
        │   └── tables/          # type: domain-model-table — one per table
        │       ├── fact_crimes.md
        │       └── fact_arrests.md
        └── sources/             # Sources grouped at domain-group level
            └── chicago/
                └── public_safety/   # type: domain-model-source — Bronze mappings
                    ├── crimes.md
                    ├── arrests.md
                    └── iucr_codes.md
```

The loader assembles `model.md` + `tables/*.md` + `sources/**/*.md` into one unified config dict. Sources are discovered by scanning the `sources/` directory at the domain-group level (e.g., `municipal/sources/`), not under each subdomain. Tables from separate files merge into `config["tables"]`.

**Source mappings** define how Bronze columns map to Silver schemas. For example, the crimes source (`domains/models/municipal/sources/chicago/public_safety/crimes.md`) maps raw Chicago fields to the snowflake schema:

```yaml
# From sources/chicago/public_safety/crimes.md
type: domain-model-source
source: crimes
maps_to: fact_crimes
from: bronze.chicago_crimes
aliases:
  - [incident_id, "ABS(HASH(case_number))"]
  - [date_id, "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"]
  - [crime_type_id, "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"]
  - [community_area, community_area]
  - [ward, ward]
  - [district, district]
  - [arrest_made, arrest]
  - [domestic, domestic]
  - [latitude, latitude]
  - [longitude, longitude]
```

### 2.2 Build Order — Dependency Resolution

Models declare dependencies via `depends_on`. The build system resolves these using topological sort (Kahn's algorithm).

```python
# Get build order for a specific model (auto-expands dependencies)
order = loader.get_build_order(["municipal.public_safety"])
print(order)
# → ['temporal', 'municipal.geospatial', 'municipal.public_safety']

# Get build order for all municipal models
order = loader.get_build_order([
    "municipal.finance", "municipal.public_safety", "municipal.regulatory",
    "municipal.transportation", "municipal.operations", "municipal.housing",
    "county.property"
])
print(order)
# → ['temporal', 'municipal.entity', 'municipal.geospatial', 'county.geospatial',
#     'municipal.finance', 'municipal.public_safety', 'municipal.regulatory',
#     'municipal.housing', 'municipal.operations', 'municipal.transportation',
#     'county.property']

# Get build order for ALL models
full_order = loader.get_build_order()
print(full_order)
# → ['temporal', 'securities.master', 'corporate.entity', 'corporate.finance',
#     'securities.stocks', 'municipal.entity', 'county.geospatial', ...]
```

**Municipal dependency graph**:

```
temporal (no deps)
├── municipal.entity
│   └── municipal.finance (depends: temporal, municipal.entity, county.property)
├── municipal.geospatial
│   ├── municipal.public_safety (depends: temporal, geospatial, municipal.geospatial)
│   ├── municipal.regulatory (depends: temporal, municipal.geospatial)
│   ├── municipal.housing (depends: temporal, municipal.geospatial)
│   ├── municipal.operations (depends: temporal, municipal.geospatial)
│   └── municipal.transportation (depends: temporal, municipal.geospatial)
└── county.geospatial
    └── county.property (depends: temporal, county.geospatial)
```

### 2.3 DomainBuilderFactory — Dynamic Builder Creation

The `DomainBuilderFactory` scans domain configs and dynamically creates builder classes for each model, registering them with `BuilderRegistry`.

```python
from de_funk.models.base.domain_builder import discover_domain_builders
from de_funk.models.base.builder import BuilderRegistry, BuildContext

# Step 1: Discover all domain model configs and create builders
builders = discover_domain_builders(repo_root)
print(f"Registered {len(builders)} builders")
# → Registered 15 builders

# Step 2: Check what's registered (municipal models highlighted)
for name, cls in sorted(BuilderRegistry.all().items()):
    deps = ", ".join(cls.depends_on) if cls.depends_on else "none"
    print(f"  {name} (depends: {deps})")
# →  county.geospatial (depends: temporal)
# →  county.property (depends: temporal, county.geospatial)
# →  municipal.entity (depends: temporal)
# →  municipal.finance (depends: temporal, municipal.entity, county.property)
# →  municipal.geospatial (depends: temporal)
# →  municipal.housing (depends: temporal, municipal.geospatial)
# →  municipal.operations (depends: temporal, municipal.geospatial)
# →  municipal.public_safety (depends: temporal, geospatial, municipal.geospatial)
# →  municipal.regulatory (depends: temporal, municipal.geospatial)
# →  municipal.transportation (depends: temporal, municipal.geospatial)
# →  ...

# Step 3: Get build order for municipal + county
order = BuilderRegistry.get_build_order([
    "municipal.finance", "municipal.public_safety", "county.property"
])
print(order)
# → ['temporal', 'municipal.entity', 'municipal.geospatial', 'county.geospatial',
#     'municipal.finance', 'municipal.public_safety', 'county.property']
```

**Custom vs. generic model classes**: Most models use the generic `DomainModel` class. Models with specialized build logic have custom classes:

| Model | Custom Class | Special Logic |
|-------|-------------|---------------|
| `temporal` | `TemporalModel` | Generates calendar dimension (2000-2050) |
| `corporate.entity` | `CompanyModel` | CIK-based company linkage |
| `securities.stocks` | `StocksModel` | Post-build technical indicators |
| All others | `DomainModel` | Generic graph-based build |

All municipal and county models use the generic `DomainModel` class — their build logic is entirely driven by the graph config in markdown.

### 2.4 Running a Build

```python
# Step 4: Create build context
context = BuildContext(
    spark=spark,
    storage_config=storage_cfg,
    repo_root=repo_root,
    date_from="2020-01-01",
    date_to="2024-12-31",
    verbose=True
)

# Step 5: Build each model in dependency order
for name in order:
    builder_cls = BuilderRegistry.get(name)
    builder = builder_cls(context)
    result = builder.build()
    print(result)
```

**Expected output**:

```
Building temporal...
Writing temporal to Silver layer...
✓ temporal: 1 dims, 0 facts (2.1s)
Building municipal.entity...
Writing municipal.entity to Silver layer...
✓ municipal.entity: 1 dims, 0 facts (3.8s)
Building municipal.geospatial...
Writing municipal.geospatial to Silver layer...
✓ municipal.geospatial: 4 dims, 0 facts (6.2s)
Building municipal.public_safety...
Writing municipal.public_safety to Silver layer...
✓ municipal.public_safety: 2 dims, 2 facts (42.5s)
Building municipal.finance...
Writing municipal.finance to Silver layer...
✓ municipal.finance: 5 dims, 3 facts (28.3s)
Building municipal.regulatory...
Writing municipal.regulatory to Silver layer...
✓ municipal.regulatory: 2 dims, 3 facts (15.7s)
```

**BuildResult fields**:

```python
@dataclass
class BuildResult:
    model_name: str          # "municipal.public_safety"
    success: bool            # True
    dimensions: int          # 2 (dim_crime_type, dim_location_type)
    facts: int               # 2 (fact_crimes, fact_arrests)
    rows_written: int        # 8,234,567
    duration_seconds: float  # 42.5
    error: Optional[str]     # None (or error message if failed)
    warnings: List[str]      # []
```

### 2.5 What Happens Inside builder.build()

The build method runs this sequence:

```python
# 1. Validate prerequisites
is_valid, errors = builder.validate()       # Check model config and class import

# 2. Pre-build hook
builder.pre_build()                         # Check bronze data exists

# 3. Create model instance
model = builder.create_model_instance()     # Instantiate model class with config

# 4. Build tables from Bronze
dims, facts = model.build()                 # GraphBuilder loads and transforms tables

# 5. Write to Silver
model.write_tables(quiet=False)             # ModelWriter persists to Delta Lake

# 6. Post-build hook
builder.post_build(result)                  # Run computed columns, enrichments
```

### 2.6 GraphBuilder — Table Construction from Config

`GraphBuilder` reads `graph.nodes` from the model config and builds each table:

```python
# For each node in graph.nodes config:
# 1. Load source data from Bronze (or Silver for cross-model references)
# 2. Apply select (column subset)
# 3. Apply derive (computed columns)
# 4. Apply filter (row-level predicates)
# 5. Apply join (cross-table enrichment)
# 6. Apply unique_key (deduplication)
```

**Node types** supported in graph config:

| Type | Description | Example |
|------|-------------|---------|
| Standard | Load from Bronze/Silver, apply transforms | `from: bronze.chicago_crimes` |
| `__seed__` | Create DataFrame from inline data | Static lookup tables |
| `__union__` | Load multiple sources, UNION them | Combine payments + contracts into `fact_ledger_entries` |
| `__distinct__` | SELECT DISTINCT with optional aggregation | Reference tables like `dim_vendor` |
| `_transform: window` | Apply window functions | Moving averages, rankings |

**Municipal finance uses `__union__`** to combine multiple Chicago source endpoints into a single fact table:

```yaml
# From municipal.finance model — payments, contracts, and budget entries
# all map to fact_ledger_entries via separate source files:
#   sources/chicago/finance/payments.md     → maps_to: fact_ledger_entries
#   sources/chicago/finance/contracts.md    → maps_to: fact_ledger_entries
# Each source provides aliases from its Bronze columns to the canonical schema.
```

**Build phases** in municipal models control execution order:

```yaml
# municipal.public_safety
build:
  partitions: [year]
  phases:
    1: { tables: [dim_crime_type, dim_location_type] }
    2: { tables: [fact_crimes, fact_arrests] }

# county.property
build:
  partitions: [year]
  phases:
    1: { tables: [dim_property_class, dim_tax_district] }
    2: { tables: [dim_parcel] }
    3: { tables: [fact_assessed_values, fact_parcel_sales] }
```

### 2.7 ModelWriter — Persisting to Silver

`ModelWriter` writes dimension and fact tables to the Silver layer as Delta Lake tables.

```python
# ModelWriter is used internally by builder.build()
# but can be accessed for inspection:

# After model.build():
model.write_tables(quiet=False)
# Output:
#   dim_crime_type: 450 rows → /shared/storage/silver/municipal/chicago/public_safety/dims/dim_crime_type/
#   dim_location_type: 180 rows → /shared/storage/silver/municipal/chicago/public_safety/dims/dim_location_type/
#   fact_crimes: 8,234,567 rows → /shared/storage/silver/municipal/chicago/public_safety/facts/fact_crimes/
#   fact_arrests: 1,123,456 rows → /shared/storage/silver/municipal/chicago/public_safety/facts/fact_arrests/
```

**Storage layout** (configured in model markdown):

```
/shared/storage/silver/
├── temporal/dims/dim_calendar/                            # 18,263 rows (2000-2050)
├── municipal/chicago/
│   ├── entity/dims/dim_municipality/
│   ├── geospatial/dims/{dim_community_area, dim_ward, dim_patrol_district, dim_patrol_area}/
│   ├── public_safety/{dims/dim_crime_type, facts/fact_crimes, facts/fact_arrests}/
│   ├── finance/{dims/{dim_vendor,dim_department,dim_contract,dim_fund,...}, facts/{fact_ledger_entries,fact_budget_events,...}}/
│   ├── regulatory/{dims/dim_facility, facts/{fact_food_inspections,fact_building_violations,fact_business_licenses}}/
│   ├── housing/facts/fact_building_permits/
│   ├── operations/facts/fact_service_requests/
│   └── transportation/{dims/dim_transit_station, facts/{fact_rail_ridership,fact_bus_ridership,fact_traffic}}/
└── county/cook_county/
    ├── geospatial/dims/{dim_township, dim_municipality_boundary}/
    └── property/{dims/{dim_parcel,dim_property_class,dim_tax_district}, facts/{fact_assessed_values,fact_parcel_sales}}/
```

**Auto-vacuum** is enabled by default (no time travel, saves storage). To enable time travel for a model, set `storage.auto_vacuum: false` in the model's markdown front matter.

### 2.8 Post-Build Enrichments

Some models declare `build.post_build` steps that run after all tables are written. These enable cross-model computed columns.

```yaml
# From domains/models/municipal/finance/model.md:
# (example of a post_build enrichment pattern)
build:
  post_build:
    - id: enrich_vendor_metrics
      type: computed_columns
      target: dim_vendor
      merge_on: vendor_id
      columns:
        - [total_payments, "SUM(fact_ledger_entries.transaction_amount)", {cast: double}]
        - [contract_count, "COUNT(DISTINCT dim_contract.contract_id)", {cast: int}]
```

This aggregates payment totals and contract counts from fact tables and merges them back into `dim_vendor` on `vendor_id`.

---

## Part 3: Adding a New Data Source (Step-by-Step)

Adding a new provider requires these files (using a hypothetical "Weather Service" as example):

| Step | File | Purpose |
|------|------|---------|
| 1 | `src/de_funk/pipelines/providers/weather_service/__init__.py` | Provider package |
| 2 | `data_sources/Endpoints/Weather Service/Daily Observations.md` | Endpoint schema (YAML front matter defines `schema`, `key_columns`, `write_strategy`, `partitions`) |
| 3 | `data_sources/Providers/Weather Service.md` | Provider config (`base_url`, `auth_type`, `rate_limit_per_sec`) |
| 4 | `src/de_funk/pipelines/providers/weather_service/weather_service_provider.py` | Provider class extending `BaseProvider` |
| 5 | `src/de_funk/pipelines/providers/weather_service/weather_service_provider.yaml` | Registry metadata (`models`, `bronze_tables`, `class_name`) |
| 6 | `.env` | API key (`WEATHER_API_KEY=...`) |

**Provider class** — the core implementation:

```python
"""Weather Service Provider Implementation."""
from __future__ import annotations
from typing import List, Dict, Generator
from de_funk.pipelines.base.provider import BaseProvider
from de_funk.pipelines.base.facet import Facet
from de_funk.pipelines.base.http_client import HttpClient
from de_funk.pipelines.base.key_pool import ApiKeyPool
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

class WeatherServiceProvider(BaseProvider):
    """Provider for Weather Service API."""
    PROVIDER_NAME = "Weather Service"

    def __init__(self, spark=None, docs_path=None, storage_path=None):
        self._stations: List[str] = []
        super().__init__(provider_id="weather_service", spark=spark, docs_path=docs_path)

    def _setup(self) -> None:
        import os
        api_keys = [k.strip() for k in os.environ.get(self.env_api_key, "").split(",") if k.strip()]
        self.key_pool = ApiKeyPool(api_keys)
        self.http = HttpClient({"core": self.base_url}, {}, self.rate_limit, self.key_pool)
        self._facet = Facet(self.spark, provider_id="weather_service", endpoint_id="daily_observations")

    def set_stations(self, stations: List[str]) -> None:
        self._stations = stations

    def list_work_items(self, **kwargs) -> List[str]:
        return ["daily_observations"]

    def fetch(self, work_item: str, max_records=None, **kwargs) -> Generator[List[Dict], None, None]:
        for station in self._stations:
            resp = self.http.get("core", "/api/v1/observations", params={"station_id": station})
            if resp and resp.get("observations"):
                for record in resp["observations"]:
                    record["station_id"] = station
                yield resp["observations"]

    def normalize(self, records: List[Dict], work_item: str):
        return self._facet.normalize([records])

    def get_table_name(self, work_item: str) -> str:
        return "weather_service/daily_observations"

def create_weather_provider(spark=None, docs_path=None, storage_path=None):
    return WeatherServiceProvider(spark=spark, docs_path=docs_path, storage_path=storage_path)
```

**Test**:

```python
provider = create_weather_provider(spark=spark, docs_path=repo_root / "data_sources")
provider.set_stations(["KORD", "KMDW"])  # Chicago O'Hare and Midway

engine = IngestorEngine(provider, storage_cfg)
results = engine.run(work_items=["daily_observations"])
results.print_summary()
```

For Socrata-based providers (like Chicago or Cook County), extend `SocrataBaseProvider` instead — it provides pagination, CSV downloads, and date parsing out of the box. See `chicago_provider.py` for a minimal example (the class body is essentially empty because `SocrataBaseProvider` handles everything).

---

## Part 4: Data Source Reference

### Providers and Bronze Tables

| Provider | API Type | Work Items | Bronze Tables |
|----------|----------|------------|---------------|
| **Chicago Data Portal** | Socrata | `crimes`, `arrests`, `building_permits`, `food_inspections`, `building_violations`, `business_licenses`, `contracts`, `payments`, `budget_appropriations`, `budget_revenue`, `cta_l_ridership`, `cta_bus_ridership`, `traffic`, `service_requests_311`, `community_areas`, `wards`, `police_districts`, `police_beats`, `zoning_districts`, `cta_l_stops` | `chicago/{endpoint_id}` |
| **Cook County Data Portal** | Socrata | `assessed_values`, `parcel_sales`, `parcel_universe`, `neighborhoods`, `townships`, `municipalities` | `cook_county/{endpoint_id}` |
| **Alpha Vantage** | REST + API key | `prices`, `reference`, `income`, `balance`, `cashflow`, `earnings`, `dividends`, `splits` | `alpha_vantage/{endpoint_id}` |

### Rate Limits

| Provider | Free Tier | Premium | Configured In |
|----------|-----------|---------|---------------|
| Chicago Data Portal | 1000 calls/hour | Same with app token | `data_sources/Providers/Chicago Data Portal.md` |
| Cook County Data Portal | 1000 calls/hour | Same with app token | `data_sources/Providers/Cook County Data Portal.md` |
| Alpha Vantage | 5 calls/min | 75 calls/min (1.25/sec) | `data_sources/Providers/Alpha Vantage.md` |

### Bronze → Silver Mapping

| Silver Model | Depends On | Bronze Sources |
|-------------|------------|---------------|
| `temporal` | (none) | Generated (2000-2050) |
| `municipal.entity` | `temporal` | Generated from source configs |
| `municipal.geospatial` | `temporal` | `chicago/community_areas`, `chicago/wards`, `chicago/police_districts`, `chicago/police_beats` |
| `municipal.public_safety` | `temporal`, `municipal.geospatial` | `chicago/crimes`, `chicago/arrests`, `chicago/iucr_codes` |
| `municipal.finance` | `temporal`, `municipal.entity`, `county.property` | `chicago/payments`, `chicago/contracts`, `chicago/budget_appropriations`, `chicago/budget_revenue`, `chicago/budget_positions` |
| `municipal.regulatory` | `temporal`, `municipal.geospatial` | `chicago/food_inspections`, `chicago/building_violations`, `chicago/business_licenses` |
| `municipal.housing` | `temporal`, `municipal.geospatial` | `chicago/building_permits`, `chicago/zoning_districts` |
| `municipal.operations` | `temporal`, `municipal.geospatial` | `chicago/service_requests_311` |
| `municipal.transportation` | `temporal`, `municipal.geospatial` | `chicago/cta_l_ridership_daily`, `chicago/cta_bus_ridership`, `chicago/traffic` |
| `county.geospatial` | `temporal` | `cook_county/neighborhoods`, `cook_county/townships`, `cook_county/municipalities` |
| `county.property` | `temporal`, `county.geospatial` | `cook_county/assessed_values`, `cook_county/parcel_sales`, `cook_county/parcel_universe` |
| `securities.master` | `temporal` | `alpha_vantage/listing_status`, `alpha_vantage/company_overview` |
| `corporate.entity` | `temporal`, `securities.master` | `alpha_vantage/company_overview` |
| `corporate.finance` | `temporal`, `corporate.entity` | `alpha_vantage/income_statement`, `alpha_vantage/balance_sheet`, `alpha_vantage/cash_flow` |
| `securities.stocks` | `temporal`, `securities.master`, `corporate.entity` | `alpha_vantage/time_series_daily_adjusted`, `alpha_vantage/dividends`, `alpha_vantage/splits` |

---

## Part 5: CLI Reference

### Seeding (one-time setup)

```bash
# Seed calendar dimension (2000-2050, ~18K rows)
python -m scripts.seed.seed_calendar --storage-path /shared/storage

# Seed geography dimensions (community areas, wards, townships, etc.)
python -m scripts.seed.seed_geography --storage-path /shared/storage

# Seed ticker listing from Alpha Vantage LISTING_STATUS (~12,499 US tickers, 1 API call)
python -m scripts.seed.seed_tickers --storage-path /shared/storage

# Seed market cap rankings (for --use-market-cap selection)
python -m scripts.seed.seed_market_cap --storage-path /shared/storage
```

### Bronze Ingestion

```bash
# Ingest all Chicago Data Portal endpoints
python -m scripts.ingest.run_bronze_ingestion --provider chicago

# Ingest specific Chicago endpoints
python -m scripts.ingest.run_bronze_ingestion --provider chicago \
    --endpoints crimes,building_permits,food_inspections,business_licenses

# Ingest Cook County endpoints
python -m scripts.ingest.run_bronze_ingestion --provider cook_county \
    --endpoints assessed_values,parcel_sales,neighborhoods

# Ingest with max records (useful for dev/testing)
python -m scripts.ingest.run_bronze_ingestion --provider chicago \
    --endpoints crimes --max-records 100000

# Force re-fetch from API (bypass raw cache)
python -m scripts.ingest.run_bronze_ingestion --provider chicago --force-api

# Custom storage path
python -m scripts.ingest.run_bronze_ingestion --storage-path /shared/storage \
    --provider chicago

# Alpha Vantage ingestion (securities data)
python -m scripts.ingest.run_bronze_ingestion --provider alpha_vantage --max-tickers 100
```

### Silver Build

```bash
# Build all models (respects dependency order)
python -m scripts.build.build_models

# Build municipal models (dependencies auto-included)
python -m scripts.build.build_models --models municipal.public_safety municipal.finance \
    municipal.regulatory municipal.transportation

# Build county property model
python -m scripts.build.build_models --models county.property

# Rebuild single model from scratch
python -m scripts.build.rebuild_model --model municipal.public_safety
```

### Full Pipeline (ingestion + build)

```bash
# Dev profile (small dataset, fast)
./scripts/spark-cluster/run_pipeline.sh --profile dev

# Quick test
./scripts/spark-cluster/run_pipeline.sh --profile quick_test

# Production (all endpoints, all models)
./scripts/spark-cluster/run_pipeline.sh --profile production
```

---

## Part 6: Storage Configuration

All storage paths and write strategies are defined in `configs/storage.json`.

```json
{
  "defaults": {
    "format": "delta"
  },
  "roots": {
    "bronze": "storage/bronze",
    "silver": "/shared/storage/silver"
  },
  "domain_roots": {
    "municipal.finance": "municipal/chicago/finance",
    "municipal.public_safety": "municipal/chicago/public_safety",
    "municipal.regulatory": "municipal/chicago/regulatory",
    "municipal.housing": "municipal/chicago/housing",
    "municipal.operations": "municipal/chicago/operations",
    "municipal.transportation": "municipal/chicago/transportation",
    "county.property": "county/cook_county/property",
    "securities.master": "securities",
    "securities.stocks": "stocks"
  },
  "tables": {
    "calendar_seed": { "root": "bronze", "rel": "seeds/calendar" },
    "dim_calendar": { "root": "silver", "rel": "temporal/dims/dim_calendar" },
    "dim_community_area": { "root": "silver", "rel": "municipal/chicago/geospatial/dims/dim_community_area" },
    "fact_crimes": { "root": "silver", "rel": "municipal/chicago/public_safety/facts/fact_crimes" },
    "dim_parcel": { "root": "silver", "rel": "county/cook_county/property/dims/dim_parcel" },
    "fact_assessed_values": { "root": "silver", "rel": "county/cook_county/property/facts/fact_assessed_values" }
  }
}
```

**Key fields**:

| Field | Purpose |
|-------|---------|
| `roots.bronze` | Base path for all Bronze tables |
| `roots.silver` | Base path for all Silver tables |
| `domain_roots` | Override silver path when it differs from the canonical model name |
| `tables.{name}.root` | Which root this table belongs to (`bronze` or `silver`) |
| `tables.{name}.rel` | Relative path from the root |

**Delta Lake** is the default format for all layers. This gives you:

- **ACID transactions**: Reliable concurrent reads and writes
- **Time travel**: Query any previous version with `versionAsOf` (if auto_vacuum is disabled)
- **Schema evolution**: New columns added seamlessly via `mergeSchema: true`
- **Efficient upserts**: `append_immutable` for time-series, `upsert` for reference data

DuckDB reads Delta tables directly via its built-in Delta extension for interactive queries and BI.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/de_funk/pipelines/base/provider.py` | `BaseProvider` abstract interface |
| `src/de_funk/pipelines/base/socrata_provider.py` | `SocrataBaseProvider` for Chicago + Cook County |
| `src/de_funk/pipelines/base/socrata_client.py` | `SocrataClient` HTTP + CSV download |
| `src/de_funk/pipelines/base/facet.py` | `Facet` base class for schema normalization |
| `src/de_funk/pipelines/base/ingestor_engine.py` | `IngestorEngine` with async writes |
| `src/de_funk/pipelines/ingestors/bronze_sink.py` | `BronzeSink` + `StreamingBronzeWriter` |
| `src/de_funk/pipelines/providers/registry.py` | `ProviderRegistry` auto-discovery |
| `src/de_funk/pipelines/providers/chicago/chicago_provider.py` | Chicago Data Portal implementation |
| `src/de_funk/pipelines/providers/cook_county/cook_county_provider.py` | Cook County implementation |
| `src/de_funk/pipelines/providers/alpha_vantage/alpha_vantage_provider.py` | Alpha Vantage implementation |
| `src/de_funk/config/domain/__init__.py` | `DomainConfigLoaderV4` model config loading |
| `src/de_funk/models/base/builder.py` | `BaseModelBuilder` + `BuilderRegistry` |
| `src/de_funk/models/base/domain_builder.py` | `DomainBuilderFactory` dynamic builder creation |
| `src/de_funk/models/base/graph_builder.py` | `GraphBuilder` table construction |
| `configs/storage.json` | Storage paths and write strategies |
| `scripts/ingest/run_bronze_ingestion.py` | Bronze ingestion CLI |
| `scripts/build/build_models.py` | Silver build CLI |
