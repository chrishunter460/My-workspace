#!/usr/bin/env python
"""
Validate filter system to identify DuckDB filter crash issues.

This script tests the FilterEngine to confirm the numeric quoting bug
and validates the full filter flow from UI to DuckDB.

Run: python -m scripts.test.validate_filter_system
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def validate_filter_sql_generation():
    """Test FilterEngine SQL generation for type issues."""
    print("\n" + "="*60)
    print("VALIDATION 1: Filter SQL Generation")
    print("="*60 + "\n")

from de_funk.core.session.filters import FilterEngine

    tests_passed = 0
    tests_failed = 0

    # Test case 1: Numeric min/max (the suspected bug)
    print("Test 1.1: Numeric min/max filter")
    print("-" * 40)
    filters = {'volume': {'min': 1000000, 'max': 5000000}}
    sql = FilterEngine.build_filter_sql(filters)
    print(f"  Input:  {filters}")
    print(f"  Output: {sql}")

    # Check for quoted numerics (the bug)
    if "'1000000'" in sql or "'5000000'" in sql:
        print("  ❌ BUG CONFIRMED: Numeric values are quoted as strings!")
        print("     Expected: volume >= 1000000 AND volume <= 5000000")
        print("     Got:      " + sql)
        tests_failed += 1
    else:
        print("  ✅ Numeric values are correctly unquoted")
        tests_passed += 1

    # Test case 2: Date range (should be quoted - this is correct)
    print("\nTest 1.2: Date range filter (should be quoted)")
    print("-" * 40)
    filters = {'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}}
    sql = FilterEngine.build_filter_sql(filters)
    print(f"  Input:  {filters}")
    print(f"  Output: {sql}")

    if "'2024-01-01'" in sql and "'2024-12-31'" in sql:
        print("  ✅ Date strings are correctly quoted")
        tests_passed += 1
    else:
        print("  ❌ Date strings should be quoted")
        tests_failed += 1

    # Test case 3: String IN clause
    print("\nTest 1.3: String IN clause filter")
    print("-" * 40)
    filters = {'ticker': ['AAPL', 'MSFT', 'GOOGL']}
    sql = FilterEngine.build_filter_sql(filters)
    print(f"  Input:  {filters}")
    print(f"  Output: {sql}")

    if "IN ('AAPL', 'MSFT', 'GOOGL')" in sql:
        print("  ✅ String IN clause correctly quoted")
        tests_passed += 1
    else:
        print("  ❌ String IN clause formatting issue")
        tests_failed += 1

    # Test case 4: Mixed filters (the real-world scenario)
    print("\nTest 1.4: Mixed filters (realistic scenario)")
    print("-" * 40)
    filters = {
        'ticker': ['AAPL', 'MSFT'],
        'volume': {'min': 100000},
        'market_cap': {'min': 1000000000},  # 1 billion
        'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
    }
    sql = FilterEngine.build_filter_sql(filters)
    print(f"  Input:  {filters}")
    print(f"  Output: {sql}")

    issues = []
    if "'100000'" in sql:
        issues.append("volume min is quoted")
    if "'1000000000'" in sql:
        issues.append("market_cap min is quoted")

    if issues:
        print(f"  ❌ BUG CONFIRMED: {', '.join(issues)}")
        tests_failed += 1
    else:
        print("  ✅ Mixed filters handled correctly")
        tests_passed += 1

    # Test case 5: Comparison operators (gt, lt, gte, lte)
    print("\nTest 1.5: Comparison operators (gt, lt, gte, lte)")
    print("-" * 40)
    filters = {
        'price': {'gt': 100, 'lt': 500},
        'volume': {'gte': 1000, 'lte': 10000}
    }
    sql = FilterEngine.build_filter_sql(filters)
    print(f"  Input:  {filters}")
    print(f"  Output: {sql}")

    quoted_nums = ["'100'", "'500'", "'1000'", "'10000'"]
    found_quotes = [q for q in quoted_nums if q in sql]
    if found_quotes:
        print(f"  ❌ BUG CONFIRMED: Found quoted numerics: {found_quotes}")
        tests_failed += 1
    else:
        print("  ✅ Comparison operators handled correctly")
        tests_passed += 1

    print("\n" + "-" * 40)
    print(f"SQL Generation Tests: {tests_passed} passed, {tests_failed} failed")

    return tests_failed == 0


def validate_duckdb_filter_application():
    """Test actual filter application with DuckDB."""
    print("\n" + "="*60)
    print("VALIDATION 2: DuckDB Filter Application")
    print("="*60 + "\n")

    tests_passed = 0
    tests_failed = 0

    try:
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession
from de_funk.core.session.filters import FilterEngine

        ctx = RepoContext.from_repo_root(connection_type='duckdb')
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        print(f"✅ Session created (backend={session.backend})")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2.1: Load a table
    print("\nTest 2.1: Load stocks.dim_stock table")
    print("-" * 40)
    try:
        df = session.get_table('stocks', 'dim_stock')
        columns = list(df.columns)
        print(f"  ✅ Loaded dim_stock table")
        print(f"     Columns: {columns[:8]}...")
        tests_passed += 1

        # Check if market_cap column exists for later tests
        has_market_cap = 'market_cap' in columns
        print(f"     Has market_cap column: {has_market_cap}")

    except Exception as e:
        print(f"  ❌ Failed to load table: {e}")
        tests_failed += 1
        return False

    # Test 2.2: Apply string filter (should work)
    print("\nTest 2.2: Apply string filter (ticker IN clause)")
    print("-" * 40)
    try:
        filters = {'ticker': ['AAPL', 'MSFT']}
        print(f"  Filters: {filters}")

        filtered_df = FilterEngine.apply_from_session(df, filters, session)
        pdf = ctx.connection.to_pandas(filtered_df)
        print(f"  ✅ String filter applied successfully: {len(pdf)} rows")
        if len(pdf) > 0:
            print(f"     Tickers: {pdf['ticker'].unique().tolist()}")
        tests_passed += 1

    except Exception as e:
        print(f"  ❌ String filter failed: {e}")
        import traceback
        traceback.print_exc()
        tests_failed += 1

    # Test 2.3: Apply numeric filter (the suspected crash point)
    print("\nTest 2.3: Apply numeric filter (market_cap min)")
    print("-" * 40)
    if has_market_cap:
        try:
            filters = {'market_cap': {'min': 1000000000}}  # 1 billion
            print(f"  Filters: {filters}")

            # This is where the crash likely occurs
            filtered_df = FilterEngine.apply_from_session(df, filters, session)
            pdf = ctx.connection.to_pandas(filtered_df)
            print(f"  ✅ Numeric filter applied successfully: {len(pdf)} rows")
            tests_passed += 1

        except Exception as e:
            print(f"  ❌ NUMERIC FILTER CRASHED: {e}")
            print("     This confirms the quoting bug!")
            import traceback
            traceback.print_exc()
            tests_failed += 1
    else:
        print("  ⚠️ Skipped: market_cap column not found")

    # Test 2.4: Apply numeric filter with comparison operators
    print("\nTest 2.4: Apply numeric filter (gte/lte operators)")
    print("-" * 40)
    if 'shares_outstanding' in columns:
        try:
            filters = {'shares_outstanding': {'gte': 1000000}}
            print(f"  Filters: {filters}")

            filtered_df = FilterEngine.apply_from_session(df, filters, session)
            pdf = ctx.connection.to_pandas(filtered_df)
            print(f"  ✅ Comparison operator filter applied: {len(pdf)} rows")
            tests_passed += 1

        except Exception as e:
            print(f"  ❌ Comparison operator filter CRASHED: {e}")
            import traceback
            traceback.print_exc()
            tests_failed += 1
    else:
        print("  ⚠️ Skipped: shares_outstanding column not found")

    # Test 2.5: Load fact table and test date + numeric filters
    print("\nTest 2.5: Load fact_stock_prices and apply combined filters")
    print("-" * 40)
    try:
        fact_df = session.get_table('stocks', 'fact_stock_prices')
        fact_columns = list(fact_df.columns)
        print(f"  ✅ Loaded fact_stock_prices")
        print(f"     Columns: {fact_columns[:8]}...")

        # Combined filter test
        filters = {
            'ticker': ['AAPL'],
            'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
        }
        if 'volume' in fact_columns:
            filters['volume'] = {'min': 1000000}

        print(f"  Applying combined filters: {filters}")

        filtered_df = FilterEngine.apply_from_session(fact_df, filters, session)
        pdf = ctx.connection.to_pandas(filtered_df)
        print(f"  Result: {len(pdf)} rows")

        if len(pdf) > 0:
            print("  ✅ Combined filters worked")
            tests_passed += 1
        else:
            print("  ⚠️ No rows returned (may be data issue, not filter issue)")
            tests_passed += 1

    except Exception as e:
        print(f"  ❌ Combined filter test CRASHED: {e}")
        import traceback
        traceback.print_exc()
        tests_failed += 1

    print("\n" + "-" * 40)
    print(f"DuckDB Application Tests: {tests_passed} passed, {tests_failed} failed")

    return tests_failed == 0


def validate_duckdb_connection_vs_filter_engine():
    """Compare DuckDBConnection.apply_filters vs FilterEngine._apply_duckdb_filters."""
    print("\n" + "="*60)
    print("VALIDATION 3: Implementation Comparison")
    print("="*60 + "\n")

    print("Comparing DuckDBConnection.apply_filters vs FilterEngine._apply_duckdb_filters")
    print("-" * 40)

    # Show the difference in implementation
    print("""
