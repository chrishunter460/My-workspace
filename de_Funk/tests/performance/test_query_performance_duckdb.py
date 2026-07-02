#!/usr/bin/env python3
"""
Test dimension selector query performance with DuckDB.

This script directly queries the silver storage with DuckDB to measure
performance and identify bottlenecks without Streamlit overhead.

Tests:
1. Base query (fact_prices)
2. Join to company
3. Join to exchange
4. Aggregation by ticker
5. Aggregation by exchange

Usage:
    python scripts/test_query_performance_duckdb.py
"""

import duckdb
import time
from pathlib import Path


def format_rows(count: int) -> str:
    """Format row count for display."""
    if count >= 1_000_000:
        return f"{count:,} ({count/1_000_000:.2f}M)"
    elif count >= 1_000:
        return f"{count:,} ({count/1_000:.1f}K)"
    else:
        return f"{count:,}"


def time_query(conn, name: str, sql: str):
    """Time a query and return result."""
    print(f"\n{'='*80}")
    print(f"⏱️  {name}")
    print(f"{'='*80}")
    print(f"\nSQL:\n{sql}\n")

    start = time.time()
    result = conn.execute(sql).fetchdf()
    elapsed = time.time() - start

    count = len(result)
    print(f"✓ Rows: {format_rows(count)}")
    print(f"⏱️  Time: {elapsed:.3f}s")

    # Show sample
    print(f"\nSample (first 5 rows):")
    print(result.head(5))

    return result, elapsed, count


