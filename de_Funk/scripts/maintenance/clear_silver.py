#!/usr/bin/env python3
"""
Clear all silver layer data.

This script completely wipes the storage/silver/ directory.
Use with caution - this is destructive and cannot be undone!

Usage:
    python -m scripts.maintenance.clear_silver           # Interactive confirmation
    python -m scripts.maintenance.clear_silver --yes     # Skip confirmation
    python -m scripts.maintenance.clear_silver --list    # Just list what would be deleted
"""

import sys
import shutil
import argparse
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def list_silver_contents(silver_root: Path):
    """List all contents in silver directory."""
    if not silver_root.exists():
        return []

    # Get all subdirectories and files
    items = []
    for item in silver_root.iterdir():
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


def clear_silver(silver_root: Path, skip_confirm: bool = False, list_only: bool = False):
    """Clear all silver layer data."""

    print("=" * 80)
    print("CLEAR SILVER LAYER")
    print("=" * 80)
    print()

    if not silver_root.exists():
        print(f"Silver directory does not exist: {silver_root}")
        print("Nothing to clear.")
        return

    # List contents
    items = list_silver_contents(silver_root)

    if not items:
        print(f"Silver directory is empty: {silver_root}")
        print("Nothing to clear.")
        return

    # Show what will be deleted
    print(f"Silver directory: {silver_root}")
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
        print("⚠️  WARNING: This will permanently delete all silver layer models!")
        print("⚠️  This action cannot be undone!")
        print()
        if not confirm_action("Are you sure you want to delete ALL silver data?"):
            print("Aborted.")
            sys.exit(0)

    # Delete everything
    print()
    print("Deleting silver data...")
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
    print("Silver layer cleared successfully!")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Clear all silver layer data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive confirmation
  python -m scripts.maintenance.clear_silver

  # Skip confirmation (dangerous!)
  python -m scripts.maintenance.clear_silver --yes

  # Just list what would be deleted
  python -m scripts.maintenance.clear_silver --list
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

    # Get silver root
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root()
    silver_root = ctx.repo / "storage" / "silver"

    # Clear silver
    clear_silver(silver_root, skip_confirm=args.yes, list_only=args.list)


if __name__ == "__main__":
    main()
