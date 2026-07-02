#!/usr/bin/env python
"""
Validate Silver Layer Columns vs DuckDB Views

This script directly reads the Parquet schemas from Silver layer
and compares them to DuckDB view columns to identify mismatches.

Run: python -m scripts.test.validate_silver_columns
"""
from __future__ import annotations

import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def get_parquet_schema(parquet_path: Path) -> dict:
    """Read schema from Parquet file(s) at path."""
    import pyarrow.parquet as pq

    # Find parquet files
    if parquet_path.is_file():
        files = [parquet_path]
    else:
        files = list(parquet_path.glob("**/*.parquet"))

    if not files:
        return {}

    # Read schema from first file
    schema = pq.read_schema(files[0])
    return {field.name: str(field.type) for field in schema}


def get_duckdb_view_columns(conn, view_name: str) -> dict:
    """Get columns from a DuckDB view."""
    try:
        result = conn.execute(f"DESCRIBE {view_name}").fetchall()
        return {row[0]: row[1] for row in result}
    except Exception as e:
        return {"_error": str(e)}


def main():
    """Validate Silver layer columns vs DuckDB views."""
    print("=" * 70)
    print("SILVER LAYER vs DUCKDB VIEW COLUMN VALIDATION")
    print("=" * 70)
    print()

    silver_root = repo_root / "storage" / "silver"

    # Check if Silver layer exists
    if not silver_root.exists():
        print(f"❌ Silver layer not found: {silver_root}")
        print("   Run: python -m scripts.build.build_silver_layer")
        return 1

    # Tables to validate
    tables_to_check = [
        ("stocks", "dims", "dim_stock"),
        ("stocks", "facts", "fact_stock_prices"),
        ("stocks", "facts", "fact_stock_technicals"),
        ("company", "dims", "dim_company"),
        ("core", "dims", "dim_calendar"),
    ]

    # Connect to DuckDB
    import duckdb
    db_path = repo_root / "storage" / "duckdb" / "analytics.db"
    conn = duckdb.connect(str(db_path), read_only=True)

    all_results = {}

    for model, table_type, table_name in tables_to_check:
        print("=" * 70)
        print(f"TABLE: {model}.{table_name}")
        print("=" * 70)

        # Get Silver layer path
        silver_path = silver_root / model / table_type / table_name

        # Get Parquet schema
        print(f"\n📁 Silver Path: {silver_path}")
        if not silver_path.exists():
            print(f"   ❌ NOT FOUND")
            parquet_cols = {}
        else:
            parquet_files = list(silver_path.glob("**/*.parquet"))
            print(f"   Found {len(parquet_files)} Parquet file(s)")
            try:
                parquet_cols = get_parquet_schema(silver_path)
                print(f"   ✓ Schema has {len(parquet_cols)} columns")
            except Exception as e:
                print(f"   ❌ Error reading schema: {e}")
                parquet_cols = {}

        # Get DuckDB view schema
        view_name = f"{model}.{table_name}"
        print(f"\n📊 DuckDB View: {view_name}")
        duckdb_cols = get_duckdb_view_columns(conn, view_name)

        if "_error" in duckdb_cols:
            print(f"   ❌ View not found or error: {duckdb_cols['_error']}")
            duckdb_cols = {}
        else:
            print(f"   ✓ View has {len(duckdb_cols)} columns")

        # Compare
        print(f"\n📋 COLUMN COMPARISON:")

        parquet_set = set(parquet_cols.keys())
        duckdb_set = set(duckdb_cols.keys())

        # Columns in both
        common = parquet_set & duckdb_set
        print(f"   ✓ In both ({len(common)}): {sorted(common)[:10]}{'...' if len(common) > 10 else ''}")

        # In Parquet but not DuckDB view
        parquet_only = parquet_set - duckdb_set
        if parquet_only:
            print(f"   ⚠️  In Silver Parquet but NOT in DuckDB view ({len(parquet_only)}):")
            for col in sorted(parquet_only):
                print(f"      - {col}: {parquet_cols[col]}")

        # In DuckDB but not Parquet
        duckdb_only = duckdb_set - parquet_set
        if duckdb_only:
            print(f"   ⚠️  In DuckDB view but NOT in Silver Parquet ({len(duckdb_only)}):")
            for col in sorted(duckdb_only):
                print(f"      - {col}: {duckdb_cols[col]}")

        # Store results
        all_results[f"{model}.{table_name}"] = {
            "parquet_cols": parquet_cols,
            "duckdb_cols": duckdb_cols,
            "parquet_only": parquet_only,
            "duckdb_only": duckdb_only,
        }

        # Show ALL Parquet columns for key tables
        if table_name in ("fact_stock_prices", "fact_stock_technicals"):
            print(f"\n   📝 ALL Parquet columns in {table_name}:")
            for col, dtype in sorted(parquet_cols.items()):
                print(f"      {col}: {dtype}")

        print()

    conn.close()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    issues_found = False
    for table, result in all_results.items():
        if result["parquet_only"]:
            issues_found = True
            print(f"\n⚠️  {table}: {len(result['parquet_only'])} columns in Parquet but not in DuckDB view")
            print(f"   Missing: {sorted(result['parquet_only'])}")

    if not issues_found:
        print("\n✓ All Silver layer columns are available in DuckDB views")
    else:
        print("\n" + "=" * 70)
        print("RECOMMENDED FIX:")
        print("=" * 70)
        print("Run: python -m scripts.setup.setup_duckdb_views --update")
        print("This will recreate views to include all Silver layer columns.")

    return 0


if __name__ == "__main__":
    try:
        import pyarrow
    except ImportError:
        print("Installing pyarrow for Parquet schema reading...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pyarrow", "-q"])

    sys.exit(main())
