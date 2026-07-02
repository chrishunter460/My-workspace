---
title: "Utilities"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/context.py
  - src/de_funk/utils/api_validator.py
  - src/de_funk/utils/env_loader.py
  - src/de_funk/utils/pipeline_tracker.py
  - src/de_funk/utils/repo.py
---

# Utilities

> Repo context, API validator, pipeline tracker -- small cross-cutting helpers.

## Purpose & Design Decisions

### What Problem This Solves

Every script and pipeline needs to answer the same bootstrapping questions: Where is the repo root? What storage paths should I use? Which database backend am I connecting to? Is the API reachable with my key and date range? These concerns cut across all layers but belong to none of them.

This group collects five small, focused utilities:

- **`RepoContext`** -- a dataclass that bundles repo root, storage paths, database connection, and typed config into a single object passed through pipelines and scripts.
- **`repo.py`** -- reliably finds the repo root by walking up the directory tree looking for marker directories (`src/`, `configs/`, `.git/`), then adds `src/` to `sys.path` so scripts can import `de_funk.*`.
- **`api_validator.py`** -- pre-flight check for Polygon API access and historical date range limitations before running expensive ingestion pipelines.
- **`pipeline_tracker.py`** -- records pipeline run history (start/end times, stages, errors, warnings) as JSON files for post-mortem analysis.
- **`env_loader.py`** -- legacy `.env` file loader, now deprecated in favor of the unified `ConfigLoader`.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| `RepoContext.from_repo_root()` delegates to `ConfigLoader` for all config | Single source of truth for storage paths, connection type, and API credentials; eliminates scattered config reads | Direct JSON parsing in RepoContext -- rejected because it duplicated ConfigLoader logic |
| `repo.py` uses marker directories (`src/`, `configs/`, `.git/`) to find root | Works regardless of cwd, even from deeply nested scripts or notebooks | Hardcoded paths or `__file__` relative navigation -- fragile across environments |
| `PipelineRunTracker` writes JSON files per run + a rolling summary | Human-readable history; each run is an independent file that survives partial failures | SQLite database -- heavier dependency, harder to inspect manually |
| `env_loader.py` marked deprecated with `LEGACY_ENV_AUTOLOAD` guard | Prevents import-time side effects; new code uses `ConfigLoader` which handles `.env` explicitly | Removing entirely -- would break old scripts that still import it |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Database backend (Spark vs. DuckDB) | `connection_type` parameter, `CONNECTION_TYPE` env var, or `storage.json` `connection.type` | `src/de_funk/core/context.py:38` via `ConfigLoader` |
| Storage paths (bronze, silver, gold) | `storage.json` paths section | `configs/storage.json` |
| API credentials for providers | `run_config.json` or environment variables (`POLYGON_API_KEYS`, `BLS_API_KEYS`, `CHICAGO_API_KEYS`) | `configs/run_config.json`, `.env` |
| Pipeline run log directory | `log_dir` parameter to `PipelineRunTracker` (default: `logs/pipeline_runs`) | Per call site |
| Legacy auto-load behavior | `LEGACY_ENV_AUTOLOAD=true` env var | `src/de_funk/utils/env_loader.py:203` |

## Architecture

### Where This Fits

```
[Scripts / Pipelines / API server]
        |
        v
[repo.py: get_repo_root()] --> [sys.path setup]
        |
        v
[RepoContext.from_repo_root()] --> [ConfigLoader] --> [storage.json, run_config.json, .env]
        |                                               |
        v                                               v
[connection (DuckDB or Spark)]                [API credentials for providers]
        |
        v
[api_validator.py] --> [Pre-flight API checks]
[pipeline_tracker.py] --> [Run history JSON files]
```

`repo.py` is the first thing called in any script to establish the repo root and import paths. `RepoContext` is then constructed to provide a fully-initialized context (connection, storage, config) to the rest of the pipeline. `APIValidator` and `PipelineRunTracker` are used during pipeline execution.

### Dependencies

| Depends On | What For |
|------------|----------|
| `de_funk.config.ConfigLoader`, `de_funk.config.AppConfig` | `RepoContext.from_repo_root()` uses ConfigLoader for all configuration |
| `de_funk.config.logging.get_logger` | `RepoContext` and context module logging |
| `de_funk.core.connection.ConnectionFactory` | `RepoContext` creates DuckDB or Spark connections |
| `de_funk.orchestration.common.spark_session.get_spark` | `RepoContext` creates Spark sessions when backend is spark |
| Python `urllib.request`, `json` | `APIValidator` makes HTTP calls to Polygon API |
| Python `pathlib`, `sys` | `repo.py` for path manipulation and `sys.path` management |

