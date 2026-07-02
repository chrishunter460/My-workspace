---
title: "Engine & Sessions"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/engine.py
  - src/de_funk/core/ops.py
  - src/de_funk/core/sql.py
  - src/de_funk/core/sessions.py
  - src/de_funk/core/session/filters.py
  - src/de_funk/core/storage.py
  - src/de_funk/core/connection.py
  - src/de_funk/core/duckdb_connection.py
---

# Engine & Sessions

> Backend-agnostic Engine (read/write/transform), scoped Sessions (Build/Query/Ingest), and connection wrappers.

## Purpose & Design Decisions

### What Problem This Solves

de_Funk supports two backends (DuckDB for interactive queries, Spark for batch ETL) that have completely different DataFrame APIs. Without an abstraction layer, every piece of business logic (model builders, API handlers, notebooks) would need backend-specific branches. This group solves that with a **Strategy pattern** split across three layers:

1. **DataOps** (abstract) + DuckDBOps/SparkOps -- backend-agnostic DataFrame operations (read, write, join, filter, aggregate, pivot, window, etc.)
2. **SqlOps** (abstract) + DuckDBSql/SparkSql -- backend-agnostic SQL operations (execute, scan, FROM clause building, WHERE clause building, distinct values)
3. **Engine** -- facade that delegates to the active DataOps + SqlOps pair

On top of Engine sit three **scoped Sessions** that restrict what each pipeline path can do:
- `BuildSession`: reads Bronze + Silver, writes Silver, has models + graph
- `QuerySession`: reads Silver (read-only), has resolver + graph for joins
- `IngestSession`: reads API configs, writes Raw + Bronze

This separation enforces the project's architecture boundaries (build code cannot accidentally query, query code cannot accidentally write) while keeping the Engine itself general-purpose.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Strategy pattern (DataOps/SqlOps) instead of inheritance on Engine | Engine stays a thin facade. Adding a new backend means implementing two interfaces (DataOps + SqlOps) without touching Engine or any session. | Engine subclasses (DuckDBEngine, SparkEngine); rejected because it doubles the surface area and sessions would need to know which Engine subclass they hold. |
| DuckDBOps uses pandas DataFrames as the internal representation | DuckDB's Python API returns pandas DataFrames natively. Avoids unnecessary conversion and lets DuckDB handle SQL pushdown via `from_df()` when needed. | DuckDB relations everywhere; rejected because most downstream code (handlers, builders) already expects pandas-like column access. |
| `scan()` method with path caching on DuckDBSql | Delta Lake scan probing (`delta_scan` vs `read_parquet`) is expensive. Caching prevents repeated filesystem probes for the same table across a single query. | No caching; rejected because a single exhibit query may reference the same table 3-4 times (SELECT, WHERE, GROUP BY). |
| Sessions are short-lived, Engine is long-lived | Engine holds the DuckDB connection (or Spark session) which is expensive to create. Sessions are cheap (just config + references) and can be created per-request without overhead. | One session for the app lifetime; rejected because it would mix build and query state. |
| `StorageRouter` as a separate class from Sessions | Path resolution logic is shared across all session types. Extracting it prevents duplication and makes path resolution testable in isolation. | Inline path logic in each Session; rejected because three sessions would duplicate the same root resolution code. |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| DuckDB memory limit | `api.duckdb_memory_limit` in storage config | `configs/storage.json` > `api` section |
| Max SQL result rows | `api.max_sql_rows` in storage config | `configs/storage.json` > `api` section |
| Max dimension distinct values | `api.max_dimension_values` in storage config | `configs/storage.json` > `api` section |
| Storage tier root paths (raw/bronze/silver/models) | `roots` dict in storage config | `configs/storage.json` > `roots` section |
| Per-domain silver path overrides | `domain_roots` dict in storage config | `configs/storage.json` > `domain_roots` section |
| Delta vs Parquet read format | Auto-detected at scan time by DuckDBSql/DuckDBOps | Tries `delta_scan()` first, falls back to `read_parquet()` |
| Filter date expressions (`current_date - 30`) | `_eval_date_expr()` in `sql.py` | Evaluated at SQL build time from filter specs |

