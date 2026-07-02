# Scripts Directory

**Last Organized:** 2025-11-17
**Total Scripts:** 24
**Validation Status:** ✅ 95.8% Pass Rate (23/24 scripts passing)

This directory contains operational scripts for the de_Funk project, organized by function into categorized subdirectories.

---

## 📁 Directory Structure

```
scripts/
├── build/                    # Model building and Silver layer construction
├── ingest/                   # Data ingestion and Bronze layer
├── maintenance/              # Clearing, resetting, cleanup operations
├── forecast/                 # Forecasting operations
├── test/                     # Testing and validation scripts
├── test_scripts.py           # Comprehensive script validation tester
└── README.md                 # This file
```

---

## 🔨 Build Scripts (6 scripts)

**Purpose:** Model building and Silver layer construction

| Script | Description | Usage |
|--------|-------------|-------|
| `build_all_models.py` | Build all models with paginated ingestion from real data sources | `python -m scripts.build.build_all_models [options]` |
| `build_silver_layer.py` | Build Silver layer from Bronze data | `python -m scripts.build.build_silver_layer` |
| `build_equity_silver.py` | Build Equity Silver Layer using Spark | `python -m scripts.build.build_equity_silver` |
| `build_weighted_aggregates_duckdb.py` | Build weighted aggregate views (DuckDB) | `python -m scripts.build.build_weighted_aggregates_duckdb` |
| `build_weighted_views.py` | Build weighted aggregate views for equity model | `python -m scripts.build.build_weighted_views` |
| `rebuild_model.py` | Rebuild specific model from Bronze layer data | `python -m scripts.build.rebuild_model --model <name>` |

### Common Build Examples

```bash
# Build all models with default settings
python -m scripts.build.build_all_models

# Build specific models only
python -m scripts.build.build_all_models --models equity corporate

# Build with date range
python -m scripts.build.build_all_models --date-from 2024-01-01 --date-to 2024-12-31

# Build with ticker limit (for testing)
python -m scripts.build.build_all_models --max-tickers 20

# Rebuild just the equity model
python -m scripts.build.rebuild_model --model equity
```

---

## 📥 Ingest Scripts (3 scripts)

**Purpose:** Data ingestion and Bronze layer operations (Delta Lake format v2.3+)

| Script | Description | Usage |
|--------|-------------|-------|
| `Bronze_pull.py` | Bronze layer data ingestion | `python -m scripts.ingest.Bronze_pull` |
| `run_full_pipeline.py` | Complete ETL pipeline orchestrator | `python -m scripts.ingest.run_full_pipeline [options]` |
| `refresh_market_cap_rankings.py` | Refresh market cap rankings from Alpha Vantage | `python -m scripts.ingest.refresh_market_cap_rankings` |

### Common Ingest Examples

```bash
# Run full pipeline with default settings
python -m scripts.ingest.run_full_pipeline

# Run pipeline with date range and ticker limit
python -m scripts.ingest.run_full_pipeline --from 2024-01-01 --max-tickers 100

# Refresh market cap rankings
python -m scripts.ingest.refresh_market_cap_rankings
```

---

## 🧹 Maintenance Scripts (3 scripts)

**Purpose:** Clearing, resetting, and cleanup operations

| Script | Description | Usage |
|--------|-------------|-------|
| `clear_and_refresh.py` | Clear storage and refresh all data from scratch | `python -m scripts.maintenance.clear_and_refresh [options]` |
| `clear_silver.py` | Clear Silver layer storage | `python -m scripts.maintenance.clear_silver [options]` |
| `reset_model.py` | Reset model storage to clean state | `python -m scripts.maintenance.reset_model --model <name>` |

### Common Maintenance Examples

```bash
# Clear and rebuild everything
python -m scripts.maintenance.clear_and_refresh

# Clear only Silver layer
python -m scripts.maintenance.clear_silver --all

# Reset a specific model
python -m scripts.maintenance.reset_model --model equity
```

---

## 📊 Forecast Scripts (3 scripts)

**Purpose:** Time series forecasting operations

| Script | Description | Usage |
|--------|-------------|-------|
| `run_forecasts.py` | Execute forecasting models | `python -m scripts.forecast.run_forecasts [options]` |
| `run_forecasts_large_cap.py` | Execute forecasts for large cap companies | `python -m scripts.forecast.run_forecasts_large_cap [options]` |
| `verify_forecast_config.py` | Verify forecast model configuration | `python -m scripts.forecast.verify_forecast_config --help` |

### Common Forecast Examples

