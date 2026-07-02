#!/usr/bin/env python3
"""
Diagnose Bronze and Silver data layers.

Scans storage directories and reports on table contents.

Usage:
    python -m scripts.diagnose.check_data_layers
    python -m scripts.diagnose.check_data_layers --storage-path /shared/storage
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
import argparse

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()


def check_table(spark, path: Path, name: str) -> dict:
    """Check a parquet or delta table and return stats."""
    result = {"name": name, "path": str(path), "exists": False, "rows": 0, "columns": [], "error": None, "format": None}

    if not path.exists():
        return result

    result["exists"] = True

    # Check if Delta table
    is_delta = (path / "_delta_log").exists()

    # Check for parquet files
    parquet_files = list(path.glob("*.parquet")) + list(path.glob("**/*.parquet"))

    if not is_delta and not parquet_files:
        result["error"] = "No parquet files found"
        return result

    try:
        if is_delta:
            result["format"] = "delta"
            df = spark.read.format("delta").load(str(path))
        else:
            result["format"] = "parquet"
            df = spark.read.parquet(str(path))
        result["rows"] = df.count()
        result["columns"] = df.columns
    except Exception as e:
        result["error"] = str(e)

    return result


def scan_silver_model(spark, model_path: Path, model_name: str) -> list:
    """Scan a Silver model directory with dims/facts structure."""
    results = []

    if not model_path.exists():
        return results

    # Check dims/ subdirectory
    dims_path = model_path / "dims"
    if dims_path.exists() and dims_path.is_dir():
        for item in sorted(dims_path.iterdir()):
            if item.is_dir():
                result = check_table(spark, item, f"{model_name}/dims/{item.name}")
                results.append(result)

    # Check facts/ subdirectory
    facts_path = model_path / "facts"
    if facts_path.exists() and facts_path.is_dir():
        for item in sorted(facts_path.iterdir()):
            if item.is_dir():
                result = check_table(spark, item, f"{model_name}/facts/{item.name}")
                results.append(result)

    # Also check for direct tables (legacy structure)
    for item in sorted(model_path.iterdir()):
        if item.is_dir() and item.name not in ("dims", "facts", "_delta_log"):
            has_parquet = bool(list(item.glob("*.parquet")) or list(item.glob("**/*.parquet")))
            has_delta = (item / "_delta_log").exists()
            if has_parquet or has_delta:
                result = check_table(spark, item, f"{model_name}/{item.name}")
                results.append(result)

    # If nothing found in dims/facts/legacy, try reading model directory itself as a table
    if not results:
        has_parquet = bool(list(model_path.glob("*.parquet")) or list(model_path.rglob("*.parquet")))
        has_delta = (model_path / "_delta_log").exists()
        if has_parquet or has_delta:
            result = check_table(spark, model_path, model_name)
            results.append(result)

    return results


def scan_directory(spark, base_path: Path, layer_name: str) -> list:
    """Scan a directory for tables (Bronze layer)."""
    results = []

    if not base_path.exists():
        print(f"  ⚠ {layer_name} path does not exist: {base_path}")
        return results

    # Look for tables (directories with parquet/delta files)
    for item in sorted(base_path.iterdir()):
        if item.is_dir():
            # Check if it's a table (has parquet files or delta log)
            has_parquet = bool(list(item.glob("*.parquet")) or list(item.glob("**/*.parquet")))
            has_delta = (item / "_delta_log").exists()

            if has_parquet or has_delta:
                result = check_table(spark, item, item.name)
                results.append(result)
            else:
                # Recurse into subdirectory
                for subitem in sorted(item.iterdir()):
                    if subitem.is_dir():
                        has_parquet = bool(list(subitem.glob("*.parquet")) or list(subitem.glob("**/*.parquet")))
                        has_delta = (subitem / "_delta_log").exists()
                        if has_parquet or has_delta:
                            result = check_table(spark, subitem, f"{item.name}/{subitem.name}")
                            results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Diagnose Bronze and Silver data layers")
    parser.add_argument("--storage-path", default="/shared/storage", help="Base storage path")
    parser.add_argument("--bronze-only", action="store_true", help="Only check Bronze layer")
    parser.add_argument("--silver-only", action="store_true", help="Only check Silver layer")
    args = parser.parse_args()

    storage_path = Path(args.storage_path)

    print("=" * 70)
    print("DATA LAYER DIAGNOSTIC")
    print("=" * 70)
    print(f"Storage path: {storage_path}")
    print()

    # Initialize Spark
    print("Initializing Spark...")
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("DataDiagnostic").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    print()

    # Check what directories exist at top level
    print("=" * 70)
    print("STORAGE STRUCTURE")
    print("=" * 70)
    if storage_path.exists():
        for item in sorted(storage_path.iterdir()):
            if item.is_dir():
                print(f"  📁 {item.name}/")
    else:
        print(f"  ⚠ Storage path does not exist: {storage_path}")
    print()

    # Check Bronze layer
    if not args.silver_only:
        print("=" * 70)
        print("BRONZE LAYER")
        print("=" * 70)
        bronze_path = storage_path / "bronze"
        bronze_tables = scan_directory(spark, bronze_path, "Bronze")

        if bronze_tables:
            total_rows = 0
            for t in bronze_tables:
                status = "✓" if t["exists"] and not t["error"] else "✗"
                rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                if t["error"]:
                    print(f"  {status} {t['name']}: {t['error']}")
                else:
                    print(f"  {status} {t['name']}: {rows_str} rows")
                    total_rows += t["rows"]
            print(f"\n  Total Bronze rows: {total_rows:,}")
        else:
            print("  No tables found in Bronze layer")
        print()

    # Check Silver layer
    if not args.bronze_only:
        print("=" * 70)
        print("SILVER LAYER")
        print("=" * 70)
        silver_path = storage_path / "silver"

        # Silver layer uses model directories with dims/facts structure
        silver_tables = []
        if silver_path.exists():
            for model_dir in sorted(silver_path.iterdir()):
                if model_dir.is_dir():
                    model_tables = scan_silver_model(spark, model_dir, model_dir.name)
                    silver_tables.extend(model_tables)

        if silver_tables:
            total_rows = 0
            for t in silver_tables:
                status = "✓" if t["exists"] and not t["error"] else "✗"
                rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                if t["error"]:
                    print(f"  {status} {t['name']}: {t['error']}")
                else:
                    print(f"  {status} {t['name']}: {rows_str} rows")
                    total_rows += t["rows"]
            print(f"\n  Total Silver rows: {total_rows:,}")
        else:
            print("  No tables found in Silver layer")
        print()

        # Also check for misplaced Silver tables (directly under storage)
        print("=" * 70)
        print("CHECKING FOR MISPLACED TABLES")
        print("=" * 70)

        # Known model names that might be misplaced
        model_names = ["stocks", "company", "temporal", "forecast", "macro", "city_finance"]
        misplaced = []

        for model in model_names:
            model_path = storage_path / model
            if model_path.exists() and model_path.is_dir():
                # Use silver model scanner for proper dims/facts handling
                tables = scan_silver_model(spark, model_path, model)
                if tables:
                    misplaced.append((model, tables))

        if misplaced:
            print("  ⚠ Found tables outside silver/ directory:")
            for model, tables in misplaced:
                print(f"\n  📁 {model}/ (should be silver/{model}/)")
                for t in tables:
                    rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                    print(f"      - {t['name']}: {rows_str} rows")
        else:
            print("  ✓ No misplaced tables found")
        print()

    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

    spark.stop()


if __name__ == "__main__":
    main()
