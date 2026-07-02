#!/usr/bin/env python
"""
Debug script for financial statements notebook.

Simulates loading exhibits using DuckDB delta_scan (same as the app).
Tests actual queries to identify performance bottlenecks.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import duckdb


def get_storage_root() -> Path:
    """Get storage root path."""
    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = Path(__file__).parent.parent.parent / "storage"
    return storage_root


def setup_duckdb() -> duckdb.DuckDBPyConnection:
    """Setup DuckDB with delta extension."""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL delta")
        conn.execute("LOAD delta")
        print("✓ Delta extension loaded")
    except Exception as e:
        print(f"✗ Could not load delta extension: {e}")
        sys.exit(1)
    return conn


def time_query(conn: duckdb.DuckDBPyConnection, name: str, query: str, show_sample: bool = False) -> tuple:
    """Execute query and return timing + row count.

    Uses DuckDB native methods - NO PANDAS (per CLAUDE.md guidelines).
    """
    print(f"\n  {name}...")
    start = time.time()
    try:
        result = conn.execute(query)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        elapsed = time.time() - start
        row_count = len(rows)
        print(f"    ✓ {row_count:,} rows in {elapsed:.2f}s")
        if show_sample and row_count > 0:
            print(f"    Sample columns: {columns[:8]}")
            if row_count <= 10:
                for row in rows:
                    print(f"    {row}")
        return elapsed, row_count, (columns, rows)
    except Exception as e:
        elapsed = time.time() - start
        print(f"    ✗ ERROR after {elapsed:.2f}s: {e}")
        return elapsed, 0, None


def check_bronze_layer(conn: duckdb.DuckDBPyConnection, storage_root: Path):
    """Check bronze tables using delta_scan."""
    print("\n" + "=" * 70)
    print("BRONZE LAYER (using delta_scan)")
    print("=" * 70)

    bronze_root = storage_root / "bronze"
    tables = [
        ("securities_reference", "Ticker reference data", False),
        ("company_income_statements", "Income statement data", False),
        ("company_balance_sheets", "Balance sheet data", False),
        ("company_cash_flows", "Cash flow data", False),
        ("company_earnings", "Earnings data", False),
        ("securities_prices_daily", "Stock prices (large table)", True),  # Count only
    ]

    results = {}
    for table_name, desc, count_only in tables:
        table_path = bronze_root / table_name
        if table_path.exists():
            if count_only:
                # For large tables, just count - don't load into memory
                query = f"SELECT COUNT(*) as cnt FROM delta_scan('{table_path}')"
                elapsed, _, result = time_query(conn, f"{table_name} ({desc}) - COUNT ONLY", query)
                if result is not None:
                    _, rows = result
                    count = rows[0][0]  # First row, first column
                    print(f"    Total rows: {count:,}")
                    results[table_name] = {"time": elapsed, "count": count}
                else:
                    results[table_name] = {"time": elapsed, "count": 0}
            else:
                query = f"SELECT * FROM delta_scan('{table_path}')"
                elapsed, count, _ = time_query(conn, f"{table_name} ({desc})", query)
                results[table_name] = {"time": elapsed, "count": count}
        else:
            print(f"\n  {table_name}: NOT FOUND at {table_path}")

    return results


def is_delta_table(path: Path) -> bool:
    """Check if path is a Delta table (has _delta_log directory)."""
    return (path / "_delta_log").exists()


def get_table_query(path: Path, select: str = "*") -> str:
    """Get appropriate query based on table format (Delta vs Parquet)."""
    if is_delta_table(path):
        return f"SELECT {select} FROM delta_scan('{path}')"
    else:
        # Plain Parquet - use glob pattern for partitioned tables
        return f"SELECT {select} FROM read_parquet('{path}/*.parquet', union_by_name=true)"


def check_silver_layer(conn: duckdb.DuckDBPyConnection, storage_root: Path):
    """Check silver layer tables (auto-detects Delta vs Parquet format)."""
    print("\n" + "=" * 70)
    print("SILVER LAYER (auto-detecting format)")
    print("=" * 70)

    silver_root = storage_root / "silver"

    # Check company model tables
    # (table_path, description, count_only)
    tables = [
        ("company/dims/dim_company", "Company dimension", False),
        ("company/facts/fact_income_statement", "Income statements", False),
        ("company/facts/fact_balance_sheet", "Balance sheets", False),
        ("company/facts/fact_cash_flow", "Cash flows", False),
        ("company/facts/fact_earnings", "Earnings", False),
        ("stocks/dims/dim_stock", "Stock dimension", False),
        ("stocks/facts/fact_stock_prices", "Stock prices (large)", True),  # Count only
    ]

    results = {}
    for table_path, desc, count_only in tables:
        full_path = silver_root / table_path
        if full_path.exists():
            fmt = "Delta" if is_delta_table(full_path) else "Parquet"
            if count_only:
                # For large tables, just count - don't load into memory
                query = get_table_query(full_path, "COUNT(*) as cnt")
                elapsed, _, result = time_query(conn, f"{table_path} ({desc}, {fmt}) - COUNT ONLY", query)
                if result is not None:
                    _, rows = result
                    count = rows[0][0]  # First row, first column
                    print(f"    Total rows: {count:,}")
                    results[table_path] = {"time": elapsed, "count": count}
                else:
                    results[table_path] = {"time": elapsed, "count": 0}
            else:
                query = get_table_query(full_path)
                elapsed, count, _ = time_query(conn, f"{table_path} ({desc}, {fmt})", query)
                results[table_path] = {"time": elapsed, "count": count}
        else:
            print(f"\n  {table_path}: NOT FOUND")
            results[table_path] = {"time": 0, "count": 0}

    return results


def get_table_source(path: Path) -> str:
    """Get the FROM clause for a table (Delta or Parquet)."""
    if is_delta_table(path):
        return f"delta_scan('{path}')"
    else:
        return f"read_parquet('{path}/*.parquet', union_by_name=true)"


def simulate_notebook_filter(conn: duckdb.DuckDBPyConnection, storage_root: Path, ticker: str = "AAPL"):
    """Simulate notebook filter for a specific ticker (what the app actually does)."""
    print("\n" + "=" * 70)
    print(f"NOTEBOOK SIMULATION (ticker={ticker}, report_type=annual)")
    print("=" * 70)

    silver_root = storage_root / "silver"

    # 1. Filter source for ticker dropdown (dim_company)
    dim_company_path = silver_root / "company/dims/dim_company"
    if dim_company_path.exists():
        source = get_table_source(dim_company_path)
        query = f"""
            SELECT DISTINCT ticker
            FROM {source}
            ORDER BY ticker
        """
        elapsed, count, _ = time_query(conn, "Filter dropdown: Get all tickers from dim_company", query)

    # 2. Simulate each exhibit query with filter applied

    # Income Statement exhibit
    income_path = silver_root / "company/facts/fact_income_statement"
    if income_path.exists():
        source = get_table_source(income_path)
        query = f"""
            SELECT
                fiscal_date_ending,
                total_revenue,
                gross_profit,
                operating_income,
                net_income,
                report_type
            FROM {source}
            WHERE ticker = '{ticker}'
              AND report_type = 'annual'
            ORDER BY fiscal_date_ending DESC
        """
        elapsed, count, _ = time_query(conn, "Income Statement exhibit", query, show_sample=True)

    # Balance Sheet exhibit
    balance_path = silver_root / "company/facts/fact_balance_sheet"
    if balance_path.exists():
        source = get_table_source(balance_path)
        query = f"""
            SELECT
                fiscal_date_ending,
                total_assets,
                total_liabilities,
                total_shareholder_equity,
                report_type
            FROM {source}
            WHERE ticker = '{ticker}'
              AND report_type = 'annual'
            ORDER BY fiscal_date_ending DESC
        """
        elapsed, count, _ = time_query(conn, "Balance Sheet exhibit", query, show_sample=True)

    # Cash Flow exhibit
    cashflow_path = silver_root / "company/facts/fact_cash_flow"
    if cashflow_path.exists():
        source = get_table_source(cashflow_path)
        query = f"""
            SELECT
                fiscal_date_ending,
                operating_cashflow,
                cashflow_from_investment,
                cashflow_from_financing,
                free_cash_flow,
                report_type
            FROM {source}
            WHERE ticker = '{ticker}'
              AND report_type = 'annual'
            ORDER BY fiscal_date_ending DESC
        """
        elapsed, count, _ = time_query(conn, "Cash Flow exhibit", query, show_sample=True)

    # Earnings exhibit
    earnings_path = silver_root / "company/facts/fact_earnings"
    if earnings_path.exists():
        source = get_table_source(earnings_path)
        query = f"""
            SELECT
                fiscal_date_ending,
                reported_eps,
                estimated_eps,
                surprise_percentage,
                report_type
            FROM {source}
            WHERE ticker = '{ticker}'
              AND report_type = 'annual'
            ORDER BY fiscal_date_ending DESC
        """
        elapsed, count, _ = time_query(conn, "Earnings exhibit", query, show_sample=True)

    # Stock Prices exhibit (with LIMIT since notebook has limit: 1000)
    prices_path = silver_root / "stocks/facts/fact_stock_prices"
    if prices_path.exists():
        source = get_table_source(prices_path)
        query = f"""
            SELECT
                trade_date,
                open,
                high,
                low,
                close,
                volume
            FROM {source}
            WHERE ticker = '{ticker}'
            ORDER BY trade_date DESC
            LIMIT 1000
        """
        elapsed, count, _ = time_query(conn, "Stock Prices exhibit (LIMIT 1000)", query)


def simulate_full_table_scan(conn: duckdb.DuckDBPyConnection, storage_root: Path):
    """Simulate what happens if NO filter is applied (potential crash scenario)."""
    print("\n" + "=" * 70)
    print("FULL TABLE SCAN TEST (no filter - potential crash scenario)")
    print("=" * 70)

    silver_root = storage_root / "silver"

    # Test: What if the filter isn't applied?
    prices_path = silver_root / "stocks/facts/fact_stock_prices"
    if prices_path.exists():
        source = get_table_source(prices_path)
        # Just count - don't fetch all data
        query = f"SELECT COUNT(*) as cnt FROM {source}"
        elapsed, _, result = time_query(conn, "Stock prices COUNT (no filter)", query)
        if result is not None:
            _, rows = result
            print(f"    Total rows: {rows[0][0]:,}")

        # Test fetching without limit - this would crash
        print("\n  WARNING: Fetching ALL stock prices without filter/limit...")
        print("  (This simulates what might happen if filter fails)")
        query = f"""
            SELECT ticker, trade_date, close
            FROM {source}
            LIMIT 10
        """
        time_query(conn, "Sample of unfiltered data (LIMIT 10)", query, show_sample=True)


def check_schema_mismatch(conn: duckdb.DuckDBPyConnection, storage_root: Path):
    """Check if notebook expects columns that don't exist."""
    print("\n" + "=" * 70)
    print("SCHEMA CHECK (columns required by notebook)")
    print("=" * 70)

    silver_root = storage_root / "silver"

    # Columns required by notebook exhibits
    required = {
        "company/facts/fact_income_statement": [
            "fiscal_date_ending", "total_revenue", "gross_profit",
            "operating_income", "net_income", "cost_of_revenue", "operating_expenses"
        ],
        "company/facts/fact_balance_sheet": [
            "fiscal_date_ending", "total_assets", "total_liabilities",
            "total_shareholder_equity", "cash_and_equivalents", "total_current_assets",
            "total_current_liabilities", "long_term_debt"
        ],
        "company/facts/fact_cash_flow": [
            "fiscal_date_ending", "operating_cashflow", "cashflow_from_investment",
            "cashflow_from_financing", "free_cash_flow", "capital_expenditures",
            "dividend_payout"
        ],
        "company/facts/fact_earnings": [
            "fiscal_date_ending", "reported_eps", "estimated_eps",
            "surprise", "surprise_percentage"
        ],
    }

    for table_path, columns in required.items():
        full_path = silver_root / table_path
        print(f"\n  {table_path}:")

        if not full_path.exists():
            print(f"    ✗ TABLE NOT FOUND")
            continue

        try:
            # Get actual columns (auto-detect format)
            source = get_table_source(full_path)
            query = f"SELECT * FROM {source} LIMIT 0"
            result = conn.execute(query)
            actual_columns = [desc[0] for desc in result.description]

            # Check each required column
            missing = []
            present = []
            for col in columns:
                if col in actual_columns:
                    present.append(col)
                else:
                    missing.append(col)

            print(f"    ✓ Present: {len(present)}/{len(columns)}")
            if missing:
                print(f"    ✗ MISSING: {missing}")

        except Exception as e:
            print(f"    ✗ ERROR: {e}")