```bash
# Run all forecasts
python -m scripts.forecast.run_forecasts

# Run large cap forecasts only
python -m scripts.forecast.run_forecasts_large_cap

# Verify forecast configuration
python -m scripts.forecast.verify_forecast_config
```

---

## 🐛 Debug Scripts (8 scripts)

**Purpose:** Debugging and diagnostic utilities

| Script | Description | Usage |
|--------|-------------|-------|
| `check_parquet_path.py` | Check and validate Parquet file paths | `python -m scripts.debug.check_parquet_path` |
| `debug_exchange_data.py` | Debug exchange data issues | `python -m scripts.debug.debug_exchange_data` |
| `debug_forecast_view.py` | Debug forecast view issues | `python -m scripts.debug.debug_forecast_view` |
| `debug_session_injection.py` | Debug session injection | `python -m scripts.debug.debug_session_injection` |
| `debug_weighted_views.py` | Debug weighted aggregate views | `python -m scripts.debug.debug_weighted_views` |
| `diagnose_view_data.py` | Diagnose view data issues | `python -m scripts.debug.diagnose_view_data` |
| `drop_view.py` | Drop database views (utility) | `python -m scripts.debug.drop_view` |

### Common Debug Examples

```bash
# Debug exchange data
python -m scripts.debug.debug_exchange_data

# Check parquet paths
python -m scripts.debug.check_parquet_path

# Debug forecast views
python -m scripts.debug.debug_forecast_view

# Diagnose view data issues
python -m scripts.debug.diagnose_view_data
```

---

## 🧪 Test Scripts (29 scripts)

**Purpose:** Testing and validation

**Organized into:**
- **Integration tests:** Domain model integration, pipeline E2E
- **Unit tests:** Measure framework, backend adapters, weighting strategies
- **Performance tests:** Query performance, dimension selector
- **Standalone tests:** Filter system, UI state, merge logic, forecasts
- **Fixtures:** Sample data generators for testing
- **Configuration:** pytest conftest.py, pipeline_tester.py

| Category | Scripts | Description |
|----------|---------|-------------|
| **Integration** | 3 scripts | Domain model integration (DuckDB/Spark), E2E pipeline |
| **Unit Tests** | 4 scripts | Measure framework, backend adapters, weighting, utils |
| **Performance** | 3 scripts | Query performance, dimension selector, UI state |
| **Standalone** | 10 scripts | Filter system, UI components, forecast views, merge logic |
| **Validation** | 3 scripts | Cross-model edges, backend tests, all models |
| **Utilities** | 2 scripts + fixtures | Pipeline tester, conftest, sample data generator |

### Key Test Scripts

| Script | Description | Usage |
|--------|-------------|-------|
| `test_all_models.py` | Test all models in the framework | `python -m scripts.test.test_all_models --help` |
| `test_domain_model_integration_duckdb.py` | DuckDB backend integration tests | `python -m scripts.test.test_domain_model_integration_duckdb` |
| `test_domain_model_integration_spark.py` | Spark backend integration tests | `python -m scripts.test.test_domain_model_integration_spark --help` |
| `test_pipeline_e2e.py` | End-to-end pipeline test | `python -m scripts.test.test_pipeline_e2e --help` |
| `test_ui_integration.py` | UI integration test for Streamlit app | `python -m scripts.test.test_ui_integration --help` |
| `test_measure_framework.py` | Unit tests for measure framework | `pytest scripts/test/test_measure_framework.py` |
| `test_backend_adapters.py` | Unit tests for backend adapters | `pytest scripts/test/test_backend_adapters.py` |
| `verify_cross_model_edges.py` | Verify cross-model edges and dependencies | `python -m scripts.test.verify_cross_model_edges` |
| `run_backend_tests.sh` | Backend compatibility tests (Shell script) | `bash scripts/test/run_backend_tests.sh` |
| `conftest.py` | Pytest configuration and fixtures | N/A (auto-loaded by pytest) |

### Common Test Examples

```bash
# Test all models
python -m scripts.test.test_all_models

# Run E2E pipeline test
python -m scripts.test.test_pipeline_e2e

# Run pytest unit tests
pytest scripts/test/test_measure_framework.py
pytest scripts/test/test_backend_adapters.py
pytest scripts/test/  # Run all pytest tests

# Verify cross-model edges
python -m scripts.test.verify_cross_model_edges

# Run backend compatibility tests
bash scripts/test/run_backend_tests.sh

# Performance tests
python -m scripts.test.test_query_performance_duckdb
python -m scripts.test.test_dimension_selector_performance

# Standalone tests
python -m scripts.test.test_filter_system_standalone
python -m scripts.test.test_ui_state_standalone
```

