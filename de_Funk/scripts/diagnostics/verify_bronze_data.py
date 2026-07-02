#!/usr/bin/env python
"""
Verify Bronze Data - Quick check of bronze layer status.

Usage:
    python -m scripts.diagnostics.verify_bronze_data
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    print("=" * 60)
    print("BRONZE LAYER VERIFICATION")
    print("=" * 60)

    bronze_path = Path(repo_root) / "storage" / "bronze"

    # Check what tables exist
    print(f"\nBronze path: {bronze_path}")
    print(f"Exists: {bronze_path.exists()}")

    if not bronze_path.exists():
        print("\n❌ Bronze directory does not exist!")
        return

    # List all subdirectories (tables)
    tables = [d for d in bronze_path.iterdir() if d.is_dir()]
    print(f"\nTables found: {len(tables)}")

    for table_dir in sorted(tables):
        table_name = table_dir.name

        # Count files
        parquet_files = list(table_dir.rglob("*.parquet"))
        delta_log = table_dir / "_delta_log"
        is_delta = delta_log.exists()

        # Get total size
        total_size = sum(f.stat().st_size for f in parquet_files) if parquet_files else 0
        size_mb = total_size / (1024 * 1024)

        format_type = "Delta" if is_delta else "Parquet"
        print(f"\n  📁 {table_name}")
        print(f"     Format: {format_type}")
        print(f"     Files: {len(parquet_files)}")
        print(f"     Size: {size_mb:.2f} MB")

        # Show partition structure
        if parquet_files:
            # Get unique partition paths
            partitions = set()
            for f in parquet_files[:100]:  # Sample first 100
                rel_path = f.relative_to(table_dir)
                parts = [p for p in rel_path.parts[:-1] if '=' in p]
                if parts:
                    partitions.add(tuple(p.split('=')[0] for p in parts))

            if partitions:
                partition_cols = list(partitions)[0] if len(partitions) == 1 else "mixed"
                print(f"     Partitions: {partition_cols}")

    # Try to read securities_prices_daily with Spark
    print("\n" + "=" * 60)
    print("READING securities_prices_daily WITH SPARK")
    print("=" * 60)

    prices_path = bronze_path / "securities_prices_daily"
    if not prices_path.exists():
        print(f"\n❌ securities_prices_daily does not exist at {prices_path}")
        return

    try:
from de_funk.core.context import RepoContext

        print("\nInitializing Spark...")
        ctx = RepoContext.from_repo_root(connection_type="spark")
        spark = ctx.spark

        # Read the table
        delta_log = prices_path / "_delta_log"
        if delta_log.exists():
            print("Reading as Delta table...")
            df = spark.read.format("delta").load(str(prices_path))
        else:
            print("Reading as Parquet...")
            df = spark.read.parquet(str(prices_path))

        # Show stats
        print(f"\nSchema:")
        df.printSchema()

        print(f"\nRow count: {df.count()}")

        print(f"\nDistinct tickers:")
        tickers = df.select("ticker").distinct().collect()
        for row in tickers[:20]:
            print(f"  - {row.ticker}")
        if len(tickers) > 20:
            print(f"  ... and {len(tickers) - 20} more")

        print(f"\nSample data:")
        df.select("ticker", "trade_date", "open", "high", "low", "close", "volume").show(10)

        print("\n✅ securities_prices_daily is readable!")

    except Exception as e:
        print(f"\n❌ Error reading securities_prices_daily: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
