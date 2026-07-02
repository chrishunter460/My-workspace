#!/usr/bin/env python3
"""
Performance Test for Financial Statements Notebook

This script recreates the exact data loading done by the financial_statements_gt
notebook to identify performance bottlenecks.

Usage:
    python -m scripts.debug.test_financial_statements_perf
"""

import sys
import time
from pathlib import Path

# Setup imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from de_funk.config.logging import setup_logging, get_logger
import logging

# Enable DEBUG logging to see auto-join trace
setup_logging()
logger = get_logger(__name__)

# Also enable DEBUG for auto_join module to trace join planning
logging.getLogger('models.api.auto_join').setLevel(logging.DEBUG)


def time_operation(name: str, func):
    """Time an operation and print results."""
    start = time.time()
    result = func()
    elapsed = time.time() - start
    status = "🐌 SLOW" if elapsed > 0.5 else "✅"
    print(f"  {status} {name}: {elapsed:.3f}s")
    return result, elapsed


def validate_silver_layer():
    """Validate that the Silver layer exists and has expected structure."""
    print("=" * 70)
    print("SILVER LAYER VALIDATION")
    print("=" * 70)
    print()
    print("This test checks what data exists on YOUR machine.")
    print("Results may differ from what Claude sees on the remote machine.")
    print()

    import json

    # Check BOTH possible storage paths
    print("-" * 70)
    print("STORAGE PATH CHECK")
    print("-" * 70)

    # Path 1: /shared/storage (cluster NFS mount from run_config.json)
    shared_storage = Path("/shared/storage")
    shared_silver = shared_storage / "silver"
    print(f"\n  Path 1: /shared/storage (cluster NFS mount)")
    print(f"    /shared/storage exists: {shared_storage.exists()}")
    print(f"    /shared/storage/silver exists: {shared_silver.exists()}")
    if shared_silver.exists():
        models = [p.name for p in shared_silver.iterdir() if p.is_dir()]
        print(f"    Models found: {models}")

    # Path 2: repo_root/storage (local development)
    local_storage = repo_root / "storage"
    local_silver = local_storage / "silver"
    print(f"\n  Path 2: {local_storage} (local repo)")
    print(f"    {local_storage} exists: {local_storage.exists()}")
    print(f"    {local_silver} exists: {local_silver.exists()}")
    if local_silver.exists():
        models = [p.name for p in local_silver.iterdir() if p.is_dir()]
        print(f"    Models found: {models}")

    # Determine which to use
    if shared_silver.exists():
        silver_root = shared_silver
        print(f"\n  => Using cluster path: {silver_root}")
    elif local_silver.exists():
        silver_root = local_silver
        print(f"\n  => Using local path: {silver_root}")
    else:
        print(f"\n  => WARNING: No Silver layer found at either path!")
        silver_root = local_silver  # Default to local for further checks

    # Now load context to verify DuckDB views
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root(connection_type="duckdb")

    # Get storage config
    storage_cfg = ctx.storage
    print(f"\nStorage config roots:")
    roots = storage_cfg.get('roots', {})
    print(f"  bronze: {roots.get('bronze', 'N/A')}")
    print(f"  silver: {roots.get('silver', 'N/A')}")

    print(f"\nSilver root being used: {silver_root}")
    print(f"  Exists: {silver_root.exists()}")

    if silver_root.exists():
        print(f"\n  Models in Silver layer:")
        for model_dir in sorted(silver_root.iterdir()):
            if model_dir.is_dir():
                tables = list(model_dir.glob("*/*"))
                print(f"    {model_dir.name}/: {len(tables)} table paths")

    # Check temporal model specifically
    print("\n" + "-" * 70)
    print("TEMPORAL MODEL CHECK")
    print("-" * 70)

    temporal_paths = [
        silver_root / "temporal",
        silver_root / "temporal" / "dims",
        silver_root / "temporal" / "dims" / "dim_calendar",
    ]

    for p in temporal_paths:
        exists = p.exists()
        is_dir = p.is_dir() if exists else False
        contents = list(p.iterdir()) if is_dir else []
        print(f"  {p.relative_to(silver_root) if p.is_relative_to(silver_root) else p}")
        print(f"    Exists: {exists}, IsDir: {is_dir}")
        if contents:
            print(f"    Contents: {[c.name for c in contents[:10]]}")

    # Check dim_calendar data files
    calendar_path = silver_root / "temporal" / "dims" / "dim_calendar"
    if calendar_path.exists():
        parquet_files = list(calendar_path.glob("*.parquet"))
        delta_log = calendar_path / "_delta_log"
        print(f"\n  dim_calendar storage:")
        print(f"    Parquet files: {len(parquet_files)}")
        print(f"    Delta log exists: {delta_log.exists()}")

        # Try to read schema
        if parquet_files or delta_log.exists():
            try:
                import pyarrow.parquet as pq
                if parquet_files:
                    schema = pq.read_schema(parquet_files[0])
                    print(f"    Schema columns: {schema.names}")
                    print(f"    Has date_id: {'date_id' in schema.names}")
                    print(f"    Has date: {'date' in schema.names}")
            except Exception as e:
                print(f"    Schema read error: {e}")

    # Check DuckDB views
    print("\n" + "-" * 70)
    print("DUCKDB VIEW CHECK")
    print("-" * 70)

    try:
        # Check if temporal schema exists
        schemas = ctx.connection.conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'temporal'"
        ).fetchall()
        print(f"  Temporal schema in DuckDB: {len(schemas) > 0}")

        if schemas:
            # Check tables/views in temporal schema
            tables = ctx.connection.conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'temporal'"
            ).fetchall()
            print(f"  Tables in temporal schema: {[t[0] for t in tables]}")

            # Check dim_calendar columns
            cols = ctx.connection.conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'temporal' AND table_name = 'dim_calendar'"
            ).fetchall()
            col_names = [c[0] for c in cols]
            print(f"  dim_calendar columns: {col_names}")
            print(f"  Has date_id: {'date_id' in col_names}")
            print(f"  Has date: {'date' in col_names}")

            # Try to get row count
            try:
                count = ctx.connection.conn.execute(
                    "SELECT COUNT(*) FROM temporal.dim_calendar"
                ).fetchone()[0]
                print(f"  dim_calendar row count: {count:,}")
            except Exception as e:
                print(f"  dim_calendar query error: {e}")

    except Exception as e:
        print(f"  DuckDB check error: {e}")

    # Check company model
    print("\n" + "-" * 70)
    print("COMPANY MODEL CHECK")
    print("-" * 70)

    company_path = silver_root / "corporate"  # Note: company model uses 'corporate' directory
    if not company_path.exists():
        company_path = silver_root / "company"

    print(f"  Company Silver path: {company_path}")
    print(f"  Exists: {company_path.exists()}")

    if company_path.exists():
        for subdir in sorted(company_path.iterdir()):
            if subdir.is_dir():
                tables = list(subdir.glob("*"))
                print(f"    {subdir.name}/: {[t.name for t in tables[:5]]}")

    # Check DuckDB company schema
    try:
        schemas = ctx.connection.conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'company'"
        ).fetchall()
        print(f"  Company schema in DuckDB: {len(schemas) > 0}")

        if schemas:
            tables = ctx.connection.conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'company'"
            ).fetchall()
            print(f"  Tables in company schema: {[t[0] for t in tables]}")

            # Check fact_income_statement columns
            cols = ctx.connection.conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'company' AND table_name = 'fact_income_statement'"
            ).fetchall()
            col_names = [c[0] for c in cols]
            print(f"  fact_income_statement columns: {col_names[:15]}...")
            print(f"  Has date_id: {'date_id' in col_names}")
            print(f"  Has company_id: {'company_id' in col_names}")

    except Exception as e:
        print(f"  Company DuckDB check error: {e}")

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)

    return ctx


