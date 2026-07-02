---
title: "Configuration & Data Classes"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/config/data_classes.py
  - src/de_funk/config/models.py
  - src/de_funk/config/loader.py
  - src/de_funk/config/domain/build.py
  - src/de_funk/config/domain/config_translator.py
  - src/de_funk/config/domain/extends.py
  - src/de_funk/config/domain/federation.py
  - src/de_funk/config/domain/graph.py
  - src/de_funk/config/domain/schema.py
  - src/de_funk/config/domain/sources.py
  - src/de_funk/config/domain/subsets.py
  - src/de_funk/config/domain/views.py
  - src/de_funk/config/markdown_loader.py
  - src/de_funk/config/constants.py
---

# Configuration & Data Classes

> Typed dataclasses mirroring YAML frontmatter, config loaders, and markdown parsers.

## Purpose & Design Decisions

### What Problem This Solves

de_Funk's configuration comes from three distinct sources: JSON files (`storage.json`, `run_config.json`), markdown files with YAML frontmatter (domain models, providers, endpoints), and environment variables (API keys, debug flags, connection overrides). Without a typed layer, every consumer passes around raw `Dict[str, Any]` values, leading to silent key mismatches, no IDE completion, and errors that surface far from where the config was loaded.

This group solves that problem at two levels:

1. **Typed data classes** (`data_classes.py`, `models.py`) -- `@dataclass` objects that mirror every YAML/JSON structure. Parse-time validation catches typos and missing fields before they reach business logic. IDE autocompletion works on every attribute.
2. **Config loaders** (`loader.py`, `markdown_loader.py`, `config/domain/`) -- read files, resolve paths, merge precedence layers (explicit param > env var > file > default), and return typed objects.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Two parallel data class files (`data_classes.py` for domain YAML, `models.py` for infrastructure) | Domain configs evolve independently of infrastructure configs. Keeping them separate prevents a single 600+ line mega-file and makes ownership clear. | Single data_classes file; rejected because domain model structures (EdgeSpec, MeasureDef) change with schema evolution while infrastructure models (SparkConfig, DuckDBConfig) are stable. |
| `from_dict()` static methods on infrastructure classes | Provides a clean boundary between raw JSON dicts and typed objects. Centralizes default values so callers don't repeat fallback logic. | Constructor-only parsing; rejected because `__init__` would need complex conditional logic for optional nested fields. |
| Markdown-first config with JSON fallback | Markdown files serve as both documentation (readable in Obsidian) and machine config (YAML frontmatter). JSON remains for backward compatibility but triggers deprecation warnings. | JSON-only; rejected because it separates docs from config, causing them to drift. |
| `ConnectionConfig.__post_init__` validation | Catches misconfigured connection types immediately at construction time rather than at first query. | Lazy validation; rejected because a bad connection type would produce confusing errors deep in Engine creation. |
| Explicit `storage_path` in `run_config.json` (no fallback) | Prevents accidental writes to wrong storage locations. Forces users to explicitly configure where data lives. | Auto-detect from environment; rejected because implicit paths led to data being written to dev locations in production. |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Connection backend (Spark vs DuckDB) | `connection.type` or `CONNECTION_TYPE` env | `configs/storage.json`, env var |
| DuckDB memory, threads | `DUCKDB_MEMORY_LIMIT`, `DUCKDB_THREADS` env | Environment or defaults in `constants.py` |
| Spark driver/executor memory | `SPARK_DRIVER_MEMORY`, `SPARK_EXECUTOR_MEMORY` env | Environment or defaults in `constants.py` |
| Storage tier root paths | `roots` dict in storage config | `configs/storage.json` + `run_config.json` `storage_path` |
| API rate limits per provider | `rate_limit_per_sec` in provider frontmatter | `Data Sources/Providers/*.md` |
| Debug logging (SQL, filters, exhibits) | `DEBUG_SQL`, `DEBUG_FILTERS`, `DEBUG_EXHIBITS` env | Environment variables, loaded by `DebugConfig.from_env()` |
| Domain model discovery | `domains/models/` directory structure | `model.md` files with `type: domain-model` frontmatter |

## Architecture

### Where This Fits

```
[.env + env vars]  [configs/*.json]  [domains/**/*.md]  [Data Sources/**/*.md]
       |                  |                  |                    |
       v                  v                  v                    v
    ConfigLoader     ConfigLoader    DomainConfigLoader   MarkdownConfigLoader
           \              |              /                      /
            \             v             /                      /
             +---->  AppConfig  <------+---------------------+
                         |
                         v
                      DeFunk
```