## Architecture

### Where This Fits

```
[DeFunk.from_app_config()]
         |
         v
      Engine -----> DataOps (DuckDBOps | SparkOps)
         |     `--> SqlOps  (DuckDBSql  | SparkSql)
         |
    +---------+---------+
    |         |         |
    v         v         v
BuildSession  QuerySession  IngestSession
    |              |              |
    v              v              v
[DomainBuilder] [API Handlers] [Ingestors]
```

The Engine is created once by `DeFunk` and shared by all sessions. Each session type adds its own context (models, resolver, providers) and exposes only the operations appropriate for its pipeline path. Downstream consumers (builders, handlers, ingestors) interact with sessions, not Engine directly.

`StorageRouter` is instantiated inside each `Session.__init__` from the storage config dict and provides path resolution for all four tiers.

### Dependencies

| Depends On | What For |
|------------|----------|
| `duckdb` (via `Engine.for_duckdb`) | In-process SQL engine for interactive queries |
| `pyspark` (via `Engine.for_spark`) | Distributed processing for batch builds |
| `de_funk.config.logging` | Logger for all engine/session operations |
| `de_funk.core.exceptions` | `DataNotFoundError`, `WriteError` for Engine error wrapping |
| `de_funk.core.storage.StorageRouter` | Path resolution in all Session subclasses |
| `de_funk.api.resolver.FieldResolver` | Domain.field resolution in QuerySession |
| `de_funk.models.base.domain_builder` | Model building in BuildSession |

| Depended On By | What For |
|----------------|----------|
| `DeFunk` (`app.py`) | Creates Engine and stamps out sessions |
| API handlers (`api/handlers/`) | Use Engine for SQL execution, FROM/WHERE building |
| Model builders (`models/base/`) | Use BuildSession for read/write/transform |
| FastAPI server (`api/server.py`) | QuerySession per request |
| `FilterEngine` (`core/session/filters.py`) | Backend-agnostic filter application |

## Key Classes

### Engine

**File**: `src/de_funk/core/engine.py:20`

**Purpose**: Backend-agnostic data engine.

| Method | Description |
|--------|-------------|
| `for_duckdb(memory_limit: str, max_sql_rows: int, max_dimension_values: int) -> Engine` | Create a DuckDB-backed engine with DataOps + SqlOps. |
| `for_spark(storage_config: dict) -> Engine` | Create a Spark-backed engine with DataOps + SqlOps. |
| `read(path: str, format: str) -> Any` | Read a table from storage. Raises `DataNotFoundError` on failure. |
| `write(df: Any, path: str, format: str, mode: str) -> None` | Write a DataFrame to storage. Raises `WriteError` on failure. |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | Create a DataFrame from rows and column schema. |
| `select(df: Any, columns: list[str]) -> Any` | Select specific columns from a DataFrame. |
| `drop(df: Any, columns: list[str]) -> Any` | Drop columns from a DataFrame. |
| `derive(df: Any, col: str, expr: str) -> Any` | Add a computed column via SQL expression. |
| `filter(df: Any, conditions: list[str]) -> Any` | Filter rows by SQL condition strings. |
| `dedup(df: Any, subset: list[str]) -> Any` | Deduplicate rows by column subset. |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | Join two DataFrames on key columns. |
| `union(dfs: list[Any]) -> Any` | Vertically stack multiple DataFrames. |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | Melt wide columns into long format. |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | Add a window function column. |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | Pivot rows to columns with aggregation. |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | Group by columns and apply aggregate functions. |
| `count(df: Any) -> int` | Count rows in a DataFrame. |
| `to_pandas(df: Any) -> Any` | Convert to pandas DataFrame (no-op for DuckDB, `.toPandas()` for Spark). |
| `columns(df: Any) -> list[str]` | Get column names from a DataFrame. |
| `execute_sql(sql_str: str, max_rows: int) -> list` | Execute raw SQL and return rows up to max_rows limit. |
| `scan(path: str) -> str` | Return a backend-specific scan expression for a storage path (e.g. `delta_scan('/path')` or `delta.\`/path\``). |
| `build_from(tables: dict[str, str], resolver, allowed_domains: set[str] | None) -> str` | Build a FROM clause with automatic join resolution via BFS. |
| `build_where(filters: list, resolver, from_tables: set[str] | None) -> list[str]` | Build WHERE clause fragments from filter spec objects. |
| `distinct_values(resolved, extra_filters, resolver, max_values: int) -> list` | Return sorted distinct values for a dimension field. |
| `distinct_values_by_measure(resolved, order_by, order_dir, extra_filters, resolver) -> list` | Return distinct values ordered by aggregated measure. |
| `get_query_engine()` | Deprecated: handlers now use Engine directly. |
| `get_handler_registry(resolver, bronze_resolver, max_response_mb: float, storage_root)` | Create a HandlerRegistry using this Engine directly. |