def main():
    print("=" * 70)
    print("FINANCIAL STATEMENTS NOTEBOOK DEBUG (DuckDB delta_scan)")
    print("=" * 70)

    storage_root = get_storage_root()
    print(f"Storage root: {storage_root}")

    if not storage_root.exists():
        print(f"ERROR: Storage root not found at {storage_root}")
        sys.exit(1)

    conn = setup_duckdb()

    try:
        # Check bronze layer
        bronze_results = check_bronze_layer(conn, storage_root)

        # Check silver layer
        silver_results = check_silver_layer(conn, storage_root)

        # Check schema for missing columns
        check_schema_mismatch(conn, storage_root)

        # Simulate notebook with filter
        simulate_notebook_filter(conn, storage_root, "AAPL")

        # Test full table scan scenario
        simulate_full_table_scan(conn, storage_root)

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        # Check if silver layer is populated
        silver_ok = all(
            silver_results.get(t, {}).get("count", 0) > 0
            for t in [
                "company/dims/dim_company",
                "company/facts/fact_income_statement",
                "company/facts/fact_balance_sheet",
                "company/facts/fact_cash_flow",
                "company/facts/fact_earnings",
            ]
        )

        if silver_ok:
            print("✓ Silver layer appears populated")
        else:
            print("✗ Silver layer has missing/empty tables!")
            print("  Run: python -m scripts.build.build_models --models company stocks")

    finally:
        conn.close()

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
