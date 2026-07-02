#!/usr/bin/env python3
"""
Test dimension selector performance outside of Streamlit.

This script replicates the query flow from NotebookManager.get_exhibit_data()
to measure performance and identify bottlenecks.

Tests:
1. Base query (fact_prices without joins)
2. Auto-join query (with exchange_name)
3. Aggregation by ticker
4. Aggregation by exchange
5. With and without filters

Usage:
    python -m scripts.test_dimension_selector_performance
"""

import sys
from pathlib import Path

import time
from typing import Dict, Any

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


def format_rows(count: int) -> str:
    """Format row count for display."""
    if count >= 1_000_000:
        return f"{count:,} ({count/1_000_000:.2f}M)"
    elif count >= 1_000:
        return f"{count:,} ({count/1_000:.1f}K)"
    else:
        return f"{count:,}"


def time_operation(name: str, func):
    """Time an operation and return result with timing."""
    print(f"\n{'='*80}")
    print(f"⏱️  {name}")
    print(f"{'='*80}")

    start = time.time()
    result = func()
    elapsed = time.time() - start

    # Get row count
    if result is not None:
        try:
            count = result.count()
            print(f"✓ Rows: {format_rows(count)}")
        except:
            print(f"✓ Result: {type(result)}")

    print(f"⏱️  Time: {elapsed:.3f}s")

    return result, elapsed


def test_base_query(session: UniversalSession):
    """Test 1: Base query without any joins."""
    print("\n" + "="*80)
    print("TEST 1: Base Query (fact_prices, no joins)")
    print("="*80)

    def query():
        return session.get_table(
            "company",
            "fact_prices",
            required_columns=["ticker", "trade_date", "close", "volume"]
        )

    df, elapsed = time_operation("Load fact_prices (ticker level)", query)

    # Show sample
    print("\nSample rows:")
    if session.backend == 'spark':
        df.show(5)
    else:
        print(df.limit(5).df())

    return df, elapsed


def test_autojoin_query(session: UniversalSession):
    """Test 2: Auto-join query to get exchange_name."""
    print("\n" + "="*80)
    print("TEST 2: Auto-Join Query (add exchange_name)")
    print("="*80)

    def query():
        return session.get_table(
            "company",
            "fact_prices",
            required_columns=["ticker", "trade_date", "close", "volume", "exchange_name"]
        )

    df, elapsed = time_operation("Load with auto-join to exchange_name", query)

    # Show sample
    print("\nSample rows:")
    if session.backend == 'spark':
        df.show(5)
    else:
        print(df.limit(5).df())

    return df, elapsed


def test_ticker_aggregation(session: UniversalSession):
    """Test 3: Aggregation by ticker (base grain)."""
    print("\n" + "="*80)
    print("TEST 3: Aggregation by Ticker (Base Grain)")
    print("="*80)

    def query():
        return session.get_table(
            "company",
            "fact_prices",
            required_columns=["ticker", "trade_date", "close", "volume"],
            group_by=["trade_date", "ticker"],
            aggregations={"close": "avg", "volume": "sum"}
        )

    df, elapsed = time_operation("Aggregate by trade_date + ticker", query)

    # Show sample
    print("\nSample rows:")
    if session.backend == 'spark':
        df.show(5)
    else:
        print(df.limit(5).df())

    return df, elapsed


def test_exchange_aggregation(session: UniversalSession):
    """Test 4: Aggregation by exchange (higher grain - requires auto-join)."""
    print("\n" + "="*80)
    print("TEST 4: Aggregation by Exchange (Higher Grain + Auto-Join)")
    print("="*80)

    def query():
        return session.get_table(
            "company",
            "fact_prices",
            required_columns=["trade_date", "exchange_name", "close", "volume"],
            group_by=["trade_date", "exchange_name"],
            aggregations={"close": "avg", "volume": "sum"}
        )

    df, elapsed = time_operation("Aggregate by trade_date + exchange_name", query)

    # Show sample
    print("\nSample rows:")
    if session.backend == 'spark':
        df.show(5)
    else:
        print(df.limit(5).df())

    # Show unique exchanges
    print("\nUnique exchanges:")
    if session.backend == 'spark':
        df.select("exchange_name").distinct().show()
    else:
        print(df.select("exchange_name").distinct().df())

    return df, elapsed


def test_exchange_aggregation_with_filters(session: UniversalSession):
    """Test 5: Exchange aggregation with filters (simulating notebook behavior)."""
    print("\n" + "="*80)
    print("TEST 5: Exchange Aggregation WITH Filters")
    print("="*80)

    # Filters from dimension_selector_demo.md
    filters = {
        "trade_date": {"start": "2024-01-01", "end": "2024-01-05"},
        "ticker": ["AAPL", "GOOGL", "MSFT"]
    }

    print(f"Filters: {filters}")

    def query():
        return session.get_table(
            "company",
            "fact_prices",
            required_columns=["trade_date", "exchange_name", "close", "volume"],
            filters=filters,
            group_by=["trade_date", "exchange_name"],
            aggregations={"close": "avg", "volume": "sum"}
        )

    df, elapsed = time_operation("Aggregate by exchange WITH filters", query)

    # Show sample
    print("\nSample rows:")
    if session.backend == 'spark':
        df.show(10)
    else:
        print(df.df())

    return df, elapsed