`ConfigLoader` is the primary entry point. It reads `storage.json`, resolves paths using `run_config.json`, loads `.env`, builds `ConnectionConfig` and `StorageConfig`, merges API configs from markdown (preferred) and JSON (fallback), and produces a single `AppConfig`. Domain model configs flow through a separate `config/domain/` pipeline that parses model markdown, resolves `extends` inheritance, and produces `DomainModelConfig` data classes.

### Dependencies

| Depends On | What For |
|------------|----------|
| `yaml` (PyYAML) | Parsing YAML frontmatter from markdown files |
| `json` (stdlib) | Reading `storage.json`, `run_config.json` |
| `os` (stdlib) | Environment variable access |
| `de_funk.utils.repo` | Centralized repo root discovery |
| `de_funk.config.constants` | Default values for all config parameters |

| Depended On By | What For |
|----------------|----------|
| `DeFunk` (`app.py`) | `ConfigLoader.load()` produces `AppConfig` used for all wiring |
| `Engine` (`core/engine.py`) | Reads `storage_config` dict for API limits |
| `StorageRouter` (`core/storage.py`) | Reads `roots` and `domain_roots` from storage config |
| `FieldResolver` (`api/resolver.py`) | Reads domain model markdown files directly |
| `BuildSession` (`core/sessions.py`) | Receives model configs as dicts or `DomainModelConfig` |

## Key Classes

### SchemaField

**File**: `src/de_funk/config/data_classes.py:25`

**Purpose**: One column in a table schema. Parsed from [name, type, nullable, desc, {opts}].

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `type` | `str` |
| `nullable` | `bool` |
| `description` | `str` |
| `derived` | `Optional[str]` |
| `fk` | `Optional[str]` |
| `format` | `Optional[str]` |

### EdgeSpec

**File**: `src/de_funk/config/data_classes.py:37`

**Purpose**: One graph edge. Parsed from [name, from, to, [keys], cardinality, domain, ...].

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `from_table` | `str` |
| `to_table` | `str` |
| `join_keys` | `list[str]` |
| `cardinality` | `str` |
| `target_domain` | `Optional[str]` |
| `optional` | `bool` |

### MeasureDef

**File**: `src/de_funk/config/data_classes.py:49`

**Purpose**: One measure definition. Parsed from [name, agg, field, label, {opts}].

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `aggregation` | `str` |
| `field` | `str | dict` |
| `label` | `str` |
| `format` | `Optional[str]` |
| `options` | `dict` |

### AliasSpec

**File**: `src/de_funk/config/data_classes.py:60`

**Purpose**: One source alias. Parsed from [target_column, expression].

| Attribute | Type |
|-----------|------|
| `target_column` | `str` |
| `expression` | `str` |

### EnrichSpec

**File**: `src/de_funk/config/data_classes.py:67`

**Purpose**: Join-based enrichment on a table.

| Attribute | Type |
|-----------|------|
| `from_table` | `str` |
| `join` | `list[str]` |
| `columns` | `list[str]` |

### HookDef

**File**: `src/de_funk/config/data_classes.py:75`

**Purpose**: One hook definition — references a Python function by dotted path.

| Attribute | Type |
|-----------|------|
| `fn` | `str` |
| `params` | `dict` |

### PipelineStep

**File**: `src/de_funk/config/data_classes.py:82`

**Purpose**: One step in a config-driven pipeline.

| Attribute | Type |
|-----------|------|
| `op` | `str` |
| `fn` | `Optional[str]` |
| `params` | `dict` |

### PhaseSpec

**File**: `src/de_funk/config/data_classes.py:92`

**Purpose**: One build phase — lists tables to build in this phase.

| Attribute | Type |
|-----------|------|
| `tables` | `list[str]` |

### ModelStorageSpec

**File**: `src/de_funk/config/data_classes.py:98`

**Purpose**: Storage configuration for a domain model.

| Attribute | Type |
|-----------|------|
| `format` | `str` |
| `silver_root` | `Optional[str]` |

### BuildSpec

**File**: `src/de_funk/config/data_classes.py:105`

**Purpose**: Build configuration for a domain model.

