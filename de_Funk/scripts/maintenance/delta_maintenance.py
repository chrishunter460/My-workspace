#!/usr/bin/env python
"""
Delta Lake Maintenance Script.

Performs maintenance operations on Delta Lake tables:
- VACUUM: Remove old files beyond retention period
- OPTIMIZE: Compact small files and Z-ORDER for query performance

This should be run periodically (weekly) to prevent disk bloat from
the "always adding" approach with Delta merge operations.

Usage:
    # Vacuum all Bronze tables (remove files older than 7 days)
    python -m scripts.maintenance.delta_maintenance --vacuum

    # Optimize all Bronze tables
    python -m scripts.maintenance.delta_maintenance --optimize

    # Full maintenance (vacuum + optimize)
    python -m scripts.maintenance.delta_maintenance --all

    # Specific table only
    python -m scripts.maintenance.delta_maintenance --table securities_reference --all

    # Dry run (show what would be done)
    python -m scripts.maintenance.delta_maintenance --all --dry-run

Author: de_Funk Team
Date: December 2025
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def get_delta_tables(storage_cfg: dict, layer: str = "bronze") -> list:
    """
    Find all Delta Lake tables in a storage layer.

    Args:
        storage_cfg: Storage configuration
        layer: "bronze" or "silver"

    Returns:
        List of (table_name, path) tuples
    """
    root = Path(storage_cfg["roots"][layer])
    tables = []

    if not root.exists():
        return tables

    for table_dir in root.iterdir():
        if table_dir.is_dir():
            delta_log = table_dir / "_delta_log"
            if delta_log.exists():
                tables.append((table_dir.name, str(table_dir)))

    return tables


def vacuum_table(spark, path: str, retention_hours: int = 168, dry_run: bool = False):
    """
    Vacuum a Delta table to remove old files.

    Args:
        spark: SparkSession
        path: Path to Delta table
        retention_hours: Files older than this are removed (default: 168 = 7 days)
        dry_run: If True, only show what would be done
    """
    from delta.tables import DeltaTable

    try:
        dt = DeltaTable.forPath(spark, path)

        if dry_run:
            # Dry run - show files that would be removed
            logger.info(f"  [DRY RUN] Would vacuum files older than {retention_hours} hours")
            return True

        # Disable safety check for shorter retention (if needed)
        spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")

        # Run vacuum
        dt.vacuum(retention_hours)

        logger.info(f"  Vacuumed successfully (retention: {retention_hours} hours)")
        return True

    except Exception as e:
        logger.error(f"  Vacuum failed: {e}")
        return False


def optimize_table(spark, path: str, zorder_cols: list = None, dry_run: bool = False):
    """
    Optimize a Delta table (compact small files).

    Args:
        spark: SparkSession
        path: Path to Delta table
        zorder_cols: Optional columns to Z-ORDER by for query performance
        dry_run: If True, only show what would be done
    """
    from delta.tables import DeltaTable

    try:
        dt = DeltaTable.forPath(spark, path)

        if dry_run:
            if zorder_cols:
                logger.info(f"  [DRY RUN] Would optimize with Z-ORDER on: {zorder_cols}")
            else:
                logger.info(f"  [DRY RUN] Would compact small files")
            return True

        if zorder_cols:
            dt.optimize().executeZOrderBy(*zorder_cols)
            logger.info(f"  Optimized with Z-ORDER on: {zorder_cols}")
        else:
            dt.optimize().executeCompaction()
            logger.info(f"  Compacted small files")

        return True

    except Exception as e:
        logger.error(f"  Optimize failed: {e}")
        return False


def get_table_stats(spark, path: str) -> dict:
    """
    Get statistics for a Delta table.

    Args:
        spark: SparkSession
        path: Path to Delta table

    Returns:
        Dictionary with table statistics
    """
    from delta.tables import DeltaTable

    try:
        dt = DeltaTable.forPath(spark, path)
        history = dt.history(1).collect()

        # Count files in _delta_log
        delta_log = Path(path) / "_delta_log"
        log_files = list(delta_log.glob("*.json"))

        # Get data files
        data_files = list(Path(path).glob("*.parquet"))
        partition_files = list(Path(path).rglob("**/*.parquet"))

        return {
            "version": history[0]["version"] if history else 0,
            "log_files": len(log_files),
            "data_files": len(partition_files),
            "last_operation": history[0]["operation"] if history else "unknown",
        }
    except Exception as e:
        return {"error": str(e)}


# Default Z-ORDER columns for known tables (optimizes common query patterns)
ZORDER_COLUMNS = {
    "securities_reference": ["ticker"],
    "securities_prices_daily": ["ticker", "trade_date"],
    "company_income_statements": ["ticker", "fiscal_date_ending"],
    "company_balance_sheets": ["ticker", "fiscal_date_ending"],
    "company_cash_flows": ["ticker", "fiscal_date_ending"],
    "company_earnings": ["ticker", "fiscal_date_ending"],
}


def main():
    parser = argparse.ArgumentParser(
        description="Delta Lake maintenance operations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--vacuum', action='store_true', help='Run VACUUM to remove old files')
    parser.add_argument('--optimize', action='store_true', help='Run OPTIMIZE to compact files')
    parser.add_argument('--all', action='store_true', help='Run both vacuum and optimize')
    parser.add_argument('--table', type=str, help='Specific table name to process')
    parser.add_argument('--layer', type=str, default='bronze', choices=['bronze', 'silver'],
                        help='Storage layer (default: bronze)')
    parser.add_argument('--retention-hours', type=int, default=168,
                        help='Vacuum retention in hours (default: 168 = 7 days)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    parser.add_argument('--stats-only', action='store_true', help='Only show table statistics')

    args = parser.parse_args()

    if not args.vacuum and not args.optimize and not args.all and not args.stats_only:
        parser.print_help()
        print("\nError: Specify at least one action: --vacuum, --optimize, --all, or --stats-only")
        sys.exit(1)

    setup_logging()

    print("=" * 70)
    print("DELTA LAKE MAINTENANCE")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Layer: {args.layer}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()

    # Initialize context
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root(connection_type="spark")

    # Get tables
    tables = get_delta_tables(ctx.storage, args.layer)

    if args.table:
        tables = [(name, path) for name, path in tables if name == args.table]
        if not tables:
            print(f"Table '{args.table}' not found in {args.layer} layer")
            sys.exit(1)

    if not tables:
        print(f"No Delta Lake tables found in {args.layer} layer")
        sys.exit(0)

    print(f"Found {len(tables)} Delta Lake table(s):\n")

    # Process each table
    results = {"vacuum": [], "optimize": [], "errors": []}

    for table_name, table_path in tables:
        print(f"Table: {table_name}")
        print(f"  Path: {table_path}")

        # Show stats
        stats = get_table_stats(ctx.spark, table_path)
        if "error" not in stats:
            print(f"  Version: {stats['version']}")
            print(f"  Log files: {stats['log_files']}")
            print(f"  Data files: {stats['data_files']}")
            print(f"  Last operation: {stats['last_operation']}")

        if args.stats_only:
            print()
            continue

        # Vacuum
        if args.vacuum or args.all:
            print(f"  Running VACUUM...")
            success = vacuum_table(ctx.spark, table_path, args.retention_hours, args.dry_run)
            if success:
                results["vacuum"].append(table_name)
            else:
                results["errors"].append((table_name, "vacuum"))

        # Optimize
        if args.optimize or args.all:
            print(f"  Running OPTIMIZE...")
            zorder_cols = ZORDER_COLUMNS.get(table_name)
            success = optimize_table(ctx.spark, table_path, zorder_cols, args.dry_run)
            if success:
                results["optimize"].append(table_name)
            else:
                results["errors"].append((table_name, "optimize"))

        print()

    # Summary
    if not args.stats_only:
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        if args.dry_run:
            print("DRY RUN - no changes were made")
        if results["vacuum"]:
            print(f"Vacuumed: {len(results['vacuum'])} table(s)")
        if results["optimize"]:
            print(f"Optimized: {len(results['optimize'])} table(s)")
        if results["errors"]:
            print(f"Errors: {len(results['errors'])}")
            for table, op in results["errors"]:
                print(f"  - {table} ({op})")

    print("\nDone!")


if __name__ == "__main__":
    main()