### DataOps

**File**: `src/de_funk/core/ops.py:19`

**Purpose**: Abstract interface for backend-agnostic DataFrame operations.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | Read a table from storage. |
| `write(df: Any, path: str, format: str, mode: str) -> None` | Write a DataFrame to storage. |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | Create a DataFrame from rows and schema. |
| `select(df: Any, columns: list[str]) -> Any` | Select columns from a DataFrame. |
| `drop(df: Any, columns: list[str]) -> Any` | Drop columns from a DataFrame. |
| `derive(df: Any, col: str, expr: str) -> Any` | Add a computed column via SQL expression. |
| `filter(df: Any, conditions: list[str]) -> Any` | Filter rows by SQL conditions. |
| `dedup(df: Any, subset: list[str]) -> Any` | Deduplicate rows by column subset. |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | Join two DataFrames. |
| `union(dfs: list[Any]) -> Any` | Vertically stack multiple DataFrames. |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | Melt wide columns into long format. |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | Add a window function column. |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | Pivot rows to columns with aggregation. |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | Group and aggregate. |
| `count(df: Any) -> int` | Count rows. |
| `to_pandas(df: Any) -> Any` | Convert to pandas DataFrame. |
| `columns(df: Any) -> list[str]` | Get column names. |

### DuckDBOps (DataOps)

**File**: `src/de_funk/core/ops.py:111`

**Purpose**: DuckDB implementation of DataOps using in-process SQL.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | Reads via `delta_scan()` or `read_parquet()` and returns a pandas DataFrame. |
| `write(df: Any, path: str, format: str, mode: str) -> None` | Writes to Parquet file at `{path}/data.parquet`. Creates directories as needed. |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | Creates a pandas DataFrame from rows and column names. |
| `select(df: Any, columns: list[str]) -> Any` | Pandas column selection via `df[columns]`. |
| `drop(df: Any, columns: list[str]) -> Any` | Pandas `drop(columns=..., errors="ignore")`. |
| `derive(df: Any, col: str, expr: str) -> Any` | Registers df as DuckDB relation, projects `*, (expr) AS col`, returns pandas. |
| `filter(df: Any, conditions: list[str]) -> Any` | Chains DuckDB relation `.filter()` calls for each condition string. |
| `dedup(df: Any, subset: list[str]) -> Any` | Pandas `drop_duplicates(subset=...)`. |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | Pandas `merge(on=..., how=...)`. |
| `union(dfs: list[Any]) -> Any` | Pandas `concat(dfs, ignore_index=True)`. |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | Pandas `melt()`. |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | Registers df as `__df`, runs SQL OVER() window expression, returns pandas. |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | Registers df, runs GROUP BY SQL with aggregation expressions, returns pandas. |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | Registers df, runs GROUP BY SQL with `func("col") AS alias`, returns pandas. |
| `count(df: Any) -> int` | Returns `len(df)`. |
| `to_pandas(df: Any) -> Any` | No-op (DuckDB DataOps already uses pandas). |
| `columns(df: Any) -> list[str]` | Returns `list(df.columns)`. |

### SparkOps (DataOps)

**File**: `src/de_funk/core/ops.py:247`

