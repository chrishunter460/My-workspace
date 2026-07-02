# Internals Walkthrough

A practical, notebook-style guide to the internal subsystems that power de_Funk. Each section walks you through real code with runnable examples, expected output, and file references so you can follow along in the source.

---

## Configuration System

**Location**: `src/de_funk/config/`

The configuration system loads settings from multiple sources with strict precedence. It is the single entry point for all runtime configuration.

### Getting Started

```python
from de_funk.config.loader import ConfigLoader

loader = ConfigLoader()                    # Auto-discovers repo root
config = loader.load()                     # Full config (APIs + storage)
```

The `ConfigLoader()` constructor walks up the directory tree from your working directory until it finds a folder containing `src/`, `configs/`, and `.git/`. That becomes the repo root. You can also pass an explicit path:

```python
loader = ConfigLoader(repo_root="/home/ms_trixie/PycharmProjects/de_Funk")
```

Once loaded, `config` is a typed `AppConfig` dataclass. Here is what you get back:

```python
print(type(config))                        # <class 'de_funk.config.models.AppConfig'>
print(config.repo_root)                    # /home/ms_trixie/PycharmProjects/de_Funk
print(config.connection.type)              # "duckdb"
print(config.connection.duckdb.memory_limit)  # "4GB"
print(config.connection.duckdb.threads)    # 4
print(config.log_level)                    # "INFO"
print(config.debug.filters)               # False
print(list(config.apis.keys()))            # ["alpha_vantage", "chicago", "cook_county"]
```

### Storage-Only Loading (Faster)

If you only need storage paths and not API/provider configs, use `load_storage()`. It skips parsing provider markdown files, making it much faster for silver-only builds.

```python
storage = loader.load_storage()            # Returns a plain dict, not a dataclass
print(storage["roots"]["bronze"])          # /shared/storage/bronze
print(storage["roots"]["silver"])          # /shared/storage/silver
print(storage["defaults"]["format"])       # "delta"
```

Under the hood, `load_storage()` reads `configs/storage.json` then resolves all relative paths against the `storage_path` defined in `configs/run_config.json`:

```json
// configs/run_config.json — single source of truth for data location
{
  "defaults": {
    "storage_path": "/shared/storage"
  }
}

// configs/storage.json — defines relative layout
{
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  }
}

// After resolution:
// bronze -> /shared/storage/bronze
// silver -> /shared/storage/silver
```

If `storage_path` is not configured in `run_config.json`, `load_storage()` raises a `ValueError` with instructions. There is no silent fallback.

### Precedence Chain

Configuration sources are checked in this order, highest priority first:

```python
# 1. Explicit parameter wins (always)
config = loader.load(connection_type="spark")
print(config.connection.type)              # "spark" — explicit param used

# 2. Environment variable (if no explicit param)
# Set CONNECTION_TYPE=duckdb in .env or shell
# → config.connection.type == "duckdb"

# 3. Config file value
# configs/storage.json: {"connection": {"type": "spark"}}
# → only used if no env var and no explicit param

# 4. Default from constants.py
# de_funk.config.constants.DEFAULT_CONNECTION_TYPE = "duckdb"
# → used when nothing else is set
```

The `.env` file is loaded lazily on the first call to `loader.load()`. It only sets variables that are not already in the environment, so system-level env vars always win over `.env` values.

### All Typed Dataclasses

Every configuration value lives in a typed dataclass. No raw dicts leak into application code.

**`AppConfig`** — top-level container (`src/de_funk/config/models.py`):

```python
@dataclass
class AppConfig:
    repo_root: Path                        # /home/ms_trixie/PycharmProjects/de_Funk
    connection: ConnectionConfig           # Typed backend config
    storage: Dict[str, Any]                # Resolved storage.json (paths are absolute)
    apis: Dict[str, Dict[str, Any]]        # Provider configs keyed by name
    log_level: str                         # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    debug: DebugConfig                     # Per-subsystem debug flags
    env_loaded: bool                       # Whether .env was loaded

    # Derived paths (properties, not stored):
    config.models_dir                      # repo_root / "domains"
    config.configs_dir                     # repo_root / "configs"
```

**`ConnectionConfig`** — backend selection:

```python
@dataclass
class ConnectionConfig:
    type: str                              # "spark" or "duckdb"
    spark: Optional[SparkConfig]           # Present when type == "spark"
    duckdb: Optional[DuckDBConfig]         # Present when type == "duckdb"
```

**`SparkConfig`** — Spark tuning:

```python
@dataclass
class SparkConfig:
    driver_memory: str = "8g"
    executor_memory: str = "8g"
    shuffle_partitions: int = 200
    timezone: str = "UTC"
    legacy_time_parser: bool = True
    additional_config: Dict[str, Any]      # Arbitrary Spark conf entries

    # Convert to spark conf dict for session builder:
    spark_config.to_spark_conf_dict()
    # → {"spark.driver.memory": "8g", "spark.sql.shuffle.partitions": "200", ...}
```

**`DuckDBConfig`** — DuckDB tuning:

```python
@dataclass
class DuckDBConfig:
    database_path: Path                    # Absolute path to .db file
    memory_limit: str = "4GB"
    threads: int = 4
    read_only: bool = False
    additional_config: Dict[str, Any]

    # Convert to connection params:
    duckdb_config.to_connection_params()
    # → {"database": "/path/analytics.db", "read_only": False,
    #    "config": {"memory_limit": "4GB", "threads": 4}}
```

