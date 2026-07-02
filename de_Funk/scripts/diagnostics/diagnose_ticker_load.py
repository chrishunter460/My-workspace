#!/usr/bin/env python
"""
Diagnose ticker list loading crash.

This script isolates the crash point when loading filter options from DuckDB.
It tests each step separately to identify where the failure occurs.

Run: python -m scripts.test.diagnose_ticker_load
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Setup imports
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def test_step(name: str, func):
    """Run a test step and capture any failure."""
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print("="*60)
    try:
        result = func()
        print(f"✅ {name}: SUCCESS")
        return result, True
    except Exception as e:
        print(f"❌ {name}: FAILED")
        print(f"   Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None, False


def main():
    """Run diagnostic tests step by step."""
    setup_logging()

    print("\n" + "="*60)
    print("TICKER LIST LOADING DIAGNOSTIC")
    print("="*60)
    print("Testing each step of filter option loading to isolate crash...")

    # Step 1: Basic DuckDB connection
    def step1_duckdb_connect():
        import duckdb
        conn = duckdb.connect(":memory:")
        result = conn.execute("SELECT 1 AS test").fetchone()
        print(f"   DuckDB test query: {result}")
        return True

    _, ok = test_step("DuckDB Basic Connection", step1_duckdb_connect)
    if not ok:
        print("\n❌ FATAL: DuckDB not working. Check installation.")
        return 1

    # Step 2: DuckDB with Delta extension
    def step2_delta_extension():
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL delta")
        conn.execute("LOAD delta")
        print("   Delta extension loaded successfully")
        return True

    _, ok = test_step("DuckDB Delta Extension", step2_delta_extension)
    if not ok:
        print("\n⚠️ WARNING: Delta extension not available")

    # Step 3: DuckDBConnection class
    def step3_duckdb_connection_class():
from de_funk.core.duckdb_connection import DuckDBConnection
        conn = DuckDBConnection(db_path=":memory:", auto_init_views=False)
        print(f"   Delta enabled: {conn.delta_enabled}")
        return conn

    conn, ok = test_step("DuckDBConnection Class (in-memory)", step3_duckdb_connection_class)
    if not ok:
        print("\n❌ FATAL: DuckDBConnection class failed")
        return 1

    # Step 4: Check if Silver layer exists
    def step4_check_silver_layer():
        silver_path = repo_root / "storage" / "silver" / "stocks"
        dim_stock_path = silver_path / "dim_stock"

        print(f"   Silver stocks path: {silver_path}")
        print(f"   Silver stocks exists: {silver_path.exists()}")

        if silver_path.exists():
            contents = list(silver_path.iterdir())
            print(f"   Contents: {[p.name for p in contents]}")

            if dim_stock_path.exists():
                dim_contents = list(dim_stock_path.iterdir())
                print(f"   dim_stock contents: {[p.name for p in dim_contents[:5]]}...")

                # Check if it's a Delta table
                delta_log = dim_stock_path / "_delta_log"
                if delta_log.exists():
                    print(f"   dim_stock is a Delta table")
                else:
                    print(f"   dim_stock is Parquet (no _delta_log)")

                return True
        else:
            print("   ⚠️ Silver layer not found!")
            return False

        return False

    silver_exists, ok = test_step("Check Silver Layer", step4_check_silver_layer)

    # Step 5: Check Bronze layer
    def step5_check_bronze_layer():
        bronze_path = repo_root / "storage" / "bronze"
        sec_ref_path = bronze_path / "securities_reference"

        print(f"   Bronze path: {bronze_path}")
        print(f"   Bronze path exists: {bronze_path.exists()}")

        if bronze_path.exists():
            contents = list(bronze_path.iterdir())
            print(f"   Contents: {[p.name for p in contents]}")

            if sec_ref_path.exists():
                sec_ref_contents = list(sec_ref_path.iterdir())
                print(f"   securities_reference contents: {[p.name for p in sec_ref_contents[:5]]}...")

                # Check if it's a Delta table
                delta_log = sec_ref_path / "_delta_log"
                if delta_log.exists():
                    print(f"   securities_reference is a Delta table")

                    # Check delta log size
                    log_files = list(delta_log.iterdir())
                    print(f"   Delta log files: {len(log_files)}")

                return True

        return False

    _, ok = test_step("Check Bronze Layer", step5_check_bronze_layer)

    # Step 6: Read Silver layer directly (if exists)
    if silver_exists:
        def step6_read_silver_directly():
from de_funk.core.duckdb_connection import DuckDBConnection
            conn = DuckDBConnection(db_path=":memory:", auto_init_views=False)

            dim_stock_path = repo_root / "storage" / "silver" / "stocks" / "dim_stock"
            print(f"   Reading from: {dim_stock_path}")

            # Try reading
            df = conn.read_table(str(dim_stock_path))
            print(f"   Columns: {list(df.columns)[:5]}...")

            # Get row count (this triggers actual read)
            pdf = conn.to_pandas(df)
            print(f"   Row count: {len(pdf)}")

            if 'ticker' in pdf.columns:
                tickers = pdf['ticker'].dropna().unique().tolist()
                print(f"   Unique tickers: {len(tickers)}")
                print(f"   Sample: {tickers[:5]}")

            return True

        _, ok = test_step("Read Silver dim_stock Directly", step6_read_silver_directly)

    # Step 7: Try loading via persistent DB (the real path)
    def step7_persistent_db():
        db_path = repo_root / "storage" / "duckdb" / "analytics.db"
        print(f"   Analytics DB path: {db_path}")
        print(f"   DB exists: {db_path.exists()}")

        if not db_path.exists():
            print("   ⚠️ Analytics DB not found - views not initialized")
            return False

from de_funk.core.duckdb_connection import DuckDBConnection

        # Connect WITHOUT auto_init_views to avoid the hang
        print("   Connecting (without auto_init_views)...")
        conn = DuckDBConnection(db_path=str(db_path), auto_init_views=False)

        # Check what schemas/views exist
        schemas = conn.conn.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%'
            AND schema_name NOT IN ('information_schema', 'main')
        """).fetchall()
        print(f"   Schemas: {[s[0] for s in schemas]}")

        # Check for stocks schema
        if any(s[0] == 'stocks' for s in schemas):
            tables = conn.conn.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'stocks'
            """).fetchall()
            print(f"   stocks tables/views: {[t[0] for t in tables]}")

            if any(t[0] == 'dim_stock' for t in tables):
                print("   ✓ stocks.dim_stock view exists!")

                # Try to query it
                result = conn.conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()
                print(f"   Row count: {result[0]}")

                # Get ticker column
                tickers = conn.conn.execute("""
                    SELECT DISTINCT ticker
                    FROM stocks.dim_stock
                    WHERE ticker IS NOT NULL
                    LIMIT 10
                """).fetchall()
                print(f"   Sample tickers: {[t[0] for t in tickers]}")

                return True
        else:
            print("   ⚠️ stocks schema not found - run setup_duckdb_views.py")
            return False

        return False

    _, ok = test_step("Check Persistent Analytics DB", step7_persistent_db)

    # Step 8: Test RepoContext (the entry point used by UI)
    def step8_repo_context():
from de_funk.core.context import RepoContext

        print("   Creating RepoContext...")
        ctx = RepoContext.from_repo_root(connection_type='duckdb')
        print(f"   Connection type: {type(ctx.connection).__name__}")

        return ctx

    ctx, ok = test_step("RepoContext Creation", step8_repo_context)

    # Step 9: Test UniversalSession
    if ctx and ok:
        def step9_universal_session():
from de_funk.models.api.session import UniversalSession

            print("   Creating UniversalSession...")
            session = UniversalSession(
                connection=ctx.connection,
                storage_cfg=ctx.storage,
                repo_root=ctx.repo
            )
            print(f"   Backend: {session.backend}")
            print(f"   Available models: {session.list_models()}")

            return session

        session, ok = test_step("UniversalSession Creation", step9_universal_session)

    # Step 10: The actual problematic call
    if ok and session:
        def step10_get_table():
            print("   Calling session.get_table('stocks', 'dim_stock')...")
            print("   (This is where the hang/crash occurs)")

            # Set a timeout for this operation
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("get_table() took too long (>30s)")

            # Set 30 second timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)

            try:
                df = session.get_table('stocks', 'dim_stock')
                signal.alarm(0)  # Cancel timeout

                print(f"   Columns: {list(df.columns)[:5]}...")

                # Convert to pandas
                print("   Converting to pandas...")
                pdf = ctx.connection.to_pandas(df)
                print(f"   Row count: {len(pdf)}")

                if 'ticker' in pdf.columns:
                    tickers = pdf['ticker'].dropna().unique().tolist()
                    print(f"   Unique tickers: {len(tickers)}")

                return True
            except TimeoutError as e:
                print(f"   ⚠️ TIMEOUT: {e}")
                return False

        _, ok = test_step("session.get_table('stocks', 'dim_stock')", step10_get_table)

    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)

    print("""
If the script hangs at Step 10, the issue is likely:
1. Silver layer views don't exist - need to run setup_duckdb_views.py
2. Building from Bronze is too slow/memory intensive
3. DuckDB Delta extension has issues with the data

RECOMMENDED FIXES:
1. Ensure Silver layer is built:
   python -m scripts.build_silver_layer

2. Setup DuckDB views:
   python -m scripts.setup.setup_duckdb_views

3. If Bronze layer is too large, consider:
   - Adding partitioning
   - Reducing data scope
   - Using Spark for initial build
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
