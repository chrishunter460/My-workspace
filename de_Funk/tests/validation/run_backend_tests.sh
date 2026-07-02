#!/bin/bash
# Backend Integration Tests
#
# Tests both Spark (ETL) and DuckDB (Reporting) backends to ensure
# the codebase works correctly with both connection types.
#
# SPARK: Used for ETL operations (build_all_models.py)
# DUCKDB: Used for reporting/UI operations (queries, measure execution)

set -e  # Exit on error

echo "================================================================================"
echo "BACKEND INTEGRATION TESTS"
echo "================================================================================"
echo ""

# DuckDB Test (always runs - no pyspark dependency)
echo ">>> TEST 1: DuckDB Backend (Reporting)"
echo "--------------------------------------------------------------------------------"
python scripts/test_domain_model_integration_duckdb.py
DUCKDB_EXIT=$?
echo ""

# Spark Test (requires pyspark)
echo ">>> TEST 2: Spark Backend (ETL)"
echo "--------------------------------------------------------------------------------"
if python -c "import pyspark" 2>/dev/null; then
    echo "PySpark detected - running Spark backend test"
    python scripts/test_domain_model_integration_spark.py
    SPARK_EXIT=$?
else
    echo "⚠ PySpark not installed - skipping Spark backend test"
    echo "  To test Spark backend, install pyspark and run:"
    echo "    python scripts/test_domain_model_integration_spark.py"
    SPARK_EXIT=0  # Don't fail if PySpark not available
fi
echo ""

# Summary
echo "================================================================================"
echo "OVERALL RESULTS"
echo "================================================================================"
if [ $DUCKDB_EXIT -eq 0 ]; then
    echo "✓ DuckDB Backend:  PASS"
else
    echo "✗ DuckDB Backend:  FAIL"
fi

if python -c "import pyspark" 2>/dev/null; then
    if [ $SPARK_EXIT -eq 0 ]; then
        echo "✓ Spark Backend:   PASS"
    else
        echo "✗ Spark Backend:   FAIL"
    fi
else
    echo "⊘ Spark Backend:   SKIPPED (PySpark not installed)"
fi
echo "================================================================================"

# Exit with failure if DuckDB failed (Spark is optional)
exit $DUCKDB_EXIT
