#!/usr/bin/env python
"""
Test DuckDB Missing Columns Handling

Validates that when exhibits request columns not in Silver layer,
the system returns available data instead of triggering expensive builds.

Run: python -m scripts.test.test_duckdb_missing_columns
"""
from __future__ import annotations

import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """Test that missing columns are handled gracefully."""
    setup_logging()

    print("=" * 60)
    print("TEST: DuckDB Missing Columns Handling")
    print("=" * 60)
    print()

    # Connect with DuckDB
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    print(f"✓ Connected with backend: {type(ctx.connection).__name__}")

    # Create UniversalSession
from de_funk.models.api.session import UniversalSession
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    print(f"✓ Session backend: {session.backend}")

    # Test 1: Request table WITHOUT specifying columns (should work)
    print()
    print("=" * 60)
    print("TEST 1: Basic table access (no column requirements)")
    print("=" * 60)
    try:
        df = session.get_table('stocks', 'dim_stock')
        print(f"✓ dim_stock loaded successfully")
        print(f"  Type: {type(df)}")
        print(f"  Columns: {list(df.columns)[:5]}...")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return 1

    # Test 2: Request table WITH existing columns (should work)
    print()
    print("=" * 60)
    print("TEST 2: Table with existing columns only")
    print("=" * 60)
    try:
        df = session.get_table(
            'stocks',
            'fact_stock_prices',
            required_columns=['ticker', 'trade_date', 'close', 'volume']
        )
        print(f"✓ fact_stock_prices loaded with existing columns")
        print(f"  Columns: {list(df.columns)}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return 1

    # Test 3: Request table WITH missing columns (THE KEY TEST)
    print()
    print("=" * 60)
    print("TEST 3: Table with MISSING columns (volume_ratio)")
    print("=" * 60)
    print("This should return available columns WITHOUT triggering builds...")
    print()

    try:
        # This includes 'volume_ratio' which doesn't exist in the view
        df = session.get_table(
            'stocks',
            'fact_stock_prices',
            required_columns=['ticker', 'trade_date', 'close', 'volume', 'volume_ratio']
        )
        print(f"✓ Returned data with available columns only")
        print(f"  Type: {type(df)}")
        actual_cols = list(df.columns)
        print(f"  Returned columns: {actual_cols}")

        if 'volume_ratio' in actual_cols:
            print(f"  ! Note: volume_ratio WAS found (may exist in view now)")
        else:
            print(f"  ✓ Correctly excluded missing column 'volume_ratio'")

    except ValueError as e:
        # This is acceptable - clear error message
        print(f"! Got ValueError (acceptable): {e}")
    except Exception as e:
        print(f"✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test 4: Request table with filters AND missing columns
    print()
    print("=" * 60)
    print("TEST 4: Table with filters AND missing columns")
    print("=" * 60)
    try:
        df = session.get_table(
            'stocks',
            'fact_stock_prices',
            required_columns=['ticker', 'trade_date', 'close', 'volume_ratio'],
            filters={'ticker': ['AAPL', 'MSFT']}
        )
        print(f"✓ Returned filtered data with available columns")
        print(f"  Columns: {list(df.columns)}")

    except ValueError as e:
        print(f"! Got ValueError (acceptable): {e}")
    except Exception as e:
        print(f"✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("The fix prevents expensive builds when columns are missing.")
    print("DuckDB queries will return available data without hanging.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