**`DebugConfig`** — per-subsystem debug toggles:

```python
@dataclass
class DebugConfig:
    filters: bool = False                  # Detailed filter logging
    exhibits: bool = False                 # Exhibit data logging
    sql: bool = False                      # SQL query logging

    # Loaded from env: DEBUG_FILTERS=true, DEBUG_SQL=true, etc.
    debug = DebugConfig.from_env()
```

**`StorageConfig`** — storage layer (used by `StorageConfig.from_dict()`):

```python
@dataclass
class StorageConfig:
    bronze_root: Path
    silver_root: Path
    tables: Dict[str, Dict[str, Any]]
```

**`APIConfig`** — provider configuration:

```python
@dataclass
class APIConfig:
    name: str                              # "chicago"
    base_url: str                          # "https://data.cityofchicago.org/resource"
    endpoints: Dict[str, Any]              # Endpoint definitions
    api_keys: List[str]                    # From env: CHICAGO_API_KEYS
    rate_limit_calls: int = 5              # Calls per period
    rate_limit_period: int = 60            # Period in seconds
    headers: Dict[str, str]
    timeout: int = 30
```

### RepoContext

`RepoContext` wraps `ConfigLoader` and creates a live database connection. Use it when you need both configuration and a ready-to-use backend.

```python
from de_funk.core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Typed config access
print(ctx.config.models_dir)              # /home/ms_trixie/PycharmProjects/de_Funk/domains
print(ctx.config.connection.type)         # "duckdb"
print(ctx.config.log_level)              # "INFO"

# API configs for any provider
chi_cfg = ctx.get_api_config("chicago")
print(chi_cfg.get("base_url"))           # "https://data.cityofchicago.org/resource"

# Storage config (already resolved to absolute paths)
print(ctx.storage["roots"]["silver"])     # /shared/storage/silver

# Live connection object (DuckDB or Spark)
print(ctx.connection)                     # <DataConnection: duckdb>
print(ctx.connection_type)                # "duckdb"
```

When `connection_type="duckdb"`, `RepoContext` creates a DuckDB connection via `ConnectionFactory`. When `connection_type="spark"`, it creates a Spark session via `get_spark()` and wraps it. The `.spark` attribute is only non-None in Spark mode.

**Source**: `src/de_funk/core/context.py`

### Environment Variables

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `CONNECTION_TYPE` | Backend selection | `duckdb` | `spark` |
| `LOG_LEVEL` | Console log level | `INFO` | `DEBUG` |
| `LOG_FILE_LEVEL` | File log level | `DEBUG` | `INFO` |
| `LOG_DIR` | Log file directory | `logs/` | `/var/log/de_funk` |
| `LOG_JSON` | Enable JSON log file | `false` | `true` |
| `ALPHA_VANTAGE_API_KEYS` | Comma-separated API keys | -- | `key1,key2` |
| `CHICAGO_API_KEYS` | Chicago Data Portal keys | -- | `your_token` |
| `COOK_COUNTY_API_KEYS` | Cook County Data Portal keys | -- | `your_token` |
| `SPARK_DRIVER_MEMORY` | Spark driver memory | `8g` | `16g` |
| `SPARK_EXECUTOR_MEMORY` | Spark executor memory | `8g` | `16g` |
| `SPARK_SHUFFLE_PARTITIONS` | Shuffle partitions | `200` | `400` |
| `DUCKDB_PATH` | DuckDB database file | `storage/duckdb/analytics.db` | `/data/analytics.db` |
| `DUCKDB_MEMORY_LIMIT` | DuckDB memory cap | `4GB` | `8GB` |
| `DUCKDB_THREADS` | DuckDB thread count | `4` | `8` |
| `DEBUG_FILTERS` | Verbose filter logging | `false` | `true` |
| `DEBUG_SQL` | Log all SQL queries | `false` | `true` |
| `DEBUG_EXHIBITS` | Exhibit data logging | `false` | `true` |

Set these in `.env` at the repo root (copy from `.env.example`) or export them in your shell.

---

## Domain Config System

**Location**: `src/de_funk/config/domain/`

Domain models are defined as markdown files with YAML front matter, spread across a multi-file directory structure under `domains/`. The `DomainConfigLoaderV4` discovers, inherits, and assembles them into unified configuration dicts that the build pipeline can consume.

### Directory Layout

```
domains/
├── _model_guides_/            # Reference docs (type: reference) — NOT loaded as models
├── _base/                     # Base templates (type: domain-base) — inherited, not built
└── models/
    └── {scope}/{model}/
        ├── model.md           # type: domain-model (main config, metadata, graph)
        ├── tables/*.md        # type: domain-model-table (schema definitions)
        ├── sources/**/*.md    # type: domain-model-source (Bronze-to-Silver mappings)
        └── views/*.md         # type: domain-model-view (query views)
```

Each `.md` file has a YAML front matter block with a `type:` field that tells the loader how to categorize it.

### Loading Model Configs

```python
from de_funk.config.domain import get_domain_loader
from pathlib import Path

loader = get_domain_loader(Path("domains"))

# List all discovered models
models = loader.list_models()
print(models)
# → ['corporate.entity', 'corporate.finance', 'county.geospatial', 'county.property',
#     'municipal.entity', 'municipal.finance', 'municipal.geospatial',
#     'municipal.housing', 'municipal.operations', 'municipal.public_safety',
#     'municipal.regulatory', 'municipal.transportation',
#     'securities.master', 'securities.stocks', 'temporal']

# Load a specific model's full config
config = loader.load_model_config("municipal.public_safety")
print(config.keys())
# → dict_keys(['type', 'model', 'version', 'description', 'extends', 'depends_on',
#              'sources_from', 'storage', 'graph', 'build', 'measures',
#              'tables', 'sources', '_source_file'])
```

