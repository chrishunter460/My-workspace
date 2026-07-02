---
title: "Application"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/app.py
---

# Application

> DeFunk entry point — assembles config, engine, graph, and sessions into a single app object.

## Purpose & Design Decisions

### What Problem This Solves

Application startup requires loading configuration from multiple sources (JSON files, markdown frontmatter, environment variables), creating backend connections (DuckDB or Spark), building a join graph from domain model edge specs, and indexing provider/endpoint configs. Without a single orchestration point, every script and API entry point would duplicate this multi-step wiring. `DeFunk` centralizes it into one object that holds the fully assembled state and exposes factory methods for scoped sessions.

The pattern follows Flask/SQLAlchemy's "application object" idiom: one long-lived object wires infrastructure together, then stamps out short-lived sessions for each unit of work.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Static factory methods (`from_config`, `from_app_config`) instead of complex `__init__` | Keeps `__init__` as a plain assignment (easy to test with mocks). Factory methods encode the ordered assembly steps (config -> models -> graph -> engine -> providers). | Single `__init__` with all logic; rejected because it mixes construction with initialization and makes partial testing harder. |
| Lazy imports inside session factory methods | Avoids circular imports between `app.py`, `sessions.py`, and `resolver.py`. The import cost is paid once per factory call, not at module load time. | Top-level imports; rejected because the bidirectional dependency chain (app -> sessions -> engine -> ops) triggers import cycles at startup. |
| Spark fallback to DuckDB in `_create_engine` | Allows running on developer machines without Spark installed. Logs a warning so the fallback is visible. | Fail hard; rejected because most interactive/notebook use cases only need DuckDB. |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Backend selection (DuckDB vs Spark) | `connection_type` param or `CONNECTION_TYPE` env var | `configs/storage.json` > `connection.type`, env var, or explicit param |
| DuckDB memory limit and row caps | `api.duckdb_memory_limit`, `api.max_sql_rows`, `api.max_dimension_values` | `configs/storage.json` > `api` section |
| Domain model discovery paths | `models_dir` property on `AppConfig` | Defaults to `{repo_root}/domains` |
| Per-domain silver storage overrides | `domain_roots` dict in storage config | `configs/storage.json` > `domain_roots` |

## Architecture

### Where This Fits

```
[ConfigLoader + MarkdownConfigLoader] --> [DeFunk] --> [BuildSession / QuerySession / IngestSession]
          (config files)                  (wiring)         (scoped work units)
```

`DeFunk.from_config()` calls `ConfigLoader.load()` to produce an `AppConfig`, then calls private helpers to load domain models, build the `DomainGraph`, create the `Engine`, load provider/endpoint configs, and create an `ArtifactStore`. Downstream code never touches config files directly -- it receives a session with everything pre-wired.

### Dependencies

| Depends On | What For |
|------------|----------|
| `ConfigLoader` (`config/loader.py`) | Produces `AppConfig` from JSON + env |
| `Engine` (`core/engine.py`) | Backend-agnostic data operations |
| `DomainGraph` (`core/graph.py`) | Join graph from EdgeSpecs |
| `FieldResolver` (`api/resolver.py`) | Domain.field resolution for `QuerySession` |
| `StorageRouter` (`core/storage.py`) | Path resolution (via sessions) |
| `ArtifactStore` (`core/artifacts.py`) | ML model lifecycle management |
| Domain config loader (`config/domain/`) | Markdown model loading |

| Depended On By | What For |
|----------------|----------|
| FastAPI server (`api/server.py`) | Creates `DeFunk` at startup, uses sessions per request |
| Scripts (`scripts/`) | Entry point for build and ingest pipelines |
| Notebooks | Interactive `query_session()` usage |

## Key Classes

### DeFunk

**File**: `src/de_funk/app.py:31`

**Purpose**: Top-level application object. Assembles everything from config.

