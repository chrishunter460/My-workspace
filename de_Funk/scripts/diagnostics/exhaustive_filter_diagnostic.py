#!/usr/bin/env python
"""
Exhaustive Filter System Diagnostic

This script tests EVERY component in the filter loading chain and
prints detailed output. Errors are NOT suppressed.

Run: python -m scripts.test.exhaustive_filter_diagnostic
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from datetime import datetime

# Setup imports
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def header(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def subheader(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def success(msg: str):
    """Print success message."""
    print(f"  ✅ {msg}")


def fail(msg: str):
    """Print failure message."""
    print(f"  ❌ {msg}")


def info(msg: str):
    """Print info message."""
    print(f"  ℹ️  {msg}")


def warn(msg: str):
    """Print warning message."""
    print(f"  ⚠️  {msg}")


def main():
    """Run exhaustive diagnostic."""
    print("\n" + "=" * 80)
    print("  EXHAUSTIVE FILTER SYSTEM DIAGNOSTIC")
    print(f"  Started: {datetime.now().isoformat()}")
    print("=" * 80)

    errors_found = []

    # =========================================================================
    # PHASE 1: Check file existence and imports
    # =========================================================================
    header("PHASE 1: File Existence and Imports")

    subheader("1.1 Check critical files exist")
    critical_files = [
        "core/duckdb_connection.py",
        "core/session/filters.py",
        "models/api/session.py",
        "app/ui/components/dynamic_filters.py",
        "storage/duckdb/analytics.db",
    ]

    for file_path in critical_files:
        full_path = repo_root / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            success(f"{file_path} exists ({size:,} bytes)")
        else:
            fail(f"{file_path} NOT FOUND")
            errors_found.append(f"Missing file: {file_path}")

    subheader("1.2 Test imports")
    try:
        import duckdb
        success(f"duckdb version: {duckdb.__version__}")
    except ImportError as e:
        fail(f"Cannot import duckdb: {e}")
        errors_found.append("DuckDB not installed")
        return 1

    try:
from de_funk.core.duckdb_connection import DuckDBConnection
        success("DuckDBConnection imported")

        # Check if table() method exists
        if hasattr(DuckDBConnection, 'table'):
            success("DuckDBConnection.table() method EXISTS")
        else:
            fail("DuckDBConnection.table() method MISSING - this is the bug!")
            errors_found.append("DuckDBConnection missing table() method")
    except Exception as e:
        fail(f"Cannot import DuckDBConnection: {e}")
        traceback.print_exc()
        errors_found.append(f"DuckDBConnection import failed: {e}")

    try:
from de_funk.core.session.filters import FilterEngine
        success("FilterEngine imported")

        # Check if _format_sql_value exists
        if hasattr(FilterEngine, '_format_sql_value'):
            success("FilterEngine._format_sql_value() method EXISTS")
        else:
            fail("FilterEngine._format_sql_value() method MISSING")
            errors_found.append("FilterEngine missing _format_sql_value() method")
    except Exception as e:
        fail(f"Cannot import FilterEngine: {e}")
        traceback.print_exc()
        errors_found.append(f"FilterEngine import failed: {e}")

    # =========================================================================
    # PHASE 2: Test DuckDB Connection
    # =========================================================================
    header("PHASE 2: DuckDB Connection")

    db_path = repo_root / "storage" / "duckdb" / "analytics.db"

    subheader("2.1 Connect to persistent database")
    try:
from de_funk.core.duckdb_connection import DuckDBConnection
        conn = DuckDBConnection(db_path=str(db_path), auto_init_views=False)
        success(f"Connected to: {db_path}")
        info(f"Delta enabled: {conn.delta_enabled}")
    except Exception as e:
        fail(f"Connection failed: {e}")
        traceback.print_exc()
        errors_found.append(f"DuckDB connection failed: {e}")
        return 1

    subheader("2.2 Check schemas in database")
    try:
        schemas = conn.conn.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'main')
        """).fetchall()
        schema_list = [s[0] for s in schemas]
        if schema_list:
            success(f"Schemas found: {schema_list}")
        else:
            warn("No custom schemas found - views may not be set up")
    except Exception as e:
        fail(f"Schema query failed: {e}")
        traceback.print_exc()

    subheader("2.3 Check for stocks schema and views")
    try:
        tables = conn.conn.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = 'stocks'
        """).fetchall()

        if tables:
            success(f"Found {len(tables)} tables/views in stocks schema:")
            for schema, table, ttype in tables:
                info(f"  {schema}.{table} ({ttype})")
        else:
            fail("No tables/views in stocks schema!")
            errors_found.append("stocks schema has no views")
    except Exception as e:
        fail(f"Table query failed: {e}")
        traceback.print_exc()

    subheader("2.4 Test table() method directly")
    try:
        if hasattr(conn, 'table'):
            result = conn.table('stocks.dim_stock')
            success(f"conn.table('stocks.dim_stock') returned: {type(result)}")

            # Get columns
            cols = list(result.columns)
            success(f"Columns: {cols[:5]}... ({len(cols)} total)")

            # Get row count
            count = conn.conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()[0]
            success(f"Row count: {count:,}")
        else:
            fail("conn.table() method not available!")
            errors_found.append("table() method missing on connection instance")
    except Exception as e:
        fail(f"table() method failed: {e}")
        traceback.print_exc()
        errors_found.append(f"table() method error: {e}")

    subheader("2.5 Test has_view() method")
    try:
        if hasattr(conn, 'has_view'):
            exists = conn.has_view('stocks.dim_stock')
            if exists:
                success("has_view('stocks.dim_stock') = True")
            else:
                fail("has_view('stocks.dim_stock') = False - view not found!")
                errors_found.append("has_view() says stocks.dim_stock doesn't exist")
        else:
            warn("has_view() method not available")
    except Exception as e:
        fail(f"has_view() failed: {e}")
        traceback.print_exc()

    # =========================================================================
    # PHASE 3: Test RepoContext and Connection Creation
    # =========================================================================
    header("PHASE 3: RepoContext and Connection Path")

    subheader("3.1 Create RepoContext")
    try:
from de_funk.core.context import RepoContext
        ctx = RepoContext.from_repo_root(connection_type='duckdb')
        success(f"RepoContext created")
        info(f"Connection type: {type(ctx.connection).__name__}")
        info(f"Repo root: {ctx.repo}")
    except Exception as e:
        fail(f"RepoContext creation failed: {e}")
        traceback.print_exc()
        errors_found.append(f"RepoContext failed: {e}")
        return 1

    subheader("3.2 Check connection has table() method")
    if hasattr(ctx.connection, 'table'):
        success("ctx.connection.table() EXISTS")
    else:
        fail("ctx.connection.table() MISSING - this is why it falls back to building!")
        errors_found.append("RepoContext connection missing table() method")

    subheader("3.3 Test connection.table() via RepoContext")
    try:
        result = ctx.connection.table('stocks.dim_stock')
        success(f"ctx.connection.table('stocks.dim_stock') works!")
    except Exception as e:
        fail(f"ctx.connection.table() failed: {e}")
        traceback.print_exc()
        errors_found.append(f"connection.table() error: {e}")

    # =========================================================================
    # PHASE 4: Test UniversalSession
    # =========================================================================
    header("PHASE 4: UniversalSession")

    subheader("4.1 Create UniversalSession")
    try:
from de_funk.models.api.session import UniversalSession
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )
        success(f"UniversalSession created")
        info(f"Backend: {session.backend}")
    except Exception as e:
        fail(f"UniversalSession creation failed: {e}")
        traceback.print_exc()
        errors_found.append(f"UniversalSession failed: {e}")
        return 1

    subheader("4.2 Check session.connection has table() method")
    if hasattr(session.connection, 'table'):
        success("session.connection.table() EXISTS")
    else:
        fail("session.connection.table() MISSING!")
        errors_found.append("session.connection missing table() method")

    subheader("4.3 Test _get_table_from_view_or_build logic")
    try:
        # Manually test what the method does
        model_name = 'stocks'
        table_name = 'dim_stock'

        info(f"Testing view lookup for: {model_name}.{table_name}")

        # Check hasattr
        has_table_method = hasattr(session.connection, 'table')
        info(f"hasattr(session.connection, 'table') = {has_table_method}")

        if has_table_method:
            view_name = f"{model_name}.{table_name}"
            info(f"Attempting: session.connection.table('{view_name}')")

            try:
                result = session.connection.table(view_name)
                success(f"View found! Type: {type(result)}")
                info("This should NOT fall back to building from source")
            except Exception as e:
                fail(f"View lookup failed: {e}")
                info("This WILL fall back to building from source")
                traceback.print_exc()
        else:
            fail("table() method not found - WILL fall back to building")

    except Exception as e:
        fail(f"Logic test failed: {e}")
        traceback.print_exc()

    subheader("4.4 Call session.get_table() - THE ACTUAL CALL")
    info("This is what the UI does. Watch for 'Building from source' messages...")
    print()  # Empty line for visibility

    try:
        import logging
        # Enable debug logging to see what happens
        logging.getLogger('models.api.session').setLevel(logging.DEBUG)

        df = session.get_table('stocks', 'dim_stock')
        success(f"get_table() returned: {type(df)}")

        # Check if it's a DuckDB relation (view) or built DataFrame
        if hasattr(df, 'fetchall'):
            success("Returned a DuckDB relation (using view)")
        elif hasattr(df, 'df'):
            success("Returned a DuckDB relation (using view)")
        else:
            info(f"Return type: {type(df)}")

    except Exception as e:
        fail(f"get_table() failed: {e}")
        traceback.print_exc()
        errors_found.append(f"get_table() error: {e}")

    # =========================================================================
    # PHASE 5: Test FilterEngine
    # =========================================================================
    header("PHASE 5: FilterEngine")

    subheader("5.1 Test _format_sql_value()")
    try:
from de_funk.core.session.filters import FilterEngine

        test_cases = [
            (1000000, "1000000"),
            ("AAPL", "'AAPL'"),
            (3.14, "3.14"),
            (True, "TRUE"),
            (None, "NULL"),
            ("O'Brien", "'O''Brien'"),
        ]

        all_pass = True
        for value, expected in test_cases:
            result = FilterEngine._format_sql_value(value)
            if result == expected:
                success(f"_format_sql_value({value!r}) = {result}")
            else:
                fail(f"_format_sql_value({value!r}) = {result}, expected {expected}")
                all_pass = False

        if not all_pass:
            errors_found.append("FilterEngine._format_sql_value() has bugs")

    except Exception as e:
        fail(f"_format_sql_value test failed: {e}")
        traceback.print_exc()

    subheader("5.2 Test build_filter_sql()")
    try:
        filters = {
            'ticker': ['AAPL', 'GOOGL'],
            'volume': {'min': 1000000},
            'close': {'gt': 100.0},
        }

        sql = FilterEngine.build_filter_sql(filters)
        info(f"Input: {filters}")
        info(f"Output SQL: {sql}")

        # Check for quoted numbers (bug)
        if "'1000000'" in sql:
            fail("BUG: Numeric value is quoted as string!")
            errors_found.append("build_filter_sql quotes numeric values")
        else:
            success("Numeric values are NOT quoted")

    except Exception as e:
        fail(f"build_filter_sql test failed: {e}")
        traceback.print_exc()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    header("DIAGNOSTIC SUMMARY")

    if errors_found:
        print(f"\n❌ Found {len(errors_found)} error(s):\n")
        for i, error in enumerate(errors_found, 1):
            print(f"  {i}. {error}")
        print()
        print("=" * 80)
        print("RECOMMENDED ACTIONS:")
        print("=" * 80)

        if any("table() method" in e.lower() for e in errors_found):
            print("""
1. The table() method is missing from DuckDBConnection.
   This means the code cannot use pre-created views.

   FIX: Pull the latest code:
     git pull origin claude/fix-duckdb-filters-crash-019Bd41xdSzv87DgP66uzHLm
""")

        if any("view" in e.lower() and "exist" in e.lower() for e in errors_found):
            print("""
2. Views don't exist in the database.

   FIX: Run the view setup:
     python -m scripts.setup.setup_duckdb_views --update
""")

        if any("numeric" in e.lower() or "quote" in e.lower() for e in errors_found):
            print("""
3. FilterEngine is quoting numeric values incorrectly.

   FIX: Pull the latest code with the fix.
""")

        return 1
    else:
        print("\n✅ All checks passed!")
        print("\nIf the UI still crashes, the issue is elsewhere.")
        print("Run the UI with verbose logging:")
        print("  PYTHONPATH=. streamlit run app/ui/notebook_app_duckdb.py --logger.level=debug")
        return 0


if __name__ == "__main__":
    sys.exit(main())