def test_financial_statements_performance():
    """Test the performance of loading financial statements data."""
    print("\n" + "=" * 70)
    print("FINANCIAL STATEMENTS NOTEBOOK - PERFORMANCE TEST")
    print("=" * 70)

    total_start = time.time()
    timings = {}

    # ============================================================
    # 1. SETUP - Create context and session (same as UI startup)
    # ============================================================
    print("\n[1] SETUP - Creating context and session...")
    print("-" * 70)

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

    ctx, timings['create_context'] = time_operation(
        "Create RepoContext",
        lambda: RepoContext.from_repo_root(connection_type="duckdb")
    )

    session, timings['create_session'] = time_operation(
        "Create UniversalSession",
        lambda: UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
    )

    # ============================================================
    # 2. FILTER DATA - Get ticker list for dropdown (dim_company)
    # ============================================================
    print("\n[2] FILTER DATA - Loading ticker filter options...")
    print("-" * 70)

    def get_ticker_filter():
        df = session.get_table('company', 'dim_company')
        # Simulate what the filter does - get distinct tickers
        if hasattr(df, 'select'):
            return df.select('ticker').distinct()
        return df

    ticker_df, timings['get_ticker_filter'] = time_operation(
        "Get dim_company for ticker filter",
        get_ticker_filter
    )

    # ============================================================
    # 3. EXHIBIT DATA - Load each financial statement table
    # ============================================================
    print("\n[3] EXHIBIT DATA - Loading financial statement tables...")
    print("-" * 70)

    # These are the tables used by the notebook with ticker filter
    tables_to_test = [
        ('company', 'fact_income_statement', ['date', 'ticker', 'total_revenue', 'gross_profit', 'operating_income', 'net_income']),
        ('company', 'fact_balance_sheet', ['date', 'ticker', 'total_assets', 'total_liabilities', 'total_shareholder_equity']),
        ('company', 'fact_cash_flow', ['date', 'ticker', 'operating_cashflow', 'cashflow_from_investment', 'cashflow_from_financing', 'free_cash_flow']),
        ('company', 'fact_earnings', ['date', 'ticker', 'reported_eps', 'estimated_eps', 'surprise_percentage']),
    ]

    ticker_filter = {'ticker': 'AAPL'}  # Default filter from notebook

    for model, table, columns in tables_to_test:
        def load_table(m=model, t=table, c=columns):
            df = session.get_table(m, t, required_columns=c, filters=ticker_filter)
            # Convert to pandas to simulate what exhibit rendering does
            if hasattr(df, 'df'):
                return df.df()
            elif hasattr(df, 'fetchdf'):
                return df.fetchdf()
            return df

        key = f"get_{table}"
        _, timings[key] = time_operation(f"Get {model}.{table}", load_table)

    # ============================================================
    # 4. STOCK PRICES - Load for chart (with auto-join)
    # ============================================================
    print("\n[4] STOCK PRICES - Loading for chart (requires auto-join)...")
    print("-" * 70)

    def load_stock_prices():
        # This is the problematic one - requires auto-join for 'date' and 'ticker'
        required = ['date', 'ticker', 'close', 'open', 'high', 'low', 'volume']
        df = session.get_table('stocks', 'fact_stock_prices',
                               required_columns=required,
                               filters=ticker_filter)
        if hasattr(df, 'df'):
            return df.df()
        elif hasattr(df, 'fetchdf'):
            return df.fetchdf()
        return df

    _, timings['get_stock_prices'] = time_operation(
        "Get stocks.fact_stock_prices (with auto-join)",
        load_stock_prices
    )

    # ============================================================
    # 5. SUMMARY
    # ============================================================
    total_time = time.time() - total_start

    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)

    print(f"\nTotal time: {total_time:.3f}s")
    print("\nBreakdown by operation:")

    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)
    for name, elapsed in sorted_timings:
        pct = (elapsed / total_time) * 100
        bar = "█" * int(pct / 2)
        print(f"  {name:40s} {elapsed:6.3f}s ({pct:5.1f}%) {bar}")

    # Identify bottlenecks
    print("\n" + "-" * 70)
    print("BOTTLENECK ANALYSIS:")
    print("-" * 70)

    slow_ops = [(k, v) for k, v in timings.items() if v > 0.5]
    if slow_ops:
        print("\n⚠️  Slow operations (>0.5s):")
        for name, elapsed in sorted(slow_ops, key=lambda x: x[1], reverse=True):
            print(f"  - {name}: {elapsed:.3f}s")
    else:
        print("\n✅ No operations slower than 0.5s")

    # Check if session caching is working
    print("\n" + "-" * 70)
    print("CACHING TEST - Second load should be faster:")
    print("-" * 70)

    def second_load():
        return session.get_table('company', 'fact_income_statement',
                                 required_columns=['date', 'ticker', 'total_revenue'],
                                 filters=ticker_filter)

    _, second_time = time_operation(
        "Second load of fact_income_statement",
        second_load
    )

    first_time = timings.get('get_fact_income_statement', 0)
    if second_time < first_time * 0.5:
        print(f"  ✅ Caching working: {first_time:.3f}s -> {second_time:.3f}s")
    else:
        print(f"  ⚠️  Caching may not be effective: {first_time:.3f}s -> {second_time:.3f}s")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Run validation first to check Silver layer status
    validate_silver_layer()

    # Then run the performance test
    print("\n\n")
    test_financial_statements_performance()
