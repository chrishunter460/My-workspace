"""
Inspect Silver layer — scan all Delta tables and report structure + stats.

Usage:
    python -m scripts.maintenance.inspect_silver
    python -m scripts.maintenance.inspect_silver --storage-root /shared/storage/silver
    python -m scripts.maintenance.inspect_silver --domain stocks
    python -m scripts.maintenance.inspect_silver --table dim_stock
    python -m scripts.maintenance.inspect_silver --table dim_stock --sample 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to path
_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "src"))


def _find_delta_tables(silver_root: Path) -> list[tuple[str, Path]]:
    """Walk silver_root and find all directories containing _delta_log/."""
    tables: list[tuple[str, Path]] = []
    for delta_log in sorted(silver_root.rglob("_delta_log")):
        table_path = delta_log.parent
        rel = table_path.relative_to(silver_root)
        tables.append((str(rel), table_path))
    return tables


def _format_bytes(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    if n >= 1e3:
        return f"{n / 1e3:.1f} KB"
    return f"{n} B"


def _inspect_table(table_path: Path, show_sample: int = 0) -> dict:
    """Inspect a single Delta table via PyArrow."""
    import pyarrow.dataset as ds

    dataset = ds.dataset(str(table_path))
    schema = dataset.schema
    row_count = dataset.count_rows()

    # File stats
    files = list(table_path.glob("*.parquet"))
    total_bytes = sum(f.stat().st_size for f in files)

    # Column details
    columns = []
    for i in range(len(schema)):
        field = schema.field(i)
        columns.append({
            "name": field.name,
            "type": str(field.type),
            "nullable": field.nullable,
        })

    # Null counts + distinct counts for small tables (< 500K rows)
    col_stats = {}
    if row_count > 0 and row_count < 500_000:
        import pyarrow.compute as pc
        table = dataset.to_table()
        for col_info in columns:
            name = col_info["name"]
            col = table.column(name)
            null_count = col.null_count
            try:
                n_distinct = pc.count_distinct(col).as_py()
            except Exception:
                n_distinct = None
            col_stats[name] = {
                "nulls": null_count,
                "null_pct": f"{null_count / row_count * 100:.1f}%" if row_count else "0%",
                "distinct": n_distinct,
            }

    # Sample rows
    sample_rows = []
    if show_sample > 0 and row_count > 0:
        table = dataset.to_table()
        sample = table.slice(0, min(show_sample, row_count))
        sample_rows = sample.to_pydict()

    return {
        "row_count": row_count,
        "col_count": len(schema),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "columns": columns,
        "col_stats": col_stats,
        "sample": sample_rows,
    }


def _print_table_summary(rel_path: str, info: dict, verbose: bool = True) -> None:
    """Print formatted summary for one table."""
    print(f"\n{'=' * 80}")
    print(f"  {rel_path}")
    print(f"{'=' * 80}")
    print(f"  Rows: {info['row_count']:,}  |  Columns: {info['col_count']}  |  "
          f"Files: {info['file_count']}  |  Size: {_format_bytes(info['total_bytes'])}")

    if verbose:
        print(f"\n  {'Column':<35} {'Type':<20} {'Nullable':<10}", end="")
        has_stats = bool(info["col_stats"])
        if has_stats:
            print(f"{'Nulls':<12} {'Null%':<8} {'Distinct':<10}", end="")
        print()
        print(f"  {'-' * 35} {'-' * 20} {'-' * 10}", end="")
        if has_stats:
            print(f"{'-' * 12} {'-' * 8} {'-' * 10}", end="")
        print()

        for col in info["columns"]:
            name = col["name"]
            print(f"  {name:<35} {col['type']:<20} {'yes' if col['nullable'] else 'no':<10}", end="")
            if has_stats and name in info["col_stats"]:
                stats = info["col_stats"][name]
                distinct_str = f"{stats['distinct']:,}" if stats["distinct"] is not None else "—"
                print(f"{stats['nulls']:<12,} {stats['null_pct']:<8} {distinct_str:<10}", end="")
            print()

    if info["sample"]:
        print(f"\n  Sample rows ({len(list(info['sample'].values())[0])} rows):")
        cols = list(info["sample"].keys())
        # Print header
        header = " | ".join(f"{c[:20]:<20}" for c in cols[:8])
        print(f"    {header}")
        print(f"    {'-' * len(header)}")
        n_rows = len(info["sample"][cols[0]])
        for i in range(n_rows):
            vals = []
            for c in cols[:8]:
                v = info["sample"][c][i]
                s = str(v) if v is not None else "NULL"
                vals.append(f"{s[:20]:<20}")
            print(f"    {' | '.join(vals)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--storage-root", default="/shared/storage/silver",
                        help="Silver storage root (default: /shared/storage/silver)")
    parser.add_argument("--domain", help="Filter to a specific domain (e.g. stocks, corporate/entity)")
    parser.add_argument("--table", help="Filter to a specific table name (e.g. dim_stock)")
    parser.add_argument("--sample", type=int, default=0, help="Show N sample rows per table")
    parser.add_argument("--summary-only", action="store_true", help="Show only the summary table, no column details")
    args = parser.parse_args()

    silver_root = Path(args.storage_root)
    if not silver_root.exists():
        print(f"Error: Silver root not found: {silver_root}")
        sys.exit(1)

    all_tables = _find_delta_tables(silver_root)
    if not all_tables:
        print(f"No Delta tables found under {silver_root}")
        sys.exit(0)

    # Apply filters
    if args.domain:
        domain_filter = args.domain.replace(".", "/")
        all_tables = [(r, p) for r, p in all_tables if r.startswith(domain_filter)]
    if args.table:
        all_tables = [(r, p) for r, p in all_tables if r.endswith(args.table)]

    if not all_tables:
        print(f"No tables matched filters (domain={args.domain}, table={args.table})")
        sys.exit(0)

    print(f"\nScanning {len(all_tables)} Silver table(s) under {silver_root}...\n")

    summaries: list[tuple[str, dict]] = []
    for rel_path, table_path in all_tables:
        try:
            info = _inspect_table(table_path, show_sample=args.sample)
            summaries.append((rel_path, info))
            if not args.summary_only:
                _print_table_summary(rel_path, info)
        except Exception as e:
            print(f"\n  ERROR reading {rel_path}: {e}")

    # Print overall summary
    print(f"\n\n{'=' * 80}")
    print(f"  SILVER LAYER SUMMARY")
    print(f"{'=' * 80}")
    print(f"\n  {'Table':<50} {'Rows':>12} {'Cols':>6} {'Size':>10}")
    print(f"  {'-' * 50} {'-' * 12} {'-' * 6} {'-' * 10}")

    total_rows = 0
    total_bytes = 0
    for rel_path, info in summaries:
        total_rows += info["row_count"]
        total_bytes += info["total_bytes"]
        print(f"  {rel_path:<50} {info['row_count']:>12,} {info['col_count']:>6} {_format_bytes(info['total_bytes']):>10}")

    print(f"  {'-' * 50} {'-' * 12} {'-' * 6} {'-' * 10}")
    print(f"  {'TOTAL':<50} {total_rows:>12,} {'':>6} {_format_bytes(total_bytes):>10}")
    print(f"\n  {len(summaries)} tables across {silver_root}\n")


if __name__ == "__main__":
    main()
