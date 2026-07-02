#!/usr/bin/env python3
"""
Storage Summary - Simple diagnostic for Bronze and Silver data.

Shows a clean table with:
- Table name
- File count
- Row count
- Partition columns (if any)
- Last modified date

Usage:
    python -m scripts.diagnostics.storage_summary
    python -m scripts.diagnostics.storage_summary --bronze-only
    python -m scripts.diagnostics.storage_summary --silver-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

import duckdb


@dataclass
class TableInfo:
    """Info about a data table."""
    layer: str          # bronze or silver
    name: str           # table name (e.g., securities_reference)
    path: Path          # full path
    file_count: int     # number of parquet files
    row_count: int      # total rows
    partitions: List[str]  # partition columns detected
    columns: List[str]  # all columns
    last_modified: Optional[datetime]  # most recent file modification
    format: str         # delta or parquet
    size_mb: float      # total size in MB


def detect_partitions(table_path: Path) -> List[str]:
    """Detect partition columns from directory structure."""
    partitions = []
    for item in table_path.iterdir():
        if item.is_dir() and '=' in item.name:
            col_name = item.name.split('=')[0]
            if col_name not in partitions:
                partitions.append(col_name)
    return sorted(partitions)


def get_table_info(conn: duckdb.DuckDBPyConnection, layer: str,
                   table_name: str, table_path: Path) -> Optional[TableInfo]:
    """Get info about a single table."""
    if not table_path.exists():
        return None

    # Check format
    is_delta = (table_path / "_delta_log").exists()
    fmt = "delta" if is_delta else "parquet"

    # Find all parquet files
    parquet_files = list(table_path.rglob("*.parquet"))
    if not parquet_files:
        return None

    # Detect partitions
    partitions = detect_partitions(table_path)

    # Calculate size
    total_size = sum(f.stat().st_size for f in parquet_files)
    size_mb = total_size / (1024 * 1024)

    # Get last modified
    last_mod = max(f.stat().st_mtime for f in parquet_files)
    last_modified = datetime.fromtimestamp(last_mod)

    # Read with DuckDB to get row count and columns
    try:
        pattern = str(table_path / "**" / "*.parquet")
        df = conn.from_parquet(pattern, union_by_name=True, hive_partitioning=True)
        columns = list(df.columns)
        row_count = df.count('*').fetchone()[0]
    except Exception as e:
        print(f"  Warning: Could not read {table_name}: {e}")
        columns = []
        row_count = 0

    return TableInfo(
        layer=layer,
        name=table_name,
        path=table_path,
        file_count=len(parquet_files),
        row_count=row_count,
        partitions=partitions,
        columns=columns,
        last_modified=last_modified,
        format=fmt,
        size_mb=size_mb
    )


def discover_tables(storage_root: Path) -> dict:
    """Discover all tables in bronze and silver."""
    tables = {"bronze": [], "silver": []}

    # Bronze tables
    bronze_path = storage_root / "bronze"
    if bronze_path.exists():
        for item in sorted(bronze_path.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                # Check for nested provider tables (e.g., bls/unemployment)
                has_parquet = any(item.rglob("*.parquet"))
                if has_parquet:
                    # Check if it's a provider directory with subtables
                    subdirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith('_') and '=' not in d.name]
                    has_subtables = any(any(sd.rglob("*.parquet")) for sd in subdirs)

                    if has_subtables:
                        # Provider with subtables (bls/unemployment, etc.)
                        for subdir in subdirs:
                            if any(subdir.rglob("*.parquet")):
                                tables["bronze"].append((f"{item.name}/{subdir.name}", subdir))
                    else:
                        # Direct table
                        tables["bronze"].append((item.name, item))

    # Silver tables
    silver_path = storage_root / "silver"
    if silver_path.exists():
        for model_dir in sorted(silver_path.iterdir()):
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                # Check dims and facts
                for table_type in ["dims", "facts"]:
                    type_dir = model_dir / table_type
                    if type_dir.exists():
                        for table_dir in sorted(type_dir.iterdir()):
                            if table_dir.is_dir() and any(table_dir.rglob("*.parquet")):
                                full_name = f"{model_dir.name}/{table_type}/{table_dir.name}"
                                tables["silver"].append((full_name, table_dir))

    return tables


def print_summary_table(tables: List[TableInfo], title: str):
    """Print a formatted summary table."""
    if not tables:
        print(f"\n{title}: No tables found")
        return

    print(f"\n{'=' * 100}")
    print(f" {title}")
    print(f"{'=' * 100}")

    # Header
    header = f"{'Table':<40} {'Rows':>12} {'Files':>8} {'Size':>10} {'Format':>8} {'Partitions':<20}"
    print(header)
    print("-" * 100)

    # Rows
    total_rows = 0
    total_files = 0
    total_size = 0.0

    for t in tables:
        part_str = ", ".join(t.partitions) if t.partitions else "-"
        if len(part_str) > 20:
            part_str = part_str[:17] + "..."

        size_str = f"{t.size_mb:.1f} MB" if t.size_mb >= 1 else f"{t.size_mb * 1024:.0f} KB"

        row = f"{t.name:<40} {t.row_count:>12,} {t.file_count:>8} {size_str:>10} {t.format:>8} {part_str:<20}"
        print(row)

        total_rows += t.row_count
        total_files += t.file_count
        total_size += t.size_mb

    # Totals
    print("-" * 100)
    size_str = f"{total_size:.1f} MB" if total_size >= 1 else f"{total_size * 1024:.0f} KB"
    print(f"{'TOTAL':<40} {total_rows:>12,} {total_files:>8} {size_str:>10}")


def print_partition_analysis(tables: List[TableInfo]):
    """Print analysis of partition columns."""
    print(f"\n{'=' * 100}")
    print(" PARTITION ANALYSIS")
    print(f"{'=' * 100}")

    # Group by partition columns
    partition_usage = {}
    for t in tables:
        key = tuple(sorted(t.partitions)) if t.partitions else ("none",)
        if key not in partition_usage:
            partition_usage[key] = []
        partition_usage[key].append(t.name)

    print(f"\n{'Partition Columns':<40} {'Tables Using':<60}")
    print("-" * 100)

    for partitions, table_names in sorted(partition_usage.items()):
        part_str = ", ".join(partitions)
        tables_str = ", ".join(table_names[:3])
        if len(table_names) > 3:
            tables_str += f" (+{len(table_names) - 3} more)"
        print(f"{part_str:<40} {tables_str:<60}")

    # Highlight snapshot_dt specifically
    snapshot_tables = [t for t in tables if "snapshot_dt" in t.partitions]
    if snapshot_tables:
        print(f"\n⚠️  Tables using snapshot_dt ({len(snapshot_tables)}):")
        for t in snapshot_tables:
            print(f"   - {t.name}")


def print_column_details(tables: List[TableInfo], show_all: bool = False):
    """Print column details for each table."""
    print(f"\n{'=' * 100}")
    print(" COLUMN DETAILS")
    print(f"{'=' * 100}")

    for t in tables:
        cols_str = ", ".join(t.columns[:10])
        if len(t.columns) > 10:
            cols_str += f" (+{len(t.columns) - 10} more)"
        print(f"\n{t.name} ({len(t.columns)} cols):")
        print(f"  {cols_str}")


def main():
    parser = argparse.ArgumentParser(description="Storage summary for Bronze and Silver data")
    parser.add_argument("--bronze-only", action="store_true", help="Show only Bronze tables")
    parser.add_argument("--silver-only", action="store_true", help="Show only Silver tables")
    parser.add_argument("--columns", action="store_true", help="Show column details")
    parser.add_argument("--partitions", action="store_true", help="Show partition analysis")
    args = parser.parse_args()

    storage_root = repo_root / "storage"

    print(f"\n📊 STORAGE SUMMARY")
    print(f"   Root: {storage_root}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Discover tables
    discovered = discover_tables(storage_root)

    if not discovered["bronze"] and not discovered["silver"]:
        print("\n❌ No data found in storage/bronze or storage/silver")
        print("   Run the ingestion pipeline first:")
        print("   python -m scripts.ingest.run_full_pipeline --max-tickers 100")
        return

    # Connect to DuckDB (in-memory for reading)
    conn = duckdb.connect()

    # Get table info
    bronze_tables = []
    silver_tables = []

    if not args.silver_only:
        for name, path in discovered["bronze"]:
            info = get_table_info(conn, "bronze", name, path)
            if info:
                bronze_tables.append(info)

    if not args.bronze_only:
        for name, path in discovered["silver"]:
            info = get_table_info(conn, "silver", name, path)
            if info:
                silver_tables.append(info)

    # Print summaries
    if bronze_tables:
        print_summary_table(bronze_tables, "BRONZE LAYER (Raw Data)")

    if silver_tables:
        print_summary_table(silver_tables, "SILVER LAYER (Dimensional Models)")

    # Combined summary
    all_tables = bronze_tables + silver_tables
    if all_tables:
        total_rows = sum(t.row_count for t in all_tables)
        total_files = sum(t.file_count for t in all_tables)
        total_size = sum(t.size_mb for t in all_tables)

        print(f"\n{'=' * 100}")
        print(f" GRAND TOTAL: {len(all_tables)} tables, {total_rows:,} rows, {total_files} files, {total_size:.1f} MB")
        print(f"{'=' * 100}")

    # Optional: partition analysis
    if args.partitions or True:  # Always show partition analysis
        print_partition_analysis(all_tables)

    # Optional: column details
    if args.columns:
        print_column_details(all_tables)

    conn.close()


if __name__ == "__main__":
    main()
