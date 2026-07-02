---
title: "Orchestration"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/orchestration/checkpoint.py
  - src/de_funk/orchestration/common/path_utils.py
  - src/de_funk/orchestration/common/spark_session.py
  - src/de_funk/orchestration/dependency_graph.py
  - src/de_funk/orchestration/scheduler.py
---

# Orchestration

> Pipeline scheduling, dependency resolution, and checkpointing.

## Purpose & Design Decisions

### What Problem This Solves

de_Funk has multiple domain models that must be built in dependency order (e.g. `temporal` before `securities.stocks`, because stocks references the calendar dimension). It also has ingestion pipelines that process hundreds of tickers and can take hours to complete. The orchestration layer solves three problems:

1. **Build ordering**: The `DependencyGraph` discovers model dependencies from YAML configs and produces a topological sort so models are built in the correct order. It also supports partial builds: request `securities.stocks` and it automatically includes `temporal` and `corporate.entity` as prerequisites.

2. **Checkpointing**: Long-running ingestion pipelines (500+ tickers across multiple data types) need to survive failures. `CheckpointManager` persists progress to JSON files so a failed pipeline can resume from the last successful ticker instead of restarting from scratch.

3. **Scheduling**: Daily and weekly jobs (price ingestion after market close, Silver rebuilds at 5 AM, weekly forecasts on Sunday) are managed by `PipelineScheduler` using APScheduler with cron triggers.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| NetworkX for graph operations with fallback to Kahn's algorithm | NetworkX provides efficient topological sort, cycle detection, and ancestor/descendant queries. The fallback ensures the system works without the optional dependency. | Custom graph implementation only |
| JSON-file checkpoints (not database) | Checkpoints are simple state snapshots for a single pipeline run. JSON files are human-readable, easy to inspect, and require no database setup. Thread-safe via `threading.Lock`. | SQLite database for checkpoints |
| APScheduler for cron scheduling (lazy import) | APScheduler is a well-tested Python scheduler with cron trigger support. Lazy import means it is only required when actually running the scheduler daemon, not for library usage. | Celery (too heavy), OS cron (less portable) |
| Checkpoint file naming: `{pipeline_name}_{timestamp}.checkpoint.json` | Allows multiple checkpoint files per pipeline (for history) while making the most recent one easy to find via glob and sort by mtime. | Single checkpoint file per pipeline (loses history) |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Model dependencies | `depends_on:` field in model YAML frontmatter | `domains/models/{domain}/model.md` or `configs/models/{model}/model.yaml` |
| Model enabled/disabled status | `enabled:` field in model YAML | Model YAML configs |
| Scheduled job times (market cap refresh, prices, Silver rebuild, forecasts) | Hardcoded cron triggers in `PipelineScheduler.register_default_jobs()` | `src/de_funk/orchestration/scheduler.py` |
| Checkpoint storage directory | `CheckpointManager.DEFAULT_CHECKPOINT_DIR` (default: `storage/checkpoints`) | `src/de_funk/orchestration/checkpoint.py` |
| Auto-save frequency for checkpoints | `auto_save` and `save_interval` constructor params | `CheckpointManager.__init__()` |

## Architecture

### Where This Fits

```
[Domain YAML Configs] --> [DependencyGraph.build()]
                                  |
                          [topological_sort()]
                                  |
               [build_models.py iterates in order]
                                  |
                    [BaseModelBuilder.build() per model]

[PipelineScheduler] --(cron)--> [job_daily_price_ingestion()]
                                [job_daily_silver_rebuild()]
                                [job_weekly_forecasts()]
                                [job_daily_market_cap_refresh()]
                                          |
                                  [IngestorEngine / build_model()]
                                          |
                                  [CheckpointManager tracks progress]
```

The orchestration layer coordinates the build pipeline (Module 06) and ingestion pipeline (Module 07). `DependencyGraph` determines model build order. `PipelineScheduler` triggers jobs on a schedule. `CheckpointManager` wraps long-running ingestion loops to provide resume capability. The scheduler job functions import and call into the ingestion and build modules directly.

### Dependencies

| Depends On | What For |
|------------|----------|
| `de_funk.config.logging` | Structured logging |
| `networkx` (optional) | Graph operations, topological sort, cycle detection |
| `apscheduler` (optional, lazy) | Cron-based job scheduling |
| `yaml` | Reading model YAML configs for dependency discovery |
| `de_funk.pipelines.base.ingestor_engine` | Called by scheduled ingestion jobs |
| `de_funk.models.base.builder` | Called by scheduled Silver rebuild jobs |
| `de_funk.core.context.RepoContext` | Provides Spark session and config for scheduled jobs |