| Depended On By | What For |
|----------------|----------|
| All scripts in `scripts/` | `setup_repo_imports()` for path setup, `RepoContext.from_repo_root()` for context |
| `de_funk.pipelines.*` | `RepoContext` provides storage paths and connections |
| `de_funk.models.*` | `RepoContext` provides Spark session and storage paths |
| Ingestion scripts | `APIValidator` for pre-flight date range checks |
| Pipeline orchestration | `PipelineRunTracker` for run history |

## Key Classes

### RepoContext

**File**: `src/de_funk/core/context.py:12`

**Purpose**: Repository context with database connection and configuration.

| Attribute | Type |
|-----------|------|
| `repo` | `Path` |
| `spark` | `Any` |
| `storage` | `Dict[str, Any]` |
| `connection` | `Optional[Any]` |
| `connection_type` | `str` |
| `_config` | `Optional[AppConfig]` |

| Method | Description |
|--------|-------------|
| `get_api_config(provider: str) -> Dict[str, Any]` | Get API configuration for any provider. |
| `from_repo_root(connection_type: Optional[str]) -> 'RepoContext'` | Create RepoContext from repository root. |
| `config() -> Optional[AppConfig]` | Get the full typed configuration object. |

### APIValidator

**File**: `src/de_funk/utils/api_validator.py:16`

**Purpose**: Validates Polygon API access and capabilities.

| Method | Description |
|--------|-------------|
| `validate_date_range(date_from: str, date_to: str, auto_adjust: bool) -> Tuple[bool, str, Optional[str]]` | Validate if date range is accessible with current API plan. |
| `test_api_connection() -> Tuple[bool, str]` | Test basic API connection and authentication. |
| `get_recommended_date_range(days: int) -> Tuple[str, str]` | Get a recommended date range that should work with most API plans. |
| `prompt_user_for_adjusted_range(original_to: str, suggested_from: str) -> Tuple[str, str, bool]` | Prompt user to accept adjusted date range or abort. |

### PipelineRunTracker

**File**: `src/de_funk/utils/pipeline_tracker.py:15`

**Purpose**: Tracks pipeline executions and maintains a history log.

| Method | Description |
|--------|-------------|
| `start_run(pipeline_type: str, config: Dict[str, Any]) -> str` | Start tracking a new pipeline run. |
| `log_stage(stage: str, status: str, details: Dict[str, Any])` | Log a pipeline stage completion. |
| `log_error(error: str, stage: str)` | Log an error during pipeline execution. |
| `log_warning(warning: str, stage: str)` | Log a warning during pipeline execution. |
| `update_results(results: Dict[str, Any])` | Update run results. |
| `end_run(status: str, summary: Dict[str, Any])` | End the current pipeline run. |
| `get_recent_runs(count: int) -> list` | Get recent pipeline runs. |
| `print_recent_runs(count: int)` | Print recent pipeline runs. |

## How to Use

### Common Operations

**Setting up imports in a script (the standard script preamble):**

```python
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Now de_funk.* imports work from anywhere
from de_funk.core.context import RepoContext
from de_funk.config.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
```

**Creating a RepoContext for pipeline work:**

```python
from de_funk.core.context import RepoContext

# Default: uses connection type from storage.json (or CONNECTION_TYPE env var)
ctx = RepoContext.from_repo_root()

# Explicit DuckDB for interactive queries
ctx = RepoContext.from_repo_root(connection_type="duckdb")

# Access storage paths
bronze_path = ctx.storage["bronze"]
silver_path = ctx.storage["silver"]

# Access API config for a provider
polygon_cfg = ctx.get_api_config("polygon")

# Access the full typed config
app_config = ctx.config
```

**Validating API access before running a pipeline:**

```python
from de_funk.utils.api_validator import APIValidator

validator = APIValidator(ctx.get_api_config("polygon"))

# Test basic connectivity
connected, message = validator.test_api_connection()

# Validate a specific date range (auto-adjusts for plan limitations)
valid, msg, adjusted_from = validator.validate_date_range("2020-01-01", "2024-12-31")
if not valid and adjusted_from:
    from_date, to_date, proceed = validator.prompt_user_for_adjusted_range(
        "2020-01-01", "2024-12-31", adjusted_from
    )
```

**Tracking a pipeline run:**

```python
from de_funk.utils.pipeline_tracker import PipelineRunTracker

tracker = PipelineRunTracker()
run_id = tracker.start_run("data_ingestion", {"provider": "polygon", "tickers": 500})

tracker.log_stage("fetch_prices", "success", {"records": 15000})
tracker.log_stage("fetch_fundamentals", "success", {"records": 3200})
tracker.log_warning("Missing market_cap for 12 tickers", stage="fetch_fundamentals")

tracker.update_results({"total_records": 18200})
tracker.end_run("success", {"tickers_processed": 500})

# View history
PipelineRunTracker.print_recent_runs()
```

**Using the context manager for temporary imports:**