| Attribute | Type |
|-----------|------|
| `sort_by` | `list[str]` |
| `optimize` | `bool` |
| `partitions` | `list[str]` |
| `phases` | `dict[str, PhaseSpec]` |

### GraphSpec

**File**: `src/de_funk/config/data_classes.py:114`

**Purpose**: Graph edges and paths for a domain model.

| Attribute | Type |
|-----------|------|
| `edges` | `list[EdgeSpec]` |
| `paths` | `dict[str, Any]` |

### MeasuresSpec

**File**: `src/de_funk/config/data_classes.py:121`

**Purpose**: Measure definitions for a domain model.

| Attribute | Type |
|-----------|------|
| `simple` | `list[MeasureDef]` |
| `computed` | `list[MeasureDef]` |

### HooksConfig

**File**: `src/de_funk/config/data_classes.py:128`

**Purpose**: Build hooks declared in YAML frontmatter.

| Attribute | Type |
|-----------|------|
| `pre_build` | `list[HookDef]` |
| `before_build` | `list[HookDef]` |
| `after_build` | `list[HookDef]` |
| `post_build` | `list[HookDef]` |

### TableConfig

**File**: `src/de_funk/config/data_classes.py:139`

**Purpose**: Parsed from tables/*.md frontmatter.

| Attribute | Type |
|-----------|------|
| `table` | `str` |
| `table_type` | `str` |
| `schema` | `list[SchemaField]` |
| `primary_key` | `list[str]` |
| `unique_key` | `list[str]` |
| `partition_by` | `list[str]` |
| `measures` | `list[MeasureDef]` |
| `enrich` | `list[EnrichSpec]` |
| `pipeline` | `list[PipelineStep]` |
| `extends` | `Optional[str]` |
| `source_file` | `Optional[str]` |

### SourceConfig

**File**: `src/de_funk/config/data_classes.py:155`

**Purpose**: Parsed from sources/**/*.md frontmatter.

| Attribute | Type |
|-----------|------|
| `source` | `str` |
| `maps_to` | `str` |
| `from_ref` | `str` |
| `aliases` | `list[AliasSpec]` |
| `domain_source` | `Optional[str]` |
| `filter` | `list[str]` |
| `discriminator` | `Optional[str]` |
| `extends` | `Optional[str]` |
| `source_file` | `Optional[str]` |

### MLModelSpec

**File**: `src/de_funk/config/data_classes.py:169`

**Purpose**: ML model definition from YAML. Parsed from model.md ml_models: section.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `type` | `str` |
| `target` | `list[str]` |
| `features` | `list[str]` |
| `lookback_days` | `int` |
| `forecast_horizon` | `int` |
| `parameters` | `dict` |
| `retrain_if_stale_days` | `int` |
| `enabled` | `bool` |

| Method | Description |
|--------|-------------|
| `from_dict(data: dict) -> MLModelSpec` | Create an MLModelSpec from a raw YAML dict, applying defaults for all optional fields. |

### DomainModelConfig

**File**: `src/de_funk/config/data_classes.py:197`

**Purpose**: Parsed from model.md frontmatter + auto-discovered tables/sources/views.

| Attribute | Type |
|-----------|------|
| `model` | `str` |
| `version` | `str` |
| `description` | `str` |
| `extends` | `list[str]` |
| `depends_on` | `list[str]` |
| `status` | `str` |
| `sources_from` | `Optional[str]` |
| `storage` | `ModelStorageSpec` |
| `graph` | `GraphSpec` |
| `build` | `BuildSpec` |
| `measures` | `MeasuresSpec` |
| `hooks` | `HooksConfig` |
| `ml_models` | `dict[str, MLModelSpec]` |
| `metadata` | `dict` |
| `tables` | `dict[str, TableConfig]` |
| `sources` | `dict[str, SourceConfig]` |
| `views` | `dict[str, Any]` |
| `source_file` | `Optional[str]` |

### BaseTemplate

**File**: `src/de_funk/config/data_classes.py:223`

**Purpose**: Reusable base template from domains/_base/.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `model` | `str` |
| `version` | `str` |
| `description` | `str` |
| `extends` | `Optional[str]` |
| `canonical_fields` | `list[SchemaField]` |
| `tables` | `dict[str, TableConfig]` |
| `depends_on` | `list[str]` |
| `source_file` | `Optional[str]` |

### EndpointSchemaField

**File**: `src/de_funk/config/data_classes.py:239`