### The Loading Process (Step by Step)

When you call `loader.load_model_config("municipal.public_safety")`, here is exactly what happens:

**Step 1 — Index (runs once at init)**

```python
# The constructor scans all .md files under domains/ and categorizes them:
loader = DomainConfigLoaderV4(Path("domains"))

# Internally, _build_index() does:
for md_file in sorted(domains_dir.rglob("*.md")):
    config = parse_front_matter(md_file)      # Extract YAML from --- blocks
    file_type = config.get("type", "")        # "domain-model", "domain-model-table", etc.
    # Store in _type_index and _model_to_path for fast lookup
```

**Step 2 — Load model.md**

```python
# Finds domains/models/municipal/public_safety/model.md
# Parses its YAML front matter into a dict
model_config = parse_front_matter(model_file)
# → {"type": "domain-model", "model": "municipal.public_safety", "version": "3.0",
#    "extends": ["_base.public_safety.crime"], "depends_on": ["temporal", "geospatial", "municipal.geospatial"], ...}
```

**Step 3 — Resolve `extends:`**

```python
# If the model extends a base template:
extends = model_config.get("extends")
# → ["_base.public_safety.crime"]

for ext_ref in extends:
    parent = resolve_extends_reference(ext_ref, domains_dir, parse_cache)
    # Loads _base/public_safety/crime/model.md (or similar)
    # Returns its parsed front matter as a dict

    model_config = deep_merge(parent, model_config)
    # Child overrides parent. Lists are replaced, not appended.
    # Dicts are merged recursively.
```

**Step 4 — Auto-discover tables, sources, views**

```python
# Finds all sibling files in the model's directory:
tables = loader._discover_tables(model_dir)
# → scans domains/models/municipal/public_safety/tables/*.md
# → {"fact_crimes": {...}, "fact_arrests": {...}, "dim_crime_type": {...}, "dim_location_type": {...}}

sources = loader._discover_sources(model_dir)
# → scans domains/models/municipal/public_safety/sources/**/*.md
# → {"chicago_crimes": {...}, "chicago_arrests": {...}, "chicago_iucr_codes": {...}}

views = loader._discover_views(model_dir)
# → scans domains/models/municipal/public_safety/views/*.md (if any)
```

**Step 5 — Assemble**

```python
# Merge discovered files into model config:
config = loader._assemble_model(model_config, tables, sources, views)
# tables go into config["tables"], sources into config["sources"], etc.
# Separate-file definitions override inline definitions from model.md.
```

**Step 6 — Resolve nested extends**

```python
# Individual tables or graph sections can also have extends:
config = resolve_nested_extends(config, domains_dir, parse_cache)
# e.g., tables.fact_crimes.extends: "_base.public_safety.crime._fact_crimes"
# → inherits schema columns from the base crime fact template
```

**Step 7 — Process schemas**

```python
# Apply additional_schema and derivations to table configs:
for table_name, table_config in config.get("tables", {}).items():
    if isinstance(table_config, dict) and table_config.get("schema"):
        process_table_schema(table_config)
```

**Step 8 — Cache**

```python
# Store the assembled config for subsequent lookups:
loader._cache[model_name] = config
# Next call to load_model_config("municipal.public_safety") returns instantly.
```

### YAML Inheritance with Examples

The `extends:` keyword works at two levels.

**Model-level inheritance** — a model inherits all config from a base template:

```yaml
# domains/models/municipal/public_safety/model.md (front matter)
---
type: domain-model
model: municipal.public_safety
extends: [_base.public_safety.crime]
depends_on: [temporal, geospatial, municipal.geospatial]
---
```

**Table-level inheritance** — a table inherits schema from a base table:

```yaml
# domains/models/municipal/public_safety/tables/fact_crimes.md (front matter)
---
type: domain-model-table
table: fact_crimes
extends: _base.public_safety.crime._fact_crimes
schema:
  # These columns are ADDED to inherited ones:
  - [beat, string, true, "Police beat"]
  - [community_area, integer, true, "Community area number"]
---
```

The resolution function `resolve_extends_reference()` works by trying progressively longer path prefixes, then navigating into the config structure. For `_base.public_safety.crime._fact_crimes`:

1. Try file: `_base/public_safety/crime/_fact_crimes.md` (not found)
2. Try file: `_base/public_safety/crime.md` then navigate to key `_fact_crimes` (not found)
3. Try file: `_base/public_safety.md` then navigate to `crime._fact_crimes` (not found)
4. Try file: `_base.md` then navigate to `public_safety.crime._fact_crimes` (not found)
5. Try directory: `_base/public_safety/crime/` and look for a file defining `_fact_crimes`

`deep_merge()` recursively merges dicts. Child values override parent values. Lists are replaced entirely (not appended).

### Config Translator

After assembly, the raw domain config needs to be translated into a format that `GraphBuilder` can process. The `ConfigTranslator` handles this.