| Method | Description |
|--------|-------------|
| `from_config(connection_type: str, log_level: str) -> DeFunk` | Create a fully wired DeFunk app from config files. |
| `from_app_config() -> DeFunk` | Create DeFunk from an already-loaded AppConfig. |
| `build_session()` | Create a BuildSession for building Silver tables. |
| `query_session()` | Create a QuerySession for interactive queries. |
| `ingest_session()` | Create an IngestSession for data ingestion. |

## How to Use

### Common Operations

```python
from de_funk.app import DeFunk

# Quickstart: create app with defaults (DuckDB backend)
app = DeFunk.from_config("configs/")

# Build all Silver models in dependency order
session = app.build_session()
results = session.build_all()
for r in results:
    print(f"{r.model_name}: {'OK' if r.success else r.error}")

# Query Silver tables interactively
session = app.query_session()
resolved = session.resolve("securities.stocks.adjusted_close")
# resolved.table_name  -> "fact_daily_price"
# resolved.silver_path -> Path("/shared/storage/silver/securities/stocks/facts/fact_daily_price")

# Ingest Bronze data
session = app.ingest_session()
provider = session.get_provider("alpha_vantage")
endpoint = session.get_endpoint("alpha_vantage", "time_series_daily")
```

### Integration Examples

```python
# Using DeFunk with the FastAPI handler registry
app = DeFunk.from_config()
resolver = app.query_session().resolver
bronze_resolver = BronzeResolver(data_sources_root=..., bronze_root=...)

registry = app.engine.get_handler_registry(
    resolver=resolver,
    bronze_resolver=bronze_resolver,
    max_response_mb=4.0,
    storage_root=app.config.storage.get("roots", {}).get("silver"),
)

# Using DeFunk from an already-loaded AppConfig (e.g. in tests)
from de_funk.config.loader import ConfigLoader
loader = ConfigLoader(repo_root=Path("/path/to/repo"))
config = loader.load(connection_type="duckdb")
app = DeFunk.from_app_config(config)
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValueError: Storage path not configured` | `run_config.json` missing `defaults.storage_path` | Add `"storage_path": "/shared/storage"` to `configs/run_config.json` |
| `Could not load domain models: ...` | `domains/models/` missing or no valid `model.md` files | Check that `domains/models/` exists and model files have `type: domain-model` frontmatter |
| `Could not create Spark engine ... Falling back to DuckDB` | PySpark not installed or Spark master unreachable | Install PySpark or use `connection_type="duckdb"` (default) |
| `KeyError: 'alpha_vantage'` from `ingest_session` | Provider markdown not found in `domains/Data Sources/Providers/` | Create provider markdown or check `data_sources/` alternate location |
| `QuerySession has no resolver` | `query_session()` created without resolver wiring failing silently | Check that `domains/models/` has table files with `schema:` frontmatter |

### Debug Checklist

- [ ] Verify `configs/storage.json` exists and is valid JSON
- [ ] Verify `configs/run_config.json` has `defaults.storage_path` set
- [ ] Check logs for "DeFunk ready: N models, M providers" line -- confirms startup succeeded
- [ ] If 0 models loaded, check `domains/models/*/model.md` files for `type: domain-model`
- [ ] If engine falls back to DuckDB, check PySpark installation if Spark was intended
- [ ] Run `ConfigLoader(repo_root=Path(".")).load()` standalone to isolate config vs app issues

### Common Pitfalls

1. **Passing `configs/` as `config_path` vs the repo root**: `from_config` expects the path to the `configs/` directory (or the repo root). If you pass a subdirectory, model discovery will fail because `domains/` won't be found relative to the resolved root.
2. **Forgetting `run_config.json`**: The storage path resolution is strict -- without `defaults.storage_path` in `run_config.json`, `ConfigLoader` raises `ValueError` rather than guessing a path.
3. **Session lifetime**: Sessions are cheap to create and hold no exclusive locks. Create a fresh session per request/task rather than reusing across threads.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/app.py` | DeFunk — Top-level application class. | `DeFunk` |