---

## 🔍 Script Validation

### Syntax Validation (test_scripts.py)

The `test_scripts.py` utility validates script syntax and structure:

```bash
# Run validation on all scripts
python -m scripts.test_scripts

# Validate with verbose output
python -m scripts.test_scripts --verbose

# Validate specific category only
python -m scripts.test_scripts --category build

# Generate JSON report
python -m scripts.test_scripts --output report.json
```

### Validation Checks

The validator tests each script for:
- ✓ **Syntax validation** - Can parse without errors
- ✓ **Documentation** - Has module docstring
- ✓ **Import capability** - Can be imported as module
- ✓ **Help flag** - Supports `--help` argument (when applicable)

### Latest Validation Results

```
Total Scripts:  24
✅ Passed:      23 (95.8%)
⚠️  Warnings:    1 (4.2%)
❌ Failed:      0 (0.0%)

By Category:
- build:       6/6 passed (100%)
- forecast:    3/3 passed (100%)
- ingest:      2/3 passed (67%) - 1 warning
- maintenance: 3/3 passed (100%)
- test:        9/9 passed (100%)
```

### Runtime Validation (validate_all_scripts.py)

The `validate_all_scripts.py` utility **actually runs** all scripts with minimal test parameters to catch runtime errors:

```bash
# Validate all scripts (safe - skips destructive operations)
python -m scripts.validate_all_scripts

# Validate specific category
python -m scripts.validate_all_scripts --category build

# Include maintenance scripts (WARNING: destructive)
python -m scripts.validate_all_scripts --include-maintenance

# Verbose output with full command details
python -m scripts.validate_all_scripts --verbose

# Generate JSON report
python -m scripts.validate_all_scripts --report validation_report.json
```

**What it validates:**
- ✅ Scripts execute without crashing
- ✅ Import statements work correctly
- ✅ Command-line arguments are parsed
- ✅ --help flags work (where applicable)
- ✅ Scripts complete within timeout limits
- ✅ Integration between components

**Safety features:**
- Uses minimal test parameters (--max-tickers 5, --days 7, etc.)
- Skips destructive maintenance operations by default
- Uses --dry-run flags where available
- Skips long-running operations by default
- 3-second warning before running maintenance scripts

**When to use:**
- After making changes to core modules
- Before committing major refactors
- After updating dependencies
- To verify scripts still work in new environment
- Before creating a pull request

---

## 🗑️ Cleaned Up

The following items were removed or consolidated during reorganization:

### Removed Obsolete Scripts (11 from scripts/)

**Migration Utilities (one-time use):**
1. `migrate_to_delta.py` - Delta Lake migration (project uses Parquet)
2. `auto_fix_migration.py` - Path migration auto-fixer
3. `validate_migration.py` - Migration validation
4. `add_bootstrap.py` - Bootstrap pattern addition
5. `remove_bootstrap.py` - Bootstrap pattern removal

**Deprecated Model References:**
6. `run_company_data_pipeline.py` - Used old `company` model (now `equity`/`corporate`)
7. `run_company_pipeline.py` - Used old `company` model
8. `investigate_ticker_count.py` - Debug script for old `company` model

**Other Obsolete:**
9. `refresh_data.py` - Used old import paths (`src.orchestration`)
10. `build_equity_silver_duckdb.py` - Marked as "FALLBACK ONLY", bypasses proper model
11. `examples/Silve_pull.py` - Typo in name, incomplete example

### Removed from Root (7 files)

**Empty Documentation (6 files):**
- FORECAST_README.md
- PIPELINE_GUIDE.md
- QUICKSTART.md
- REBUILD_STORAGE.md
- RUNNING.md
- SHARED_CALENDAR_DIMENSION.md

**Duplicate (1 file):**
- run_full_pipeline.py (older version, scripts/ingest/ has current)

### Consolidated (tests/ folder → scripts/test/)

**All test files moved to scripts/test/ and tests/ folder removed:**
- Unit tests (4 files)
- Integration tests (1 file)
- Fixtures (sample_data_generator.py)
- Configuration (conftest.py)
- Pipeline tester and other test utilities

**Root test scripts moved to scripts/test/:**
- API_key_tests.py
- test_env_loader.py
- test_filter_system_standalone.py
- test_forecast_view_standalone.py
- test_merge_logic.py
- test_ui_state_standalone.py
- test_unified_filters.py
- test_weighted_fix.py

**Debug scripts moved to scripts/debug/:**
- check_parquet_path.py
- debug_exchange_data.py
- debug_forecast_view.py
- debug_session_injection.py
- debug_weighted_views.py
- diagnose_view_data.py
- drop_view.py