```python
from de_funk.config.domain.config_translator import translate_domain_config

# raw_config is what load_model_config() returns
translated = translate_domain_config(raw_config)

# The translator ADDS a synthesized graph.nodes dict:
print(translated["graph"]["nodes"].keys())
# → dict_keys(['fact_crimes', 'fact_arrests', 'dim_crime_type', 'dim_location_type'])

# Each node has the info GraphBuilder needs:
node = translated["graph"]["nodes"]["fact_crimes"]
print(node["from"])       # "bronze.chicago.chicago_crimes"
print(node["type"])       # "fact"
print(node["select"])     # {"incident_id": "incident_id", "case_number": "case_number", ...}
print(node["filters"])    # []
print(node["unique_key"]) # ["incident_id"]
```

The translator detects node types automatically:

| Node Type | Detection | Example |
|-----------|-----------|---------|
| **seed** | `table_config` has static seed data | `dim_calendar` with hardcoded date ranges |
| **generated** | Flagged as `generated: true` | Computed tables with no Bronze source |
| **window** | `transform: window` | Rolling averages over time series |
| **distinct/aggregate** | `transform: distinct` or `aggregate` | Deduplication with GROUP BY |
| **standard** | Has matching source(s) | Most dimension and fact tables |
| **union** | Multiple sources map to same table | Tables combining data from multiple providers |

**Source**: `src/de_funk/config/domain/config_translator.py`

### Build Order

The loader can compute a topological build order from `depends_on` declarations:

```python
order = loader.get_build_order()
print(order)
# → ['temporal', 'corporate.entity', 'corporate.finance', 'county.geospatial',
#     'county.property', 'municipal.entity', 'municipal.geospatial', ...]

# Or for a subset:
order = loader.get_build_order(["municipal.public_safety", "municipal.geospatial", "temporal"])
print(order)
# → ['temporal', 'municipal.geospatial', 'municipal.public_safety']
```

This uses Kahn's algorithm. If circular dependencies are detected, a warning is logged and the remaining models are appended at the end.

---

## Logging Framework

**Location**: `src/de_funk/config/logging.py`

### Quick Start

```python
from de_funk.config.logging import setup_logging, get_logger, LogTimer

setup_logging()                            # Call once at startup (idempotent)
logger = get_logger(__name__)              # Module-specific logger

logger.info("Starting pipeline")           # [    INFO] __main__: Starting pipeline
logger.debug("Processing community area LOOP")  # Only in log file by default
logger.warning("Rate limit approaching")   # [WARNING ] __main__: Rate limit approaching
logger.error("Failed to fetch", exc_info=True)  # Includes full stack trace
```

`setup_logging()` is idempotent. Call it as many times as you want; only the first call configures handlers. All subsequent calls return immediately.

### Handlers

Three output handlers are configured:

| Handler | Level | Format | Rotation | Destination |
|---------|-------|--------|----------|-------------|
| **Console** | `LOG_LEVEL` env (default: INFO) | Colored, `[LEVEL] name: message` | -- | stdout |
| **File** | `LOG_FILE_LEVEL` env (default: DEBUG) | Includes `filename:lineno` | 10 MB, 5 backups | `logs/de_funk.log` |
| **JSON** (optional) | DEBUG | Structured JSON with extra fields | 10 MB, 5 backups | `logs/de_funk.json` |

Enable JSON logging by setting `LOG_JSON=true` in your environment.

The console handler uses `ColoredFormatter` which auto-detects TTY support. Colors are disabled when piping output or when the `NO_COLOR` env var is set.

### LogTimer

A context manager for timing operations with automatic logging:

```python
with LogTimer(logger, "Building public_safety model", model="public_safety"):
    build_public_safety()

# On success:
# [   DEBUG] de_funk.build: Starting: Building public_safety model
# [   DEBUG] de_funk.build: Completed: Building public_safety model (2350.12ms)

# On error:
# [   DEBUG] de_funk.build: Starting: Building public_safety model
# [   ERROR] de_funk.build: Failed: Building public_safety model (150.34ms)
# Traceback (most recent call last): ...
```

The `**context` kwargs (like `model="public_safety"`) are passed as `extra` fields to the logger, which means they show up in JSON logs for structured querying.

LogTimer does NOT suppress exceptions. They propagate after being logged.

### Configuration

Override defaults by constructing a `LogConfig` explicitly:

```python
from de_funk.config.logging import LogConfig

config = LogConfig(
    console_level="DEBUG",                 # Show everything in console
    file_level="DEBUG",                    # Log everything to file
    max_bytes=20 * 1024 * 1024,            # 20 MB log files
    backup_count=10,                       # Keep 10 rotated files
    enable_json=True,                      # Enable JSON log file
)
setup_logging(config=config)
```

Or load from environment variables:

```python
config = LogConfig.from_env(repo_root=Path("/home/ms_trixie/PycharmProjects/de_Funk"))
# Reads LOG_LEVEL, LOG_FILE_LEVEL, LOG_DIR, LOG_JSON from env
# Resolves log_dir relative to repo_root if not absolute
```

### Module Noise Suppression

`LogConfig.module_levels` silences noisy third-party loggers at WARNING level by default:

```python
# These modules are suppressed automatically:
# urllib3, duckdb, pyspark, py4j, streamlit, watchdog, httpx, httpcore, numexpr
```

### Function Call Decorator

```python
from de_funk.config.logging import log_function_call

@log_function_call(logger)
def build_model(name):
    # ...
    return model

build_model("municipal.finance")
# [   DEBUG] Entering: build_model
# [   DEBUG] Exiting: build_model
```

---

## Exception Hierarchy