def main():
    print("="*80)
    print("DIMENSION SELECTOR QUERY PERFORMANCE TEST (DuckDB)")
    print("="*80)
    print()

    # Find storage directory
    repo_root = get_repo_root()
    storage_path = repo_root / "storage" / "silver" / "company"

    if not storage_path.exists():
        print(f"❌ Storage not found at: {storage_path}")
        print("\nPlease run data refresh first:")
        print("  python scripts/clear_and_refresh.py")
        return

    print(f"Storage path: {storage_path}")
    print()

    # Create DuckDB connection
    conn = duckdb.connect(":memory:")

    # Register parquet files as views
    print("Registering parquet files as DuckDB views...")

    fact_prices_path = storage_path / "fact_prices"
    dim_company_path = storage_path / "dim_company"
    dim_exchange_path = storage_path / "dim_exchange"

    if not fact_prices_path.exists():
        print(f"❌ fact_prices not found at: {fact_prices_path}")
        return

    # Register tables
    conn.execute(f"""
        CREATE VIEW fact_prices AS
        SELECT * FROM read_parquet('{fact_prices_path}/**/*.parquet')
    """)

    if dim_company_path.exists():
        conn.execute(f"""
            CREATE VIEW dim_company AS
            SELECT * FROM read_parquet('{dim_company_path}/**/*.parquet')
        """)

    if dim_exchange_path.exists():
        conn.execute(f"""
            CREATE VIEW dim_exchange AS
            SELECT * FROM read_parquet('{dim_exchange_path}/**/*.parquet')
        """)

    print("✓ Tables registered\n")

    # Show table schemas
    print("="*80)
    print("TABLE SCHEMAS")
    print("="*80)

    for table in ['fact_prices', 'dim_company', 'dim_exchange']:
        try:
            print(f"\n{table}:")
            schema = conn.execute(f"DESCRIBE {table}").fetchdf()
            print(schema.to_string(index=False))
        except Exception as e:
            print(f"  (not available: {e})")

    # Store results
    results = {}

    # TEST 1: Base query
    sql = """
        SELECT
            ticker,
            trade_date,
            close,
            volume
        FROM fact_prices
        ORDER BY trade_date, ticker
    """
    results['base'] = time_query(conn, "TEST 1: Base Query (fact_prices)", sql)

    # TEST 2: Join to company
    sql = """
        SELECT
            f.ticker,
            f.trade_date,
            f.close,
            f.volume,
            c.company_name,
            c.exchange_code
        FROM fact_prices f
        LEFT JOIN dim_company c ON f.ticker = c.ticker
        ORDER BY f.trade_date, f.ticker
    """
    results['company_join'] = time_query(conn, "TEST 2: Join to dim_company", sql)

    # TEST 3: Join to exchange (through company)
    sql = """
        SELECT
            f.ticker,
            f.trade_date,
            f.close,
            f.volume,
            c.company_name,
            e.exchange_name
        FROM fact_prices f
        LEFT JOIN dim_company c ON f.ticker = c.ticker
        LEFT JOIN dim_exchange e ON c.exchange_code = e.exchange_code
        ORDER BY f.trade_date, f.ticker
    """
    results['exchange_join'] = time_query(conn, "TEST 3: Join to dim_exchange", sql)

    # TEST 4: Aggregation by ticker
    sql = """
        SELECT
            trade_date,
            ticker,
            AVG(close) as close,
            SUM(volume) as volume
        FROM fact_prices
        GROUP BY trade_date, ticker
        ORDER BY trade_date, ticker
    """
    results['ticker_agg'] = time_query(conn, "TEST 4: Aggregate by ticker", sql)

    # TEST 5: Aggregation by exchange (with join)
    sql = """
        SELECT
            f.trade_date,
            e.exchange_name,
            AVG(f.close) as avg_close,
            SUM(f.volume) as total_volume,
            COUNT(DISTINCT f.ticker) as ticker_count
        FROM fact_prices f
        LEFT JOIN dim_company c ON f.ticker = c.ticker
        LEFT JOIN dim_exchange e ON c.exchange_code = e.exchange_code
        GROUP BY f.trade_date, e.exchange_name
        ORDER BY f.trade_date, e.exchange_name
    """
    results['exchange_agg'] = time_query(conn, "TEST 5: Aggregate by exchange", sql)

    # TEST 6: Aggregation by exchange WITH FILTERS
    sql = """
        SELECT
            f.trade_date,
            e.exchange_name,
            AVG(f.close) as avg_close,
            SUM(f.volume) as total_volume,
            COUNT(DISTINCT f.ticker) as ticker_count
        FROM fact_prices f
        LEFT JOIN dim_company c ON f.ticker = c.ticker
        LEFT JOIN dim_exchange e ON c.exchange_code = e.exchange_code
        WHERE f.trade_date BETWEEN '2024-01-01' AND '2024-01-05'
          AND f.ticker IN ('AAPL', 'GOOGL', 'MSFT')
        GROUP BY f.trade_date, e.exchange_name
        ORDER BY f.trade_date, e.exchange_name
    """
    results['exchange_filtered'] = time_query(conn, "TEST 6: Aggregate by exchange WITH FILTERS", sql)

    # TEST 7: Check for duplicates in dimension tables
    print(f"\n{'='*80}")
    print("TEST 7: Dimension Table Duplicate Check")
    print(f"{'='*80}")

    # Check dim_company
    sql = """
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT ticker) as distinct_tickers,
            COUNT(*) - COUNT(DISTINCT ticker) as duplicates
        FROM dim_company
    """
    result = conn.execute(sql).fetchdf()
    print(f"\ndim_company:")
    print(result.to_string(index=False))

    total = result['total_rows'].iloc[0]
    distinct = result['distinct_tickers'].iloc[0]
    dupes = result['duplicates'].iloc[0]

    if dupes > 0:
        print(f"\n⚠️  WARNING: {dupes} duplicate ticker rows found!")
        # Show duplicates
        sql = """
            SELECT ticker, COUNT(*) as count
            FROM dim_company
            GROUP BY ticker
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10
        """
        dupes_df = conn.execute(sql).fetchdf()
        print(f"\nTop duplicate tickers:")
        print(dupes_df.to_string(index=False))
    else:
        print(f"✓ No duplicates")

    # Check dim_exchange
    sql = """
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT exchange_code) as distinct_codes,
            COUNT(*) - COUNT(DISTINCT exchange_code) as duplicates
        FROM dim_exchange
    """
    result = conn.execute(sql).fetchdf()
    print(f"\ndim_exchange:")
    print(result.to_string(index=False))

    total = result['total_rows'].iloc[0]
    distinct = result['distinct_codes'].iloc[0]
    dupes = result['duplicates'].iloc[0]

    if dupes > 0:
        print(f"\n⚠️  WARNING: {dupes} duplicate exchange_code rows found!")
    else:
        print(f"✓ No duplicates")

    # TEST 8: Row explosion analysis
    print(f"\n{'='*80}")
    print("TEST 8: Row Explosion Analysis")
    print(f"{'='*80}")

    base_count = results['base'][2]
    company_count = results['company_join'][2]
    exchange_count = results['exchange_join'][2]

    print(f"\nRow counts:")
    print(f"  Base fact_prices:     {format_rows(base_count)}")
    print(f"  After company join:   {format_rows(company_count)} ({(company_count/base_count - 1)*100:+.1f}%)")
    print(f"  After exchange join:  {format_rows(exchange_count)} ({(exchange_count/base_count - 1)*100:+.1f}%)")

    if exchange_count > base_count:
        explosion = exchange_count - base_count
        pct = (explosion / base_count) * 100
        print(f"\n⚠️  Join explosion: +{format_rows(explosion)} rows (+{pct:.1f}%)")
    else:
        print(f"\n✓ No row explosion")

    # Summary
    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    print()
    print(f"{'Test':<45} {'Time':>10} {'Rows':>20}")
    print("-"*80)

    for name, (df, elapsed, count) in results.items():
        print(f"{name:<45} {elapsed:>7.3f}s {format_rows(count):>20}")

    # Key findings
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    print()

    # Check if exchange aggregation is slow
    exchange_time = results['exchange_agg'][1]
    if exchange_time > 1.0:
        print(f"⚠️  Exchange aggregation is SLOW: {exchange_time:.3f}s")
        print("   This should be instant with proper indexing and no duplicates")
    else:
        print(f"✓ Exchange aggregation is fast: {exchange_time:.3f}s")

    # Check filter impact
    filtered_time = results['exchange_filtered'][1]
    unfiltered_time = results['exchange_agg'][1]
    if filtered_time >= unfiltered_time * 0.8:
        print(f"\n⚠️  Filters NOT being pushed down efficiently")
        print(f"   Filtered: {filtered_time:.3f}s vs Unfiltered: {unfiltered_time:.3f}s")
        print("   With filter pushdown, filtered should be much faster")
    else:
        print(f"\n✓ Filters appear to be pushed down: {filtered_time:.3f}s vs {unfiltered_time:.3f}s")

    # Check row explosion
    if exchange_count > base_count * 1.01:  # More than 1% increase
        print(f"\n⚠️  Row explosion detected: {(exchange_count/base_count - 1)*100:.1f}%")
        print("   Check dimension tables for duplicates (see TEST 7 above)")
    else:
        print(f"\n✓ No significant row explosion")

    print()


if __name__ == "__main__":
    main()