def test_row_explosion(session: UniversalSession):
    """Test 6: Investigate row explosion from joins."""
    print("\n" + "="*80)
    print("TEST 6: Row Explosion Investigation")
    print("="*80)

    # Count base fact_prices rows
    def count_base():
        df = session.get_table("company", "fact_prices", required_columns=["ticker"])
        return df.count()

    base_count, _ = time_operation("Count base fact_prices", count_base)

    # Count after join to dim_company
    def count_after_company_join():
        df = session.get_table("company", "fact_prices", required_columns=["ticker", "company_name"])
        return df.count()

    company_count, _ = time_operation("Count after company join", count_after_company_join)

    # Count after join to exchange (via company)
    def count_after_exchange_join():
        df = session.get_table("company", "fact_prices", required_columns=["ticker", "exchange_name"])
        return df.count()

    exchange_count, _ = time_operation("Count after exchange join", count_after_exchange_join)

    # Analysis
    print(f"\n{'='*80}")
    print("ROW EXPLOSION ANALYSIS")
    print(f"{'='*80}")
    print(f"Base fact_prices:           {format_rows(base_count)}")
    print(f"After company join:         {format_rows(company_count)} ({(company_count/base_count - 1)*100:+.1f}%)")
    print(f"After exchange join:        {format_rows(exchange_count)} ({(exchange_count/base_count - 1)*100:+.1f}%)")

    # Check for duplicates in dimension tables
    print(f"\n{'='*80}")
    print("DIMENSION TABLE ANALYSIS")
    print(f"{'='*80}")

    # Check dim_company for duplicates
    def check_company_dupes():
        df = session.get_table("company", "dim_company", required_columns=["ticker", "company_name"])
        total = df.count()
        distinct = df.select("ticker").distinct().count()
        return total, distinct

    company_total, company_distinct = check_company_dupes()
    print(f"\ndim_company:")
    print(f"  Total rows:     {format_rows(company_total)}")
    print(f"  Distinct tickers: {format_rows(company_distinct)}")
    if company_total > company_distinct:
        print(f"  ⚠️  DUPLICATES FOUND: {company_total - company_distinct} duplicate ticker rows!")
    else:
        print(f"  ✓ No duplicates")

    # Check dim_exchange for duplicates
    def check_exchange_dupes():
        df = session.get_table("company", "dim_exchange", required_columns=["exchange_code", "exchange_name"])
        total = df.count()
        distinct = df.select("exchange_code").distinct().count()
        return total, distinct

    exchange_total, exchange_distinct = check_exchange_dupes()
    print(f"\ndim_exchange:")
    print(f"  Total rows:       {format_rows(exchange_total)}")
    print(f"  Distinct codes:   {format_rows(exchange_distinct)}")
    if exchange_total > exchange_distinct:
        print(f"  ⚠️  DUPLICATES FOUND: {exchange_total - exchange_distinct} duplicate exchange_code rows!")
    else:
        print(f"  ✓ No duplicates")


def main():
    print("="*80)
    print("DIMENSION SELECTOR PERFORMANCE TEST")
    print("="*80)
    print()
    print("This script tests the query execution flow to identify performance bottlenecks.")
    print()

    # Initialize context
    print("Initializing context...")
    ctx = RepoContext.from_repo_root()

    # Create session
    print("Creating UniversalSession...")
    session = UniversalSession(ctx.spark, ctx.storage, ctx.repo)

    # Load company model
    print("Loading company model...")
    session.load_model("company")

    print("\n✓ Setup complete")

    # Run tests
    results = {}

    try:
        # Test 1: Base query
        results['base'] = test_base_query(session)

        # Test 2: Auto-join
        results['autojoin'] = test_autojoin_query(session)

        # Test 3: Ticker aggregation
        results['ticker_agg'] = test_ticker_aggregation(session)

        # Test 4: Exchange aggregation
        results['exchange_agg'] = test_exchange_aggregation(session)

        # Test 5: Exchange aggregation with filters
        results['exchange_filtered'] = test_exchange_aggregation_with_filters(session)

        # Test 6: Row explosion investigation
        test_row_explosion(session)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Summary
    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    print()
    print(f"{'Operation':<50} {'Time':<10} {'Rows':<15}")
    print("-"*80)

    for name, (df, elapsed) in results.items():
        try:
            count = df.count() if df is not None else 0
            print(f"{name:<50} {elapsed:>6.3f}s   {format_rows(count):>15}")
        except:
            print(f"{name:<50} {elapsed:>6.3f}s   {'N/A':>15}")

    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    print()
    print("1. Check 'Row Explosion Analysis' above to see if joins are creating duplicates")
    print("2. Compare 'exchange_agg' vs 'exchange_filtered' to see filter pushdown impact")
    print("3. If dimension tables have duplicates, that's the root cause of slowness")
    print("4. With proper deduplication, exchange aggregation should be instant")
    print()


if __name__ == "__main__":
    main()