**Location**: `src/de_funk/core/exceptions.py`

All de_Funk exceptions extend `DeFunkError`, which provides three attributes on every error: `message`, `details` (a dict for structured debugging), and `recovery_hint` (a human-readable suggestion).

### The Full Tree

```
DeFunkError
├── ConfigurationError
│   ├── MissingConfigError(config_key, config_file)
│   └── InvalidConfigError(config_key, value, expected)
├── PipelineError
│   ├── IngestionError(provider, endpoint, error)
│   ├── RateLimitError(provider, retry_after)
│   └── TransformationError(stage, error, record_count)
├── ModelError
│   ├── ModelNotFoundError(model_name, available_models)
│   ├── TableNotFoundError(model_name, table_name, available_tables)
│   ├── MeasureError(measure_name, error, model_name)
│   └── DependencyError(model_name, missing_deps)
├── QueryError
│   ├── FilterError(filter_spec, error)
│   └── JoinError(left_table, right_table, error)
├── StorageError
│   ├── DataNotFoundError(path, table)
│   └── WriteError(path, error)
├── ForecastError
│   ├── InsufficientDataError(required, available, entity)
│   └── ModelTrainingError(model_type, error, entity)
└── ConnectionError(backend, error)
```

### Using Exceptions

Every exception auto-generates a `recovery_hint` from its constructor arguments:

```python
from de_funk.core.exceptions import (
    ModelNotFoundError, ConfigurationError,
    IngestionError, RateLimitError, DependencyError,
    MissingConfigError
)

# ModelNotFoundError — includes available models in hint
try:
    model = registry.get_model("nonexistent")
except ModelNotFoundError as e:
    print(e.message)           # "Model not found: 'nonexistent'"
    print(e.details)           # {'model': 'nonexistent', 'available': ['temporal', ...]}
    print(e.recovery_hint)     # "Available models: temporal, corporate.entity, ..."
    print(str(e))              # "Model not found: 'nonexistent' | Hint: Available models: ..."

# RateLimitError — tells you how long to wait
try:
    fetch_data()
except RateLimitError as e:
    print(e.details)           # {'provider': 'chicago', 'retry_after': 60}
    print(e.recovery_hint)     # "Wait 60 seconds before retrying"

# DependencyError — shows the build order you need
try:
    build_model("municipal.public_safety")
except DependencyError as e:
    print(e.recovery_hint)     # "Build dependent models first: temporal -> municipal.geospatial -> municipal.public_safety"

# MissingConfigError — points to the file
try:
    load_api_keys()
except MissingConfigError as e:
    print(e.recovery_hint)     # "Add 'CHICAGO_API_KEYS' to your configuration file or environment"

# Exception chaining with `from`
try:
    fetch_data_from_api()
except requests.RequestException as e:
    raise IngestionError("chicago", "chicago_crimes", str(e)) from e
```

### Error Handling Decorators

**Location**: `src/de_funk/core/error_handling.py`

Four utilities for consistent error handling:

**`@handle_exceptions`** — catch specific errors, log them, return a default:

```python
from de_funk.core.error_handling import handle_exceptions

@handle_exceptions(ValueError, KeyError, default_return=[])
def parse_config(data):
    return json.loads(data)

result = parse_config("invalid json")
# Logs: "Exception in parse_config: JSONDecodeError: ..."
# Returns: []

# With reraise — logs but still raises:
@handle_exceptions(reraise=True)
def must_succeed():
    raise RuntimeError("oops")

must_succeed()  # Logs the error, then raises RuntimeError
```

**`@retry_on_exception`** — exponential backoff for transient failures:

```python
from de_funk.core.error_handling import retry_on_exception

@retry_on_exception(
    ConnectionError, TimeoutError,
    max_retries=3,
    delay_seconds=1.0,
    backoff_factor=2.0,
    max_delay=60.0,
)
def fetch_api_data(url):
    return requests.get(url)

fetch_api_data("https://api.example.com/data")
# Attempt 1: fails → wait 1.0s
# Attempt 2: fails → wait 2.0s
# Attempt 3: fails → wait 4.0s
# Attempt 4: fails → raises last exception
```

**`safe_call`** — one-off safe execution without a decorator:

```python
from de_funk.core.error_handling import safe_call

result = safe_call(json.loads, '{"valid": true}', default={})
# → {"valid": True}

result = safe_call(json.loads, 'broken', default={})
# Logs: "safe_call: loads raised JSONDecodeError: ..."
# → {}

# Suppress logging for expected failures:
result = safe_call(risky_function, log_errors=False, default=None)
```

**`ErrorContext`** — context manager with timing and error logging:

```python
from de_funk.core.error_handling import ErrorContext

with ErrorContext("Loading model", model_name="municipal.finance"):
    model = load_model("municipal.finance")

# On success:
# [   DEBUG] Starting: Loading model
# [   DEBUG] Completed: Loading model (45.23ms)

# On error:
# [   DEBUG] Starting: Loading model
# [   ERROR] Failed: Loading model (12.10ms)
# Traceback (most recent call last): ...
```

`ErrorContext` never suppresses exceptions. They propagate after being logged.

**`ensure_not_none`** — guard clause for required values:

```python
from de_funk.core.error_handling import ensure_not_none

config = ensure_not_none(get_config(), "config")
# → returns config if not None
# → raises ValueError("config must not be None") if None
```

---

## Measure Framework

**Location**: `src/de_funk/models/measures/`