**Purpose**: Spark implementation of DataOps.

| Method | Description |
|--------|-------------|
| `read(path: str, format: str) -> Any` | `spark.read.format(format).load(path)` -- returns Spark DataFrame. |
| `write(df: Any, path: str, format: str, mode: str) -> None` | `df.write.format(format).mode(mode).save(path)`. |
| `create_df(rows: list[list], schema: list[tuple[str, str]]) -> Any` | Creates Spark DataFrame with StructType schema from type map. |
| `select(df: Any, columns: list[str]) -> Any` | `df.select(*columns)`. |
| `drop(df: Any, columns: list[str]) -> Any` | `df.drop(*columns)`. |
| `derive(df: Any, col: str, expr: str) -> Any` | `df.withColumn(col, F.expr(expr))`. |
| `filter(df: Any, conditions: list[str]) -> Any` | Chains `df.filter(cond)` for each condition. |
| `dedup(df: Any, subset: list[str]) -> Any` | `df.dropDuplicates(subset)`. |
| `join(left: Any, right: Any, on: list[str], how: str) -> Any` | `left.join(right, on=on, how=how)`. |
| `union(dfs: list[Any]) -> Any` | `unionByName(allowMissingColumns=True)` across all DataFrames. |
| `unpivot(df: Any, id_cols: list[str], value_cols: list[str], var_name: str, val_name: str) -> Any` | Spark `df.unpivot()`. |
| `window(df: Any, partition: list[str], order: list[str], expr: str, alias: str) -> Any` | `F.expr(expr).over(Window.partitionBy(...).orderBy(...))`. |
| `pivot(df: Any, rows: list[str], cols: list[str], measures: list[dict]) -> Any` | `groupBy(*rows).pivot(cols[0]).agg(...)`. |
| `aggregate(df: Any, group_by: list[str], aggs: list[dict]) -> Any` | `groupBy(*group_by).agg(...)` with dynamic aggregate functions. |
| `count(df: Any) -> int` | `df.count()`. |
| `to_pandas(df: Any) -> Any` | `df.toPandas()`. |
| `columns(df: Any) -> list[str]` | `df.columns`. |

### SqlOps

**File**: `src/de_funk/core/sql.py:40`

**Purpose**: Abstract interface for SQL operations.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | Execute raw SQL and return rows. |
| `scan(path: str) -> str` | Return a backend-specific scan expression for a storage path. |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | Build a FROM clause with automatic join resolution. |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | Build WHERE clause fragments from filter specs. |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | Return sorted distinct values for a dimension field. |

### DuckDBSql (SqlOps)

**File**: `src/de_funk/core/sql.py:74`

**Purpose**: DuckDB implementation of SqlOps.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | Executes SQL via DuckDB connection with `fetchmany(limit)`. Uses `_max_sql_rows` as default limit. |
| `scan(path: str) -> str` | Returns `delta_scan('{path}')` or `read_parquet('{path}/*.parquet')` with result caching. |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | Builds FROM with JOINs by using resolver BFS to find join paths between tables. Falls back to CROSS JOIN when no path exists. Resolves intermediate table paths for multi-hop joins. |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | Translates filter specs (in, eq, gte, lte, like, between) to SQL WHERE fragments. Supports date expressions like `current_date - 30`. Skips filters for tables not in the FROM clause. |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | Runs `SELECT DISTINCT ... ORDER BY ... LIMIT` against a single table scan. |

### SparkSql (SqlOps)

**File**: `src/de_funk/core/sql.py:234`

**Purpose**: Spark implementation of SqlOps.

| Method | Description |
|--------|-------------|
| `execute_sql(sql: str, max_rows: int) -> list` | `spark.sql(sql).limit(max_rows).collect()` converted to list of lists. |
| `scan(path: str) -> str` | Returns `delta.\`{path}\`` for Spark SQL. |
| `build_from(tables: dict[str, str], resolver: Any, allowed_domains: set[str] | None) -> str` | Simplified implementation: CROSS JOINs all tables (no BFS join resolution). |
| `build_where(filters: list, resolver: Any, from_tables: set[str] | None) -> list[str]` | Returns empty list (filter building not yet implemented for Spark). |
| `distinct_values(resolved: Any, extra_filters: list | None, resolver: Any, max_values: int) -> list` | Reads Delta table, selects distinct column values, limits, and collects. |

