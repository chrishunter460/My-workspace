# Architecture

de_Funk is a graph-based analytical overlay that turns markdown domain configs into a queryable data warehouse. Users write exhibit blocks in Obsidian notes; the plugin sends structured queries to a FastAPI backend that resolves fields, builds joins, and executes SQL against DuckDB over Delta Lake silver tables.

## System Diagram

```
Obsidian Note (```de_funk block)
       |
       v
+--------------------+       HTTP/JSON        +------------------------------+
|  Obsidian Plugin   | ----------------------> |   FastAPI Backend             |
|  (TypeScript)      |                         |   :8765                      |
|                    | <---------------------- |                              |
|  * filter-sidebar  |    Plotly traces /      |  DeFunk.from_config()        |
|  * de-funk.ts      |    GT HTML /            |    ├── Engine (DuckDB)       |
|  * render/*        |    metric values        |    ├── FieldResolver         |
+--------------------+                         |    ├── HandlerRegistry       |
                                               |    ├── DomainGraph           |
                                               |    └── ArtifactStore         |
                                               |                              |
                                               |  Silver (Delta)  Bronze (Delta)
                                               +------------------------------+

Build Pipeline (offline, Spark):

  API Sources → Raw (JSON/CSV) → Bronze (Delta) → Silver (Delta) → Models (pkl)
       |              |                |                |               |
  rate-limited    archived         typed tables     dims + facts    ArtifactStore
  incremental    compressed        per endpoint     per domain      versioned
```

## Three Execution Paths

**Query path (interactive)**: `DeFunk.from_config()` creates an `Engine` with `DuckDBOps` + `DuckDBSql`. The `HandlerRegistry` injects the Engine into each `ExhibitHandler`. When an Obsidian exhibit fires, the handler uses `FieldResolver` to map `domain.field` → `table.column`, `DomainGraph` for BFS join paths, and `Engine.execute_sql()` for DuckDB queries.

**Build path (batch)**: `DomainBuilderFactory` scans `domains/models/` for `model.md` files, creates builders, resolves dependencies via topological sort, and builds Silver tables from Bronze using Spark. `GraphBuilder` delegates to `NodeExecutor` when an `Engine` is available. Hooks fire from YAML config via `_run_hooks()`.

**Ingest path**: `IngestorEngine` orchestrates `BaseProvider` subclasses (Chicago, Cook County, Alpha Vantage) to fetch from APIs, save raw responses via `RawSink`, normalize to DataFrames, and write Delta tables via `BronzeSink`. Raw data is archived to compressed tar.gz after Bronze write.

## Core Classes

### DeFunk (Application Entry Point)

```python
app = DeFunk.from_config("configs/")
# Creates: Engine, DomainGraph, ArtifactStore
# Loads: 26 domain models, 3 providers, 49 endpoints

session = app.build_session()    # → BuildSession (Bronze → Silver)
session = app.query_session()    # → QuerySession (read Silver)
session = app.ingest_session()   # → IngestSession (API → Raw → Bronze)
```

### Engine (Backend-Agnostic Operations)

```python
engine = Engine.for_duckdb(storage_config=cfg)   # DuckDBOps + DuckDBSql
engine = Engine.for_spark(spark, storage_config)  # SparkOps + SparkSql

# All operations delegate to DataOps strategy:
engine.read(path)                    # → DuckDBOps.read() or SparkOps.read()
engine.filter(df, ["col > 5"])       # → backend filter
engine.join(left, right, on=["id"])  # → backend join
engine.write(df, path)               # → backend write

# SQL operations delegate to SqlOps:
engine.execute_sql("SELECT ...")     # → DuckDBSql or SparkSql
engine.build_from(tables, resolver)  # → FROM with BFS joins
engine.scan(path)                    # → delta_scan() or read_parquet()
```

### Sessions (Scoped Contexts)

```python
# BuildSession: scoped to Silver builds
session = app.build_session()
session.engine          # Engine with ops
session.graph           # DomainGraph for dependency resolution
session.storage_router  # StorageRouter for path resolution
session.build("temporal")  # → BaseModelBuilder → BaseModel → Silver

# QuerySession: scoped to reads
session = app.query_session()
session.resolve("securities.stocks.close")  # → ResolvedField
session.build_from(tables, resolver)         # → SQL FROM clause
session.distinct_values(resolved)            # → dimension values

# IngestSession: scoped to API ingestion
session = app.ingest_session()
session.get_provider("chicago")
session.get_endpoint("chicago", "crimes")
```

### DomainGraph (Join Resolution)

Built from `EdgeSpec` objects across all domain model configs. Provides BFS shortest-path join resolution.

```python
graph = DomainGraph(models)
graph.all_tables()     # → 70 tables
graph.all_edges()      # → 91 edges
graph.find_join_path("dim_stock", "dim_calendar")  # → BFS path
graph.reachable_domains({"securities.stocks"})      # → transitive deps
```

### Handlers (Exhibit Execution)

All handlers inherit `ExhibitHandler` and use `Engine` directly (no mixin inheritance):

```python
class GraphicalHandler(ExhibitHandler):
    handles = {"line", "bar", "scatter", "area", "pie", "heatmap"}

    def execute(self, payload, resolver):
        tables = self._collect_tables(resolved_fields)
        from_clause = self._build_from(tables, resolver)  # → Engine.build_from()
        rows = self._execute(sql)                          # → Engine.execute_sql()
        return GraphicalResponse(series=...)
```

### NodeExecutor (Config-Driven Pipeline)

Executes build pipelines from YAML config. 12 built-in ops mapping to Engine methods:

```python
executor = NodeExecutor(build_session)
executor.register_op("custom_transform", my_fn)

# Execute all nodes in a model config
results = executor.execute_all(graph_nodes_config)

# Built-in ops: filter, join, select, derive, dedup, drop,
#               enrich, window, unpivot, pivot, aggregate, hook
```

### ArtifactStore (ML Model Lifecycle)

```python
store = ArtifactStore(models_root="/shared/storage/models")
store.save(artifact, trained_model)     # → model.pkl + metadata.json
artifact, model = store.latest("stock_predictor")  # recall latest
versions = store.list_versions("stock_predictor")   # all versions
```

## Storage Tiers

| Tier | Mount | Format | Contents |
|------|-------|--------|----------|
| Raw | `/shared/storage/raw/` | JSON/CSV | API responses, archived to tar.gz |
| Bronze | `/shared/storage/bronze/` | Delta Lake | Typed tables per endpoint |
| Silver | `/shared/storage/silver/` | Delta Lake | Dimensional star schemas per domain |
| Models | `/shared/storage/models/` | Pickle + JSON | Trained ML artifacts |

## Data Flow

```
Chicago API ──┐                    ┌── temporal
Cook County ──┤  RawSink  BronzeSink  │── municipal.geospatial
Alpha Vantage ┘  (JSON)   (Delta)  ├── municipal.public_safety  ──┐
                    │         │     ├── securities.stocks         ├── ArtifactStore
                    ▼         ▼     └── ...                      │   (model.pkl)
                 archive   Bronze     Silver                     │
                (tar.gz)  (typed)   (dims+facts)            Train + Save
```

## Configuration

All domain models defined in markdown YAML frontmatter:

```
domains/models/
├── temporal/model.md              # Calendar dimension
├── securities/stocks/model.md     # Stock prices + technicals
├── municipal/public_safety/       # Chicago crime data
│   ├── model.md
│   └── tables/
│       ├── dim_crime_type.md
│       └── fact_crimes.md
└── analytics/workbook/model.md    # ML workbook (cross-domain)
```

Infrastructure config in `configs/`:
- `storage.json` — storage roots, API limits, domain_roots overrides
- `run_config.json` — provider settings, cluster config, retry policy
- `.env` — API keys, Spark master URL
