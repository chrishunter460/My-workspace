---
title: "Logging"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/config/logging.py
---

# Logging

> Structured + colored logging, LogTimer context manager, file + console output.

## Purpose & Design Decisions

### What Problem This Solves

Scattered `print()` statements throughout the codebase produced unstructured, unleveled output that could not be filtered, rotated, or shipped to monitoring. Debug prints left in production polluted console output; removing them meant losing diagnostic information when issues arose.

This module replaces all `print()` usage with a centralized logging system that provides:
- **Two output channels**: colored console (INFO and above by default) and rotating log file (DEBUG and above).
- **Optional JSON structured logging** for machine-parseable output.
- **Module-specific level overrides** to silence noisy third-party libraries (urllib3, pyspark, duckdb, etc.).
- **One-time initialization** via `setup_logging()` with idempotency guard to prevent duplicate handlers.
- **`LogTimer`** context manager for automatic operation timing without manual stopwatch code.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| `setup_logging()` is idempotent via module-level `_logging_initialized` flag | Prevents duplicate handlers when multiple entry points or tests call setup; subsequent calls are no-ops | Checking `root_logger.handlers` length -- fragile if other libraries add handlers |
| Console uses `ColoredFormatter` with TTY detection + `NO_COLOR` env var support | Colored output is readable in terminals but breaks in CI/piped output; auto-detection handles both | Always-on colors -- breaks log file parsing and CI output |
| File handler uses `RotatingFileHandler` with 10 MB / 5 backups | Prevents disk exhaustion on long-running pipelines without manual log rotation setup | `TimedRotatingFileHandler` -- size-based is simpler and catches burst scenarios better |
| Module-specific levels suppress 12 noisy libraries at WARNING | Keeps console clean; DEBUG output from urllib3/pyspark/httpx floods the log otherwise | Global filter -- too coarse, loses useful debug output from de_funk's own modules |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Console log level | `LOG_LEVEL` env var (default: `INFO`) | Environment |
| File log level | `LOG_FILE_LEVEL` env var (default: `DEBUG`) | Environment |
| Log directory | `LOG_DIR` env var (default: `logs/` relative to repo root) | Environment |
| JSON structured logging | `LOG_JSON=true` env var (default: disabled) | Environment |
| Log rotation size | `LogConfig.max_bytes` (default: 10 MB) | `src/de_funk/config/logging.py:58` |
| Log rotation backup count | `LogConfig.backup_count` (default: 5) | `src/de_funk/config/logging.py:59` |
| Per-module log levels | `LogConfig.module_levels` dict | `src/de_funk/config/logging.py:70-83` |

## Architecture

### Where This Fits

```
[Environment vars / LogConfig] --> [setup_logging()] --> [Root logger with console + file + JSON handlers]
                                                              |
[Every module via get_logger(__name__)] ──────────────────────┘
```

`setup_logging()` is called once at application startup (in `run_app.py`, API server entry, or script `main()`). Every other module calls `get_logger(__name__)` to get a child logger that inherits the configured handlers. `LogTimer` and `log_function_call` are used at call sites for timing and tracing.

### Dependencies

| Depends On | What For |
|------------|----------|
| Python `logging`, `logging.handlers` | Standard library logging infrastructure, `RotatingFileHandler` |
| Python `json` | `StructuredFormatter` serializes log records to JSON |
| Python `os`, `sys`, `pathlib.Path` | Environment variable reads, TTY detection, log directory creation |
| Python `datetime` | `LogTimer` and `StructuredFormatter` timestamp generation |
| Python `dataclasses` | `LogConfig` is a dataclass |

| Depended On By | What For |
|----------------|----------|
| `de_funk.core.error_handling` | Imports `get_logger` for decorator/context manager logging |
| `de_funk.core.context` | Imports `get_logger` for RepoContext operations |
| `de_funk.config.loader` | Imports `get_logger` for config loading diagnostics |
| `de_funk.api.*` | All API handlers use `get_logger(__name__)` |
| `de_funk.pipelines.*` | All pipeline modules use `get_logger(__name__)` |
| `de_funk.models.*` | All model builders use `get_logger(__name__)` |
| All scripts | Call `setup_logging()` at startup, then `get_logger(__name__)` |

## Key Classes

### LogConfig

**File**: `src/de_funk/config/logging.py:41`

**Purpose**: Logging configuration with sensible defaults.

| Attribute | Type |
|-----------|------|
| `console_level` | `str` |
| `file_level` | `str` |
| `log_dir` | `Path` |
| `log_file` | `str` |
| `json_log_file` | `str` |
| `max_bytes` | `int` |
| `backup_count` | `int` |
| `console_format` | `str` |
| `file_format` | `str` |
| `date_format` | `str` |
| `enable_json` | `bool` |
| `module_levels` | `Dict[str, str]` |

| Method | Description |
|--------|-------------|
| `from_env(repo_root: Optional[Path]) -> 'LogConfig'` | Create LogConfig from environment variables. |

### StructuredFormatter (Formatter)

**File**: `src/de_funk/config/logging.py:115`

**Purpose**: JSON formatter for structured logging.

| Method | Description |
|--------|-------------|
| `format(record: logging.LogRecord) -> str` | Format log record as JSON. |

### ColoredFormatter (Formatter)

**File**: `src/de_funk/config/logging.py:144`

**Purpose**: Colored console output for better readability.

| Attribute | Type |
|-----------|------|
| `COLORS` | `---` |
| `RESET` | `---` |

| Method | Description |
|--------|-------------|
| `format(record: logging.LogRecord) -> str` | Format with optional colors. |

