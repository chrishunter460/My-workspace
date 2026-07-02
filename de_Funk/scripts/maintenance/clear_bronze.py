#!/usr/bin/env python3
"""
Clear all bronze layer data.

This script completely wipes the storage/bronze/ directory.
Use with caution - this is destructive and cannot be undone!

Usage:
    python -m scripts.maintenance.clear_bronze           # Interactive confirmation
    python -m scripts.maintenance.clear_bronze --yes     # Skip confirmation
    python -m scripts.maintenance.clear_bronze --list    # Just list what would be deleted
"""

import sys
import shutil
import argparse
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def list_bronze_contents(bronze_root: Path):
    """List all contents in bronze directory."""
    if not bronze_root.exists():
        return []

    # Get all subdirectories and files
    items = []
    for item in bronze_root.iterdir():
        if item.is_dir():
            # Count files recursively
            file_count = sum(1 for _ in item.rglob('*') if _.is_file())
            items.append((item, 'directory', file_count))
        else:
            items.append((item, 'file', 1))

    return sorted(items, key=lambda x: x[0].name)


def format_size(path: Path):
    """Get human-readable size of path."""
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())

    # Convert to human readable
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def confirm_action(prompt: str) -> bool:
    """Ask user for confirmation."""
    response = input(f"{prompt} (yes/no): ").strip().lower()
    return response in ['yes', 'y']


def clear_bronze(bronze_root: Path, skip_confirm: bool = False, list_only: bool = False):
    """Clear all bronze layer data."""

    print("=" * 80)
    print("CLEAR BRONZE LAYER")
    print("=" * 80)
    print()

    if not bronze_root.exists():
        print(f"Bronze directory does not exist: {bronze_root}")
        print("Nothing to clear.")
        return

    # List contents
    items = list_bronze_contents(bronze_root)

    if not items:
        print(f"Bronze directory is empty: {bronze_root}")
        print("Nothing to clear.")
        return

    # Show what will be deleted
    print(f"Bronze directory: {bronze_root}")
    print()
    print("The following will be DELETED:")
    print("-" * 80)

    total_files = 0
    for item_path, item_type, file_count in items:
        size = format_size(item_path)
        if item_type == 'directory':
            print(f"  📁 {item_path.name}/")
            print(f"     ({file_count:,} files, {size})")
            total_files += file_count
        else:
            print(f"  📄 {item_path.name}")
            print(f"     ({size})")
            total_files += 1

    print("-" * 80)
    print(f"Total: {len(items)} items, {total_files:,} files")
    print()

    if list_only:
        print("List-only mode - not deleting anything.")
        return

    # Confirm
    if not skip_confirm:
        print("⚠️  WARNING: This will permanently delete all bronze data!")
        print("⚠️  This action cannot be undone!")
        print()
        if not confirm_action("Are you sure you want to delete ALL bronze data?"):
            print("Aborted.")
            sys.exit(0)

    # Delete everything
    print()
    print("Deleting bronze data...")
    print("-" * 80)

    deleted_count = 0
    for item_path, item_type, _ in items:
        try:
            print(f"  → Deleting: {item_path.name}")
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
            print(f"  ✓ Deleted: {item_path.name}")
            deleted_count += 1
        except Exception as e:
            print(f"  ✗ Failed to delete {item_path.name}: {e}")

    print("-" * 80)
    print(f"✓ Deleted {deleted_count}/{len(items)} items")
    print()
    print("Bronze layer cleared successfully!")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Clear all bronze layer data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive confirmation
  python -m scripts.maintenance.clear_bronze

  # Skip confirmation (dangerous!)
  python -m scripts.maintenance.clear_bronze --yes

  # Just list what would be deleted
  python -m scripts.maintenance.clear_bronze --list
        """
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt (use with caution!)'
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List contents without deleting'
    )

    args = parser.parse_args()

    # Get bronze root
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root()
    bronze_root = ctx.repo / "storage" / "bronze"

    # Clear bronze
    clear_bronze(bronze_root, skip_confirm=args.yes, list_only=args.list)


if __name__ == "__main__":
    main()
