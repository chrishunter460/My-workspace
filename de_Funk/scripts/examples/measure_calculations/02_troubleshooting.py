#!/usr/bin/env python3
"""
Troubleshooting Guide - Common Issues and Solutions

Demonstrates how to debug and resolve common problems with the measure framework.
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()


def problem_1_measure_not_found():
    """Problem 1: Measure not found error."""
    print("\n" + "=" * 70)
    print("PROBLEM 1: Measure Not Found")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # This will fail
    try:
        result = model.calculate_measure('nonexistent_measure')
    except ValueError as e:
        print(f"\n✗ Error (expected): {e}")

    # SOLUTION: List available measures
    print("\n✓ Solution: List available measures")
    measures = model.measures.list_measures()
    print(f"\nAvailable measures: {list(measures.keys())}")


def problem_2_backend_not_supported():
    """Problem 2: Backend not supported."""
    print("\n" + "=" * 70)
    print("PROBLEM 2: Backend Issues")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Check detected backend
    print(f"\nDetected backend: {model.backend}")

    # Check backend capabilities
    adapter = model.measures.adapter
    print(f"\nBackend adapter: {type(adapter).__name__}")
    print(f"Dialect: {adapter.get_dialect()}")

    print("\nSupported features:")
    for feature in ['window_functions', 'cte', 'qualify', 'lateral_join']:
        supported = adapter.supports_feature(feature)
        print(f"  {feature}: {'✓' if supported else '✗'}")


def problem_3_table_not_found():
    """Problem 3: Table not found in schema."""
    print("\n" + "=" * 70)
    print("PROBLEM 3: Table Not Found")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Check model schema
    print("\nModel schema:")
    schema = model.model_cfg.get('schema', {})

    print("\nDimensions:")
    for dim_name in schema.get('dimensions', {}).keys():
        print(f"  - {dim_name}")

    print("\nFacts:")
    for fact_name in schema.get('facts', {}).keys():
        print(f"  - {fact_name}")

    # This helps debug measure source errors
    print("\n✓ If measure fails, check that source table exists in schema")


def problem_4_sql_generation_error():
    """Problem 4: SQL generation error."""
    print("\n" + "=" * 70)
    print("PROBLEM 4: SQL Generation Error")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Use explain to see generated SQL
    print("\n✓ Use explain_measure() to debug SQL:")

    measure_name = 'avg_close_price'
    sql = model.measures.explain_measure(measure_name)

    print(f"\nGenerated SQL for '{measure_name}':")
    print("-" * 70)
    print(sql)
    print("-" * 70)

    # You can copy this SQL and test it directly in DuckDB
    print("\n✓ Tip: Copy SQL and test in DuckDB CLI for debugging")


def problem_5_performance_slow():
    """Problem 5: Slow measure calculation."""
    print("\n" + "=" * 70)
    print("PROBLEM 5: Performance Issues")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel
    import time

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Measure execution time
    print("\n✓ Measuring query performance:")

    measure_name = 'avg_close_price'

    start = time.time()
    result = model.calculate_measure(measure_name, entity_column='ticker', limit=10)
    elapsed = time.time() - start

    print(f"\nMeasure: {measure_name}")
    print(f"Total time: {elapsed * 1000:.2f}ms")
    print(f"Query time: {result.query_time_ms:.2f}ms")
    print(f"Overhead: {(elapsed * 1000 - result.query_time_ms):.2f}ms")

    print("\n✓ Tips for improving performance:")
    print("  1. Add LIMIT clause to reduce result set")
    print("  2. Use filters to reduce data scanned")
    print("  3. Ensure bronze data is partitioned properly")
    print("  4. Check for table scans in EXPLAIN PLAN")


def problem_6_data_type_mismatch():
    """Problem 6: Data type mismatch."""
    print("\n" + "=" * 70)
    print("PROBLEM 6: Data Type Issues")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Check measure data types
    print("\n✓ Checking measure data types:")

    measures = model.measures.list_measures()
    for measure_name in list(measures.keys())[:5]:
        info = model.measures.get_measure_info(measure_name)
        print(f"\n  {measure_name}:")
        print(f"    Data type: {info['data_type']}")
        print(f"    Source: {info['source']}")

    print("\n✓ Ensure source column type matches measure data_type in config")


def problem_7_weighted_measure_wrong_results():
    """Problem 7: Weighted measure producing unexpected results."""
    print("\n" + "=" * 70)
    print("PROBLEM 7: Weighted Measure Validation")
    print("=" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.implemented.company.model import CompanyModel

    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Compare different weighting methods
    print("\n✓ Comparing weighting methods:")

    weighted_measures = [
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index'
    ]

    measures = model.measures.list_measures()

    for measure_name in weighted_measures:
        if measure_name not in measures:
            print(f"\n  {measure_name}: not defined")
            continue

        try:
            result = model.calculate_measure(measure_name)
            first_value = result.data.iloc[0]['weighted_value'] if result.rows > 0 else None

            print(f"\n  {measure_name}:")
            print(f"    Rows: {result.rows}")
            print(f"    First value: {first_value:.2f if first_value else 'N/A'}")

            # Show SQL for debugging
            sql = model.measures.explain_measure(measure_name)
            print(f"    SQL preview: {sql[:100]}...")
        except Exception as e:
            print(f"\n  {measure_name}: ERROR - {e}")

    print("\n✓ Tips:")
    print("  - Equal weighted should be simple average")
    print("  - Volume weighted weights by trading volume")
    print("  - Market cap weighted weights by price × volume")


def problem_8_etf_holdings_not_working():
    """Problem 8: ETF holdings-based measures not working."""
    print("\n" + "=" * 70)
    print("PROBLEM 8: ETF Holdings Measures")
    print("=" * 70)

    try:
from de_funk.core.context import RepoContext
from de_funk.models.implemented.etf.model import ETFModel

        ctx = RepoContext.from_repo_root(connection_type='duckdb')
        etf_model = ETFModel(ctx.connection, ctx.storage, ctx.repo)

        # Check ETF measures
        print("\n✓ ETF model loaded successfully")

        measures = etf_model.measures.list_measures()
        print(f"\nAvailable ETF measures: {len(measures)}")

        for measure_name in measures.keys():
            info = etf_model.measures.get_measure_info(measure_name)
            if info['type'] == 'weighted':
                print(f"\n  {measure_name}:")
                print(f"    Type: {info['type']}")
                print(f"    Source: {info['source']}")

    except ImportError:
        print("\n✗ ETF model not available")
        print("\n✓ Solution: Ensure etf.yaml exists in configs/models/")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\n✓ Check that:")
        print("  1. ETF bronze data exists")
        print("  2. ETF holdings table is populated")
        print("  3. Cross-model references are configured correctly")


def main():
    """Run all troubleshooting examples."""
    problems = [
        problem_1_measure_not_found,
        problem_2_backend_not_supported,
        problem_3_table_not_found,
        problem_4_sql_generation_error,
        problem_5_performance_slow,
        problem_6_data_type_mismatch,
        problem_7_weighted_measure_wrong_results,
        problem_8_etf_holdings_not_working,
    ]

    print("\n" + "=" * 70)
    print("MEASURE FRAMEWORK - TROUBLESHOOTING GUIDE")
    print("=" * 70)

    for problem in problems:
        try:
            problem()
        except Exception as e:
            print(f"\n✗ Error in {problem.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Troubleshooting guide complete!")
    print("\n✓ Common solutions:")
    print("  1. List available measures with model.measures.list_measures()")
    print("  2. Use explain_measure() to see generated SQL")
    print("  3. Check schema with model.model_cfg['schema']")
    print("  4. Verify backend with model.backend")
    print("  5. Test SQL directly in DuckDB for debugging")
    print("=" * 70)


if __name__ == '__main__':
    main()