| Depended On By | What For |
|----------------|----------|
| `scripts/build/build_models.py` | Uses `DependencyGraph` to determine build order |
| `scripts/ingest/` | Uses `CheckpointManager` for resumable ingestion |
| CLI/daemon entry point | `PipelineScheduler.main()` runs as a daemon process |

## Key Classes

### TickerCheckpoint

**File**: `src/de_funk/orchestration/checkpoint.py:26`

**Purpose**: Checkpoint state for a single ticker.

| Attribute | Type |
|-----------|------|
| `ticker` | `str` |
| `status` | `str` |
| `started_at` | `Optional[str]` |
| `completed_at` | `Optional[str]` |
| `error` | `Optional[str]` |
| `retries` | `int` |
| `data_endpoints` | `Dict[str, str]` |

| Method | Description |
|--------|-------------|
| `to_dict() -> dict` | Serialize to dict via `dataclasses.asdict()`. |
| `from_dict(data: dict) -> 'TickerCheckpoint'` | Construct from a dict (classmethod). |

### PipelineCheckpoint

**File**: `src/de_funk/orchestration/checkpoint.py:45`

**Purpose**: Checkpoint state for an entire pipeline run.

| Attribute | Type |
|-----------|------|
| `pipeline_id` | `str` |
| `pipeline_name` | `str` |
| `started_at` | `str` |
| `last_updated` | `str` |
| `status` | `str` |
| `total_tickers` | `int` |
| `processed_count` | `int` |
| `failed_count` | `int` |
| `tickers` | `Dict[str, TickerCheckpoint]` |
| `metadata` | `Dict[str, Any]` |

| Method | Description |
|--------|-------------|
| `to_dict() -> dict` | Serialize to dict, including nested `TickerCheckpoint` objects. |
| `from_dict(data: dict) -> 'PipelineCheckpoint'` | Construct from a dict, deserializing nested ticker checkpoints (classmethod). |

### CheckpointManager

**File**: `src/de_funk/orchestration/checkpoint.py:70`

**Purpose**: Manages checkpoint state for ingestion pipelines.

| Attribute | Type |
|-----------|------|
| `DEFAULT_CHECKPOINT_DIR` | `—` |

| Method | Description |
|--------|-------------|
| `create_checkpoint(pipeline_name: str, tickers: List[str], metadata: Dict[str, Any]) -> PipelineCheckpoint` | Create a new checkpoint for a pipeline run. |
| `load_checkpoint(pipeline_id: str) -> Optional[PipelineCheckpoint]` | Load an existing checkpoint. |
| `find_latest_checkpoint(pipeline_name: str) -> Optional[PipelineCheckpoint]` | Find the most recent checkpoint for a pipeline. |
| `find_resumable_checkpoint(pipeline_name: str) -> Optional[PipelineCheckpoint]` | Find a checkpoint that can be resumed (not completed). |
| `mark_ticker_started(ticker: str) -> None` | Mark a ticker as started processing. |
| `mark_ticker_completed(ticker: str, endpoints: Dict[str, str]) -> None` | Mark a ticker as completed. |
| `mark_ticker_failed(ticker: str, error: str) -> None` | Mark a ticker as failed. |
| `get_pending_tickers() -> List[str]` | Get list of tickers that still need processing. |
| `get_failed_tickers() -> List[str]` | Get list of failed tickers. |
| `mark_pipeline_completed() -> None` | Mark the entire pipeline as completed. |
| `mark_pipeline_failed(error: str) -> None` | Mark the entire pipeline as failed. |
| `get_progress() -> Dict[str, Any]` | Get current progress summary. |
| `clear_checkpoint(pipeline_id: str) -> bool` | Clear a checkpoint file. |
| `list_checkpoints() -> List[Dict[str, Any]]` | List all available checkpoints. |

### ModelInfo

**File**: `src/de_funk/orchestration/dependency_graph.py:53`

**Purpose**: Metadata about a model for dependency resolution.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `version` | `str` |
| `depends_on` | `List[str]` |
| `inherits_from` | `Optional[str]` |
| `storage_root` | `str` |
| `enabled` | `bool` |

### DependencyGraph

**File**: `src/de_funk/orchestration/dependency_graph.py:63`

**Purpose**: Model dependency graph with topological sorting.

