# Example Validation Tests

This directory contains comprehensive tests for all example scripts in `scripts/examples/`.

## Overview

Two complementary approaches to testing examples:

1. **Unit Tests** (`test_examples.py`) - Comprehensive pytest-based tests
2. **Import Validation** (`validate_all_examples.py`) - Quick sanity check for import errors

## Running Tests

### Full Test Suite (Recommended)

Run all example tests with pytest:

```bash
# Run all tests
pytest scripts/test/validation/test_examples.py -v

# Run with detailed output
pytest scripts/test/validation/test_examples.py -v --tb=short

# Run specific test class
pytest scripts/test/validation/test_examples.py::TestQueryExamples -v
pytest scripts/test/validation/test_examples.py::TestExtensionExamples -v
pytest scripts/test/validation/test_examples.py::TestAutoEnrichExamples -v

# Run with coverage
pytest scripts/test/validation/test_examples.py --cov=scripts.examples
```

### Quick Validation

Quick check that all examples can be imported:

```bash
# Run import validation
python scripts/test/validation/validate_all_examples.py

# Or using module syntax
python -m scripts.test.validation.validate_all_examples
```

## Test Coverage

### test_examples.py

Comprehensive unit tests covering:

#### 1. TestParameterInterface
- Calculator initialization
- Model listing (checks for 'stocks' or 'company')
- Measure listing
- Measure information retrieval

#### 2. TestCalculationRequest
- Request creation with 'stocks' model
- Date filtering
- Parameter conversion

#### 3. TestParameterValidation
- Valid parameter validation
- Missing required fields
- Invalid date formats
- Invalid backends
- Date range validation
- Invalid limits

#### 4. TestWeightedCalculations
- Volume-weighted index calculations
- Multiple ticker calculations
- Strategy comparisons
- All tests use 'stocks' model (v2.0)

#### 5. TestQueryExamples ✨ NEW
- Directory structure validation
- `01_auto_join.py` imports and functions
- `02_query_planner.py` imports and functions
- `03_session_queries.py` imports and functions

#### 6. TestExtensionExamples ✨ NEW
- Directory structure validation
- `custom_facet.py` imports
- `custom_model.py` imports
- `custom_provider.py` imports
- `custom_notebook.md` exists and has content

#### 7. TestAutoEnrichExamples ✨ NEW
- `04_auto_enrich_demo.py` imports and functions
- `05_auto_enrich_example.py` imports and functions

#### 8. TestExampleDocumentation ✨ NEW
- Main README exists and has content
- Queries README exists
- Extending README exists
- Documentation completeness

#### 9. TestExampleIntegrity ✨ NEW
- All Python examples have docstrings
- Examples use proper import patterns
- No hardcoded absolute paths

### validate_all_examples.py

Quick validation script that:
- Finds all Python example files
- Attempts to import each one
- Reports successes and failures
- Returns exit code (0 = success, 1 = failures)

## Example Test Output

### Successful Run

```
======================================= test session starts ========================================
collected 37 items

scripts/test/validation/test_examples.py::TestParameterInterface::test_calculator_initialization PASSED
scripts/test/validation/test_examples.py::TestParameterInterface::test_list_models PASSED
scripts/test/validation/test_examples.py::TestQueryExamples::test_query_examples_directory_structure PASSED
scripts/test/validation/test_examples.py::TestQueryExamples::test_auto_join_example_imports PASSED
scripts/test/validation/test_examples.py::TestExtensionExamples::test_extending_directory_structure PASSED
scripts/test/validation/test_examples.py::TestExampleIntegrity::test_all_python_examples_have_docstrings PASSED

====================================== 30 passed, 7 skipped in 2.5s =======================================
```

### Quick Validation Output

```
======================================================================
Example Files Validation
======================================================================

🔍 Searching for examples in: /home/user/de_Funk/scripts/examples
📝 Found 12 example files

  Testing: scripts/examples/queries/01_auto_join.py... ✅
  Testing: scripts/examples/queries/02_query_planner.py... ✅
  Testing: scripts/examples/queries/03_session_queries.py... ✅
  Testing: scripts/examples/extending/custom_facet.py... ✅
  Testing: scripts/examples/extending/custom_model.py... ✅
  Testing: scripts/examples/extending/custom_provider.py... ✅
  Testing: scripts/examples/measure_calculations/04_auto_enrich_demo.py... ✅
  Testing: scripts/examples/measure_calculations/05_auto_enrich_example.py... ✅

======================================================================
Summary
======================================================================
✅ Passed: 12
❌ Failed: 0

🎉 All examples validated successfully!
```

## Test Classes by Category

### Query Examples
- **TestQueryExamples** - Tests for `scripts/examples/queries/`
  - Auto-join example
  - Query planner example
  - Session queries example

### Extension Examples
- **TestExtensionExamples** - Tests for `scripts/examples/extending/`
  - Custom facet example
  - Custom model example
  - Custom provider example
  - Custom notebook example

### Measure Calculations
- **TestAutoEnrichExamples** - Tests for auto-enrichment examples
  - Auto-enrich demo
  - Auto-enrich example

### Documentation
- **TestExampleDocumentation** - Validates README files
  - Main examples README
  - Queries README
  - Extending README

### Code Quality
- **TestExampleIntegrity** - Code quality checks
  - Module docstrings
  - Proper import patterns
  - No hardcoded paths

## Continuous Integration

Add to CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Test Examples
  run: |
    pytest scripts/test/validation/test_examples.py -v
    python scripts/test/validation/validate_all_examples.py
```

## Skipped Tests

Tests may be skipped if:
- Model not available (e.g., "Stocks model not available")
- No data available for calculations
- Dependencies not installed

This is expected in test environments without full data setup.

## Troubleshooting

### Import Errors

If tests fail with import errors:
1. Ensure you're in the repo root
2. Check that `utils.repo` module exists
3. Verify Python path includes repo root

### Model Not Found

If tests skip due to missing models:
1. Build the models: `python -m scripts.build.build_all_models`
2. Check model registry: `python -c "from models.api.registry import get_model_registry; print(get_model_registry().list_models())"`

### Path Issues

If examples have path errors:
1. Check they use `setup_repo_imports()`
2. Verify no hardcoded absolute paths
3. Run integrity tests: `pytest scripts/test/validation/test_examples.py::TestExampleIntegrity -v`

## Adding New Tests

When adding new examples:

1. **Add to test_examples.py**:
   - Create test method in appropriate class
   - Test import succeeds
   - Test key functions/classes exist
   - Add to integrity checks

2. **Update this README**:
   - Document new test coverage
   - Update test count
   - Add example output

3. **Run validation**:
   ```bash
   pytest scripts/test/validation/test_examples.py -v
   python scripts/test/validation/validate_all_examples.py
   ```

## Related Documentation

- **Examples Overview**: `scripts/examples/README.md`
- **Query Examples**: `scripts/examples/queries/README.md`
- **Extension Examples**: `scripts/examples/extending/README.md`
- **Testing Guide**: `/TESTING_GUIDE.md`

## Support

For issues with tests:
1. Check that examples are in correct locations
2. Verify import patterns are correct
3. Review test output for specific errors
4. Check related documentation above
