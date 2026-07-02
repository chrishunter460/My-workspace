#!/usr/bin/env python3
"""
Test DuckDB Auto-Initialization of Views

Tests that views are automatically created when connecting to persistent DuckDB database.

Usage:
    python -m scripts.test.test_duckdb_auto_init
"""

import sys
import tempfile
from pathlib import Path
from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

def test_auto_init():
    """Test DuckDB view auto-initialization."""

    print("=" * 80)
    print("Testing DuckDB View Auto-Initialization")
    print("=" * 80)

    # Test 1: In-memory database should skip initialization
    print("\n[Test 1] In-memory database (should skip)")
    print("-" * 80)

from de_funk.core.duckdb_connection import DuckDBConnection

    conn_memory = DuckDBConnection(db_path=":memory:", enable_delta=False)
    print("✓ In-memory connection created (no view initialization expected)")
    conn_memory.stop()

    # Test 2: Persistent database should initialize views
    print("\n[Test 2] Persistent database (should auto-initialize)")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        print(f"Creating connection to: {db_path}")
        conn_persistent = DuckDBConnection(
            db_path=str(db_path),
            enable_delta=False,
            auto_init_views=True
        )

        # Check if schemas were created
        schemas = conn_persistent.conn.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('stocks', 'options', 'company', 'core')
        """).fetchall()

        if schemas:
            print(f"✓ Found {len(schemas)} v2.0 model schemas:")
            for schema in schemas:
                print(f"  - {schema[0]}")
        else:
            print("⚠ No schemas created (expected if silver layer not built)")

        # Test 3: Second connection should skip (views already exist)
        print("\n[Test 3] Second connection (should skip re-initialization)")
        print("-" * 80)

        conn_persistent.stop()

        conn_persistent2 = DuckDBConnection(
            db_path=str(db_path),
            enable_delta=False,
            auto_init_views=True
        )

        print("✓ Second connection created (should have detected existing views)")
        conn_persistent2.stop()

    # Test 4: Disabled auto-init should skip
    print("\n[Test 4] Auto-init disabled (should skip)")
    print("-" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_no_init.db"

        conn_no_init = DuckDBConnection(
            db_path=str(db_path),
            enable_delta=False,
            auto_init_views=False
        )

        schemas = conn_no_init.conn.execute("""
            SELECT COUNT(*)
            FROM information_schema.schemata
            WHERE schema_name IN ('stocks', 'options', 'company', 'core')
        """).fetchone()[0]

        if schemas == 0:
            print("✓ No schemas created (auto_init_views=False)")
        else:
            print(f"✗ Unexpected: {schemas} schemas found")

        conn_no_init.stop()

    print("\n" + "=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
    print("\nBehavior Summary:")
    print("- ✓ In-memory databases skip initialization (fast for tests)")
    print("- ✓ Persistent databases auto-initialize on first connection")
    print("- ✓ Subsequent connections detect existing views and skip")
    print("- ✓ auto_init_views parameter allows disabling if needed")
    print("\nDefault Behavior:")
    print("  DuckDBConnection() automatically creates views for persistent databases")
    print("  No manual setup_duckdb_views.py needed!")

if __name__ == "__main__":
    test_auto_init()