The measure framework defines calculations declaratively in YAML and executes them through backend-agnostic adapters. Measures generate SQL; adapters execute it.

### Defining Measures in YAML

Measures are defined in model markdown front matter. The compact list format is `[name, aggregation, source, description, {options}]`:

```yaml
# In model.md frontmatter
measures:
  simple:
    - [crime_count, count_distinct, fact_crimes.incident_id, "Total crime incidents", {format: "#,##0"}]
    - [total_budget, sum, fact_budget_events.amount, "Total budget amount", {format: "$#,##0.00"}]
    - [department_count, count_distinct, dim_department.org_unit_id, "City departments", {format: "#,##0"}]
    - [avg_assessed_value, avg, fact_assessed_values.assessed_value_total, "Avg assessed value", {format: "$#,##0"}]
  computed:
    - [arrest_rate, expression, "100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)", "Arrest rate %", {format: "#,##0.0%"}]
```

### Measure Types

| Type | Class | Purpose | YAML Syntax | SQL Output |
|------|-------|---------|-------------|------------|
| `simple` | `SimpleMeasure` | Direct SQL aggregation | `[name, sum, table.col, desc]` | `SELECT SUM(col) as measure_value FROM ...` |
| `computed` | `ComputedMeasure` | Expression before aggregation | `[name, expression, "SQL_EXPR", desc]` | `SELECT (SQL_EXPR) as measure_value FROM ...` |
| `weighted` | `WeightedMeasure` | Weighted aggregation | `{source: t.col, weight: t.w}` | `SELECT SUM(col * w) / SUM(w) FROM ...` |
| `window` | `WindowMeasure` | Window functions | `{source: t.col, window: rolling_avg}` | `SELECT AVG(col) OVER (PARTITION BY ...) FROM ...` |
| `ratio` | `RatioMeasure` | Ratios and percentages | `{numerator: t.a, denominator: t.b}` | `SELECT SUM(a) / NULLIF(SUM(b), 0) FROM ...` |
| `custom` | `CustomMeasure` | Custom SQL/code | `{sql: "SELECT ..."}` | Passed through directly |

### Creating and Executing Measures

The `MeasureRegistry` is a factory that maps type strings to implementation classes using a decorator pattern:

```python
from de_funk.models.measures.registry import MeasureRegistry
from de_funk.models.measures.base_measure import MeasureType

# See what's registered
print(MeasureRegistry.get_registered_types())
# → [<MeasureType.SIMPLE: 'simple'>, <MeasureType.COMPUTED: 'computed'>]

# Create a measure from config dict
measure = MeasureRegistry.create_measure({
    "name": "total_budget",
    "type": "simple",
    "source": "fact_budget_events.amount",
    "aggregation": "sum",
})

# The measure knows its table and column:
print(measure.name)            # "total_budget"
print(measure.source)          # "fact_budget_events.amount"
print(measure.aggregation)     # "SUM"

# Generate SQL (requires a backend adapter):
sql = measure.to_sql(adapter)
# → "SELECT SUM(amount) as measure_value
#    FROM read_parquet('/path/to/fact_budget_events/*.parquet')
#    WHERE amount IS NOT NULL"

# Execute with filters:
result = measure.execute(adapter, filters={"fiscal_year": 2024})
```

Registration happens via decorator in each measure module:

```python
# src/de_funk/models/measures/simple.py
@MeasureRegistry.register(MeasureType.SIMPLE)
class SimpleMeasure(BaseMeasure):
    # Supported aggregations: AVG, SUM, MIN, MAX, COUNT, STDDEV, VARIANCE
    ...
```

### MeasureExecutor (High-Level)

The `MeasureExecutor` is the main entry point for measure calculation. It reads measure definitions from model config, creates measure instances, handles auto-enrichment, and executes through the appropriate backend adapter.

```python
from de_funk.models.measures.executor import MeasureExecutor

executor = MeasureExecutor(model, backend="duckdb")

# Simple execution
result = executor.execute_measure("total_budget", entity_column="department_description")
print(result.data)             # DataFrame with department_description, measure_value columns
print(result.rows)             # Number of rows returned

# With filters
result = executor.execute_measure(
    "total_budget",
    filters={"fiscal_year": {"min": 2020, "max": 2024}},
    entity_column="department_description",
    limit=10,
)

# List all available measures in the model
all_measures = executor.list_measures()
print(all_measures.keys())     # → dict_keys(['total_budget', 'department_count', ...])

# Get info about a measure
info = executor.get_measure_info("total_budget")
print(info)
# → {'name': 'total_budget', 'type': 'simple', 'description': 'Total budget amount',
#     'source': 'fact_budget_events.amount', 'data_type': 'double', 'tags': []}

# Preview the SQL without executing
sql = executor.explain_measure("total_budget")
print(sql)
```

### Auto-Enrichment

When a measure's `auto_enrich: true`, the executor automatically joins related tables to bring in missing columns. For example, if you group by `community_name` but it lives in `dim_community_area` (not `fact_crimes`), the executor uses the model's `GraphQueryPlanner` to find and execute the join chain.

```python
# This works even though community_name is NOT in fact_crimes:
result = executor.execute_measure(
    "crime_count",
    entity_column="community_name",    # Lives in dim_community_area
)
# The executor:
# 1. Detects community_name is missing from fact_crimes
# 2. Queries GraphQueryPlanner for path: fact_crimes -> dim_community_area
# 3. Joins along that path to bring in community_name
# 4. Executes the measure on the enriched table
```

