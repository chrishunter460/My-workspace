# CLAUDE.md - AI Assistant Guide for de_Funk

**Last Updated**: 2026-03-16
**Version**: 4.0

This file provides rules and conventions for AI assistants working with the de_Funk codebase. For architecture, API, pipeline, and model documentation, see [docs/README.md](docs/README.md).

## Project Overview

**de_Funk** is a graph-based analytical overlay that turns markdown domain configs into a queryable data warehouse. Users write exhibit blocks in Obsidian notes; the plugin queries a FastAPI backend that resolves fields, builds joins, and executes SQL against DuckDB over Delta Lake silver tables.

**Key concepts:**
- Two-layer architecture: Bronze (raw API data) → Silver (dimensional star schemas)
- Domain models defined in `domains/models/` as markdown with YAML frontmatter
- Canonical domain names (e.g. `securities.stocks`, `corporate.entity`) used everywhere
- Spark for offline builds, DuckDB for interactive queries
- Delta Lake for all storage (ACID, schema evolution)

## Documentation

| Document | Topics |
|----------|--------|
| [docs/architecture.md](docs/architecture.md) | System diagram, query pipeline, build pipeline, domain scoping |
| [docs/api.md](docs/api.md) | FastAPI endpoints, handlers, request/response formats |
| [docs/obsidian-plugin.md](docs/obsidian-plugin.md) | Block syntax, filters, controls, plugin architecture |
| [docs/domain-models.md](docs/domain-models.md) | Domain catalog, YAML frontmatter, inheritance, graph edges |
| [docs/data-pipeline.md](docs/data-pipeline.md) | Bronze ingestion, facets, providers, Silver builds |
| [docs/internals.md](docs/internals.md) | Config, logging, errors, measures, filters, storage routing |
| [docs/operations.md](docs/operations.md) | Running the server, building models, scripts reference |

## Repository Structure

```
de_Funk/
├── src/de_funk/           # Python package
│   ├── api/               # FastAPI backend (resolver, executor, handlers)
│   ├── config/            # ConfigLoader, logging, constants
│   ├── core/              # Exceptions, error handling, session/filters
│   ├── models/            # BaseModel, measures, domain builders
│   ├── pipelines/         # Facets, ingestors, providers
│   └── orchestration/     # Spark session, scheduler
├── domains/               # Domain model configs (markdown + YAML)
│   ├── _base/             # Reusable base templates
│   ├── _model_guides_/    # YAML syntax reference
│   └── models/            # All domain model directories
├── obsidian-plugin/       # TypeScript Obsidian plugin
├── configs/               # Runtime config (storage.json, run_config.json)
├── scripts/               # Operational scripts
├── tests/                 # Unit and integration tests
├── docs/                  # Technical documentation
└── notebooks/             # User notebooks (markdown)
```

## Best Practices for AI Assistants

1. **Read before editing** — always use Read tool before Edit tool
2. **Search before creating** — check for existing similar code first
3. **Use canonical names** — `securities.stocks` not `stocks`, `corporate.entity` not `company`
4. **Use session abstraction** — never import `duckdb` or `pyspark` directly
5. **Follow conventions** — match existing code style and patterns
6. **Run tests** — execute relevant test scripts before committing

---

## Code Quality Rules (MUST FOLLOW)

### File Size Limits (ENFORCED)

| Threshold | Action Required |
|-----------|-----------------|
| **<300 lines** | Target size - proceed normally |
| **300-500 lines** | Warning - consider splitting before adding more |
| **500-800 lines** | Must justify why not splitting |
| **>800 lines** | **STOP** - Must refactor before adding ANY new code |

### Error Handling Rules (ENFORCED)

```python
# NEVER: bare except, silent pass, catching too broadly
except:
    pass

# CORRECT: specific exceptions with proper handling
try:
    do_something()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    raise
except FileNotFoundError as e:
    logger.error(f"File not found: {e}")
    raise ConfigurationError(f"Missing file: {e}") from e
```

**Rules**:
1. Never use bare `except:` — always specify exception types
2. Never silently pass — at minimum log the error
3. Use `from e` for exception chaining
4. Reraise unexpected exceptions — don't swallow bugs

### Logging Rules (ENFORCED)

```python
# NEVER use print() in production code
# CORRECT:
from de_funk.config.logging import setup_logging, get_logger, LogTimer

setup_logging()                          # Once at startup
logger = get_logger(__name__)            # Module-specific logger

logger.debug(f"Details: {details}")      # File only by default
logger.info(f"Processing {item}")        # Console + file
logger.warning(f"Rate limit reached")    # Issues
logger.error(f"Failed", exc_info=True)   # Errors with stack trace

with LogTimer(logger, "Building model"):
    model.build()
```

See [docs/internals.md](docs/internals.md) for the full exception hierarchy and error handling decorators.

### No Hardcoded Default Data (ENFORCED)

