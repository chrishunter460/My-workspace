#!/usr/bin/env python3
"""
Reset model storage to clean state.

This script removes all data from a model's Silver layer tables and optionally
reinitializes with empty schema-compliant tables.

⚠️  WARNING: This is a destructive operation! All data will be deleted.

Usage:
    # Reset single model (with confirmation)
    python -m scripts.reset_model --model stocks

    # Reset with backup first
    python -m scripts.reset_model --model stocks --backup

    # Reset and reinitialize empty tables
    python -m scripts.reset_model --model stocks --reinit

    # Reset specific tables only
    python -m scripts.reset_model --model stocks --tables fact_stock_prices dim_stock

    # Dry run (show what would be deleted)
    python -m scripts.reset_model --model stocks --dry-run

    # Force reset without confirmation
    python -m scripts.reset_model --model stocks --force
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import logging
import shutil
from datetime import datetime
import yaml


from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.models.registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelResetter:
    """Reset model storage to clean state."""

    def __init__(self, model_name: str, config_dir: str = "configs/models"):
        """
        Initialize model resetter.

        Args:
            model_name: Name of the model (e.g., 'stocks', 'company')
            config_dir: Directory containing model configs
        """
        self.model_name = model_name
        self.config_dir = Path(config_dir)

        # Load model config
        self.registry = ModelRegistry(str(self.config_dir))
        self.model_cfg = self.registry.get_model_config(model_name)

        logger.info(f"Initialized resetter for model: {model_name}")

    def reset_model(
        self,
        tables: Optional[List[str]] = None,
        backup: bool = False,
        reinit: bool = False,
        dry_run: bool = False,
        force: bool = False
    ) -> bool:
        """
        Reset model storage.

        Args:
            tables: Specific tables to reset (None = all tables)
            backup: Whether to backup data before reset
            reinit: Whether to reinitialize empty tables after reset
            dry_run: If True, only show what would be done
            force: Skip confirmation prompt

        Returns:
            True if reset successful, False otherwise
        """
        logger.info(f"=== Resetting model: {self.model_name} ===")

        # Get tables to reset
        if tables:
            tables_to_reset = tables
        else:
            tables_to_reset = self._get_all_tables()

        if not tables_to_reset:
            logger.error("No tables found to reset")
            return False

        logger.info(f"Tables to reset: {', '.join(tables_to_reset)}")

        # Get storage root
        storage_root = Path(self.model_cfg['storage']['root'])
        logger.info(f"Storage root: {storage_root}")

        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            return self._dry_run_report(tables_to_reset, backup, reinit)

        # Confirmation prompt
        if not force:
            if not self._confirm_reset(tables_to_reset, storage_root):
                logger.info("Reset cancelled by user")
                return False

        try:
            # Step 1: Backup if requested
            if backup:
                backup_path = self._backup_model(tables_to_reset, storage_root)
                logger.info(f"Backup created at: {backup_path}")

            # Step 2: Delete tables
            for table_name in tables_to_reset:
                self._delete_table(table_name, storage_root)

            # Step 3: Reinitialize if requested
            if reinit:
                for table_name in tables_to_reset:
                    self._reinitialize_table(table_name, storage_root)

            # Summary
            logger.info(f"✓ Reset complete for model: {self.model_name}")
            logger.info(f"  Tables reset: {len(tables_to_reset)}")
            if backup:
                logger.info(f"  Backup location: {backup_path}")
            if reinit:
                logger.info(f"  Empty tables created: {len(tables_to_reset)}")

            return True

        except Exception as e:
            logger.error(f"Reset failed: {e}", exc_info=True)
            return False

    def _get_all_tables(self) -> List[str]:
        """Get all table names in the model."""
        schema = self.model_cfg.get('schema', {})
        dimensions = list(schema.get('dimensions', {}).keys())
        facts = list(schema.get('facts', {}).keys())
        return dimensions + facts

    def _get_table_path(self, table_name: str) -> Path:
        """Get physical path for a table."""
        schema = self.model_cfg.get('schema', {})

        # Check dimensions
        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        # Check facts
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(f"Table '{table_name}' not found in model schema")

        storage_root = Path(self.model_cfg['storage']['root'])
        return storage_root / relative_path

    def _is_delta_table(self, path: Path) -> bool:
        """Check if path is a Delta table."""
        return path.exists() and (path / "_delta_log").exists()

    def _confirm_reset(self, tables: List[str], storage_root: Path) -> bool:
        """
        Prompt user for confirmation.

        Args:
            tables: List of tables to reset
            storage_root: Storage root path

        Returns:
            True if user confirms, False otherwise
        """
        print("\n" + "=" * 70)
        print("⚠️  WARNING: DESTRUCTIVE OPERATION")
        print("=" * 70)
        print(f"\nModel: {self.model_name}")
        print(f"Storage: {storage_root}")
        print(f"\nThe following {len(tables)} table(s) will be DELETED:")
        for table in tables:
            table_path = self._get_table_path(table)
            is_delta = self._is_delta_table(table_path)
            format_str = "Delta" if is_delta else "Parquet"
            exists_str = "EXISTS" if table_path.exists() else "NOT FOUND"
            print(f"  - {table} ({format_str}) [{exists_str}]")

        print("\n⚠️  ALL DATA IN THESE TABLES WILL BE PERMANENTLY DELETED!")
        print("\nThis action cannot be undone unless you have backups.")
        print("=" * 70)

        response = input("\nType 'DELETE' to confirm: ")
        return response.strip() == 'DELETE'

    def _backup_model(self, tables: List[str], storage_root: Path) -> Path:
        """
        Backup model data before reset.

        Args:
            tables: Tables to backup
            storage_root: Storage root path

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = storage_root.parent / f"{storage_root.name}_backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating backup at: {backup_dir}")

        for table_name in tables:
            table_path = self._get_table_path(table_name)

            if not table_path.exists():
                logger.warning(f"  Skipping {table_name} (does not exist)")
                continue

            # Backup path
            backup_table_path = backup_dir / table_path.relative_to(storage_root)

            # Copy table
            logger.info(f"  Backing up {table_name}...")
            shutil.copytree(table_path, backup_table_path)

        return backup_dir

    def _delete_table(self, table_name: str, storage_root: Path):
        """
        Delete a table from storage.

        Args:
            table_name: Table name
            storage_root: Storage root path
        """
        table_path = self._get_table_path(table_name)

        if not table_path.exists():
            logger.warning(f"  Table {table_name} does not exist, skipping")
            return

        is_delta = self._is_delta_table(table_path)
        format_str = "Delta" if is_delta else "Parquet"

        logger.info(f"  Deleting {table_name} ({format_str})...")

        # Delete the directory
        shutil.rmtree(table_path)

        logger.info(f"  ✓ Deleted {table_name}")

    def _reinitialize_table(self, table_name: str, storage_root: Path):
        """
        Reinitialize empty table with proper structure.

        Args:
            table_name: Table name
            storage_root: Storage root path
        """
        table_path = self._get_table_path(table_name)

        logger.info(f"  Reinitializing {table_name}...")

        # Create directory
        table_path.mkdir(parents=True, exist_ok=True)

        # Create a .gitkeep or README to mark as initialized
        readme_path = table_path / "README.md"
        with open(readme_path, 'w') as f:
            f.write(f"# {table_name}\n\n")
            f.write(f"This table is part of the `{self.model_name}` model.\n\n")
            f.write("Table initialized but empty. No data files present.\n")

        logger.info(f"  ✓ Initialized {table_name}")

    def _dry_run_report(self, tables: List[str], backup: bool, reinit: bool) -> bool:
        """
        Show what would be done in dry run.

        Args:
            tables: Tables to reset
            backup: Whether backup would be created
            reinit: Whether tables would be reinitialized

        Returns:
            True (dry run always succeeds)
        """
        storage_root = Path(self.model_cfg['storage']['root'])

        print("\n" + "=" * 70)
        print("DRY RUN - No changes will be made")
        print("=" * 70)
        print(f"\nModel: {self.model_name}")
        print(f"Storage: {storage_root}")

        print(f"\nWould reset {len(tables)} table(s):")
        for table in tables:
            table_path = self._get_table_path(table)
            is_delta = self._is_delta_table(table_path)
            format_str = "Delta" if is_delta else "Parquet"
            exists_str = "EXISTS" if table_path.exists() else "NOT FOUND"
            size_str = self._get_dir_size(table_path) if table_path.exists() else "0 B"
            print(f"  - {table} ({format_str}) [{exists_str}] - {size_str}")

        print("\nActions that would be performed:")
        if backup:
            print("  1. ✓ Create backup of existing data")
        else:
            print("  1. ✗ Skip backup (not requested)")

        print("  2. ✓ Delete all table data")

        if reinit:
            print("  3. ✓ Reinitialize empty table directories")
        else:
            print("  3. ✗ Skip reinitialization (not requested)")

        print("\n" + "=" * 70)

        return True

    def _get_dir_size(self, path: Path) -> str:
        """Get human-readable directory size."""
        if not path.exists():
            return "0 B"

        total = 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size

        # Convert to human readable
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if total < 1024.0:
                return f"{total:.1f} {unit}"
            total /= 1024.0

        return f"{total:.1f} PB"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reset model storage to clean state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--model',
        required=True,
        help='Model name (e.g., stocks, company, options)'
    )

    parser.add_argument(
        '--tables',
        nargs='+',
        help='Specific tables to reset (default: all tables)'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup before reset'
    )

    parser.add_argument(
        '--reinit',
        action='store_true',
        help='Reinitialize empty tables after reset'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt (dangerous!)'
    )

    parser.add_argument(
        '--config-dir',
        default='configs/models',
        help='Directory containing model configs (default: configs/models)'
    )

    args = parser.parse_args()

    try:
        # Initialize resetter
        resetter = ModelResetter(
            model_name=args.model,
            config_dir=args.config_dir
        )

        # Reset model
        success = resetter.reset_model(
            tables=args.tables,
            backup=args.backup,
            reinit=args.reinit,
            dry_run=args.dry_run,
            force=args.force
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