---

## 📝 Script Execution Pattern

All Python scripts in this directory should be executed using the **module pattern**:

```bash
# ✅ Correct (recommended)
python -m scripts.<category>.<script_name>

# ❌ Incorrect (avoid)
python scripts/<category>/<script_name>.py
```

### Why Use Module Pattern?

1. **Proper import resolution** - Python's module system handles paths correctly
2. **Consistent behavior** - Works regardless of current working directory
3. **Better debugging** - Stack traces show module names, not file paths
4. **Follows best practices** - Aligns with Python packaging standards

### Examples

```bash
# Build all models
python -m scripts.build.build_all_models

# Run full pipeline
python -m scripts.ingest.run_full_pipeline

# Clear and refresh
python -m scripts.maintenance.clear_and_refresh

# Run forecasts
python -m scripts.forecast.run_forecasts

# Test all models
python -m scripts.test.test_all_models

# Validate scripts
python -m scripts.test_scripts
```

---

## 🎯 Quick Reference

### Most Common Operations

| Task | Command |
|------|---------|
| Build all models | `python -m scripts.build.build_all_models` |
| Run full pipeline | `python -m scripts.ingest.run_full_pipeline` |
| Rebuild specific model | `python -m scripts.build.rebuild_model --model equity` |
| Clear everything | `python -m scripts.maintenance.clear_and_refresh` |
| Test all models | `python -m scripts.test.test_all_models` |
| Validate scripts | `python -m scripts.test_scripts` |
| Run forecasts | `python -m scripts.forecast.run_forecasts` |

### Getting Help

Every script supports the `--help` flag:

```bash
python -m scripts.<category>.<script_name> --help
```

Example:
```bash
$ python -m scripts.build.build_all_models --help
usage: build_all_models.py [-h] [--models MODELS [MODELS ...]]
                           [--date-from DATE_FROM] [--date-to DATE_TO]
                           [--days DAYS] [--max-tickers MAX_TICKERS]
                           [--skip-ingestion] [--parallel]
                           [--max-workers MAX_WORKERS] [--output OUTPUT]
                           [--config-dir CONFIG_DIR] [--dry-run]

Build all models with paginated ingestion from real data sources
...
```

---

## 🔄 Script Dependencies

**Prerequisites for all scripts:**
- Python 3.x
- Required packages installed (see `requirements.txt`)
- Proper `.env` configuration (API keys, etc.)

**Additional requirements by category:**

| Category | Additional Requirements |
|----------|------------------------|
| Build | Bronze data must exist (run ingest first) |
| Ingest | API keys configured in `.env` |
| Forecast | Silver data must exist, forecast model configured |
| Test | Both Bronze and Silver data for integration tests |

---

## 📊 Statistics

- **Total Scripts:** 52 organized scripts
- **Previously Scattered:** ~45 scripts across root, tests/, and scripts/
- **Scripts Removed:** 18 obsolete/empty files
- **Total Lines of Code:** ~15,000 lines (organized)
- **Categories:** 6 (build, ingest, maintenance, forecast, test, debug)
- **Test Coverage:** 29 test scripts + fixtures
- **Debug Tools:** 8 diagnostic scripts

---

## 🆘 Troubleshooting

### Common Issues

**Issue:** Script fails with import error
**Solution:** Ensure you're using the module pattern: `python -m scripts.<category>.<script>`

**Issue:** API errors during ingestion
**Solution:** Check `.env` file has valid API keys

**Issue:** No data found errors
**Solution:** Run ingestion first: `python -m scripts.ingest.run_full_pipeline`

**Issue:** Model build fails
**Solution:** Ensure Bronze data exists, check logs for specific errors

---

## 📚 Related Documentation

- **CLAUDE.md** - Comprehensive AI assistant guide
- **QUICKSTART.md** - Getting started guide
- **RUNNING.md** - How to run the application
- **TESTING_GUIDE.md** - Comprehensive testing guide
- **PIPELINE_GUIDE.md** - Data pipeline documentation

---

## ✅ Maintenance Checklist

When adding new scripts:

1. ☐ Place in appropriate category folder
2. ☐ Add module docstring
3. ☐ Support `--help` flag (if interactive)
4. ☐ Use `python -m` execution pattern in docs
5. ☐ Run `python -m scripts.test_scripts` to validate
6. ☐ Update this README with new script

---

**For questions or issues, refer to the comprehensive documentation or run `python -m scripts.test_scripts` to validate all scripts.**
