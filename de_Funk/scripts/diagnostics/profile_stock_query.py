#!/usr/bin/env python
"""
Profile stock price query performance.

This script measures actual query times to identify where slowness occurs.

Usage:
    python -m scripts.diagnostics.profile_stock_query
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def format_time(seconds: float) -> str:
    """Format time in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def main():
    print("=" * 70)
    print("STOCK QUERY PERFORMANCE PROFILER")
    print("=" * 70)
    print()

    timings = {}

    # 1. Import timing
    print("1. Import & Setup Times")
    print("-" * 40)

    start = time.perf_counter()
from de_funk.core.context import RepoContext
    timings['import_context'] = time.perf_counter() - start
    print(f"   Import RepoContext: {format_time(timings['import_context'])}")

    start = time.perf_counter()
from de_funk.models.registry import ModelRegistry
    timings['import_registry'] = time.perf_counter() - start
    print(f"   Import ModelRegistry: {format_time(timings['import_registry'])}")

    # 2. Context initialization
    print()
    print("2. Initialization Times")
    print("-" * 40)

    start = time.perf_counter()
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    timings['init_context'] = time.perf_counter() - start
    print(f"   RepoContext init: {format_time(timings['init_context'])}")

    start = time.perf_counter()
    registry = ModelRegistry(ctx.repo / "configs" / "models")
    timings['init_registry'] = time.perf_counter() - start
    print(f"   ModelRegistry init: {format_time(timings['init_registry'])}")

    # 3. First query (cold)
    print()
    print("3. Query Times (Silver Layer)")
    print("-" * 40)

    # Get stocks model
    start = time.perf_counter()
    model = registry.get_model("securities.stocks")
    timings['get_model'] = time.perf_counter() - start
    print(f"   Get model 'securities.stocks': {format_time(timings['get_model'])}")

    # Get table path
    start = time.perf_counter()
    table_path = model.get_table_path("fact_stock_prices")
    timings['get_path'] = time.perf_counter() - start
    print(f"   Get table path: {format_time(timings['get_path'])}")
    print(f"   Path: {table_path}")

    # Read table (first query - includes metadata scan)
    start = time.perf_counter()
    df = ctx.connection.read_table(table_path)
    timings['read_cold'] = time.perf_counter() - start
    print(f"   Read table (cold): {format_time(timings['read_cold'])}")

    # Count rows
    start = time.perf_counter()
    row_count = df.count('*').fetchone()[0]
    timings['count'] = time.perf_counter() - start
    print(f"   Count rows: {format_time(timings['count'])} ({row_count:,} rows)")

    # Read with filter (typical UI query)
    start = time.perf_counter()
    filtered = df.filter("trade_date >= '2024-01-01' AND trade_date <= '2024-12-31'")
    result = filtered.df()
    timings['filtered_query'] = time.perf_counter() - start
    print(f"   Filtered query (2024): {format_time(timings['filtered_query'])} ({len(result):,} rows)")

    # Read with ticker filter
    start = time.perf_counter()
    ticker_filtered = df.filter("ticker IN ('AAPL', 'MSFT', 'GOOGL')")
    result2 = ticker_filtered.df()
    timings['ticker_query'] = time.perf_counter() - start
    print(f"   Ticker filter (3 tickers): {format_time(timings['ticker_query'])} ({len(result2):,} rows)")

    # Combined filter
    start = time.perf_counter()
    combined = df.filter("trade_date >= '2024-01-01' AND ticker IN ('AAPL', 'MSFT', 'GOOGL')")
    result3 = combined.df()
    timings['combined_query'] = time.perf_counter() - start
    print(f"   Combined filter: {format_time(timings['combined_query'])} ({len(result3):,} rows)")

    # 4. Second read (warm - tests caching)
    print()
    print("4. Second Query (Warm)")
    print("-" * 40)

    start = time.perf_counter()
    df2 = ctx.connection.read_table(table_path)
    timings['read_warm'] = time.perf_counter() - start
    print(f"   Read table (warm): {format_time(timings['read_warm'])}")

    # 5. Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_init = timings['init_context'] + timings['init_registry']
    total_first_query = timings['read_cold'] + timings['count']

    print(f"\n  Initialization: {format_time(total_init)}")
    print(f"  First query (cold): {format_time(total_first_query)}")
    print(f"  Filtered query: {format_time(timings['filtered_query'])}")

    # Identify bottlenecks
    print("\n  Bottleneck Analysis:")
    if timings['init_context'] > 2:
        print(f"    ⚠️  Context init slow ({format_time(timings['init_context'])}) - check DuckDB view setup")
    if timings['read_cold'] > 5:
        print(f"    ⚠️  Cold read slow ({format_time(timings['read_cold'])}) - large file or many files")
    if timings['count'] > 2:
        print(f"    ⚠️  Count query slow ({format_time(timings['count'])}) - full table scan needed")
    if timings['filtered_query'] > 1:
        print(f"    ⚠️  Filtered query slow ({format_time(timings['filtered_query'])}) - filter not pushing down")

    # Recommendations
    print("\n  Recommendations:")
    if timings['filtered_query'] < timings['count'] / 2:
        print("    ✅ Filters are working - always use date/ticker filters in UI")
    else:
        print("    ⚠️  Filters may not be pushing down efficiently")

    if total_init > 3:
        print("    Consider: Disable auto-init views or pre-initialize DuckDB")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