### LogTimer

**File**: `src/de_funk/config/logging.py:290`

**Purpose**: Context manager for timing operations with automatic logging.

## How to Use

### Common Operations

**Basic setup and usage (every script and entry point):**

```python
from de_funk.config.logging import setup_logging, get_logger

# Call once at startup
setup_logging()

# In any module
logger = get_logger(__name__)

logger.debug("Detailed info for file log only")      # File only (console is INFO)
logger.info("Processing securities.stocks")           # Console + file
logger.warning("Rate limit approaching")              # Yellow in console
logger.error("Query failed", exc_info=True)           # Red in console, includes traceback
```

**Timing an operation with LogTimer:**

```python
from de_funk.config.logging import get_logger, LogTimer

logger = get_logger(__name__)

with LogTimer(logger, "Building silver model"):
    build_model("corporate.entity")
# Output:
#   Starting: Building silver model
#   Completed: Building silver model (3421.50ms)

# With extra context fields (appear in JSON log):
with LogTimer(logger, "Processing ticker", ticker="AAPL"):
    process("AAPL")
```

**Tracing function entry/exit with the decorator:**

```python
from de_funk.config.logging import get_logger, log_function_call

logger = get_logger(__name__)

@log_function_call(logger)
def resolve_query(domain, table):
    ...
# Output:
#   Entering: resolve_query
#   Exiting: resolve_query
```

**Custom configuration via environment:**

```bash
# Verbose console output for debugging
LOG_LEVEL=DEBUG python -m scripts.build.silver

# Enable JSON structured logging for monitoring
LOG_JSON=true python -m scripts.serve.run_api

# Custom log directory
LOG_DIR=/var/log/de_funk python -m scripts.serve.run_api
```

### Integration Examples

**Using LogTimer inside ErrorContext for combined timing + error reporting:**

```python
from de_funk.config.logging import get_logger, LogTimer
from de_funk.core.error_handling import ErrorContext

logger = get_logger(__name__)

# ErrorContext adds error details; LogTimer adds timing
with ErrorContext("Loading model", model_name="securities.stocks"):
    with LogTimer(logger, "Model load"):
        model = load_model("securities.stocks")
```

**Structured logging with extra fields (captured by StructuredFormatter):**

```python
logger.info("Ingestion complete", extra={
    'provider': 'polygon',
    'record_count': 15420,
    'duration_ms': 3200.5,
})
# JSON output: {"timestamp": "...", "level": "INFO", "message": "Ingestion complete",
#               "provider": "polygon", "record_count": 15420, "duration_ms": 3200.5}
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No console output at all | `setup_logging()` never called | Add `setup_logging()` to your entry point before any logging calls |
| Duplicate log lines (same message printed twice) | `setup_logging()` called multiple times before the idempotency guard was added, or another library added a handler to root | Check that only one call to `setup_logging()` exists; the guard prevents duplicates in current code |
| DEBUG messages not visible in console | Console level defaults to INFO | Set `LOG_LEVEL=DEBUG` in environment |
| Log file not created | Log directory does not exist and `mkdir` failed (permissions) | Check write permissions on the `logs/` directory or set `LOG_DIR` to a writable path |
| Colors showing as escape codes (`[32m`) | Output is piped or redirected (not a TTY) | This is expected; `ColoredFormatter` auto-detects TTY. Set `NO_COLOR=1` to force plain output |
| urllib3/pyspark flooding console with DEBUG | Module-level overrides not applied | Ensure `setup_logging()` is called; it sets `module_levels` for 12 noisy libraries to WARNING |
| Log files growing unbounded | Rotation misconfigured or never triggered | Check `max_bytes` (default 10 MB) and `backup_count` (default 5) in `LogConfig` |
| JSON log file empty | JSON logging not enabled | Set `LOG_JSON=true` in environment |

### Debug Checklist

- [ ] Verify `setup_logging()` is called exactly once before any `get_logger()` usage
- [ ] Check that `LOG_LEVEL` env var is set to the desired level (DEBUG, INFO, WARNING, ERROR)
- [ ] Inspect `logs/de_funk.log` for full DEBUG output when console shows only INFO+
- [ ] Confirm log directory exists and is writable: `ls -la logs/`
- [ ] For structured logging issues, enable JSON with `LOG_JSON=true` and check `logs/de_funk.json`
- [ ] If LogTimer shows unexpected durations, check that the timed block does not include unrelated I/O

### Common Pitfalls

1. **Calling `get_logger()` before `setup_logging()`**: The logger will work (Python's default), but output goes to stderr with no formatting, no file handler, and no level filtering. Always call `setup_logging()` first in your entry point.

2. **Using `print()` instead of `logger`**: The CLAUDE.md rules enforce `logger` over `print()`. Print statements bypass the entire logging infrastructure -- no levels, no rotation, no structured output.

3. **Passing `extra` fields not in `StructuredFormatter.extra_fields` list**: The JSON formatter only captures a fixed set of extra field names (`ticker`, `model`, `duration_ms`, `provider`, `endpoint`, `record_count`, `operation`, `table`, `path`). Other extra fields are silently ignored in JSON output. Add new field names to the `extra_fields` list in `StructuredFormatter.format()` if needed.

4. **Assuming LogTimer suppresses exceptions**: Like `ErrorContext`, `LogTimer.__exit__` returns `False` -- exceptions always propagate. It logs the failure with timing but does not catch anything.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/config/logging.py` | Centralized Logging Configuration for de_Funk. | `LogConfig`, `StructuredFormatter`, `ColoredFormatter`, `LogTimer` |
