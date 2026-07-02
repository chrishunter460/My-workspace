#!/usr/bin/env python3
"""
Bronze Layer Diagnostic - Scan and check all bronze tables.

Usage:
    spark-submit --packages io.delta:delta-spark_2.13:4.0.0 \
        scripts/diagnostics/check_bronze_counts.py --storage-root /shared/storage
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, countDistinct


def get_spark() -> SparkSession:
    """Get or create Spark session with Delta Lake support."""
    return (
        SparkSession.builder
        .appName("BronzeDiagnostics")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )


def find_data_directories(root: Path, depth: int = 3) -> list:
    """Find directories that contain parquet files or _delta_log."""
    data_dirs = []

    def scan_dir(path: Path, current_depth: int):
        if current_depth > depth:
            return
        if not path.exists() or not path.is_dir():
            return

        # Check if this is a data directory
        has_parquet = any(path.glob("*.parquet"))
        has_delta = (path / "_delta_log").exists()
        has_partition_dirs = any(
            d.name.startswith(("snapshot_dt=", "trade_date=", "year=", "report_type="))
            for d in path.iterdir() if d.is_dir()
        )

        if has_parquet or has_delta or has_partition_dirs:
            data_dirs.append(path)
            return  # Don't recurse into data directories

        # Recurse into subdirectories
        for subdir in path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith(("_", ".")):
                scan_dir(subdir, current_depth + 1)

    scan_dir(root, 0)
    return data_dirs


def check_table(spark: SparkSession, path: Path) -> dict:
    """Check a bronze table and return stats."""
    result = {
        "path": str(path),
        "exists": False,
        "format": "unknown",
        "row_count": 0,
        "columns": [],
    }

    if not path.exists():
        return result

    result["exists"] = True

    try:
        # Try Delta first, fall back to Parquet
        try:
            df = spark.read.format("delta").load(str(path))
            result["format"] = "delta"
        except Exception:
            df = spark.read.parquet(str(path))
            result["format"] = "parquet"

        result["row_count"] = df.count()
        result["columns"] = df.columns

        # Check for ticker count if applicable
        if "ticker" in df.columns:
            result["distinct_tickers"] = df.select("ticker").distinct().count()
            sample = df.select("ticker").distinct().limit(5).collect()
            result["sample_tickers"] = [row["ticker"] for row in sample]
        elif "Symbol" in df.columns:
            result["distinct_tickers"] = df.select("Symbol").distinct().count()
            sample = df.select("Symbol").distinct().limit(5).collect()
            result["sample_tickers"] = [row["Symbol"] for row in sample]

        # Check for snapshot_dt
        if "snapshot_dt" in df.columns:
            snapshots = df.select("snapshot_dt").distinct().orderBy(col("snapshot_dt").desc()).limit(5).collect()
            result["snapshot_dates"] = [str(row["snapshot_dt"]) for row in snapshots]

            # Count by snapshot
            snapshot_counts = (
                df.groupBy("snapshot_dt")
                .agg(count("*").alias("cnt"))
                .orderBy(col("snapshot_dt").desc())
                .limit(5)
                .collect()
            )
            result["snapshot_counts"] = [
                {"date": str(row["snapshot_dt"]), "count": row["cnt"]}
                for row in snapshot_counts
            ]

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Check bronze layer row counts")
    parser.add_argument("--storage-root", default="/shared/storage", help="Storage root path")
    args = parser.parse_args()

    storage_root = Path(args.storage_root)
    bronze_root = storage_root / "bronze"

    print("=" * 70)
    print("  Bronze Layer Diagnostic Report")
    print("=" * 70)
    print(f"\nStorage root: {storage_root}")
    print(f"Bronze root: {bronze_root}")

    # First, scan for what directories exist
    print(f"\n{'=' * 70}")
    print("  Scanning Bronze Directory Structure")
    print("=" * 70)

    if not bronze_root.exists():
        print(f"\n❌ Bronze root does not exist: {bronze_root}")
        print("\nChecking if data is at different location...")

        # Try alternative locations
        alt_locations = [
            storage_root / "bronze",
            storage_root,
            Path("/shared/storage"),
            Path("/shared/storage/bronze"),
        ]
        for loc in alt_locations:
            if loc.exists():
                print(f"  Found: {loc}")
                for item in sorted(loc.iterdir())[:20]:
                    print(f"    - {item.name}")
        return

    # List top-level directories
    print(f"\nTop-level directories in {bronze_root}:")
    for item in sorted(bronze_root.iterdir()):
        if item.is_dir():
            print(f"  📁 {item.name}/")
            # List subdirectories
            for subitem in sorted(item.iterdir())[:10]:
                if subitem.is_dir():
                    # Check for _delta_log or parquet files
                    has_delta = (subitem / "_delta_log").exists()
                    has_parquet = any(subitem.glob("*.parquet")) or any(subitem.glob("**/*.parquet"))
                    marker = "Δ" if has_delta else ("📊" if has_parquet else "")
                    print(f"      {marker} {subitem.name}/")

    # Find all data directories
    print(f"\n{'=' * 70}")
    print("  Found Data Tables")
    print("=" * 70)

    data_dirs = find_data_directories(bronze_root, depth=4)
    print(f"\nFound {len(data_dirs)} data directories")

    spark = get_spark()

    for data_dir in sorted(data_dirs):
        rel_path = data_dir.relative_to(bronze_root)
        print(f"\n{'─' * 70}")
        print(f"Table: {rel_path}")
        print(f"Path: {data_dir}")
        print(f"{'─' * 70}")

        stats = check_table(spark, data_dir)

        if not stats["exists"]:
            print("  ❌ Could not read")
            continue

        print(f"  Format: {stats['format']}")
        print(f"  Row count: {stats['row_count']:,}")
        print(f"  Columns ({len(stats['columns'])}): {stats['columns'][:8]}{'...' if len(stats['columns']) > 8 else ''}")

        if stats.get("distinct_tickers"):
            print(f"  Distinct tickers: {stats['distinct_tickers']:,}")
            print(f"  Sample tickers: {stats.get('sample_tickers', [])}")

        if stats.get("snapshot_dates"):
            print(f"  Snapshot dates: {stats['snapshot_dates']}")

        if stats.get("snapshot_counts"):
            print(f"  Rows per snapshot:")
            for sc in stats["snapshot_counts"]:
                print(f"    {sc['date']}: {sc['count']:,} rows")

        if stats.get("error"):
            print(f"  ⚠️ Error: {stats['error']}")

    spark.stop()
    print(f"\n{'=' * 70}")
    print("✓ Diagnostic complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