**Purpose**: One field in an endpoint schema — different from domain SchemaField.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `type` | `str` |
| `source_field` | `str` |
| `nullable` | `bool` |
| `description` | `str` |
| `transform` | `Optional[str]` |
| `coerce` | `Optional[str]` |
| `default` | `Optional[Any]` |

### EndpointConfig

**File**: `src/de_funk/config/data_classes.py:252`

**Purpose**: Parsed from Endpoints/**/*.md frontmatter.

| Attribute | Type |
|-----------|------|
| `endpoint_id` | `str` |
| `provider` | `str` |
| `method` | `str` |
| `endpoint_pattern` | `str` |
| `format` | `str` |
| `auth` | `str` |
| `response_key` | `Optional[str]` |
| `default_query` | `dict` |
| `required_params` | `list[str]` |
| `pagination_type` | `str` |
| `bulk_download` | `bool` |
| `download_method` | `str` |
| `json_structure` | `str` |
| `raw_schema` | `list[list]` |
| `schema` | `list[EndpointSchemaField]` |
| `bronze` | `Optional[str]` |
| `partitions` | `list[str]` |
| `write_strategy` | `str` |
| `key_columns` | `list[str]` |
| `date_column` | `Optional[str]` |
| `domain` | `str` |
| `data_tags` | `list[str]` |
| `status` | `str` |
| `update_cadence` | `str` |
| `source_file` | `Optional[str]` |

### ProviderConfig

**File**: `src/de_funk/config/data_classes.py:282`

