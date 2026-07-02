# Test Scripts

**Purpose:** Comprehensive test suite for de_Funk platform
**Organization:** Tests organized by type (unit, integration, performance, validation)

---

## 📁 Directory Structure

```
scripts/test/
├── unit/               # Unit tests (6 files)
├── integration/        # Integration tests (6 files)
├── performance/        # Performance tests (2 files)
├── validation/         # Validation tests (3 files)
├── fixtures/           # Test data generators
├── conftest.py         # Pytest configuration
├── pipeline_tester.py  # Pipeline testing utility
└── __init__.py
```

**Total:** 21 test files organized into 4 categories

---

## 🧪 Unit Tests (6 files)

**Location:** `scripts/test/unit/`

Essential pytest test suites with proper fixtures and assertions:

| Test | Description | Usage |
|------|-------------|-------|
| `test_backend_adapters.py` | Tests DuckDB/Spark backend adapters | `pytest scripts/test/unit/test_backend_adapters.py` |
| `test_measure_framework.py` | Core measure framework tests | `pytest scripts/test/unit/test_measure_framework.py` |
| `test_utils_repo.py` | Tests repo utility functions | `pytest scripts/test/unit/test_utils_repo.py` |
| `test_weighting_strategies.py` | Tests various weighting strategies | `pytest scripts/test/unit/test_weighting_strategies.py` |
| `test_env_loader.py` | Tests environment variable loading | `pytest scripts/test/unit/test_env_loader.py` |
| `API_key_tests.py` | Validates API key configuration | `python -m scripts.test.unit.API_key_tests` |

```bash
# Run all unit tests
pytest scripts/test/unit/

# Run specific unit test
pytest scripts/test/unit/test_measure_framework.py -v
```

---

## 🔗 Integration Tests (6 files)

**Location:** `scripts/test/integration/`

Comprehensive integration test suites testing end-to-end workflows:

| Test | Description | Usage |
|------|-------------|-------|
| `test_domain_model_integration_duckdb.py` | DuckDB backend integration tests | `python -m scripts.test.integration.test_domain_model_integration_duckdb` |
| `test_domain_model_integration_spark.py` | Spark backend integration tests | `python -m scripts.test.integration.test_domain_model_integration_spark` |
| `test_measure_pipeline.py` | Measure pipeline integration | `pytest scripts/test/integration/test_measure_pipeline.py` |
| `test_measures_with_spark.py` | Spark measure application tests | `pytest scripts/test/integration/test_measures_with_spark.py` |
| `test_pipeline_e2e.py` | End-to-end pipeline tests | `python -m scripts.test.integration.test_pipeline_e2e` |
| `test_ui_integration.py` | UI integration tests | `python -m scripts.test.integration.test_ui_integration` |

```bash
# Run all integration tests
pytest scripts/test/integration/

# Run specific integration test
python -m scripts.test.integration.test_pipeline_e2e
```

---

## ⚡ Performance Tests (2 files)

**Location:** `scripts/test/performance/`

Performance benchmarking and profiling tests:

| Test | Description | Usage |
|------|-------------|-------|
| `test_dimension_selector_performance.py` | Dimension selector performance | `python -m scripts.test.performance.test_dimension_selector_performance` |
| `test_query_performance_duckdb.py` | DuckDB query performance | `python -m scripts.test.performance.test_query_performance_duckdb` |

```bash
# Run performance tests
python -m scripts.test.performance.test_query_performance_duckdb
python -m scripts.test.performance.test_dimension_selector_performance
```

---

## ✅ Validation Tests (3 files)

**Location:** `scripts/test/validation/`

Model validation and verification tests:

| Test | Description | Usage |
|------|-------------|-------|
| `test_all_models.py` | Tests all model implementations | `python -m scripts.test.validation.test_all_models` |
| `verify_cross_model_edges.py` | Verifies cross-model relationships | `python -m scripts.test.validation.verify_cross_model_edges` |
| `run_backend_tests.sh` | Backend compatibility tests | `bash scripts/test/validation/run_backend_tests.sh` |

