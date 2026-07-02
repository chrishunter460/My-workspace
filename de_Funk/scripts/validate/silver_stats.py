#!/usr/bin/env python
"""
Silver Layer Stats — Print row counts, columns, and sizes for all built Silver tables.

Usage:
    python -m scripts.validate.silver_stats [--storage-root /shared/storage]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Delta Lake reads via pyarrow
try:
    from deltalake import DeltaTable as DLTable
except ImportError:
    DLTable = None

import pyarrow.parquet as pq


def get_table_stats(table_path: str) -> dict:
    """Get row count, columns, and size for a Delta or Parquet table."""
    path = Path(table_path)
    if not path.exists():
        return None

    is_delta = (path / "_delta_log").exists()

    if is_delta and DLTable is not None:
        try:
            dt = DLTable(str(path))
            schema = dt.schema().to_pyarrow()
            col_names = [f.name for f in schema]
            # Row count from metadata
            files = dt.file_uris()
            row_count = 0
            for f in files:
                fp = f.replace("file://", "")
                if os.path.exists(fp):
                    row_count += pq.read_metadata(fp).num_rows
            # Size on disk
            size_bytes = sum(
                os.path.getsize(f.replace("file://", ""))
                for f in files
                if os.path.exists(f.replace("file://", ""))
            )
            return {
                "rows": row_count,
                "columns": col_names,
                "num_cols": len(col_names),
                "size_bytes": size_bytes,
                "format": "delta",
            }
        except Exception as e:
            pass

    # Fallback: scan parquet files directly
    parquet_files = list(path.rglob("*.parquet"))
    if not parquet_files:
        return None

    row_count = 0
    size_bytes = 0
    schema = None
    for pf in parquet_files:
        if "_delta_log" in str(pf):
            continue
        meta = pq.read_metadata(str(pf))
        row_count += meta.num_rows
        size_bytes += pf.stat().st_size
        if schema is None:
            schema = pq.read_schema(str(pf))

    col_names = [f.name for f in schema] if schema else []
    return {
        "rows": row_count,
        "columns": col_names,
        "num_cols": len(col_names),
        "size_bytes": size_bytes,
        "format": "delta" if is_delta else "parquet",
    }


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_rows(n: int) -> str:
    """Comma-formatted row count."""
    return f"{n:,}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--storage-root", default="/shared/storage",
        help="Root storage directory (default: /shared/storage)",
    )
    parser.add_argument(
        "--model", action="append", dest="models",
        help="Specific model(s) to report (default: all)",
    )
    parser.add_argument(
        "--columns", action="store_true",
        help="Show column names for each table",
    )
    args = parser.parse_args()

    silver_root = Path(args.storage_root) / "silver"
    if not silver_root.exists():
        print(f"Silver root not found: {silver_root}")
        sys.exit(1)

    # Discover models
    model_dirs = sorted(
        d for d in silver_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    if args.models:
        model_dirs = [d for d in model_dirs if d.name in args.models]

    total_rows = 0
    total_size = 0
    total_tables = 0
    total_dims = 0
    total_facts = 0

    print()
    print("=" * 90)
    print("  Silver Layer Statistics")
    print("=" * 90)
    print()

    for model_dir in model_dirs:
        model_name = model_dir.name
        dims_dir = model_dir / "dims"
        facts_dir = model_dir / "facts"

        tables = []

        # Collect dimension tables
        if dims_dir.exists():
            for table_dir in sorted(dims_dir.iterdir()):
                if table_dir.is_dir() and not table_dir.name.startswith("."):
                    stats = get_table_stats(str(table_dir))
                    if stats:
                        tables.append(("dim", table_dir.name, stats))

        # Collect fact tables
        if facts_dir.exists():
            for table_dir in sorted(facts_dir.iterdir()):
                if table_dir.is_dir() and not table_dir.name.startswith("."):
                    stats = get_table_stats(str(table_dir))
                    if stats:
                        tables.append(("fact", table_dir.name, stats))

        if not tables:
            continue

        model_rows = sum(t[2]["rows"] for t in tables)
        model_size = sum(t[2]["size_bytes"] for t in tables)
        model_dims = sum(1 for t in tables if t[0] == "dim")
        model_facts = sum(1 for t in tables if t[0] == "fact")

        print(f"  {model_name}")
        print(f"  {'─' * (len(model_name) + 2)}")

        for ttype, tname, stats in tables:
            icon = "◆" if ttype == "dim" else "▣"
            print(
                f"    {icon} {tname:<40s}  "
                f"{format_rows(stats['rows']):>12s} rows  "
                f"{stats['num_cols']:>3d} cols  "
                f"{format_size(stats['size_bytes']):>8s}  "
                f"[{stats['format']}]"
            )
            if args.columns:
                col_str = ", ".join(stats["columns"])
                # Wrap at 80 chars
                while col_str:
                    print(f"      {col_str[:78]}")
                    col_str = col_str[78:]

        print(
            f"    {'':40s}  {'─' * 12}       {'─' * 8}"
        )
        print(
            f"    {'Subtotal':<40s}  "
            f"{format_rows(model_rows):>12s} rows  "
            f"{model_dims}d/{model_facts}f   "
            f"{format_size(model_size):>8s}"
        )
        print()

        total_rows += model_rows
        total_size += model_size
        total_tables += len(tables)
        total_dims += model_dims
        total_facts += model_facts

    print("=" * 90)
    print(
        f"  TOTAL: {total_tables} tables "
        f"({total_dims} dims, {total_facts} facts)  |  "
        f"{format_rows(total_rows)} rows  |  "
        f"{format_size(total_size)}"
    )
    print("=" * 90)
    print()


if __name__ == "__main__":
    main()