| Method | Description |
|--------|-------------|
| `build(force: bool) -> None` | Build dependency graph by discovering model configs. |
| `get_dependencies(model_name: str, recursive: bool) -> List[str]` | Get dependencies for a model. |
| `topological_sort() -> List[str]` | Get all models in correct build order. |
| `filter_buildable(requested: List[str]) -> List[str]` | Get build order for specific models with their dependencies. |
| `get_dependents(model_name: str) -> List[str]` | Get models that depend on this model. |
| `visualize() -> str` | Generate text visualization of dependency graph. |
| `get_tiers() -> Dict[int, List[str]]` | Get models organized by dependency tier. |
| `list_models() -> List[str]` | Get list of all discovered models. |
| `get_model_info(model_name: str) -> Optional[ModelInfo]` | Get info for a specific model. |
| `validate() -> List[str]` | Validate the dependency graph. |

## How to Use

### Common Operations

**Getting the correct build order for all models:**

```python
from de_funk.orchestration.dependency_graph import DependencyGraph
from pathlib import Path

dep_graph = DependencyGraph(Path("configs/models"))
dep_graph.build()

# Full build order
order = dep_graph.topological_sort()
# ['temporal', 'corporate.entity', 'macro', 'securities.stocks', 'city.finance', ...]

# Visualize
print(dep_graph.visualize())
# Model Dependency Graph:
# ========================================
#   temporal (no dependencies)
#   corporate.entity <- temporal
#   securities.stocks <- temporal, corporate.entity
```

**Building specific models with auto-resolved dependencies:**

```python
# Request just stocks -- temporal and corporate.entity are auto-included
order = dep_graph.filter_buildable(["securities.stocks"])
# ['temporal', 'corporate.entity', 'securities.stocks']

# Check what depends on a model (impact analysis)
dependents = dep_graph.get_dependents("temporal")
# ['corporate.entity', 'securities.stocks', 'macro', ...]
```

**Using dependency tiers for parallel builds:**

```python
tiers = dep_graph.get_tiers()
# {0: ['temporal'], 1: ['corporate.entity', 'macro'], 2: ['securities.stocks']}
# Tier 0 can be built first, then Tier 1 in parallel, then Tier 2
```

**Checkpointing an ingestion pipeline:**

```python
from de_funk.orchestration.checkpoint import CheckpointManager

mgr = CheckpointManager(checkpoint_dir="storage/checkpoints")

# Create a new checkpoint
cp = mgr.create_checkpoint(
    pipeline_name="alpha_vantage_ingestion",
    tickers=["AAPL", "MSFT", "GOOGL", "AMZN"],
    metadata={"data_types": ["prices", "reference"]}
)

# Track progress
mgr.mark_ticker_started("AAPL")
mgr.mark_ticker_completed("AAPL", endpoints={"prices": "ok", "reference": "ok"})
mgr.mark_ticker_started("MSFT")
mgr.mark_ticker_failed("MSFT", "HTTP 429 rate limit exceeded")

# Check progress
progress = mgr.get_progress()
# {'pipeline_id': 'alpha_vantage_ingestion_20260326_140000',
#  'status': 'running', 'total': 4, 'processed': 1, 'failed': 1,
#  'pending': 2, 'percent_complete': 25.0}

# Resume later
resumable = mgr.find_resumable_checkpoint("alpha_vantage_ingestion")
if resumable:
    pending = mgr.get_pending_tickers()
    # ['MSFT', 'GOOGL', 'AMZN']  -- MSFT retried because status is 'failed'
```

**Starting the scheduler daemon:**

```bash
# As a daemon
python -m de_funk.orchestration.scheduler

# List available jobs
python -m de_funk.orchestration.scheduler --list-jobs

# Run a specific job immediately
python -m de_funk.orchestration.scheduler --run-job daily_price_ingestion
```

### Integration Examples

**Build script using DependencyGraph:**

```python
from de_funk.orchestration.dependency_graph import DependencyGraph
from de_funk.models.base.builder import BuilderRegistry
from de_funk.models.base.domain_builder import discover_domain_builders

# Discover domain builders
discover_domain_builders(repo_root)
builders = BuilderRegistry.all()

# Get build order
dep_graph = DependencyGraph(configs_path)
dep_graph.build()
errors = dep_graph.validate()
if errors:
    for err in errors:
        logger.error(err)
    sys.exit(1)

order = dep_graph.filter_buildable(requested_models)
for model_name in order:
    if model_name in builders:
        builder = builders[model_name](session)
        result = builder.build()
        logger.info(str(result))
```

**Scheduler with custom jobs:**

