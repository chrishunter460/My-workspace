#!/usr/bin/env python3
"""
Test SilverStorageService data access.

Usage:
    python -m scripts.test.test_storage_service
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup repo imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')


def main():
from de_funk.core.context import RepoContext
from de_funk.models.registry import ModelRegistry
    from de_funk.services.storage_service import SilverStorageService

    print("=" * 60)
    print("  Testing SilverStorageService Data Access")
    print("=" * 60)

    # Initialize
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    registry = ModelRegistry(repo_root / "domains")

    print(f"\nRepo root: {ctx.repo}")
    print(f"Connection type: DuckDB")

    # Create storage service
    service = SilverStorageService(ctx.connection, registry)

    print(f"\nAvailable models: {service.list_models()}")

    # Test stocks model
    print("\n--- Testing stocks model ---")

    # Get model config
    stocks_model = registry.get_model('stocks')
    print(f"Storage root: '{stocks_model.storage_root}'")
    print(f"Storage format: '{stocks_model.storage_format}'")
    print(f"Tables: {stocks_model.list_tables()}")

    # Test table path resolution
    for table_name in ['dim_stock', 'fact_stock_prices']:
        try:
            table_path = stocks_model.get_table_path(table_name)
            full_path = Path(table_path)
            if not full_path.is_absolute():
                full_path = ctx.repo / table_path
            print(f"\n{table_name}:")
            print(f"  Path: {table_path}")
            print(f"  Full path: {full_path}")
            print(f"  Exists: {full_path.exists()}")
            print(f"  Is Delta: {(full_path / '_delta_log').exists()}")
        except Exception as e:
            print(f"\n{table_name}: ERROR - {e}")

    # Test reading data via storage service
    print("\n--- Testing data access via SilverStorageService ---")

    for table_name in ['dim_stock', 'fact_stock_prices']:
        print(f"\nReading {table_name}...")
        try:
            df = service.get_table('stocks', table_name)
            print(f"  Type: {type(df)}")

            # Get row count
            if hasattr(df, 'count'):
                count = df.count().fetchone()[0]
            elif hasattr(df, 'shape'):
                count = df.shape[0]
            else:
                # DuckDB relation - execute count
                count_result = df.aggregate("COUNT(*)").fetchone()
                count = count_result[0] if count_result else "unknown"

            print(f"  Row count: {count}")

            # Get sample data
            if hasattr(df, 'limit'):
                sample = df.limit(3).fetchdf()
            elif hasattr(df, 'head'):
                sample = df.head(3)
            else:
                sample = df.fetchdf().head(3)

            print(f"  Columns: {list(sample.columns)}")
            print(f"  Sample:\n{sample.to_string()}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Test using DuckDB views directly
    print("\n--- Testing DuckDB views directly ---")

    try:
        result = ctx.connection.conn.execute("SELECT * FROM stocks.dim_stock LIMIT 5").fetchdf()
        print(f"stocks.dim_stock via view: {len(result)} rows")
        print(result[['ticker', 'security_name', 'exchange_code']].to_string())
    except Exception as e:
        print(f"DuckDB view query failed: {e}")

    print("\n" + "=" * 60)
    print("  Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
