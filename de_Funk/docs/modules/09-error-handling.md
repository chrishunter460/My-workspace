---
title: "Error Handling"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/exceptions.py
  - src/de_funk/core/error_handling.py
  - src/de_funk/core/validation.py
---

# Error Handling

> Exception hierarchy (23 typed errors), ErrorContext for structured debugging, and validation utilities.

## Purpose & Design Decisions

### What Problem This Solves

Raw Python exceptions (KeyError, FileNotFoundError, ValueError) carry no domain context. When a query fails deep in the join resolver, the traceback says `KeyError: 'ticker'` -- but is that a missing config key, a bad filter column, or a schema mismatch? Every layer had to guess.

This group provides a single, typed exception hierarchy where every error carries:
- A **human-readable message** with domain terminology (model name, table, provider).
- A **details dict** for structured logging and machine inspection.
- A **recovery_hint** that tells the caller (or end user) what to do next.

The companion `error_handling.py` adds decorators and context managers so callers never need bare `try/except` boilerplate, and `validation.py` catches configuration mistakes before any query runs.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Single base class `DeFunkError` with `details` + `recovery_hint` fields | Every catch site can inspect structured data without parsing message strings; hints surface in the Obsidian plugin error cards | Separate error dataclasses alongside stdlib exceptions -- rejected because it doubles the objects callers must handle |
| Six top-level branches (Configuration, Pipeline, Model, Query, Storage, Forecast) | Maps 1-to-1 with architecture layers so a `except PipelineError` in the orchestrator catches all ingestion/rate-limit/transform failures without over-catching | Flat list of exceptions -- rejected because callers would need long `except` tuples |
| `ErrorContext` never suppresses exceptions (always returns `False`) | Prevents silent swallowing; the context manager only adds logging and timing, then re-raises | Suppression flag -- rejected as it hides bugs; `safe_call()` exists for the intentional-swallow case |
| `retry_on_exception` uses exponential backoff with `max_delay` cap | Transient API/network errors recover automatically without hammering the provider | Fixed-interval retry -- too aggressive for rate-limited APIs |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Which exceptions `@handle_exceptions` catches | Positional `*exception_types` args in decorator call | Per call site |
| Retry count, delay, backoff factor | `max_retries`, `delay_seconds`, `backoff_factor` kwargs | Per call site via `@retry_on_exception` |
| ErrorContext log level for non-error messages | `log_level` parameter (defaults to `logging.DEBUG`) | Per call site |
| Validation strictness (errors vs. warnings) | `level` field on `ValidationError` dataclass (`'error'` or `'warning'`) | `src/de_funk/core/validation.py` |

## Architecture

### Where This Fits

```
[config/, pipelines/, models/, api/] --> [core/exceptions.py + error_handling.py] --> [logging system, API error responses]
                                         [core/validation.py] --> [notebook configs, Obsidian error cards]
```

All layers raise typed exceptions from `exceptions.py`. The `error_handling.py` decorators and context managers wrap call sites in any layer. `validation.py` is invoked before query execution to pre-check notebook/exhibit configurations against the model registry.

### Dependencies

| Depends On | What For |
|------------|----------|
| `de_funk.config.logging.get_logger` | `error_handling.py` uses the centralized logger for all decorator and context manager output |
| Python `functools`, `time`, `datetime` | `retry_on_exception` backoff timing, `ErrorContext` duration tracking |
| `dataclasses` | `ValidationError` is a dataclass |

| Depended On By | What For |
|----------------|----------|
| `de_funk.pipelines.*` (ingestors, providers) | Raise `IngestionError`, `RateLimitError`, `TransformationError` |
| `de_funk.models.*` (builders, measures) | Raise `ModelNotFoundError`, `TableNotFoundError`, `MeasureError`, `DependencyError` |
| `de_funk.api.*` (handlers, executor) | Catch typed exceptions and return structured error responses to the plugin |
| `de_funk.config.loader` | Raises `MissingConfigError`, `InvalidConfigError` |
| `de_funk.core.connection` | Raises `ConnectionError` on backend init failure |
| Scripts and orchestration | Use `@handle_exceptions`, `@retry_on_exception`, `ErrorContext` |

## Key Classes

### DeFunkError (Exception)

**File**: `src/de_funk/core/exceptions.py:57`

**Purpose**: Base exception for all de_Funk errors.

### ConfigurationError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:107`

**Purpose**: Error in configuration loading or validation.

### MissingConfigError (ConfigurationError)

**File**: `src/de_funk/core/exceptions.py:112`

**Purpose**: Required configuration is missing.

### InvalidConfigError (ConfigurationError)

**File**: `src/de_funk/core/exceptions.py:136`

**Purpose**: Configuration value is invalid.

### PipelineError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:162`

**Purpose**: Error in data pipeline execution.