```python
from de_funk.orchestration.scheduler import PipelineScheduler

scheduler = PipelineScheduler(blocking=False)  # non-blocking for embedding

# Add a custom job
def my_custom_job():
    logger.info("Running custom ETL")

scheduler.add_job(
    my_custom_job,
    trigger="cron",
    job_id="custom_etl",
    name="Custom ETL",
    hour=3, minute=0,
)

scheduler.start(register_defaults=True)
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValueError: Circular dependency detected: ['A', 'B']` | Two or more models depend on each other | Break the cycle by removing one direction of the dependency in the model YAML `depends_on:` field |
| `Model 'X' depends on unknown model 'Y'` | The `depends_on` field references a model name that does not exist in the configs directory | Check the model name spelling. Ensure the referenced model has a `model.yaml` or `model.md` file. |
| Checkpoint shows 0% complete after resume | The checkpoint file was loaded but `_current_checkpoint` was not set | Verify `load_checkpoint()` returned a non-None result. Check the checkpoint JSON file is not corrupt. |
| `ImportError: APScheduler is not installed` | Trying to use `PipelineScheduler` without the optional dependency | `pip install apscheduler` |
| Scheduled job fails with `RepoContext` error | The scheduler job function cannot find the repo root or configs | Ensure the scheduler daemon is started from the repo root directory, or set `DEFUNK_REPO_ROOT` env var |
| `topological_sort()` returns models in unexpected order | Models at the same dependency tier may appear in different order between runs | This is expected -- models within the same tier have no ordering constraint. Use `get_tiers()` if you need tier-grouped ordering. |
| Checkpoint file not found on resume | Pipeline ID changed (timestamp-based naming) or file was manually deleted | Use `find_resumable_checkpoint(pipeline_name)` instead of `load_checkpoint(pipeline_id)` to find by name pattern |

### Debug Checklist

- [ ] Verify model configs are discoverable: `ls configs/models/*/model.yaml` or `ls domains/models/*/model.md`
- [ ] Validate the dependency graph: `dep_graph.validate()` returns empty list if no errors
- [ ] Inspect checkpoint file: `cat storage/checkpoints/<pipeline_id>.checkpoint.json | python -m json.tool`
- [ ] Check checkpoint directory exists and is writable: `ls -la storage/checkpoints/`
- [ ] For scheduler issues, verify APScheduler is installed: `python -c "import apscheduler; print(apscheduler.__version__)"`
- [ ] Check that scheduled job functions can import their dependencies (Spark, providers, etc.)
- [ ] Use `dep_graph.visualize()` to see the full dependency tree and spot missing edges

### Common Pitfalls

1. **DependencyGraph.build() is lazy and cached**: The graph is only built on first access (or when `force=True`). If you add new model configs after `build()` was called, the graph will not reflect them. Call `build(force=True)` to refresh.

2. **Checkpoint `get_pending_tickers()` includes failed tickers**: Both `pending` and `failed` status tickers are returned by `get_pending_tickers()`. This is intentional for retry semantics, but may surprise callers who only want truly-never-attempted tickers.

3. **Scheduler job functions use hardcoded model lists**: `job_daily_silver_rebuild()` has a hardcoded list of models to build (`['temporal', 'corporate.entity', 'securities.stocks', 'macro']`). Adding a new domain model requires updating this list, or switching to `DependencyGraph.topological_sort()` for dynamic discovery.

4. **Thread safety of CheckpointManager**: All state mutations are protected by `threading.Lock`, but the underlying JSON file writes are not atomic. In rare cases of process crash during write, the checkpoint file may be corrupted. The `auto_save` mode writes after every ticker update, which is safe but slow for large pipelines -- consider `save_interval=10` for batched saves.

5. **NetworkX is optional but strongly recommended**: Without NetworkX, the fallback implementations (Kahn's algorithm for topo sort, recursive DFS for dependencies) work correctly but lack cycle reporting detail. Install NetworkX for better error messages on circular dependencies.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/orchestration/checkpoint.py` | Checkpoint System - Resume capability for long-running ingestion pipelines. | `TickerCheckpoint`, `PipelineCheckpoint`, `CheckpointManager` |
| `src/de_funk/orchestration/common/path_utils.py` | — | — |
| `src/de_funk/orchestration/common/spark_session.py` | — | — |
| `src/de_funk/orchestration/dependency_graph.py` | Dependency Graph - Model build ordering via topological sort. | `ModelInfo`, `DependencyGraph` |
| `src/de_funk/orchestration/scheduler.py` | — | — |