**Purpose**: Parsed from Providers/*.md frontmatter.

| Attribute | Type |
|-----------|------|
| `provider_id` | `str` |
| `provider` | `str` |
| `api_type` | `str` |
| `base_url` | `str` |
| `auth_model` | `str` |
| `env_api_key` | `str` |
| `rate_limit_per_sec` | `float` |
| `default_headers` | `dict` |
| `provider_settings` | `dict` |
| `endpoints` | `list[str]` |
| `models` | `list[str]` |
| `category` | `str` |
| `data_domains` | `list[str]` |
| `data_tags` | `list[str]` |
| `status` | `str` |
| `source_file` | `Optional[str]` |

### RootsConfig

**File**: `src/de_funk/config/data_classes.py:306`

**Purpose**: Storage mount points for each data tier.

| Attribute | Type |
|-----------|------|
| `raw` | `str` |
| `bronze` | `str` |
| `silver` | `str` |
| `models` | `str` |

| Method | Description |
|--------|-------------|
| `from_dict() -> RootsConfig` | Create a RootsConfig from a raw dict, applying defaults (`storage/raw`, `storage/bronze`, etc.) for missing keys. |

### ApiLimits

**File**: `src/de_funk/config/data_classes.py:324`

**Purpose**: Query limits for the API layer.

| Attribute | Type |
|-----------|------|
| `duckdb_memory_limit` | `str` |
| `max_sql_rows` | `int` |
| `max_dimension_values` | `int` |
| `max_response_mb` | `float` |

| Method | Description |
|--------|-------------|
| `from_dict() -> ApiLimits` | Create ApiLimits from a raw dict with defaults (3GB memory, 30000 rows, 10000 dimension values, 4MB response). |

### TablePath

**File**: `src/de_funk/config/data_classes.py:342`

**Purpose**: Storage path for one table (root tier + relative path).

| Attribute | Type |
|-----------|------|
| `root` | `str` |
| `rel` | `str` |
| `partitions` | `list[str]` |

| Method | Description |
|--------|-------------|
| `full_path() -> str` | Returns `"{root}/{rel}"` or just `root` if `rel` is empty. Property, not a method call. |
| `from_dict() -> TablePath` | Create a TablePath from a raw dict with defaults (root="silver", rel="", partitions=[]). |

### ClusterConfig

**File**: `src/de_funk/config/data_classes.py:362`

**Purpose**: Spark cluster settings from run_config.json.

| Attribute | Type |
|-----------|------|
| `spark_master` | `str` |
| `fallback_to_local` | `bool` |
| `task_batch_size` | `int` |

| Method | Description |
|--------|-------------|
| `from_dict() -> ClusterConfig` | Create ClusterConfig from a raw dict with defaults (spark_master="auto", fallback_to_local=True, task_batch_size=50). |

### RetryConfig

**File**: `src/de_funk/config/data_classes.py:378`

**Purpose**: Retry policy from run_config.json.

| Attribute | Type |
|-----------|------|
| `max_retries` | `int` |
| `retry_delay_seconds` | `float` |
| `exponential_backoff` | `bool` |

| Method | Description |
|--------|-------------|
| `from_dict() -> RetryConfig` | Create RetryConfig from a raw dict with defaults (max_retries=3, retry_delay_seconds=2.0, exponential_backoff=True). |

### RunConfig

**File**: `src/de_funk/config/data_classes.py:394`

**Purpose**: Pipeline run configuration from run_config.json.

| Attribute | Type |
|-----------|------|
| `defaults` | `dict` |
| `providers` | `dict[str, dict]` |
| `silver_models` | `list[str]` |
| `cluster` | `ClusterConfig` |
| `retry` | `RetryConfig` |
| `profiles` | `dict[str, dict]` |

| Method | Description |
|--------|-------------|
| `from_dict() -> RunConfig` | Create RunConfig from a raw dict. Handles both `silver_models` as a list and as a dict with a `models` key. Delegates nested objects to `ClusterConfig.from_dict()` and `RetryConfig.from_dict()`. |

### SparkConfig

**File**: `src/de_funk/config/models.py:13`

**Purpose**: Spark connection configuration.

| Attribute | Type |
|-----------|------|
| `driver_memory` | `str` |
| `executor_memory` | `str` |
| `shuffle_partitions` | `int` |
| `timezone` | `str` |
| `legacy_time_parser` | `bool` |
| `additional_config` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `to_spark_conf_dict() -> Dict[str, str]` | Convert to Spark configuration dictionary. |

### DuckDBConfig

**File**: `src/de_funk/config/models.py:36`

**Purpose**: DuckDB connection configuration.

| Attribute | Type |
|-----------|------|
| `database_path` | `Path` |
| `memory_limit` | `str` |
| `threads` | `int` |
| `read_only` | `bool` |
| `additional_config` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `to_connection_params() -> Dict[str, Any]` | Convert to DuckDB connection parameters. |

### ConnectionConfig

**File**: `src/de_funk/config/models.py:58`

**Purpose**: Database connection configuration.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `spark` | `Optional[SparkConfig]` |
| `duckdb` | `Optional[DuckDBConfig]` |

### StorageConfig

**File**: `src/de_funk/config/models.py:77`

**Purpose**: Storage layer configuration.

| Attribute | Type |
|-----------|------|
| `bronze_root` | `Path` |
| `silver_root` | `Path` |
| `tables` | `Dict[str, Dict[str, Any]]` |

| Method | Description |
|--------|-------------|
| `from_dict(data: Dict[str, Any], repo_root: Path) -> 'StorageConfig'` | Create from storage.json dictionary. |

### APIConfig

**File**: `src/de_funk/config/models.py:94`

**Purpose**: API provider configuration.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `base_url` | `str` |
| `endpoints` | `Dict[str, Any]` |
| `api_keys` | `List[str]` |
| `rate_limit_calls` | `int` |
| `rate_limit_period` | `int` |
| `headers` | `Dict[str, str]` |
| `timeout` | `int` |

| Method | Description |
|--------|-------------|
| `from_dict(name: str, data: Dict[str, Any], api_keys: Optional[List[str]]) -> 'APIConfig'` | Create from endpoint JSON dictionary. |

### DebugConfig

**File**: `src/de_funk/config/models.py:138`

**Purpose**: Debug logging configuration.

| Attribute | Type |
|-----------|------|
| `filters` | `bool` |
| `exhibits` | `bool` |
| `sql` | `bool` |

| Method | Description |
|--------|-------------|
| `from_env() -> 'DebugConfig'` | Load debug flags from environment variables. |

### AppConfig

**File**: `src/de_funk/config/models.py:156`

**Purpose**: Main application configuration.

| Attribute | Type |
|-----------|------|
| `repo_root` | `Path` |
| `connection` | `ConnectionConfig` |
| `storage` | `Dict[str, Any]` |
| `apis` | `Dict[str, Dict[str, Any]]` |
| `log_level` | `str` |
| `debug` | `DebugConfig` |
| `env_loaded` | `bool` |

| Method | Description |
|--------|-------------|
| `models_dir() -> Path` | Get models configuration directory (v3.0 domains/). |
| `legacy_models_dir() -> Path` | Get legacy models configuration directory (v1.x/v2.x configs/models/). |
| `configs_dir() -> Path` | Get configs directory. |

### ConfigLoader

**File**: `src/de_funk/config/loader.py:55`

**Purpose**: Centralized configuration loader.

| Method | Description |
|--------|-------------|
| `load_env(env_file: Optional[Path]) -> None` | Load environment variables from .env file. |
| `load_storage() -> Dict[str, Any]` | Load only storage configuration (no API/provider configs). |
| `load(connection_type: Optional[str], load_env: bool) -> AppConfig` | Load complete application configuration including API configs. |
| `repo_root() -> Path` | Get repository root path. |

### SchemaField

**File**: `src/de_funk/config/markdown_loader.py:46`

**Purpose**: Parsed schema field from array format.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `type` | `str` |
| `source` | `str` |
| `nullable` | `bool` |
| `description` | `str` |
| `transform` | `Optional[str]` |
| `coerce` | `Optional[str]` |
| `expr` | `Optional[str]` |
| `default` | `Optional[Any]` |

| Method | Description |
|--------|-------------|
| `is_computed() -> bool` | Check if this field is computed (source is _computed or expr is set). |
| `is_generated() -> bool` | Check if this field is generated (source is _generated). |

### BronzeConfig

**File**: `src/de_funk/config/markdown_loader.py:82`

**Purpose**: Bronze layer configuration for an endpoint.

| Attribute | Type |
|-----------|------|
| `table` | `str` |
| `partitions` | `List[str]` |
| `write_strategy` | `str` |
| `key_columns` | `List[str]` |
| `date_column` | `Optional[str]` |
| `comment` | `str` |

### EndpointConfig

**File**: `src/de_funk/config/markdown_loader.py:93`

**Purpose**: Parsed endpoint configuration from markdown.

| Attribute | Type |
|-----------|------|
| `endpoint_id` | `str` |
| `provider` | `str` |
| `method` | `str` |
| `endpoint_pattern` | `str` |
| `format` | `str` |
| `auth` | `str` |
| `response_key` | `Optional[str]` |
| `default_query` | `Dict[str, Any]` |
| `required_params` | `List[str]` |
| `pagination_type` | `str` |
| `schema` | `List[SchemaField]` |
| `bronze` | `Optional[BronzeConfig]` |
| `domain` | `str` |
| `data_tags` | `List[str]` |
| `status` | `str` |
| `enabled` | `bool` |
| `view_ids` | `Dict[str, str]` |
| `download_method` | `str` |
| `json_structure` | `str` |
| `raw_schema` | `List[List[Any]]` |
| `raw` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `get_spark_raw_schema()` | Convert raw_schema to a Spark StructType for explicit JSON reading. |

### ProviderConfig

**File**: `src/de_funk/config/markdown_loader.py:170`

**Purpose**: Parsed provider configuration from markdown.

| Attribute | Type |
|-----------|------|
| `provider_id` | `str` |
| `provider` | `str` |
| `api_type` | `str` |
| `base_url` | `str` |
| `auth_model` | `str` |
| `env_api_key` | `str` |
| `rate_limit_per_sec` | `float` |
| `default_headers` | `Dict[str, str]` |
| `models` | `List[str]` |
| `category` | `str` |
| `data_domains` | `List[str]` |
| `data_tags` | `List[str]` |
| `status` | `str` |
| `raw` | `Dict[str, Any]` |

### MarkdownConfigLoader

**File**: `src/de_funk/config/markdown_loader.py:190`

**Purpose**: Load configuration from markdown files with YAML frontmatter.

| Method | Description |
|--------|-------------|
| `parse_frontmatter(md_path: Path) -> Tuple[Dict[str, Any], str]` | Parse YAML frontmatter from a markdown file. |
| `parse_schema_block(body: str) -> Optional[List[Dict[str, Any]]]` | Extract schema from ```yaml code block in markdown body. |
| `parse_view_ids_table(body: str) -> Dict[str, str]` | Extract view_id mappings from markdown table. |
| `parse_schema_array(schema_list: List) -> List[SchemaField]` | Convert compact array schema to structured SchemaField objects. |
| `parse_bronze_config(frontmatter: Dict[str, Any]) -> Optional[BronzeConfig]` | Parse bronze layer configuration from frontmatter. |
| `load_provider(md_path: Path) -> Optional[ProviderConfig]` | Load a single provider configuration from markdown. |
| `load_endpoint(md_path: Path) -> Optional[EndpointConfig]` | Load a single endpoint configuration from markdown. |
| `load_providers(force_reload: bool) -> Dict[str, ProviderConfig]` | Load all provider configurations from markdown files. |
| `load_endpoints(provider: Optional[str], force_reload: bool) -> Dict[str, EndpointConfig]` | Load all endpoint configurations recursively. |
| `get_provider_config(provider_id: str) -> Optional[Dict[str, Any]]` | Get combined provider config in format compatible with existing code. |
| `get_bronze_configs() -> Dict[str, Dict[str, Any]]` | Extract all bronze table configurations from endpoints. |
| `get_endpoint_schema(endpoint_id: str) -> List[Dict[str, Any]]` | Get schema for an endpoint as list of dicts. |
| `get_coercion_rules(endpoint_id: str) -> Dict[str, str]` | Get source field to type coercion rules for an endpoint. |
| `get_field_mappings(endpoint_id: str) -> Dict[str, str]` | Get source field to output field name mappings for an endpoint. |
| `get_computed_fields(endpoint_id: str) -> List[Dict[str, Any]]` | Get computed field definitions for an endpoint. |
| `clear_cache() -> None` | Clear all cached configurations. |

## How to Use

### Common Operations

```python
from pathlib import Path
from de_funk.config.loader import ConfigLoader

# Load full application config
loader = ConfigLoader(repo_root=Path("/home/user/de_Funk"))
config = loader.load(connection_type="duckdb")
# config.repo_root       -> Path("/home/user/de_Funk")
# config.connection.type  -> "duckdb"
# config.storage["roots"]["silver"] -> "/shared/storage/silver"

# Load storage-only config (faster, skips API config parsing)
storage = loader.load_storage()
# storage["roots"]["bronze"] -> "/shared/storage/bronze"

# Load markdown provider/endpoint configs
from de_funk.config.markdown_loader import MarkdownConfigLoader
md_loader = MarkdownConfigLoader(repo_root=Path("/home/user/de_Funk"))
providers = md_loader.load_providers()
endpoints = md_loader.load_endpoints(provider="Alpha Vantage")

# Get bronze write config for an endpoint
bronze_configs = md_loader.get_bronze_configs()
# {"alpha_vantage.time_series_daily": {"table": "time_series_daily", ...}}

# Use typed data classes directly
from de_funk.config.data_classes import RunConfig
import json
with open("configs/run_config.json") as f:
    raw = json.load(f)
run_config = RunConfig.from_dict(raw)
# run_config.cluster.spark_master    -> "auto"
# run_config.retry.max_retries       -> 3
# run_config.silver_models            -> ["securities.stocks", ...]
```

### Integration Examples

```python
# ConfigLoader feeds into DeFunk app creation
from de_funk.app import DeFunk
app = DeFunk.from_config("configs/")
# Internally: ConfigLoader.load() -> AppConfig -> DeFunk.from_app_config()

# MarkdownConfigLoader used by ingest pipelines
from de_funk.config.markdown_loader import MarkdownConfigLoader
md_loader = MarkdownConfigLoader(repo_root=Path("."))
endpoint = md_loader.load_endpoint(Path("Data Sources/Endpoints/Alpha Vantage/Prices/Time Series Daily.md"))
# endpoint.schema       -> [SchemaField(name="open", type="double", ...)]
# endpoint.bronze.table -> "time_series_daily"

# DebugConfig enables runtime SQL logging
import os
os.environ["DEBUG_SQL"] = "true"
from de_funk.config.models import DebugConfig
debug = DebugConfig.from_env()
# debug.sql -> True
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValueError: Configuration file not found: .../storage.json` | Missing `configs/storage.json` | Create the file or check repo root detection |
| `ValueError: Storage path not configured` | `run_config.json` missing `defaults.storage_path` | Add `"defaults": {"storage_path": "/shared/storage"}` to `configs/run_config.json` |
| `ValueError: Invalid connection type: foo` | Typo in `CONNECTION_TYPE` env var or `connection_type` param | Use `"spark"` or `"duckdb"` |
| `ValueError: Repository root does not exist` | `AppConfig.__post_init__` validation failed | Check that the path exists on disk |
| `FALLBACK: Using JSON config for 'alpha_vantage'` (warning) | Provider not yet migrated to markdown | Create `Data Sources/Providers/Alpha Vantage.md` |
| `No .env file found` (debug log) | Missing `.env` in repo root | Create `.env` or set env vars directly |
| Empty `providers` dict after load | `Data Sources/Providers/` directory missing or files lack `type: api-provider` frontmatter | Check markdown files have correct `type:` field |

### Debug Checklist

- [ ] Run `ConfigLoader(repo_root=Path(".")).load()` in isolation to verify config loading works
- [ ] Check `configs/storage.json` is valid JSON (`python -m json.tool configs/storage.json`)
- [ ] Check `configs/run_config.json` has `defaults.storage_path` key
- [ ] Verify `.env` file has API keys in `PROVIDER_API_KEYS=key1,key2` format
- [ ] For markdown config issues, check that files have `---` YAML frontmatter delimiters
- [ ] If repo root auto-detection fails, check that `src/`, `configs/`, and `.git/` all exist in the same directory
- [ ] Set `LOG_LEVEL=DEBUG` to see all config loading details

### Common Pitfalls

1. **Two SchemaField classes**: `data_classes.SchemaField` (domain schemas) and `markdown_loader.SchemaField` (endpoint schemas) are different classes with different attributes. Import the correct one for your context.
2. **`AppConfig.storage` is a raw dict, not `StorageConfig`**: Despite `StorageConfig` existing in `models.py`, `AppConfig.storage` stores the resolved JSON dict (with absolute paths). This is intentional -- it preserves the full structure including `domain_roots` and `tables`.
3. **Environment variables only set if not already present**: `ConfigLoader.load_env()` uses `os.environ.setdefault` semantics -- it will not overwrite existing env vars. Set vars before calling `load_env()` to override `.env` file values.
4. **Nested DuckDB path detection**: `ConfigLoader` has a defensive check for paths like `/path/duckdb/storage/duckdb/analytics.db` and auto-corrects them. If you see a "Detected nested duckdb path" warning, check your `DUCKDB_PATH` env var.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/config/data_classes.py` | Typed data classes mirroring domain YAML frontmatter structure. | `SchemaField`, `EdgeSpec`, `MeasureDef`, `AliasSpec`, `EnrichSpec`, `HookDef`, `PipelineStep`, `PhaseSpec`, `ModelStorageSpec`, `BuildSpec`, `GraphSpec`, `MeasuresSpec`, `HooksConfig`, `TableConfig`, `SourceConfig`, `MLModelSpec`, `DomainModelConfig`, `BaseTemplate`, `EndpointSchemaField`, `EndpointConfig`, `ProviderConfig`, `RootsConfig`, `ApiLimits`, `TablePath`, `ClusterConfig`, `RetryConfig`, `RunConfig` |
| `src/de_funk/config/models.py` | Typed configuration models using dataclasses. | `SparkConfig`, `DuckDBConfig`, `ConnectionConfig`, `StorageConfig`, `APIConfig`, `DebugConfig`, `AppConfig` |
| `src/de_funk/config/loader.py` | Centralized configuration loader. | `ConfigLoader` |
| `src/de_funk/config/domain/build.py` | Build configuration processing for domain v4 configs. | — |
| `src/de_funk/config/domain/config_translator.py` | Domain config translator for model builds. | — |
| `src/de_funk/config/domain/extends.py` | Extends resolution and deep merge for domain v4 configs. | — |
| `src/de_funk/config/domain/federation.py` | Federation configuration processing for domain v4 configs. | — |
| `src/de_funk/config/domain/graph.py` | Graph configuration processing for domain v4 configs. | — |
| `src/de_funk/config/domain/schema.py` | Schema processing for domain v4 configs. | — |
| `src/de_funk/config/domain/sources.py` | Source file processing for domain v4 configs. | — |
| `src/de_funk/config/domain/subsets.py` | Subset auto-absorption for domain v4 configs. | — |
| `src/de_funk/config/domain/views.py` | View configuration processing for domain v4 configs. | — |
| `src/de_funk/config/markdown_loader.py` | Markdown Config Loader - Parse YAML frontmatter from markdown files. | `SchemaField`, `BronzeConfig`, `EndpointConfig`, `ProviderConfig`, `MarkdownConfigLoader` |
| `src/de_funk/config/constants.py` | Default configuration constants. | — |