### Filter Support in Measures

Filters can be passed to any measure execution. They support exact match, IN lists, and range conditions:

```python
filters = {
    "community_area": 32,                              # Exact match → WHERE community_area = 32
    "primary_type": ["THEFT", "BATTERY"],               # IN clause → WHERE primary_type IN ('THEFT', 'BATTERY')
    "year": {"min": 2020, "max": 2024},                 # Range → WHERE year BETWEEN ...
    "amount": {"gte": 1000000},                         # Inclusive lower bound
    "assessed_value_total": {"gt": 100000, "lt": 500000},  # Exclusive bounds
}
```

---

## Filter Engine

**Location**: `src/de_funk/core/session/filters.py`

### Basic Usage

The `FilterEngine` provides a single, backend-agnostic interface for applying filters to any DataFrame type:

```python
from de_funk.core.session.filters import FilterEngine

# Apply to a Spark DataFrame
filtered = FilterEngine.apply_filters(spark_df, {"community_area": 32}, backend="spark")

# Apply to a DuckDB relation or pandas DataFrame
filtered = FilterEngine.apply_filters(duckdb_rel, {"primary_type": ["THEFT", "BATTERY"]}, backend="duckdb")

# Auto-detect backend from session
filtered = FilterEngine.apply_from_session(df, filters, session)
```

### Filter Specification Format

All filter types with examples and the SQL they produce:

```python
# Exact match
{"community_area": 32}
# Spark: df.filter(F.col("community_area") == 32)
# SQL:   WHERE community_area = 32

# IN clause (list of values)
{"primary_type": ["THEFT", "BATTERY", "ASSAULT"]}
# Spark: df.filter(F.col("primary_type").isin(["THEFT", "BATTERY", "ASSAULT"]))
# SQL:   WHERE primary_type IN ('THEFT', 'BATTERY', 'ASSAULT')

# Range filter (inclusive)
{"year": {"min": 2020, "max": 2024}}
# Spark: df.filter(F.col("year") >= 2020).filter(F.col("year") <= 2024)
# SQL:   WHERE year >= 2020 AND year <= 2024

# Numeric bounds (explicit operators)
{"amount": {"gte": 1000000}}
# Spark: df.filter(F.col("amount") >= 1000000)
# SQL:   WHERE amount >= 1000000

{"assessed_value_total": {"gt": 100000, "lt": 500000}}
# Spark: df.filter(F.col("assessed_value_total") > 100000).filter(F.col("assessed_value_total") < 500000)
# SQL:   WHERE assessed_value_total > 100000 AND assessed_value_total < 500000

# Combined — all conditions are ANDed
{"department_description": "DEPARTMENT OF POLICE", "amount": {"min": 1000000}, "fiscal_year": {"min": 2020}}
# SQL:   WHERE department_description = 'DEPARTMENT OF POLICE' AND amount >= 1000000 AND fiscal_year >= 2020
```

### SQL Generation

You can generate a WHERE clause string without applying it to a DataFrame:

```python
sql_clause = FilterEngine.build_filter_sql({"department_description": "DEPARTMENT OF POLICE", "amount": {"gte": 1000000}})
print(sql_clause)
# → "department_description = 'DEPARTMENT OF POLICE' AND amount >= 1000000"
```

Value formatting is type-aware:

```python
FilterEngine._format_sql_value(1000000)     # → "1000000" (no quotes — numeric)
FilterEngine._format_sql_value("THEFT")     # → "'THEFT'" (quoted — string)
FilterEngine._format_sql_value(True)        # → "TRUE" (boolean keyword)
FilterEngine._format_sql_value(None)        # → "NULL"
```

### Smart Features

**Column availability checking** — filters for non-existent columns are silently skipped. This is safe for multi-table queries where different tables have different columns:

```python
# If df only has ["incident_id", "year"], a filter on "beat" is skipped
filtered = FilterEngine.apply_filters(df, {"year": 2024, "beat": {"min": 100}}, "duckdb")
# Only the year filter is applied; beat filter is ignored
```

**Date ID translation** — when filtering a `date_id` column (integer format YYYYMMDD), string dates are automatically converted:

```python
# "2024-01-01" → 20240101 for date_id columns
FilterEngine._convert_date_to_date_id("2024-01-01")   # → 20240101
FilterEngine._convert_date_to_date_id("2024/06/15")   # → 20240615
```

**Period overlap logic** — for tables with `period_start_date_id` and `period_end_date_id` columns (like corporate finance tables with fiscal periods), the engine applies overlap semantics instead of simple range filters. A date range filter matches any row whose period overlaps with the requested range.

### Backend Dispatch

Internally, `apply_filters()` dispatches to backend-specific implementations:

- **Spark**: Uses `F.col()`, `.isin()`, chained `.filter()` calls. Requires PySpark.
- **DuckDB**: Generates SQL WHERE clauses for DuckDB relations. Falls back to pandas boolean indexing for already-converted DataFrames.

---

## Storage Routing

### StorageRouter

**Location**: `src/de_funk/models/api/dal.py`

The `StorageRouter` resolves logical table references (like `bronze.chicago.chicago_crimes`) to filesystem paths. It reads `configs/storage.json` for root directories and table mappings.