### IngestionError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:167`

**Purpose**: Error during data ingestion from API.

### RateLimitError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:189`

**Purpose**: API rate limit exceeded.

### TransformationError (PipelineError)

**File**: `src/de_funk/core/exceptions.py:210`

**Purpose**: Error during data transformation.

### ModelError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:239`

**Purpose**: Error in model operations.

### ModelNotFoundError (ModelError)

**File**: `src/de_funk/core/exceptions.py:244`

**Purpose**: Requested model does not exist.

### TableNotFoundError (ModelError)

**File**: `src/de_funk/core/exceptions.py:269`

**Purpose**: Requested table does not exist in model.

### MeasureError (ModelError)

**File**: `src/de_funk/core/exceptions.py:296`

**Purpose**: Error calculating a measure.

### DependencyError (ModelError)

**File**: `src/de_funk/core/exceptions.py:322`

**Purpose**: Model dependency not satisfied.

### QueryError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:346`

**Purpose**: Error executing a query.

### FilterError (QueryError)

**File**: `src/de_funk/core/exceptions.py:351`

**Purpose**: Error applying filters.

### JoinError (QueryError)

**File**: `src/de_funk/core/exceptions.py:370`

**Purpose**: Error joining tables.

### StorageError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:395`

**Purpose**: Error in storage operations.

### DataNotFoundError (StorageError)

**File**: `src/de_funk/core/exceptions.py:400`

**Purpose**: Requested data does not exist.

### WriteError (StorageError)

**File**: `src/de_funk/core/exceptions.py:424`

**Purpose**: Error writing data to storage.

### ForecastError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:448`

**Purpose**: Error in forecasting operations.

### InsufficientDataError (ForecastError)

**File**: `src/de_funk/core/exceptions.py:453`

**Purpose**: Not enough data for forecasting.

### ModelTrainingError (ForecastError)

**File**: `src/de_funk/core/exceptions.py:478`

**Purpose**: Error training forecast model.

### ConnectionError (DeFunkError)

**File**: `src/de_funk/core/exceptions.py:507`

**Purpose**: Error in database connection.

### ErrorContext

**File**: `src/de_funk/core/error_handling.py:204`

**Purpose**: Context manager for detailed error reporting.

### ValidationError

**File**: `src/de_funk/core/validation.py:20`

**Purpose**: Represents a validation error.

| Attribute | Type |
|-----------|------|
| `level` | `str` |
| `message` | `str` |
| `location` | `Optional[str]` |

### NotebookValidator

**File**: `src/de_funk/core/validation.py:27`

**Purpose**: Validates notebook configuration against available models.

| Method | Description |
|--------|-------------|
| `validate(notebook_config: NotebookConfig) -> List[ValidationError]` | Validate notebook configuration. |
| `validate_and_raise(notebook_config: NotebookConfig)` | Validate and raise exception if errors found. |
| `get_warnings(notebook_config: NotebookConfig) -> List[ValidationError]` | Get only validation warnings. |
| `get_errors(notebook_config: NotebookConfig) -> List[ValidationError]` | Get only validation errors. |
| `is_valid(notebook_config: NotebookConfig) -> bool` | Check if notebook is valid (no errors). |

## How to Use

### Common Operations

**Raising typed exceptions with structured details:**

```python
from de_funk.core.exceptions import ModelNotFoundError, IngestionError

# Raise with structured details -- message, details dict, and recovery hint are automatic
raise ModelNotFoundError("securities.stocks", available_models=["corporate.entity", "transit.cta"])
# Output: Model not found: 'securities.stocks' | Hint: Available models: corporate.entity, transit.cta

# Chain exceptions to preserve the original cause
try:
    fetch_data()
except requests.RequestException as e:
    raise IngestionError("alpha_vantage", "prices", str(e)) from e
```

**Using the `@handle_exceptions` decorator:**

```python
from de_funk.core.error_handling import handle_exceptions

# Return a default value on failure (logs the error automatically)
@handle_exceptions(ValueError, KeyError, default_return=[])
def parse_data(raw):
    return json.loads(raw)

# Log and reraise -- useful for debugging without losing the exception
@handle_exceptions(reraise=True)
def must_succeed():
    critical_operation()
```

**Using `@retry_on_exception` for transient failures:**

```python
from de_funk.core.error_handling import retry_on_exception

@retry_on_exception(ConnectionError, TimeoutError, max_retries=3, delay_seconds=2.0)
def fetch_from_api():
    return requests.get("https://api.polygon.io/...")
# Attempt 1/4 failed for fetch_from_api: TimeoutError: ... Retrying in 2.0s...
# Attempt 2/4 failed for fetch_from_api: TimeoutError: ... Retrying in 4.0s...
```

**Using `ErrorContext` for operation tracking:**