```bash
# Run validation tests
python -m scripts.test.validation.test_all_models
python -m scripts.test.validation.verify_cross_model_edges
bash scripts/test/validation/run_backend_tests.sh
```

---

## 🛠️ Test Utilities

### conftest.py
Pytest configuration and shared fixtures for all tests.

**Auto-loaded by pytest** - provides common fixtures like `sample_price_data`, `sample_company_data`, etc.

### pipeline_tester.py
Comprehensive pipeline testing utility for validating entire data pipeline.

```bash
python -m scripts.test.pipeline_tester
```

### fixtures/
Test data generators for creating sample data:
- `sample_data_generator.py` - Generates sample price data, company data, etc.

---

## 🚀 Running Tests

### Run All Tests
```bash
# Run all pytest tests
pytest scripts/test/

# Run with verbose output
pytest scripts/test/ -v

# Run with coverage
pytest scripts/test/ --cov=models --cov=core
```

### Run by Category
```bash
# Unit tests only
pytest scripts/test/unit/

# Integration tests only
pytest scripts/test/integration/

# Performance tests
python -m scripts.test.performance.test_query_performance_duckdb

# Validation tests
python -m scripts.test.validation.test_all_models
```

### Run Specific Test
```bash
# Run specific pytest test
pytest scripts/test/unit/test_measure_framework.py

# Run specific Python test script
python -m scripts.test.integration.test_pipeline_e2e
```

---

## 📊 Test Coverage

| Category | Files | Purpose |
|----------|-------|---------|
| **Unit** | 6 | Test individual components in isolation |
| **Integration** | 6 | Test component interactions and workflows |
| **Performance** | 2 | Benchmark and profile system performance |
| **Validation** | 3 | Validate models and cross-model relationships |
| **Utilities** | 3 | Test infrastructure (fixtures, conftest, pipeline tester) |

**Total:** 21 well-maintained test files

---

## 🔍 Test Organization Principles

1. **Unit tests** - Fast, isolated, no external dependencies
2. **Integration tests** - Test real workflows with database
3. **Performance tests** - Benchmark performance metrics
4. **Validation tests** - Verify system-wide consistency

---

## 📝 Adding New Tests

### Unit Test Template
```python
import pytest
from your_module import your_function

def test_your_function():
    # Arrange
    input_data = ...

    # Act
    result = your_function(input_data)

    # Assert
    assert result == expected_output
```

Place in `scripts/test/unit/test_your_module.py`

### Integration Test Template
```python
from scripts.test.conftest import *  # Import fixtures

def test_your_integration(sample_price_data):
    # Test with real data and database
    ...
```

Place in `scripts/test/integration/test_your_integration.py`

---

## 🗑️ Recently Removed

**6 standalone diagnostic test scripts removed** (2025-11-17):
- `test_weighted_fix.py` - One-time verification script
- `test_merge_logic.py` - Basic functionality check
- `test_unified_filters.py` - Redundant test
- `test_forecast_view_standalone.py` - Debug script
- `test_filter_system_standalone.py` - Duplicated in integration
- `test_ui_state_standalone.py` - Covered in UI integration tests

**Reason:** One-time diagnostic scripts that served their purpose. Functionality now covered in comprehensive integration tests.

---

## 🆘 Troubleshooting

**Issue:** Pytest can't find tests
**Solution:** Make sure you're running from repo root:
```bash
cd /home/user/de_Funk
pytest scripts/test/
```

**Issue:** Import errors in tests
**Solution:** Tests use `utils.repo.setup_repo_imports()` to handle paths

**Issue:** Test requires data
**Solution:** Ensure Bronze/Silver data exists or use fixtures from `conftest.py`

---

**For more information, see the main scripts README: `/scripts/README.md`**