```python
from de_funk.models.api.dal import StorageRouter

router = StorageRouter(storage_cfg)

# Bronze paths: dots → slashes
path = router.resolve("bronze.chicago.chicago_crimes")
print(path)
# → /shared/storage/bronze/chicago/chicago_crimes

# Silver paths: layer prefix stripped, rest preserved
path = router.resolve("silver.municipal/chicago/public_safety/dims/dim_crime_type")
print(path)
# → /shared/storage/silver/municipal/chicago/public_safety/dims/dim_crime_type

# Absolute paths pass through unchanged
path = router.resolve("/shared/storage/bronze/seeds/calendar")
print(path)
# → /shared/storage/bronze/seeds/calendar
```

Under the hood, `resolve()` calls `parse_table_ref()` to split the reference:

```python
router.parse_table_ref("bronze.chicago.chicago_crimes")
# → ("bronze", "chicago/chicago_crimes")

router.parse_table_ref("silver.municipal/chicago/public_safety/facts/fact_crimes")
# → ("silver", "municipal/chicago/public_safety/facts/fact_crimes")

# No prefix defaults to silver:
router.parse_table_ref("municipal/chicago/public_safety/facts/fact_crimes")
# → ("silver", "municipal/chicago/public_safety/facts/fact_crimes")
```

Then it looks up the layer root from `storage_cfg["roots"]` and joins them. Bronze table references are also checked against the explicit `tables` mapping in `storage.json`.

### Domain Root Overrides

`configs/storage.json` provides `domain_roots` for cases where the model name does not match the physical storage path:

```json
{
  "domain_roots": {
    "municipal.finance": "municipal/chicago/finance",
    "municipal.public_safety": "municipal/chicago/public_safety",
    "county.property": "county/cook/property"
  }
}
```

Without overrides, `municipal.finance` would resolve to `silver/municipal/finance/`. With the override, it maps to `silver/municipal/chicago/finance/` — including the entity in the path.

### Table Reader

The `Table` class reads Delta Lake or Parquet tables with auto-detection:

```python
from de_funk.models.api.dal import Table

table = Table(spark, router, "bronze.chicago.chicago_crimes")

# Check the resolved path
print(table.path)
# → /shared/storage/bronze/chicago/chicago_crimes

# Read with auto-format detection
df = table.read()
# If _delta_log/ exists → reads as Delta Lake
# Otherwise → reads as Parquet with mergeSchema=true
```

### ModelWriter

**Location**: `src/de_funk/models/base/model.py (write_tables method)`

The `ModelWriter` persists model dimensions and facts to the Silver layer using Delta Lake format.

```python
# ModelWriter removed — BaseModel.write_tables() writes directly

writer = ModelWriter(model)
stats = writer.write_tables(mode="overwrite")

# Returns statistics dict:
# {
#     "dimensions": {
#         "dim_crime_type": {"rows": 450, "files": 1, "time": 0.8},
#         "dim_location_type": {"rows": 160, "files": 1, "time": 0.5}
#     },
#     "facts": {
#         "fact_crimes": {"rows": 7800000, "files": 4, "time": 85.3},
#         "fact_arrests": {"rows": 1200000, "files": 2, "time": 22.1}
#     },
#     "total_rows": 8000610,
#     "total_tables": 4
# }
```

Override output location and format:

```python
stats = writer.write_tables(
    output_root="/shared/storage/silver/municipal/chicago/public_safety",
    format="delta",                        # "delta" or "parquet"
    mode="overwrite",                      # "overwrite" or "append"
    partition_by={"fact_crimes": ["year"]},
    quiet=True,                            # Suppress verbose output
)
```

**Format resolution** (highest to lowest priority):

1. Explicit `format` parameter to `write_tables(format="delta")`
2. Model config: `model.md` front matter `storage.format`
3. Global storage config: `configs/storage.json` `defaults.format`
4. Hardcoded default: `"delta"`

```python
# Check format resolution:
# write_tables reads from model_cfg, then storage_cfg, then DEFAULT_FORMAT
format = (
    model.model_cfg.get("storage", {}).get("format")    # 1. model.md
    or storage_cfg.get("defaults", {}).get("format")    # 2. storage.json
    or "delta"                                          # 3. hardcoded default
)
```

**Auto-vacuum** — by default, `ModelWriter` vacuums Delta tables after writing to remove old file versions. This saves disk space but disables time travel.

```python
# Check if auto-vacuum is enabled (default: True)
print(writer.auto_vacuum)                  # True

# Disable in model markdown to keep version history:
# storage:
#   auto_vacuum: false
```

When `auto_vacuum` is True, the writer calls `DeltaTable.vacuum(0)` after each table write, removing all old files immediately.

**Delta Lake features used by ModelWriter**:

| Feature | Setting | Purpose |
|---------|---------|---------|
| Schema evolution | `overwriteSchema: true` | Handles column additions/removals between builds |
| ACID writes | Delta format | No partial writes on failure |
| Auto-vacuum | `vacuum(0)` | Clean up old versions (configurable per model) |

### Delta Lake Storage

All Bronze and Silver data uses Delta Lake format by default. Key capabilities:

```python
# ACID transactions — writes are atomic, no partial data on failure
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)

# Time travel (when auto_vacuum is disabled)
spark.read.format("delta").option("versionAsOf", 5).load(path)

# Schema evolution — new columns are added automatically
df.write.format("delta").option("mergeSchema", "true").mode("append").save(path)
```

Spark 4.x with `delta-spark` handles all writes. DuckDB reads Delta tables directly via its built-in Delta extension, so no format conversion is needed for the analytics layer.