### Session

**File**: `src/de_funk/core/sessions.py:22`

**Purpose**: Abstract base for all sessions.

| Method | Description |
|--------|-------------|
| `raw_path(provider: str, endpoint: str) -> str` | Resolve raw storage path. |
| `bronze_path(provider: str, endpoint: str) -> str` | Resolve bronze storage path. |
| `silver_path(domain: str, table: str) -> str` | Resolve silver storage path. |
| `model_path(model_name: str, version: str) -> str` | Resolve ML model artifact path. |
| `close()` | Clean up session resources. |

### BuildSession (Session)

**File**: `src/de_funk/core/sessions.py:54`

**Purpose**: Session for building Silver tables from Bronze + Silver dependencies.

| Method | Description |
|--------|-------------|
| `get_model(model_name: str) -> dict` | Get a domain model config by name. |
| `get_dependencies(model_name: str) -> list[str]` | Get dependency list for a model. |
| `build(model_name: str) -> Any` | Build a single model — passes this session directly to the builder. |
| `build_all() -> list` | Build all models in dependency order (Kahn's topological sort). |
| `close()` | No-op (Engine owns the connection). |

### QuerySession (Session)

**File**: `src/de_funk/core/sessions.py:153`

**Purpose**: Session for querying Silver tables (read-only).

| Method | Description |
|--------|-------------|
| `resolve(ref_str: str)` | Resolve a domain.field reference to a ResolvedField. |
| `find_join_path(src: str, dst: str) -> list` | Find join path between two tables. |
| `distinct_values(resolved, extra_filters, resolver) -> list` | Return distinct values for a dimension field. |
| `build_from(tables: dict[str, str], allowed_domains: set[str] | None) -> str` | Build FROM clause with automatic join resolution. |
| `build_where(filters: list, from_tables: set[str] | None) -> list[str]` | Build WHERE clause fragments from filter specs. |
| `close()` | No-op (Engine owns the connection). |

### IngestSession (Session)

**File**: `src/de_funk/core/sessions.py:194`

**Purpose**: Session for ingesting data from external APIs.

| Method | Description |
|--------|-------------|
| `get_provider(provider_id: str) -> dict` | Get provider config by ID. |
| `get_endpoint(provider_id: str, endpoint_id: str) -> dict` | Get endpoint config by provider + endpoint ID. |
| `close()` | No-op (Engine owns the connection). |

### FilterEngine

**File**: `src/de_funk/core/session/filters.py:24`

**Purpose**: Centralized filter application for all backends.

| Method | Description |
|--------|-------------|
| `apply_filters(filters: Dict[str, Any], backend: str) -> Any` | Apply filters based on backend type. |
| `apply_from_session(filters: Dict[str, Any], session) -> Any` | Apply filters using session's backend detection. |
| `build_filter_sql() -> str` | Build SQL WHERE clause from filter specifications. |

### StorageRouter

**File**: `src/de_funk/core/storage.py:22`

**Purpose**: Resolves storage paths from config.

| Method | Description |
|--------|-------------|
| `raw_path(provider: str, endpoint: str) -> str` | Resolve raw storage path: raw_root/provider/endpoint. |
| `bronze_path(provider: str, endpoint: str) -> str` | Resolve bronze storage path: bronze_root/provider/endpoint. |
| `silver_path(domain: str, table: str) -> str` | Resolve silver storage path with domain_roots overrides. |
| `model_path(model_name: str, version: str) -> str` | Resolve ML model artifact path. |
| `resolve(table_ref: str) -> str` | Resolve a config-style table reference to a path. |
| `silver_root() -> str` | Property returning the silver root path string. |
| `bronze_root() -> str` | Property returning the bronze root path string. |
| `raw_root() -> str` | Property returning the raw root path string. |
| `models_root() -> str` | Property returning the models root path string. |

### DataConnection

**File**: `src/de_funk/core/connection.py:20`

**Purpose**: Abstract base class for data connections.

| Method | Description |
|--------|-------------|
| `read_table(path: str, format: str) -> Any` | Read a table from storage. |
| `apply_filters(df: Any, filters: Dict[str, Any]) -> Any` | Apply filters to a dataframe. |
| `to_pandas(df: Any) -> pd.DataFrame` | Convert to Pandas DataFrame. |
| `count(df: Any) -> int` | Get row count. |
| `cache(df: Any) -> Any` | Cache dataframe in memory. |
| `uncache(df: Any)` | Remove from cache. |
| `stop()` | Close connection and cleanup resources. |

### SparkConnection (DataConnection)

**File**: `src/de_funk/core/connection.py:93`

**Purpose**: Spark-based data connection with Delta Lake support.

| Method | Description |
|--------|-------------|
| `read_table(path: str, format: str, version: Optional[int], timestamp: Optional[str])` | Read table using Spark with optional Delta Lake time travel. |
| `write_delta_table(df, path: str, mode: str, partition_by: Optional[List[str]])` | Write Spark DataFrame to Delta Lake table. |
| `merge_delta_table(source_df, target_path: str, merge_condition: str, update_set: Optional[Dict[str, str]], insert_values: Optional[Dict[str, str]])` | Merge (upsert) data into Delta table using Spark's Delta Lake API. |
| `optimize_delta_table(path: str, zorder_by: Optional[List[str]])` | Optimize Delta table (compact files, optionally z-order). |
| `vacuum_delta_table(path: str, retention_hours: int)` | Vacuum Delta table (remove old files). |
| `get_delta_table_history(path: str, limit: Optional[int]) -> pd.DataFrame` | Get version history of Delta table. |
| `apply_filters(df, filters: Dict[str, Any])` | Apply filters using Spark SQL. |
| `to_pandas(df) -> pd.DataFrame` | Convert Spark DataFrame to pandas. |
| `count(df) -> int` | Get row count. |
| `cache(df)` | Cache Spark DataFrame. |
| `uncache(df)` | Uncache Spark DataFrame. |
| `stop()` | Stop Spark session and cleanup. |

### ConnectionFactory

**File**: `src/de_funk/core/connection.py:468`

**Purpose**: Factory for creating data connections.

| Method | Description |
|--------|-------------|
| `create() -> DataConnection` | Create a data connection. |

### DuckDBConnection (DataConnection)

**File**: `src/de_funk/core/duckdb_connection.py:37`

**Purpose**: DuckDB connection for analytics queries with Delta Lake support.

| Method | Description |
|--------|-------------|
| `table(view_name: str) -> Any` | Get a table or view by name from the DuckDB catalog. |
| `has_view(view_name: str) -> bool` | Check if a view exists in the database. |
| `read_table(path: str, format: str, version: Optional[int], timestamp: Optional[str]) -> Any` | Read a table from storage (Parquet or Delta Lake). |
| `write_delta_table(df: pd.DataFrame, path: str, mode: str, partition_by: Optional[List[str]])` | Write DataFrame to Delta Lake table. |
| `get_delta_table_history(path: str) -> pd.DataFrame` | Get the version history of a Delta table. |
| `optimize_delta_table(path: str, zorder_by: Optional[List[str]])` | Optimize Delta table (compact small files, optionally z-order). |
| `vacuum_delta_table(path: str, retention_hours: int, enforce_retention: bool)` | Vacuum Delta table (remove old files no longer needed). |
| `read_parquet(path: str) -> Any` | Read parquet file(s) from path. |
| `createDataFrame(data: list, schema) -> Any` | Create a DuckDB relation from data and schema. |
| `apply_filters(df: Any, filters: Dict[str, Any]) -> Any` | Apply filters to a DuckDB relation. |
| `to_pandas(df: Any) -> pd.DataFrame` | Convert DuckDB relation to pandas DataFrame. |
| `count(df: Any) -> int` | Get row count from DuckDB relation. |
| `cache(df: Any, name: Optional[str]) -> Any` | Cache a DuckDB relation. |
| `uncache(df: Any)` | Remove cached table. |
| `stop()` | Close the DuckDB connection. |
| `execute_sql(query: str) -> Any` | Execute raw SQL query. |
| `execute(query: str) -> Any` | Execute raw SQL query (alias for execute_sql). |

## How to Use

### Common Operations

```python
from de_funk.core.engine import Engine

# Create a DuckDB engine for interactive use
engine = Engine.for_duckdb(memory_limit="4GB", max_sql_rows=50000)

# Read a Silver table
df = engine.read("/shared/storage/silver/securities/stocks/facts/fact_daily_price")

# Filter and aggregate
filtered = engine.filter(df, ["date_id >= 20260101"])
result = engine.aggregate(
    filtered,
    group_by=["ticker"],
    aggs=[
        {"func": "AVG", "col": "adjusted_close", "alias": "avg_close"},
        {"func": "SUM", "col": "volume", "alias": "total_volume"},
    ],
)

# Execute raw SQL against a Delta table
rows = engine.execute_sql(
    f"SELECT ticker, COUNT(*) FROM {engine.scan('/shared/storage/silver/stocks/facts/fact_daily_price')} GROUP BY ticker",
    max_rows=100,
)

# Build a multi-table FROM clause with automatic joins
from_sql = engine.build_from(
    tables={
        "fact_daily_price": "/shared/storage/silver/stocks/facts/fact_daily_price",
        "dim_stock": "/shared/storage/silver/stocks/dims/dim_stock",
    },
    resolver=resolver,  # FieldResolver instance
)
# -> 'delta_scan(...) AS "fact_daily_price" JOIN delta_scan(...) AS "dim_stock" ON ...'
```

```python
# Using sessions via DeFunk
from de_funk.app import DeFunk
app = DeFunk.from_config()

# Build session: build a single domain model
session = app.build_session()
result = session.build("securities.stocks")
# result.success -> True/False
# result.duration_seconds -> 12.5

# Query session: resolve fields and query
session = app.query_session()
resolved = session.resolve("securities.stocks.ticker")
values = session.distinct_values(resolved)
# values -> ["AAPL", "GOOGL", "MSFT", ...]

# StorageRouter path resolution
from de_funk.core.storage import StorageRouter
router = StorageRouter({"roots": {"silver": "/shared/storage/silver", "bronze": "/shared/storage/bronze"}})
router.silver_path("securities.stocks", "facts/fact_daily_price")
# -> "/shared/storage/silver/securities/stocks/facts/fact_daily_price"
router.bronze_path("alpha_vantage", "time_series_daily")
# -> "/shared/storage/bronze/alpha_vantage/time_series_daily"
```

### Integration Examples

```python
# FilterEngine with DuckDB backend
from de_funk.core.session.filters import FilterEngine

filters = {
    "ticker": ["AAPL", "GOOGL"],
    "volume": {"min": 1000000},
    "date_id": {"start": "2025-01-01", "end": "2025-12-31"},
}

# Generate SQL WHERE clause
where_sql = FilterEngine.build_filter_sql(filters)
# -> "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000 AND date_id >= '2025-01-01' AND date_id <= '2025-12-31'"

# Apply directly to a DuckDB relation
filtered_df = FilterEngine.apply_filters(df, filters, backend="duckdb")

# QuerySession used by API handlers
session = app.query_session()
from_clause = session.build_from(
    {"fact_daily_price": "/path/to/table", "dim_stock": "/path/to/dim"},
    allowed_domains={"securities.stocks"},
)
where_clauses = session.build_where(filter_specs, from_tables={"fact_daily_price", "dim_stock"})
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `DataNotFoundError: Engine.read failed` | Delta table path does not exist or has no data files | Verify the path exists on disk; check `StorageRouter.silver_path()` output |
| `CROSS JOIN` in generated SQL instead of proper JOIN | Resolver returned `None` for join path -- tables have no declared edge | Add an edge in the domain model's `graph.edges` YAML section |
| `RuntimeError: QuerySession has no resolver` | `query_session()` was created but FieldResolver failed to build index | Check `domains/models/` has table files with `schema:` frontmatter |
| `KeyError: 'securities.stocks'` from `BuildSession.get_model()` | Model name not in loaded models dict | Verify `domains/models/securities/stocks/model.md` exists with `model: securities.stocks` |
| Empty distinct values list | Table exists but column has all NULLs or path is wrong | Check data quality; run `engine.execute_sql("SELECT COUNT(*) FROM ...")` to verify |
| `WriteError: Engine.write failed` | Permission denied or disk full on storage path | Check filesystem permissions and available space |
| Filter silently ignored | Filter references a table not in the FROM clause (`from_tables` check) | Ensure the filtered field's table is included in the query's table set |
| DuckDB `read_parquet` instead of `delta_scan` | Delta extension failed to install/load | Check `INSTALL delta; LOAD delta;` succeeds in DuckDB. May need `pip install duckdb[delta]`. |

### Debug Checklist

- [ ] Check `engine.backend` is the expected value ("duckdb" or "spark")
- [ ] Verify table paths with `StorageRouter`: `router.silver_path("domain", "table")`
- [ ] Test `engine.scan("/path/to/table")` to see if it returns `delta_scan` or `read_parquet`
- [ ] For JOIN issues, test `resolver.find_join_path("table_a", "table_b")` directly
- [ ] For filter issues, call `engine.build_where(filters, resolver)` in isolation
- [ ] Set `DEBUG_SQL=true` to log all generated SQL queries
- [ ] Check DuckDB memory limit: `engine._sql._conn.execute("SELECT current_setting('memory_limit')")`

### Common Pitfalls

1. **DuckDBOps `write()` always writes Parquet, not Delta**: Despite accepting `format="delta"`, DuckDBOps writes to `{path}/data.parquet`. For true Delta writes, use `DuckDBConnection.write_delta_table()` or the Spark backend.
2. **`_from_tables` side effect in DuckDBSql.build_from()**: `build_from()` sets `self._from_tables` as a side effect, which `build_where()` reads. These methods must be called in order: `build_from()` first, then `build_where()`. Calling `build_where()` without a prior `build_from()` skips table membership checks.
3. **SparkSql.build_where() returns empty list**: The Spark WHERE clause builder is not yet implemented. Spark-backend queries must build filters through SparkOps or Spark SQL directly.
4. **Session.close() is a no-op for all session types**: Sessions do not own the Engine connection. Closing a session does not close the underlying DuckDB/Spark connection. The Engine (and its connection) is managed by `DeFunk`.
5. **FilterEngine date-to-date_id auto-conversion**: When a table has `date_id` (integer YYYYMMDD) but no `date` column, FilterEngine silently converts `date` filter keys to `date_id` with integer conversion. This is correct for star schema tables but may surprise users expecting string date comparisons.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/core/engine.py` | Engine — long-lived backend-agnostic data operations. | `Engine` |
| `src/de_funk/core/ops.py` | DataOps — backend-agnostic DataFrame operation interfaces. | `DataOps`, `DuckDBOps`, `SparkOps` |
| `src/de_funk/core/sql.py` | SqlOps — backend-agnostic SQL operation interfaces. | `SqlOps`, `DuckDBSql`, `SparkSql` |
| `src/de_funk/core/sessions.py` | Session abstractions — scoped contexts for each pipeline path. | `Session`, `BuildSession`, `QuerySession`, `IngestSession` |
| `src/de_funk/core/session/filters.py` | Centralized filter engine for applying filters across different backends. | `FilterEngine` |
| `src/de_funk/core/storage.py` | StorageRouter — resolves storage paths for all 4 data tiers. | `StorageRouter` |
| `src/de_funk/core/connection.py` | Connection layer abstraction for data access. | `DataConnection`, `SparkConnection`, `ConnectionFactory` |
| `src/de_funk/core/duckdb_connection.py` | DuckDB connection implementation with Delta Lake support. | `DuckDBConnection` |
