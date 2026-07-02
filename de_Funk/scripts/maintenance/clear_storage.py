#!/usr/bin/env python3
"""
Clear Bronze and/or Silver storage layers.

Usage:
    python -m scripts.maintenance.clear_storage              # Clear both layers
    python -m scripts.maintenance.clear_storage --bronze     # Clear bronze only
    python -m scripts.maintenance.clear_storage --silver     # Clear silver only
    python -m scripts.maintenance.clear_storage --dry-run    # Show what would be deleted
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def get_dir_stats(path: Path) -> tuple:
    """Get file count and total size for a directory."""
    if not path.exists():
        return 0, 0

    files = list(path.rglob("*"))
    file_count = len([f for f in files if f.is_file()])
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    return file_count, total_size


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def clear_directory(path: Path, dry_run: bool = False) -> tuple:
    """Clear all contents of a directory. Returns (files_deleted, bytes_freed)."""
    if not path.exists():
        return 0, 0

    file_count, total_size = get_dir_stats(path)

    if not dry_run:
        # Remove all contents but keep the directory
        for item in path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    return file_count, total_size


def main():
    parser = argparse.ArgumentParser(description="Clear Bronze and/or Silver storage")
    parser.add_argument("--bronze", action="store_true", help="Clear bronze layer only")
    parser.add_argument("--silver", action="store_true", help="Clear silver layer only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    # Default to both if neither specified
    clear_bronze = args.bronze or (not args.bronze and not args.silver)
    clear_silver = args.silver or (not args.bronze and not args.silver)

    storage_root = repo_root / "storage"
    bronze_path = storage_root / "bronze"
    silver_path = storage_root / "silver"

    print("=" * 60)
    print(" STORAGE CLEARING UTILITY")
    print("=" * 60)

    # Show current state
    layers_to_clear = []

    if clear_bronze:
        bronze_files, bronze_size = get_dir_stats(bronze_path)
        print(f"\n📦 BRONZE: {bronze_path}")
        print(f"   Files: {bronze_files:,}")
        print(f"   Size:  {format_size(bronze_size)}")
        if bronze_files > 0:
            layers_to_clear.append(("bronze", bronze_path, bronze_files, bronze_size))

    if clear_silver:
        silver_files, silver_size = get_dir_stats(silver_path)
        print(f"\n📦 SILVER: {silver_path}")
        print(f"   Files: {silver_files:,}")
        print(f"   Size:  {format_size(silver_size)}")
        if silver_files > 0:
            layers_to_clear.append(("silver", silver_path, silver_files, silver_size))

    if not layers_to_clear:
        print("\n✓ Nothing to clear - storage is already empty")
        return

    # Summary
    total_files = sum(f for _, _, f, _ in layers_to_clear)
    total_size = sum(s for _, _, _, s in layers_to_clear)

    print(f"\n{'=' * 60}")
    print(f" WILL DELETE: {total_files:,} files ({format_size(total_size)})")
    print(f"{'=' * 60}")

    if args.dry_run:
        print("\n[DRY RUN] No files were deleted")
        return

    # Confirmation
    if not args.yes:
        response = input("\nProceed with deletion? [y/N]: ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    # Clear
    for layer_name, path, files, size in layers_to_clear:
        print(f"\nClearing {layer_name}...")
        clear_directory(path, dry_run=False)
        print(f"  ✓ Deleted {files:,} files ({format_size(size)})")

    print(f"\n{'=' * 60}")
    print(f" DONE: Cleared {total_files:,} files ({format_size(total_size)})")
    print(f"{'=' * 60}")

    # Reminder
    print("\nTo rebuild:")
    print("  python -m scripts.run_full_pipeline --days 90 --max-tickers 100 --use-bulk-listing")


if __name__ == "__main__":
    main()