```python
from de_funk.utils.repo import repo_imports

with repo_imports() as repo_root:
    from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root()
    # ... work with ctx ...
# sys.path is restored after exiting the context
```

### Integration Examples

**Complete script using RepoContext + PipelineRunTracker together:**

```python
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger
from de_funk.core.context import RepoContext
from de_funk.utils.pipeline_tracker import PipelineRunTracker

setup_logging()
logger = get_logger(__name__)

ctx = RepoContext.from_repo_root(connection_type="spark")
tracker = PipelineRunTracker()

run_id = tracker.start_run("silver_build", {"models": ["corporate.entity"]})
try:
    build_silver_model(ctx, "corporate.entity")
    tracker.log_stage("build", "success", {})
    tracker.end_run("success", {})
except Exception as e:
    tracker.log_error(str(e), stage="build")
    tracker.end_run("failed", {})
    raise
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValueError: Could not find repository root from ...` | Script is running outside the repo tree, or `src/`, `configs/`, `.git/` markers are missing | Run from within the repo directory; verify `.git/`, `src/`, and `configs/` exist |
| `RepoContext.from_repo_root()` hangs | Spark session initialization is slow or waiting for a resource | Set `connection_type="duckdb"` for interactive/script use; Spark startup can take 10-30s |
| `APIValidator` returns `(False, 'Access denied', ...)` | Polygon API key is invalid or plan lacks historical data access | Check `POLYGON_API_KEYS` env var or `run_config.json` credentials; free plans have limited history |
| `get_api_config()` returns empty dict `{}` | Provider not configured in `run_config.json` or `AppConfig.apis` | Add the provider config to `configs/run_config.json` |
| Pipeline run JSON files not appearing | `log_dir` does not exist or is not writable | Check `logs/pipeline_runs/` exists; `PipelineRunTracker.__init__` creates it with `mkdir(parents=True)` |
| `LEGACY_ENV_AUTOLOAD` deprecation warning | Old code is using `env_loader.py` auto-load | Migrate to `ConfigLoader`; remove `LEGACY_ENV_AUTOLOAD` env var |
| `ImportError: No module named 'de_funk'` | `setup_repo_imports()` not called before importing | Add `from de_funk.utils.repo import setup_repo_imports; setup_repo_imports()` at the top of your script |

### Debug Checklist

- [ ] Verify repo root detection: `python -c "from de_funk.utils.repo import get_repo_root; print(get_repo_root())"`
- [ ] Check that `configs/storage.json` exists and has valid JSON
- [ ] For DuckDB mode, verify the database path exists: check `storage.json` `connection.duckdb.database_path`
- [ ] For Spark mode, verify Spark is installed and `SPARK_HOME` is set
- [ ] For API issues, run `APIValidator.test_api_connection()` standalone to isolate network/auth problems
- [ ] Check `logs/pipeline_runs/runs_summary.json` for recent run history
- [ ] Inspect individual run files: `logs/pipeline_runs/run_YYYYMMDD_HHMMSS.json`

### Common Pitfalls

1. **Importing `RepoContext` before `setup_repo_imports()`**: If your script is not installed as a package, Python cannot find `de_funk.*` without the `sys.path` setup. Always call `setup_repo_imports()` first, or use `repo_imports()` context manager.

2. **Using `env_loader.py` in new code**: This module is deprecated. Use `ConfigLoader` which handles `.env` loading, config merging, and validation in one place. The `env_loader` functions still work but will be removed in a future version.

3. **Assuming `RepoContext.spark` is always set**: In DuckDB mode, `ctx.spark` is `None`. Check `ctx.connection_type` before using the Spark session, or use `ctx.connection` which works for both backends.

4. **`APIValidator` uses `print()` not `logger`**: This is a known inconsistency. The validator predates the logging system and still uses print statements with unicode symbols for console output. It works for interactive script use but output is not captured in log files.

5. **`PipelineRunTracker` summary file grows unbounded if runs are very frequent**: The summary is capped at 100 entries, but individual `run_*.json` files are never cleaned up. For long-running systems, add periodic cleanup of old run files.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/core/context.py` | Repository context with database connection and configuration | `RepoContext` |
| `src/de_funk/utils/api_validator.py` | API Validation Utility | `APIValidator` |
| `src/de_funk/utils/env_loader.py` | Environment Variable Loader for de_Funk (DEPRECATED) | `find_dotenv`, `load_dotenv`, `get_api_keys`, `inject_credentials_into_config` |
| `src/de_funk/utils/pipeline_tracker.py` | Pipeline Run Tracker | `PipelineRunTracker` |
| `src/de_funk/utils/repo.py` | Centralized repository path and import management. | `get_repo_root`, `setup_repo_imports`, `repo_imports`, `verify_repo_structure` |
