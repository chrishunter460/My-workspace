# Python Class & Method Reference

**Last Updated**: 2026-03-23

This document catalogs every public Python class in `src/de_funk/`, explaining what each class does, why it exists, and what its key methods manage. Organized by package.

---

## Table of Contents

1. [config/ — Configuration](#config--configuration)
2. [core/ — Connections, Exceptions, Filters](#core--connections-exceptions-filters)
3. [models/ — Domain Models, Measures, Graph](#models--domain-models-measures-graph)
4. [pipelines/ — Ingestion, Providers, Bronze](#pipelines--ingestion-providers-bronze)
5. [api/ — FastAPI Backend](#api--fastapi-backend)
6. [orchestration/ — Scheduling, Checkpoints](#orchestration--scheduling-checkpoints)

---

## config/ — Configuration

Loading configuration from multiple sources (env vars, JSON files, markdown frontmatter) with clear precedence rules. The `config/domain/` subpackage handles the multi-file domain model format where models, tables, sources, and views live in separate markdown files.

### ConfigLoader

**File**: `config/loader.py`
**Why**: Single entry point for all configuration. Enforces precedence: env vars > explicit params > config files > defaults. Without this, every module would parse `.env` and `storage.json` independently.

| Method | What it does |
|--------|-------------|
| `load(connection_type, load_env)` → `AppConfig` | Load complete application configuration — API keys, storage paths, connection settings, debug flags |
| `load_storage()` → `Dict` | Load only storage configuration (lightweight, no API configs) |
| `repo_root` (property) | Repository root path, discovered by walking up until a marker directory is found |

### AppConfig

**File**: `config/models.py`
**Why**: Typed container replacing loose dictionaries. Catches invalid config at startup instead of runtime KeyError deep in a pipeline.

| Field / Property | Purpose |
|-----------------|---------|
| `connection: ConnectionConfig` | Backend selection (spark or duckdb) |
| `storage: StorageConfig` | Bronze/silver root paths, storage format |
| `api_configs: Dict[str, APIConfig]` | Per-provider API settings (keys, rate limits, base URLs) |
| `debug: DebugConfig` | Debug logging flags (filters, exhibits, SQL) |
| `models_dir` (property) | Path to `domains/` model configs |

**Related dataclasses** (same file): `ConnectionConfig`, `StorageConfig`, `SparkConfig`, `DuckDBConfig`, `APIConfig`, `DebugConfig` — each validates its own section.

### MarkdownConfigLoader

**File**: `config/markdown_loader.py`
**Why**: Providers and endpoints are defined as markdown files in `data_sources/`. This class parses YAML frontmatter, schema blocks, and view-ID tables from those files so the pipeline code never touches raw markdown.

| Method | What it does |
|--------|-------------|
| `load_providers()` → `Dict[str, ProviderConfig]` | Scan all `Providers/*.md` files and return parsed configs |
| `load_endpoints(provider)` → `Dict[str, EndpointConfig]` | Scan all `Endpoints/**/*.md` files, optionally filtered by provider |
| `get_bronze_configs()` → `Dict` | Extract bronze table configs (partitions, write strategy, key columns) from all endpoints |
| `get_coercion_rules(endpoint_id)` → `Dict` | Source field → type coercion map for an endpoint |
| `get_field_mappings(endpoint_id)` → `Dict` | Source field → output field renaming map |
| `get_computed_fields(endpoint_id)` → `List` | Computed/derived field definitions |

**Related dataclasses**: `EndpointConfig` (parsed endpoint with schema, bronze config, query defaults), `ProviderConfig` (parsed provider with base URL, auth model, rate limits), `SchemaField` (single column definition), `BronzeConfig` (table-level bronze settings).

### DomainConfigLoaderV4

**File**: `config/domain/__init__.py`
**Why**: Multi-file domain format where `model.md`, `tables/*.md`, `sources/*.md`, and `views/*.md` are separate files. This loader assembles them into one config dict, handles extends resolution, and provides topological build ordering.

| Method | What it does |
|--------|-------------|
| `load_model_config(model_name)` → `Dict` | Assemble complete config from model.md + discovered tables/sources/views |
| `get_build_order(models)` → `List[str]` | Kahn's algorithm topological sort on `depends_on` |
| `get_dependencies(model_name)` → `List[str]` | Direct dependencies for a model |
| `load_base(base_ref, with_subsets)` → `Dict` | Load a base template by dotted reference (e.g., `_base.fact_table`) |
| `list_models()` → `List[str]` | All discovered domain model names |

**Factory function**: `get_domain_loader(domains_dir)` → `DomainConfigLoaderV4` — entry point for all domain config loading.

### Domain Config Submodules

These are pure-function modules in `config/domain/` that process specific parts of a domain config. No classes — just functions called by the loaders.

| Module | Key Functions | Purpose |
|--------|--------------|---------|
| `config_translator.py` | `translate_domain_config()` | Translate domain YAML into build-compatible `graph.nodes` format |
| `build.py` | `parse_build_config()`, `get_table_build_flags()`, `extract_seed_data()` | Parse build phases, extract seed data from static tables |
| `schema.py` | `process_table_schema()`, `merge_additional_schema()` | Process table schemas through base → additional → derivations pipeline |
| `extends.py` | `resolve_extends_reference()`, `deep_merge()` | Resolve dotted extends references, deep-merge config dicts |
| `federation.py` | `get_federation_config()`, `resolve_union_references()` | Handle federation (cross-domain UNION) configs |
| `graph.py` | `parse_graph_config()`, `resolve_auto_edges()` | Parse graph edges, resolve auto_edges against table schemas |
| `sources.py` | `group_sources_by_target()`, `build_select_expressions()` | Process source → target table mappings, generate SELECT expressions |
| `subsets.py` | `absorb_subsets()` | Scan for subset children and absorb their fields into parent tables |
| `views.py` | `parse_view_config()`, `resolve_view_chain()` | Process view configs, topologically sort view dependencies |

### Logging Utilities

**File**: `config/logging.py`

| Class / Function | Purpose |
|-----------------|---------|
| `setup_logging(config)` | Configure logging once at startup — console (colored) + file (JSON) handlers |
| `get_logger(name)` → `Logger` | Get a module-specific logger |
| `LogTimer(logger, operation)` | Context manager that logs operation start/end with elapsed time |
| `log_function_call(logger)` | Decorator that logs function entry and exit |
| `ColoredFormatter` | Console formatter with ANSI colors by log level |
| `StructuredFormatter` | JSON formatter for file logging (machine-parseable) |

---

## core/ — Connections, Exceptions, Filters

Database connections, exception hierarchy, error handling decorators, and the filter engine.

### DataConnection (ABC)

**File**: `core/connection.py`
**Why**: Abstract interface so model code works identically against Spark or DuckDB. Methods like `read_table()`, `apply_filters()`, `to_pandas()` are backend-agnostic.

### SparkConnection

**File**: `core/connection.py`
**Why**: Wraps a SparkSession with Delta Lake support — time travel reads, merge/upsert, optimize, vacuum, history.

| Method | What it does |
|--------|-------------|
| `read_table(path, format, version, timestamp)` | Read table with optional Delta time travel |
| `write_delta_table(df, path, mode, partition_by)` | Write DataFrame to Delta Lake |
| `merge_delta_table(source_df, target_path, merge_condition)` | Upsert into Delta table |
| `optimize_delta_table(path, zorder_by)` | Compact small files and optionally z-order |
| `vacuum_delta_table(path, retention_hours)` | Remove old Delta files |
| `get_delta_table_history(path)` | Get version history |

### DuckDBConnection

**File**: `core/duckdb_connection.py`
**Why**: In-process analytics connection. Auto-discovers Silver tables and registers them as views on startup. Provides the same Delta Lake operations as SparkConnection for local development.

| Method | What it does |
|--------|-------------|
| `read_table(path, format, version, timestamp)` | Read table with Delta time travel support |
| `write_delta_table(df, path, mode, partition_by)` | Write Pandas DataFrame to Delta |
| `execute_sql(query)` | Execute raw SQL and return result |
| `table(view_name)` | Get a registered view by name |
| `has_view(view_name)` | Check if a view exists |
| `createDataFrame(data, schema)` | Spark-compatible DataFrame creation |

### ConnectionFactory

**File**: `core/connection.py`
**Why**: Creates the right connection type from a string (`"spark"` or `"duckdb"`).

| Method | What it does |
|--------|-------------|
| `create(connection_type, **kwargs)` (static) | Return SparkConnection or DuckDBConnection |

### RepoContext

**File**: `core/context.py`
**Why**: Bundles repo root, storage config, and database connection into one object passed to scripts and builders. Avoids threading 5 separate arguments through every call.

| Method | What it does |
|--------|-------------|
| `from_repo_root(connection_type)` (classmethod) | Create context from repo root with auto-discovered config |
| `get_api_config(provider)` | Get API config for a provider |

### FilterEngine

**File**: `core/session/filters.py`
**Why**: Centralized filter application. One set of filter logic for both Spark DataFrames and DuckDB relations. Also generates SQL WHERE clauses for the API layer.

| Method | What it does |
|--------|-------------|
| `apply_filters(df, filters, backend)` (static) | Apply filters based on backend type |
| `build_filter_sql(filters)` (static) | Build SQL WHERE clause from filter dict |
| `apply_from_session(df, filters, session)` (static) | Apply filters with auto-detected backend |

### Exception Hierarchy

**File**: `core/exceptions.py`
**Why**: Typed exceptions with structured `details` dict and `recovery_hint`. Lets error handlers provide actionable messages instead of raw tracebacks.

```
DeFunkError (base)
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
│   ├── InsufficientDataError(required, available, ticker)
│   └── ModelTrainingError(model_type, error, ticker)
└── ConnectionError(backend, error)
```

### Error Handling Utilities

**File**: `core/error_handling.py`

| Function / Class | Purpose |
|-----------------|---------|
| `handle_exceptions(*types, default_return, reraise)` | Decorator for consistent exception handling |
| `retry_on_exception(*types, max_retries, backoff_factor)` | Decorator for automatic retry with exponential backoff |
| `safe_call(func, *args, default)` | Call function safely, return default on exception |
| `ErrorContext(operation, **context)` | Context manager that logs operation start/end with timing |

### NotebookValidator

**File**: `core/validation.py`
**Why**: Validates exhibit configurations against the model registry before execution. Catches bad field references, missing models, and invalid filters at parse time.

| Method | What it does |
|--------|-------------|
| `validate(notebook_config)` → `List[ValidationError]` | Full validation pass — models, exhibits, filters |
| `is_valid(notebook_config)` → `bool` | Quick check: any errors? |

---

## models/ — Domain Models, Measures, Graph

The model layer reads domain configs, builds Silver tables from Bronze, provides table access and measure calculation, and writes results to storage.

### BaseModel

**File**: `models/base/model.py`
**Why**: The core abstraction. Reads a YAML/markdown domain config and provides a complete model lifecycle: build from Bronze, access tables, calculate measures, write to Silver. Every domain model either uses BaseModel directly or subclasses it.

| Method | What it does |
|--------|-------------|
| `build()` → `(dims, facts)` | Build all model tables from Bronze layer using GraphBuilder |
| `ensure_built()` | Lazy build — only build when first table is requested |
| `get_table(table_name)` | Get any table (dimension or fact) by name |
| `get_table_enriched(table_name, enrich_with, columns)` | Get table with dimension columns joined in via graph edges |
| `get_denormalized(fact_table, include_dims, columns)` | Get fact table with all related dimensions joined |
| `calculate_measure(measure_name, filters, entity_column)` | Calculate any measure defined in model config |
| `write_tables(output_root, format, mode, partition_by)` | Persist all tables to Delta Lake storage |
| `before_build()` / `after_build(dims, facts)` | Hooks for subclass customization |
| `custom_node_loading(node_id, node_config)` | Override to handle special node types |

**Composition**: BaseModel delegates to `GraphBuilder` (build), `TableAccessor` (table access), `MeasureCalculator` (measures), `ModelWriter` (persistence), `GraphQueryPlanner` (enriched queries).

### DomainModel

**File**: `models/base/domain_model.py`
**Why**: Extends BaseModel for multi-file domain configs. Handles node types that don't come from Bronze: seed/static tables, multi-source UNION tables, generated tables, and distinct projections.

| Method | What it does |
|--------|-------------|
| `custom_node_loading(node_id, node_config)` | Handle `__seed__`, `__union__`, `__generated__`, `__distinct__` node markers |

### GraphBuilder

**File**: `models/base/graph_builder.py`
**Why**: Turns the `graph.nodes` config into actual DataFrames. Loads each node from Bronze (or from custom_node_loading), applies SELECT/WHERE/JOIN transforms, handles cross-model references, and returns built dimensions and facts.

| Method | What it does |
|--------|-------------|
| `build()` → `(dims, facts)` | Execute the full build graph — load nodes, apply transforms, partition into dims/facts |

### TableAccessor

**Why**: Extracted from BaseModel to keep table-access logic in one place. Handles the "search dims then facts" pattern, schema inspection, and enriched queries.

### MeasureCalculator

**Why**: Extracted from BaseModel. Routes measure calculation to the right executor (simple SQL, computed expression, or Python measure module).

### ModelWriter

**Why**: Handles Delta Lake persistence with auto-vacuum, partitioning, and overwrite/append modes. Separated so write logic doesn't clutter the model class.

| Method | What it does |
|--------|-------------|
| `write_tables(output_root, format, mode, partition_by, quiet)` | Write all model tables to storage as Delta Lake |

### DomainBuilderFactory

**File**: `models/base/domain_builder.py`
**Why**: Scans `domains/` at startup and dynamically creates a builder class for each domain model. These builders are registered in the `BuilderRegistry` so the build pipeline can instantiate any model by name.

| Method | What it does |
|--------|-------------|
| `create_builders(domains_dir)` (classmethod) | Scan configs, create builder classes, register them |

### GraphQueryPlanner

**File**: `models/api/query_planner.py`
**Why**: Uses NetworkX graph of table relationships to plan dynamic joins at query time. When you request `get_table_enriched("fact_crimes", enrich_with=["dim_community_area"])`, this finds the join path through the graph edges.

| Method | What it does |
|--------|-------------|
| `get_table_enriched(table_name, enrich_with, columns)` | Join tables along graph edges, select requested columns |

### StorageRouter

**File**: `models/api/dal.py`
**Why**: Translates config-style table references (like `bronze://chicago/crimes` or `silver://municipal.public_safety/fact_crimes`) into filesystem paths. Single source of truth for where data lives.

| Method | What it does |
|--------|-------------|
| `resolve(table_ref)` → `str` | Resolve a table reference to an absolute path |
| `bronze_path(logical_table)` | Legacy: resolve bronze table path |
| `silver_path(logical_rel)` | Legacy: resolve silver table path |

### Session

**File**: `models/api/session.py`
**Why**: Model-agnostic session for cross-model queries. Loads models on demand, provides the model registry and dependency graph, and supports auto-join across models.

### ModelGraph

**File**: `models/api/graph.py`
**Why**: Cross-model dependency graph using NetworkX. Two graphs: a DAG for build ordering and a join graph (which can have cycles) for query-time relationship traversal.

| Method | What it does |
|--------|-------------|
| `build_from_registry(model_registry)` | Build both graphs from the model registry |
| `validate_no_cycles()` | Verify the dependency DAG has no cycles |

### DomainConfigLoader

**File**: `models/registry.py`
**Why**: Central catalog of all available models. Provides model lookup, table listing, schema inspection, and class registration for dynamic instantiation.

| Method | What it does |
|--------|-------------|
| `list_models()` → `List[str]` | All available model names |
| `get_model(model_name)` → `ModelConfig` | Get model configuration |
| `list_tables(model_name)` / `list_measures(model_name)` | Tables/measures in a model |
| `get_table_schema(model_name, table_name)` | Column definitions for a table |
| `register_model_class(model_name, model_class)` | Register a Python class for a model |

### Measures Framework

**Location**: `models/measures/`
**Why**: Pluggable measure system. Each measure type (simple aggregation, computed expression, weighted, window, ratio) is a separate class implementing `BaseMeasure.to_sql()`. The registry + executor route measure requests to the right implementation.

| Class | File | Purpose |
|-------|------|---------|
| `BaseMeasure` (ABC) | `measures/base_measure.py` | Contract: `to_sql(adapter)` generates SQL for this measure |
| `SimpleMeasure` | `measures/simple.py` | Standard aggregations: AVG, SUM, MIN, MAX, COUNT |
| `ComputedMeasure` | `measures/computed.py` | Custom SQL expressions before aggregation |
| `MeasureRegistry` | `measures/registry.py` | Decorator-based registration of measure types |
| `MeasureExecutor` | `measures/executor.py` | Single entry point: `execute_measure(name, filters, entity_column)` |

### Backend Adapters

**Location**: `models/base/backend/`
**Why**: SQL generation and execution abstraction. The model layer generates queries through the adapter interface; the adapter handles dialect differences between Spark SQL and DuckDB.

| Class | File | Purpose |
|-------|------|---------|
| `BackendAdapter` (ABC) | `backend/adapter.py` | Interface: `execute_sql()`, `get_table_reference()`, `get_dialect()` |
| `SparkAdapter` | `backend/spark_adapter.py` | Spark SQL execution with Delta Lake table references |
| `DuckDBAdapter` | `backend/duckdb_adapter.py` | DuckDB execution with delta_scan/read_parquet references |
| `SQLBuilder` | `backend/sql_builder.py` | Utility for building SQL with dialect support |

### Other Model Classes

| Class | File | Purpose |
|-------|------|---------|
| `AutoJoinHandler` | `models/api/auto_join.py` | Plans and executes automatic joins based on model graph |
| `AggregationHandler` | `models/api/aggregation.py` | Group-by aggregation with measure-aware inference |
| `TimeSeriesForecastModel` | `models/base/forecast_model.py` | Abstract base for time series forecasting models |
| `DataValidator` / `ValidationReport` | `models/base/data_validator.py` | Base class for data quality validation during builds |

---

## pipelines/ — Ingestion, Providers, Bronze

Fetching data from external APIs, normalizing it, and writing to the Bronze layer as Delta Lake tables.

### BaseProvider (ABC)

**File**: `pipelines/base/provider.py`
**Why**: Abstract interface that all data providers implement. Defines the contract: list work items, fetch data, normalize records, get table names. Provider-specific details (API auth, pagination, rate limits) live in subclasses.

| Method | What it does |
|--------|-------------|
| `list_work_items(**kwargs)` → `List[str]` | Discover available work items (endpoints, tickers, etc.) |
| `fetch(work_item, max_records)` → `Generator` | Fetch data for a work item, yielding batches |
| `normalize(records, work_item)` → `DataFrame` | Normalize raw API records to Spark DataFrame |
| `get_table_name(work_item)` → `str` | Bronze table name for a work item |
| `get_write_strategy(work_item)` → `str` | Write strategy: append, overwrite, or append_immutable |

### SocrataBaseProvider

**File**: `pipelines/base/socrata_provider.py`
**Why**: Base class for Socrata (Chicago, Cook County) providers. Handles Socrata-specific concerns: SoQL pagination, multi-year view IDs, CSV bulk download, raw file caching, Socrata date/timestamp parsing.

| Method | What it does |
|--------|-------------|
| `fetch(work_item, max_records)` | Fetch from Socrata, auto-detecting single-resource vs multi-year |
| `normalize(records, work_item)` | Normalize with Socrata-specific type casting and date parsing |
| `read_csv_with_spark(csv_path, endpoint)` | Bulk-read a downloaded CSV with Spark |
| `enable_raw_save(storage_path)` | Enable saving raw CSV responses for replay |

### ChicagoProvider

**File**: `pipelines/providers/chicago/chicago_provider.py`
**Why**: Chicago Data Portal provider. Inherits everything from SocrataBaseProvider — just sets the provider ID and factory function.

### CookCountyProvider

**File**: `pipelines/providers/cook_county/cook_county_provider.py`
**Why**: Cook County Data Portal provider. Same Socrata base with an extra `fetch_parcel_data(pins)` method for PIN-specific queries.

### AlphaVantageProvider

**File**: `pipelines/providers/alpha_vantage/alpha_vantage_provider.py`
**Why**: Alpha Vantage REST API provider. Handles API key rotation, raw-layer caching, per-ticker/per-datatype fetching, and Alpha Vantage-specific response parsing.

### IngestorEngine

**File**: `pipelines/base/ingestor_engine.py`
**Why**: Universal ingestion orchestrator. Takes any `BaseProvider` and runs the full cycle: discover work items → fetch → normalize → write to Bronze. Supports async writes (background Delta Lake writes while fetching the next batch) and batch progress tracking.

| Method | What it does |
|--------|-------------|
| `run(work_items, write_batch_size, max_records)` → `IngestionResults` | Run ingestion for specified work items |
| `run_with_discovery(write_batch_size, max_records)` → `IngestionResults` | Auto-discover work items and ingest all |

**Factory function**: `create_engine(provider_name, storage_cfg)` — create an engine for any registered provider.

### Facet

**File**: `pipelines/base/facet.py`
**Why**: Markdown-driven data transformation. Reads schema from endpoint markdown files and applies a normalization pipeline: clean raw values → coerce types → apply Spark casts → apply computed fields → enforce final column set. Used by AlphaVantageProvider for per-endpoint transforms.

| Method | What it does |
|--------|-------------|
| `normalize(raw_batches)` → `DataFrame` | Full normalization pipeline from raw dicts to typed DataFrame |
| `postprocess(df)` → `DataFrame` | Override hook for custom transforms |

### SocrataClient

**File**: `pipelines/base/socrata_client.py`
**Why**: HTTP client for Socrata Open Data APIs (SODA). Handles pagination, rate limiting, CSV bulk download, row counting, and metadata retrieval.

| Method | What it does |
|--------|-------------|
| `fetch_all(resource_id, query_params, limit, max_records)` | Paginated fetch yielding batches |
| `fetch_csv(resource_id, batch_size, max_records)` | Bulk CSV download yielding batches |
| `download_csv_to_file(resource_id, output_path)` | Stream CSV to local file for Spark reading |
| `get_row_count(resource_id, where_clause)` | Get total record count via SoQL |

### BronzeSink

**File**: `pipelines/ingestors/bronze_sink.py`
**Why**: Writes DataFrames to the Bronze layer as Delta Lake tables. Handles write-if-missing and append-immutable (deduplicated time-series append) strategies.

| Method | What it does |
|--------|-------------|
| `write_if_missing(table, partitions, df)` | Write only if table doesn't exist |
| `append_immutable(df, table, key_columns, date_column)` | Append new records, skip duplicates by key |

### Resilience Classes

| Class | File | Purpose |
|-------|------|---------|
| `CircuitBreaker` | `base/circuit_breaker.py` | Failure isolation — stops calling a failing endpoint after N failures, auto-recovers after timeout |
| `CircuitBreakerManager` | `base/circuit_breaker.py` | Singleton managing circuit breakers for all endpoints |
| `TokenBucket` | `base/rate_limiter.py` | Token bucket rate limiter with configurable refill rate |
| `RateLimiterManager` | `base/rate_limiter.py` | Singleton managing rate limiters per provider |
| `ApiKeyPool` | `base/key_pool.py` | Rotates API keys with cooldown tracking |
| `HttpClient` | `base/http_client.py` | HTTP client with rate limiting, retry, and API key substitution |

### Progress & Metrics

| Class | File | Purpose |
|-------|------|---------|
| `PipelineProgressTracker` | `base/progress_tracker.py` | Multi-phase progress tracking with ETA and progress bars |
| `BatchProgressTracker` | `base/progress_tracker.py` | Per-ticker, per-data-type progress for batch ingestion |
| `MetricsCollector` | `base/metrics.py` | Collects timing metrics per pipeline step |
| `TimingContext` | `base/metrics.py` | Context manager: `with metrics.time("step"):` |

### SparkNormalizer

**File**: `pipelines/base/normalizer.py`
**Why**: Standard Spark-based normalizer for all providers. Applies field mappings, type coercions, date parsing, computed columns, and metadata columns.

| Method | What it does |
|--------|-------------|
| `normalize(records, field_mappings, type_coercions, ...)` → `DataFrame` | Full normalization pipeline |
| `normalize_with_schema(records, schema_fields)` → `DataFrame` | Normalize using endpoint schema field definitions |

### ProviderRegistry

**File**: `pipelines/providers/registry.py`
**Why**: Auto-discovers available providers and provides factory access. Scripts call `ProviderRegistry.get_ingestor("chicago")` without knowing the class or module path.

| Method | What it does |
|--------|-------------|
| `discover()` (classmethod) | Scan provider directories and register all found providers |
| `get_ingestor(provider_name, spark, storage_cfg)` | Instantiate a provider by name |
| `list_available()` → `List[str]` | All registered provider names |
| `get_providers_for_model(model_name)` → `List[str]` | Providers that feed a specific model |

---

## api/ — FastAPI Backend

The query execution layer. The Obsidian plugin sends exhibit block payloads to these endpoints; handlers resolve fields, build SQL, execute against DuckDB, and return formatted results.

### FieldResolver

**File**: `api/resolver.py`
**Why**: Translates `domain.field` references (like `municipal.public_safety.crime_type`) into Silver table paths and column names. Scans `domains/models/` at startup and builds an index with a join graph for multi-table queries.

| Method | What it does |
|--------|-------------|
| `resolve(ref_str)` → `ResolvedField` | Resolve one `domain.field` reference to table path + column |
| `resolve_many(refs)` → `Dict[str, ResolvedField]` | Batch resolve multiple references |
| `find_join_path(src, dst, allowed_domains)` | BFS over graph edges to find join path between tables |
| `reachable_domains(core_domains)` | Compute allowed domains: core + their depends_on |
| `get_field_catalog()` | Full catalog for `GET /api/domains` |

**Supporting classes**: `FieldRef` (parsed domain.field with longest-prefix matching), `ResolvedField` (resolution result with table_name, column, silver_path, format_code).

### Engine

**File**: `api/executor.py`
**Why**: Shared DuckDB infrastructure for all handlers. Manages the DuckDB connection, builds FROM clauses with automatic joins, builds WHERE clauses from filters, and provides centralized query execution with row limits and MB caps.

| Method | What it does |
|--------|-------------|
| `_execute(sql, max_rows)` | Execute SQL, stream at most max_rows |
| `_build_from(tables, resolver, allowed_domains)` | Build FROM clause with BFS join resolution |
| `_build_where(filters, resolver)` | Build WHERE fragments from filter specs |
| `distinct_values(resolved, extra_filters)` | Sorted distinct values for a dimension field |

### Exhibit Handlers

Each handler subclasses `ExhibitHandler` and implements `execute(payload, resolver)`. They inherit `Engine` for shared SQL infrastructure.

| Handler | File | Block Types | What it produces |
|---------|------|-------------|-----------------|
| `GraphicalHandler` | `handlers/graphical.py` | `plotly.line`, `bar`, `scatter`, `area`, `pie`, `heatmap` | `GraphicalResponse` with series data |
| `PivotHandler` | `handlers/pivot.py` | `table.pivot`, `pivot`, `great_table`, `gt` | `GreatTablesResponse` with rendered HTML |
| `TableDataHandler` | `handlers/table_data.py` | `table.data`, `data_table` | `TableResponse` with columns and rows |
| `MetricsHandler` | `handlers/metrics.py` | `cards.metric`, `kpi` | `MetricResponse` with formatted KPI values |
| `BoxHandler` | `handlers/box.py` | `plotly.box`, `ohlcv`, `candlestick` | Box plot / OHLCV series data |

### HandlerRegistry

**File**: `api/handlers/__init__.py`
**Why**: Maps block type strings to handler instances. The `/api/query` endpoint looks up the handler by `payload.type` and delegates execution.

| Method | What it does |
|--------|-------------|
| `register(handler)` | Register a handler for all its type strings |
| `get(type_str)` → `ExhibitHandler` | Look up handler by block type |

### Request / Response Models

**File**: `api/models/requests.py`
**Why**: Pydantic models that validate incoming exhibit payloads and structure outgoing responses. Each exhibit type has a request model (validating required fields) and a response model.

**Key request models**: `GraphicalQueryRequest`, `PivotQueryRequest`, `TableDataQueryRequest`, `MetricQueryRequest`, `BoxQueryRequest`

**Key response models**: `GraphicalResponse` (series data), `TableResponse` (columns + rows), `GreatTablesResponse` (rendered HTML + expandable data), `MetricResponse` (KPI values), `DimensionValuesResponse` (dropdown values)

**Shared specs**: `FilterSpec`, `SortSpec`, `MeasureTuple`, `ColumnTuple`, `WindowSpec`, `BucketSpec`, `TotalsSpec`

### Supporting Modules

| Module | Key Functions | Purpose |
|--------|--------------|---------|
| `measures.py` | `build_measure_sql(measure, resolver)` | Translate measure tuples to SQL expressions |
| `gt_formatter.py` | `build_gt(rows, columns, formatting)` | Build Great Tables HTML from pivot data |
| `formatting.py` | `resolve_format(key, column_format, overrides)` | Resolve format codes ($, %, number) for columns |
| `reshape.py` | `apply_windows_1d(rows, columns, windows)` | Apply window calculations (pct_change, diff, rank) |

### FastAPI Routes

**File**: `api/main.py` + `api/routers/`

| Route | Method | Purpose |
|-------|--------|---------|
| `GET /api/health` | Health check | Liveness probe |
| `GET /api/domains` | Field catalog | Returns all available `domain.field` references |
| `GET /api/dimensions/{ref}` | Dimension values | Distinct values for sidebar dropdowns |
| `POST /api/query` | Execute query | Dispatches exhibit payload to appropriate handler |

---

## orchestration/ — Scheduling, Checkpoints

Pipeline scheduling, checkpoint/resume, dependency resolution, and Spark session management.

### CheckpointManager

**File**: `orchestration/checkpoint.py`
**Why**: Long-running ingestion pipelines (hundreds of tickers) can fail mid-run. This persists progress to disk so you can resume from where you left off instead of re-ingesting everything.

| Method | What it does |
|--------|-------------|
| `create_checkpoint(pipeline_name, tickers)` | Create a new checkpoint for a pipeline run |
| `find_resumable_checkpoint(pipeline_name)` | Find a checkpoint that can be resumed |
| `mark_ticker_completed(ticker, endpoints)` | Record a ticker as done |
| `mark_ticker_failed(ticker, error)` | Record a ticker failure |
| `get_pending_tickers()` → `List[str]` | Tickers still needing processing |
| `get_progress()` → `Dict` | Current progress summary with statistics |

### PipelineScheduler

**File**: `orchestration/scheduler.py`
**Why**: Cron-style scheduling for recurring pipeline jobs using APScheduler. Default jobs: daily price ingestion, daily silver rebuild, weekly forecasts.

| Method | What it does |
|--------|-------------|
| `add_job(func, trigger, job_id, **trigger_kwargs)` | Add a scheduled job |
| `register_default_jobs()` | Register the default pipeline jobs |
| `start(register_defaults)` | Start the scheduler |
| `run_job_now(job_id)` | Manually trigger a job |

### DependencyGraph

**File**: `orchestration/dependency_graph.py`
**Why**: Model dependency resolution for build ordering. Discovers model configs, builds a NetworkX graph, and provides topological sort and tier grouping.

| Method | What it does |
|--------|-------------|
| `topological_sort()` → `List[str]` | All models in correct build order |
| `filter_buildable(requested)` → `List[str]` | Build order for specific models with auto-included dependencies |
| `get_dependents(model_name)` → `List[str]` | Models that depend on this model |
| `get_tiers()` → `Dict[int, List[str]]` | Models grouped by dependency tier |
| `validate()` → `List[str]` | Validate graph integrity (returns errors) |

### Spark Session

**File**: `orchestration/common/spark_session.py`

| Function | Purpose |
|----------|---------|
| `get_spark(app_name, config, master)` → `SparkSession` | Get or create a Spark session with Delta Lake, memory tuning, and standard configs |

### Airflow DAGs

**Location**: `orchestration/airflow/dags/`
**Why**: Declarative DAG definitions for Airflow deployment. Three DAGs: model building (with dependency-based task ordering), stock forecasting (with task groups), and Alpha Vantage ingestion.

| DAG File | Purpose |
|----------|---------|
| `build_models.py` | Model building with dependency-aware task ordering |
| `forecast_stocks.py` | Distributed stock price forecasting |
| `ingest_alpha_vantage.py` | Alpha Vantage API data ingestion |

---

## Design Patterns Summary

| Pattern | Where | Why |
|---------|-------|-----|
| **Composition over inheritance** | BaseModel delegates to GraphBuilder, TableAccessor, MeasureCalculator, ModelWriter | Keeps each concern < 300 lines |
| **Abstract base + factory** | DataConnection → SparkConnection/DuckDBConnection via ConnectionFactory | Backend-agnostic code |
| **Registry + decorator** | MeasureRegistry, HandlerRegistry, ProviderRegistry | Plugin-style extensibility |
| **Strategy** | BackendAdapter → SparkAdapter/DuckDBAdapter | Dialect-specific SQL generation |
| **Template method** | BaseProvider.fetch/normalize, Facet.normalize/postprocess | Common pipeline with provider-specific overrides |
| **Circuit breaker + token bucket** | CircuitBreaker, TokenBucket | Resilient API calls with failure isolation and rate limiting |
| **Checkpoint/resume** | CheckpointManager | Recover long-running pipelines from failure |