```python
from de_funk.core.error_handling import ErrorContext

with ErrorContext("Loading model", model_name="securities.stocks"):
    model = load_model("securities.stocks")
# On success: DEBUG "Completed: Loading model (125.30ms)"
# On failure: ERROR "Failed: Loading model (12.45ms)" with full traceback
```

**Using `safe_call` for one-off safe invocations:**

```python
from de_funk.core.error_handling import safe_call

# Functional alternative to try/except for simple cases
result = safe_call(parse_json, raw_data, default={})
```

### Integration Examples

**API handler catching typed exceptions and returning structured errors:**

```python
from de_funk.core.exceptions import ModelNotFoundError, FilterError, QueryError

try:
    result = executor.run(query)
except ModelNotFoundError as e:
    return {"error": str(e), "hint": e.recovery_hint, "details": e.details}
except FilterError as e:
    return {"error": str(e), "filter": e.filter_spec}
except QueryError as e:
    return {"error": str(e)}
```

**Pipeline using retry + ErrorContext together:**

```python
@retry_on_exception(RateLimitError, max_retries=3, delay_seconds=30.0)
def ingest_provider(provider_name):
    with ErrorContext("Ingesting provider", provider=provider_name):
        data = fetch_all_endpoints(provider_name)
        write_bronze(data)
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ModelNotFoundError: 'stocks'` | Using short name instead of canonical domain name | Use `securities.stocks` not `stocks` |
| `MissingConfigError: Missing required configuration: polygon` | API provider not configured in `run_config.json` | Add provider config to `configs/run_config.json` or set env vars |
| `RateLimitError: Rate limit exceeded for polygon` | Too many API calls in short window | Wait for `retry_after` seconds; the `@retry_on_exception` decorator handles this automatically |
| `DependencyError: Model 'X' has unmet dependencies: [Y, Z]` | Silver models built out of order | Build dependent models first: follow the hint in the error message |
| `DataNotFoundError: Data not found at: .../silver/...` | Silver tables not built yet | Run the build pipeline: `python -m scripts.build.silver` |
| `JoinError: Failed to join 'A' with 'B'` | No join path exists between the two tables in the domain graph | Check that both tables share a join key or are connected via an intermediate table |
| `ConnectionError: Failed to connect to duckdb` | DuckDB database file missing or locked | Check that the database path in `storage.json` exists and no other process holds a write lock |

### Debug Checklist

- [ ] Check the `recovery_hint` field on the exception -- it usually tells you exactly what to do
- [ ] Inspect `e.details` for structured context (model name, table, provider, path, etc.)
- [ ] Look for the full traceback in `logs/de_funk.log` -- file logging is at DEBUG level
- [ ] If using `@handle_exceptions` with `default_return`, check logs for silently-caught errors
- [ ] For `@retry_on_exception`, check if all retry attempts failed (logged at ERROR with `exc_info=True`)
- [ ] Verify exception chaining: look for `Caused by:` in the traceback (`from e` preserves the chain)

### Common Pitfalls

1. **Catching `DeFunkError` too broadly**: Catching the base class in business logic swallows errors from unrelated layers. Catch the specific branch (`ModelError`, `PipelineError`, etc.) instead.

2. **Forgetting `from e` when re-raising**: Always use `raise NewError(...) from e` to preserve the original traceback chain. Without it, the original cause is lost.

3. **Using `@handle_exceptions` without `reraise=True` in production paths**: The decorator silently returns `default_return` on failure. This is fine for optional features but dangerous for critical code paths where failures must propagate.

4. **Shadowing Python's built-in `ConnectionError`**: The project defines `de_funk.core.exceptions.ConnectionError` which shadows the stdlib class. Always import explicitly: `from de_funk.core.exceptions import ConnectionError as DeFunkConnectionError` if you need both.

5. **`NotebookValidator` references removed classes**: The validator still references `ModelRegistry`, `NotebookConfig`, and `Exhibit` from an earlier Streamlit path (now set to `None`). It validates model configs but the notebook schema validation path is inactive.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/core/exceptions.py` | Custom Exception Hierarchy for de_Funk. | `DeFunkError`, `ConfigurationError`, `MissingConfigError`, `InvalidConfigError`, `PipelineError`, `IngestionError`, `RateLimitError`, `TransformationError`, `ModelError`, `ModelNotFoundError`, `TableNotFoundError`, `MeasureError`, `DependencyError`, `QueryError`, `FilterError`, `JoinError`, `StorageError`, `DataNotFoundError`, `WriteError`, `ForecastError`, `InsufficientDataError`, `ModelTrainingError`, `ConnectionError` |
| `src/de_funk/core/error_handling.py` | Error Handling Utilities for de_Funk. | `ErrorContext` |
| `src/de_funk/core/validation.py` | Validation layer for notebooks. | `ValidationError`, `NotebookValidator` |
