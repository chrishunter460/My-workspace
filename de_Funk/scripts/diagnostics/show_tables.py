#!/usr/bin/env python3
"""
Show Tables - Print row counts and columns for Bronze/Silver tables.

Usage:
    python scripts/diagnostics/show_tables.py
    python scripts/diagnostics/show_tables.py --storage /shared/storage
"""
import sys
from pathlib import Path

def main():
    storage = Path(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--storage" else "/shared/storage")

    from pyspark.sql import SparkSession
    spark = SparkSession.builder \
        .appName("ShowTables") \
        .config("spark.driver.memory", "2g") \
        .config("spark.ui.enabled", "false") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    def show(name, path):
        if not path.exists(): return
        try:
            df = spark.read.parquet(str(path))
            print(f"\n{name}: {df.count():,} rows")
            print(f"  Columns: {', '.join([f.name for f in df.schema.fields])}")
        except Exception as e:
            print(f"\n{name}: ERROR - {e}")

    print("=" * 70)
    print("BRONZE LAYER")
    print("=" * 70)
    bronze = storage / "bronze"
    for t in sorted(bronze.iterdir()) if bronze.exists() else []:
        if t.is_dir() and not t.name.startswith('.'): show(t.name, t)

    print("\n" + "=" * 70)
    print("SILVER LAYER")
    print("=" * 70)
    silver = storage / "silver"
    for m in sorted(silver.iterdir()) if silver.exists() else []:
        if m.is_dir() and not m.name.startswith('.'):
            for sub in ["dims", "facts"]:
                for t in sorted((m/sub).iterdir()) if (m/sub).exists() else []:
                    if t.is_dir(): show(f"{m.name}/{sub}/{t.name}", t)

    spark.stop()

if __name__ == "__main__":
    main()