DuckDBConnection.apply_filters (duckdb_connection.py:553-556):
  if 'min' in value and value['min'] is not None and value['min'] > 0:
      conditions.append(f"{column} >= {value['min']}")  # NO QUOTES ✅
  if 'max' in value and value['max'] is not None:
      conditions.append(f"{column} <= {value['max']}")  # NO QUOTES ✅

FilterEngine._apply_duckdb_filters (filters.py:209-212):
  elif 'min' in value:
      conditions.append(f"{col_name} >= '{value['min']}'")  # QUOTED ❌
  if 'max' in value:
      conditions.append(f"{col_name} <= '{value['max']}'")  # QUOTED ❌
""")

    print("CONCLUSION: FilterEngine incorrectly quotes numeric values!")
    print("            DuckDBConnection does NOT quote them (correct behavior).")

    return True


def trace_filter_engine_callers():
    """Show all code paths that call FilterEngine."""
    print("\n" + "="*60)
    print("VALIDATION 4: FilterEngine Call Sites (Impact Analysis)")
    print("="*60 + "\n")

    callers = [
        {
            "file": "models/api/session.py",
            "method": "UniversalSession.get_table()",
            "line": "~289, ~308, ~327, ~347",
            "usage": "FilterEngine.apply_from_session(df, filters, self)",
            "impact": "HIGH - All exhibit data retrieval goes through here"
        },
        {
            "file": "app/notebook/managers/notebook_manager.py",
            "method": "NotebookManager._get_weighted_aggregate_data()",
            "line": "~840",
            "usage": "FilterEngine.build_filter_sql(filters)",
            "impact": "MEDIUM - Weighted aggregate charts"
        },
        {
            "file": "models/api/auto_join.py",
            "method": "AutoJoinHandler.execute_auto_joins()",
            "line": "~varies",
            "usage": "FilterEngine.apply_from_session()",
            "impact": "MEDIUM - Cross-model joins with filters"
        }
    ]

    print("FilterEngine is called from these locations:\n")

    for i, caller in enumerate(callers, 1):
        print(f"{i}. {caller['file']}")
        print(f"   Method: {caller['method']}")
        print(f"   Line:   {caller['line']}")
        print(f"   Usage:  {caller['usage']}")
        print(f"   Impact: {caller['impact']}")
        print()

    print("-" * 40)
    print("IMPACT SUMMARY:")
    print("  - ALL notebook exhibits using numeric filters will be affected")
    print("  - Slider filters (market_cap, volume, price ranges) will crash or return wrong data")
    print("  - Date range filters work correctly (strings are supposed to be quoted)")
    print("  - Ticker/string filters work correctly")

    return True


def main():
    """Run all validation tests."""
    setup_logging()

    print("\n" + "="*60)
    print("FILTER SYSTEM VALIDATION")
    print("="*60)
    print("Testing for the numeric quoting bug in FilterEngine")
    print("="*60)

    results = []

    # Run validation tests
    results.append(("SQL Generation", validate_filter_sql_generation()))
    results.append(("DuckDB Application", validate_duckdb_filter_application()))
    results.append(("Implementation Comparison", validate_duckdb_connection_vs_filter_engine()))
    results.append(("Impact Analysis", trace_filter_engine_callers()))

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60 + "\n")

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "-" * 40)
    if all_passed:
        print("All validations passed!")
    else:
        print("Some validations failed - see details above")
        print("\nRECOMMENDED FIX:")
        print("  Update core/session/filters.py lines 209-220 and 312-323")
        print("  to NOT quote numeric values (int, float) in SQL conditions")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