```python
# NEVER hardcode default tickers/data
if not tickers:
    tickers = ['AAPL', 'MSFT', 'GOOGL']  # BAD

# CORRECT: fail explicitly
if not tickers:
    raise ValueError("No tickers provided. Run ingestion pipeline.")

# CORRECT: explicit demo mode
if args.demo_mode:
    logger.warning("Running in DEMO MODE")
    tickers = DEMO_TICKERS
else:
    tickers = get_tickers_from_data_layer()
```

### No Pandas in Pipelines (ENFORCED)

Pandas is only allowed as the **final conversion step** in `app/ui/` when a visualization library requires a DataFrame. Use PyArrow or Spark everywhere else.

```python
# NEVER in scripts/, pipelines/, models/
df = dt.to_pandas()

# CORRECT
table = dt.to_pyarrow_table()           # PyArrow for reads
df = spark.read.format('delta').load(p)  # Spark for transforms
chart_data = spark_df.limit(1000).toPandas()  # Only in app/ui/
```

### Backend Selection (ENFORCED)

Never import `duckdb` or `pyspark` directly. Use `UniversalSession(backend=...)`.

| Use Case | Backend |
|----------|---------|
| Model building (ETL) | **Spark** |
| Bronze → Silver transforms | **Spark** |
| Interactive queries | **DuckDB** |
| Notebook execution | **DuckDB** |
| Unit tests | **DuckDB** |

### Architecture Boundaries

| Layer | Location | Does NOT Do |
|-------|----------|-------------|
| **Config** | `config/`, `configs/` | Query data, HTTP requests |
| **Core** | `core/` | Business logic, UI |
| **Pipelines** | `pipelines/` | Query data, build models |
| **Models** | `models/` | Fetch APIs, handle UI |
| **API** | `api/` | Direct DB imports, pipeline code |

### Anti-Patterns

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| God File (>800 lines) | Split into focused modules |
| Bare `except: pass` | Specific exceptions with logging |
| `print()` debugging | `logger.debug()` |
| Duplicate implementation | Extend existing code |
| Cross-layer import | Add service layer between |
| `import duckdb` directly | Use `UniversalSession` |
| Hardcoded tickers/data | Read from config or data layer |
| `.to_pandas()` on large tables | PyArrow or Spark |

### Code Duplication Rules

Before implementing new functionality:
1. Search the codebase for similar code
2. Extend existing if close to what you need
3. Never create a "similar but different" version

**Canonical implementations** (use these, don't recreate):
- FilterEngine: `core/session/filters.py`
- Configuration: `config/loader.py`
- Backend detection: existing session patterns

### Pre-Commit Checklist

- [ ] Target file is <300 lines (or I'm extracting, not adding)
- [ ] No bare `except:` clauses added
- [ ] No `print()` statements added (use logger)
- [ ] Searched for existing similar code first
- [ ] Imports don't cross layer boundaries
- [ ] No direct `import duckdb` or `import pyspark`
- [ ] Correct backend selected (Spark for batch, DuckDB for interactive)
- [ ] No hardcoded default data
- [ ] No `.to_pandas()` on large tables
- [ ] Added/updated tests if behavior changed
- [ ] Updated `docs/modules/*.md` if public class/method added or renamed

### Module Documentation

When adding or renaming a public class or method in `src/de_funk/`, update the relevant `docs/modules/*.md` document and its `last_updated` frontmatter field. Run `python -m scripts.docs.scaffold_module_docs --check` to find stale docs.

### Docstring Standards

```python
def calculate_measure(self, measure_name: str, filters: Optional[Dict] = None) -> Any:
    """
    Calculate a measure by name.

    Args:
        measure_name: Name of the measure from YAML config
        filters: Optional filters to apply before calculation

    Returns:
        Calculated measure value

    Raises:
        MeasureNotFoundError: If measure_name not in config
    """
```

Module docstrings required at top of every new file.

### Testing Rules

| Change Type | Test Required? |
|-------------|---------------|
| New function with logic | Yes — unit test |
| Bug fix | Yes — regression test |
| New model / API endpoint | Yes — integration test |
| Refactoring (no behavior change) | Yes — verify existing tests pass |
| Documentation only | No |

```bash
pytest tests/unit/ -v                    # Unit tests
pytest tests/integration/ -v             # Integration tests
pytest tests/ -v                         # All tests
```

### Script Conventions

All scripts use `python -m scripts.{category}.{name}` syntax. Template:

```python
#!/usr/bin/env python
"""Script Name - Brief description."""
from __future__ import annotations
import argparse, sys
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
from de_funk.config.logging import setup_logging, get_logger
logger = get_logger(__name__)

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    try:
        # Script logic
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Commit Message Conventions

```
type: Short description (imperative mood, <50 chars)
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

### When to Ask for Clarification

Stop and ask when:
1. Ambiguous requirements
2. Multiple valid approaches
3. Breaking changes (function signatures, config structure)
4. Large scope (>5 files, >500 lines)
5. Unclear priority between multiple tasks
