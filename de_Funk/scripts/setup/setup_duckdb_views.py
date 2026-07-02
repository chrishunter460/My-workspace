#!/usr/bin/env python3
"""
Setup DuckDB Views for v2.0 Models

Creates a persistent DuckDB database with views pointing to Silver layer Delta/Parquet tables.
This is OPTIONAL for performance optimization - base measures work without it via schema aliases.

Usage:
    # Create fresh database with all views
    python -m scripts.setup.setup_duckdb_views

    # Update existing database (recreate views)
    python -m scripts.setup.setup_duckdb_views --update

    # Dry run (show SQL without executing)
    python -m scripts.setup.setup_duckdb_views --dry-run

    # Custom database path
    python -m scripts.setup.setup_duckdb_views --db-path custom/path/analytics.db

Features:
- Creates views for ALL v2.0 models (temporal, company, stocks, options, etfs, futures)
- Auto-detects Delta Lake vs Parquet format (uses delta_scan or read_parquet)
- Points views to Silver layer tables (zero data duplication)
- Creates alias views (stocks.fact_prices → securities.fact_security_prices) for DuckDB caching
- Backend-agnostic base measures work via schema aliases (DomainConfigLoaderV4)
- This script provides performance optimization by pre-creating database views
- Handles missing tables gracefully (skips if not built yet)
- Validates views after creation
- Shows table statistics

Note:
- Requires DuckDB delta extension for Delta Lake tables (auto-installed)
- Alias views here are DuckDB-specific performance optimization
- Functional aliasing (backend-agnostic) is handled by schema-level aliases
- Both Spark and DuckDB backends work via schema aliases
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

# Add repo root to path
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import duckdb
except ImportError:
    print("❌ ERROR: DuckDB not installed")
    print("Install it with: pip install duckdb")
    sys.exit(1)

from de_funk.config import ConfigLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DuckDBViewSetup:
    """Setup DuckDB views for v2.0 models."""

    def __init__(self, db_path: Path, config: ConfigLoader, repo_root: Path, storage_root: Optional[Path] = None):
        """
        Initialize DuckDB view setup.

        Args:
            db_path: Path to DuckDB database file
            config: Application configuration
            repo_root: Repository root path for resolving relative paths
            storage_root: Optional override for storage root (e.g., /shared/storage)
                         If not provided, uses repo_root/storage
        """
        self.db_path = db_path
        self.config = config
        self.repo_root = repo_root
        self.storage_root = storage_root  # Absolute path to storage (e.g., /shared/storage)
        self.conn = None
        self.created_views = []
        self.skipped_views = []

    def connect(self, read_only: bool = False):
        """Connect to DuckDB database."""
        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Connecting to DuckDB: {self.db_path}")
        self.conn = duckdb.connect(str(self.db_path), read_only=read_only)
        logger.info("✓ Connected")

        # Install and load Delta extension for reading Delta Lake tables
        try:
            self.conn.execute("INSTALL delta;")
            self.conn.execute("LOAD delta;")
            logger.info("✓ Delta extension loaded")
            self.delta_enabled = True
        except Exception as e:
            logger.warning(f"⚠ Delta extension not available: {e}")
            logger.warning("  Will fall back to reading Parquet files directly")
            self.delta_enabled = False

    def close(self):
        """Close DuckDB connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_bronze_path(self) -> Path:
        """Get Bronze layer path (absolute path)."""
        if self.storage_root:
            return self.storage_root / 'bronze'
        else:
            return self.repo_root / 'storage' / 'bronze'

    # Schema to directory mapping for legacy Silver layer paths
    # Some schemas have different directory names in the Silver layer
    SCHEMA_DIR_ALIASES = {
        'temporal': ['temporal', 'core'],      # temporal model data may be in 'core' dir
        'company': ['company', 'corporate'],   # company model data may be in 'corporate' dir
    }

    def get_silver_path(self, model: str) -> Path:
        """Get Silver layer path for model (absolute path).

        If storage_root is set (e.g., /shared/storage), uses that.
        Otherwise falls back to repo_root/storage.

        Handles legacy directory name aliases (e.g., 'temporal' -> 'core').
        """
        base_path = self.storage_root if self.storage_root else self.repo_root / 'storage'

        # Check if this model has directory aliases
        dirs_to_try = self.SCHEMA_DIR_ALIASES.get(model, [model])

        for dir_name in dirs_to_try:
            if self.storage_root:
                path = self.storage_root / 'silver' / dir_name
            else:
                relative_path = self.config.storage.get(f'{dir_name}_silver', f'storage/silver/{dir_name}')
                path = self.repo_root / relative_path

            if path.exists():
                logger.debug(f"get_silver_path('{model}'): Found at {path}")
                return path

        # Return primary path even if it doesn't exist (caller will handle)
        if self.storage_root:
            return self.storage_root / 'silver' / model
        else:
            relative_path = self.config.storage.get(f'{model}_silver', f'storage/silver/{model}')
            return self.repo_root / relative_path

    def create_view(self, schema: str, table: str, table_path: Path, dry_run: bool = False) -> bool:
        """
        Create a DuckDB view pointing to Delta Lake or Parquet files.

        Args:
            schema: Schema name (e.g., 'core', 'company', 'stocks')
            table: Table name (e.g., 'dim_calendar', 'dim_company')
            table_path: Path to Delta table or Parquet file/directory
            dry_run: If True, show SQL without executing

        Returns:
            True if view created, False if skipped
        """
        # Check if path exists - try multiple locations:
        # 1. Original path (may be local or shared)
        # 2. Flat structure (table directly under model folder)
        # 3. Shared NFS storage (cluster builds write here)
        paths_to_try = [table_path]

        # Try flat structure
        flat_path = table_path.parent.parent / table
        if flat_path != table_path:
            paths_to_try.append(flat_path)

        # Try shared storage paths (NFS mount from cluster builds)
        # Convert local path to shared path: storage/silver/X -> /shared/storage/silver/X
        path_str = str(table_path)
        if 'storage/silver/' in path_str and not path_str.startswith('/shared/'):
            # Extract relative part after storage/silver/
            rel_idx = path_str.find('storage/silver/')
            rel_path = path_str[rel_idx + len('storage/'):]  # silver/model/...
            shared_path = Path('/shared/storage') / rel_path
            paths_to_try.append(shared_path)
            # Also try shared flat path
            shared_flat = shared_path.parent.parent / table
            paths_to_try.append(shared_flat)

        # Find first existing path
        found_path = None
        for p in paths_to_try:
            if p.exists():
                found_path = p
                if p != table_path:
                    logger.debug(f"Using alternate path: {p}")
                break

        if not found_path:
            logger.warning(f"⚠ Skipping {schema}.{table} - path not found in any location")
            logger.debug(f"  Tried: {[str(p) for p in paths_to_try]}")
            self.skipped_views.append(f"{schema}.{table}")
            return False

        table_path = found_path

        # Check if this is a Delta table (has _delta_log directory)
        is_delta = (table_path / "_delta_log").exists() if table_path.is_dir() else False

        if is_delta and self.delta_enabled:
            # Use delta_scan for Delta tables
            read_sql = f"delta_scan('{table_path}')"
            format_used = "Delta"
        elif table_path.is_dir():
            # Check if directory has any parquet files
            parquet_files = list(table_path.glob("**/*.parquet"))
            if not parquet_files:
                logger.warning(f"⚠ Skipping {schema}.{table} - no parquet files in: {table_path}")
                self.skipped_views.append(f"{schema}.{table}")
                return False
            read_sql = f"read_parquet('{table_path}/**/*.parquet')"
            format_used = "Parquet"
        else:
            read_sql = f"read_parquet('{table_path}')"
            format_used = "Parquet"

        # Create schema if needed
        schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema};"

        # Create view SQL
        view_sql = f"""
CREATE OR REPLACE VIEW {schema}.{table} AS
SELECT * FROM {read_sql};
"""

        full_sql = schema_sql + view_sql

        if dry_run:
            print(f"\n-- {schema}.{table} [{format_used}]")
            print(full_sql)
            return True

        try:
            self.conn.execute(schema_sql)
            self.conn.execute(view_sql)
            logger.info(f"✓ Created view: {schema}.{table} [{format_used}]")
            self.created_views.append(f"{schema}.{table}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create {schema}.{table}: {e}")
            self.skipped_views.append(f"{schema}.{table}")
            return False

    def create_temporal_views(self, dry_run: bool = False):
        """Create views for temporal model (calendar dimension).

        Checks both 'temporal' and 'core' directories since the calendar
        dimension may be stored under either name depending on the build version.
        """
        logger.info("\n" + "="*80)
        logger.info("TEMPORAL MODEL VIEWS")
        logger.info("="*80)

        # Try multiple paths for calendar dimension (temporal vs core legacy naming)
        base_path = self.storage_root if self.storage_root else self.repo_root / 'storage'
        calendar_paths = [
            base_path / 'silver' / 'temporal' / 'dims' / 'dim_calendar',
            base_path / 'silver' / 'core' / 'dims' / 'dim_calendar',
        ]

        table_path = None
        for path in calendar_paths:
            if self._check_path_exists(path):
                table_path = path
                logger.debug(f"Found calendar dimension at: {path}")
                break

        if table_path:
            self.create_view(
                schema='temporal',
                table='dim_calendar',
                table_path=table_path,
                dry_run=dry_run
            )
        else:
            logger.warning(f"⚠ Skipping temporal.dim_calendar - not found at any of: {calendar_paths}")

    def create_geospatial_views(self, dry_run: bool = False):
        """Create views for geospatial model (geographic dimensions)."""
        logger.info("\n" + "="*80)
        logger.info("GEOSPATIAL MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('geospatial')

        # Dimensions (v3.0 schema)
        dimensions = [
            'dim_location',
            'dim_state',
            'dim_county',
            'dim_city'
        ]

        for dim in dimensions:
            self.create_view(
                schema='geospatial',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

    def create_company_views(self, dry_run: bool = False):
        """Create views for company model."""
        logger.info("\n" + "="*80)
        logger.info("COMPANY MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('company')

        # Dimensions (v3.0 schema)
        dimensions = [
            'dim_company'
        ]

        for dim in dimensions:
            self.create_view(
                schema='company',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

        # Facts (v3.0 schema - financial statement facts)
        facts = [
            'fact_income_statement',
            'fact_balance_sheet',
            'fact_cash_flow',
            'fact_earnings'
        ]

        for fact in facts:
            self.create_view(
                schema='company',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

    def create_securities_views(self, dry_run: bool = False):
        """Create views for master securities model (v3.0 normalized architecture).

        If securities-specific data doesn't exist but stocks data does,
        creates alias views pointing to stocks data for backward compatibility.
        """
        logger.info("\n" + "="*80)
        logger.info("SECURITIES MODEL VIEWS (Master)")
        logger.info("="*80)

        silver_path = self.get_silver_path('securities')
        stocks_path = self.get_silver_path('stocks')

        # Create securities schema
        if not dry_run:
            self.conn.execute("CREATE SCHEMA IF NOT EXISTS securities;")

        # Check if securities-specific data exists
        securities_dim_path = silver_path / 'dims' / 'dim_security'
        securities_fact_path = silver_path / 'facts' / 'fact_security_prices'

        # Check alternative paths (shared storage, flat structure)
        securities_paths_exist = self._check_path_exists(securities_dim_path) and self._check_path_exists(securities_fact_path)

        # Check if stocks data exists as fallback
        stocks_dim_path = stocks_path / 'dims' / 'dim_stock'
        stocks_fact_path = stocks_path / 'facts' / 'fact_stock_prices'
        stocks_paths_exist = self._check_path_exists(stocks_dim_path) and self._check_path_exists(stocks_fact_path)

        if securities_paths_exist:
            # Use actual securities data
            logger.info("Using securities-specific data")
            self.create_view(
                schema='securities',
                table='dim_security',
                table_path=securities_dim_path,
                dry_run=dry_run
            )
            self.create_view(
                schema='securities',
                table='fact_security_prices',
                table_path=securities_fact_path,
                dry_run=dry_run
            )
        elif stocks_paths_exist:
            # Fallback: Create alias views pointing to stocks data
            logger.info("Securities data not found, creating aliases from stocks data")

            # Create dim_security as alias to stocks.dim_stock
            self.create_view(
                schema='securities',
                table='dim_security',
                table_path=stocks_dim_path,
                dry_run=dry_run
            )

            # Create fact_security_prices as alias to stocks.fact_stock_prices
            self.create_view(
                schema='securities',
                table='fact_security_prices',
                table_path=stocks_fact_path,
                dry_run=dry_run
            )
        else:
            # No data available
            logger.warning("⚠ Neither securities nor stocks data found - skipping securities views")
            self.skipped_views.extend(["securities.dim_security", "securities.fact_security_prices"])

    def _check_path_exists(self, path: Path) -> bool:
        """Check if a path exists, including shared storage fallbacks."""
        if path.exists():
            return True

        # Check shared storage
        path_str = str(path)
        if 'storage/silver/' in path_str and not path_str.startswith('/shared/'):
            rel_idx = path_str.find('storage/silver/')
            rel_path = path_str[rel_idx + len('storage/'):]
            shared_path = Path('/shared/storage') / rel_path
            if shared_path.exists():
                return True

        return False

    def create_stocks_views(self, dry_run: bool = False):
        """Create views for stocks model (v3.0 normalized - FKs to securities)."""
        logger.info("\n" + "="*80)
        logger.info("STOCKS MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('stocks')

        # Dimensions (v3.0 schema - extends securities.dim_security, uses dims/ subdirectory)
        self.create_view(
            schema='stocks',
            table='dim_stock',
            table_path=silver_path / 'dims' / 'dim_stock',
            dry_run=dry_run
        )

        # Facts (v3.0 schema - stock-specific facts, prices are in securities, uses facts/ subdirectory)
        stock_facts = [
            'fact_stock_technicals',
            'fact_dividends',
            'fact_splits'
        ]

        for fact in stock_facts:
            self.create_view(
                schema='stocks',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

        # Create fact_stock_prices view (primary price data for stocks)
        self.create_view(
            schema='stocks',
            table='fact_stock_prices',
            table_path=silver_path / 'facts' / 'fact_stock_prices',
            dry_run=dry_run
        )

        # Alias views for backward compatibility
        alias_sql = """
-- Alias views for backward compatibility

-- fact_prices alias points to stocks.fact_stock_prices
CREATE OR REPLACE VIEW stocks.fact_prices AS
  SELECT * FROM stocks.fact_stock_prices;

-- dim_security alias points to stocks dimension
CREATE OR REPLACE VIEW stocks.dim_security AS
  SELECT * FROM stocks.dim_stock;
"""

        if dry_run:
            print(f"\n-- stocks aliases")
            print(alias_sql)
        else:
            try:
                self.conn.execute(alias_sql)
                logger.info("✓ Created alias views: fact_prices, dim_security")
                self.created_views.extend(["stocks.fact_prices", "stocks.dim_security"])
            except Exception as e:
                logger.warning(f"⚠ Could not create alias views: {e}")

    def create_options_views(self, dry_run: bool = False):
        """Create views for options model."""
        logger.info("\n" + "="*80)
        logger.info("OPTIONS MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('options')

        # Dimensions
        dimensions = [
            'dim_option'
        ]

        for dim in dimensions:
            self.create_view(
                schema='options',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

        # Facts
        facts = [
            'fact_option_prices',
            'fact_option_greeks'
        ]

        for fact in facts:
            self.create_view(
                schema='options',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

        # Alias views for inherited base securities measures
        alias_sql = """
-- Alias views for base securities compatibility
CREATE OR REPLACE VIEW options.fact_prices AS
  SELECT * FROM options.fact_option_prices;

CREATE OR REPLACE VIEW options.dim_security AS
  SELECT * FROM options.dim_option;
"""

        if dry_run:
            print(f"\n-- options aliases")
            print(alias_sql)
        else:
            try:
                self.conn.execute(alias_sql)
                logger.info("✓ Created alias views: fact_prices, dim_security")
                self.created_views.extend(["options.fact_prices", "options.dim_security"])
            except Exception as e:
                logger.warning(f"⚠ Could not create alias views: {e}")

    def create_etfs_views(self, dry_run: bool = False):
        """Create views for ETFs model."""
        logger.info("\n" + "="*80)
        logger.info("ETFS MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('etfs')

        # Dimensions
        dimensions = [
            'dim_etf'
        ]

        for dim in dimensions:
            self.create_view(
                schema='etfs',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

        # Facts
        facts = [
            'fact_etf_prices',
            'fact_etf_holdings'
        ]

        for fact in facts:
            self.create_view(
                schema='etfs',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

        # Alias views for inherited base securities measures
        alias_sql = """
-- Alias views for base securities compatibility
CREATE OR REPLACE VIEW etfs.fact_prices AS
  SELECT * FROM etfs.fact_etf_prices;

CREATE OR REPLACE VIEW etfs.dim_security AS
  SELECT * FROM etfs.dim_etf;
"""

        if dry_run:
            print(f"\n-- etfs aliases")
            print(alias_sql)
        else:
            try:
                self.conn.execute(alias_sql)
                logger.info("✓ Created alias views: fact_prices, dim_security")
                self.created_views.extend(["etfs.fact_prices", "etfs.dim_security"])
            except Exception as e:
                logger.warning(f"⚠ Could not create alias views: {e}")

    def create_futures_views(self, dry_run: bool = False):
        """Create views for futures model."""
        logger.info("\n" + "="*80)
        logger.info("FUTURES MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('futures')

        # Dimensions
        dimensions = [
            'dim_future'
        ]

        for dim in dimensions:
            self.create_view(
                schema='futures',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

        # Facts
        facts = [
            'fact_future_prices',
            'fact_future_margins'
        ]

        for fact in facts:
            self.create_view(
                schema='futures',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

        # Alias views for inherited base securities measures
        alias_sql = """
-- Alias views for base securities compatibility
CREATE OR REPLACE VIEW futures.fact_prices AS
  SELECT * FROM futures.fact_future_prices;

CREATE OR REPLACE VIEW futures.dim_security AS
  SELECT * FROM futures.dim_future;
"""

        if dry_run:
            print(f"\n-- futures aliases")
            print(alias_sql)
        else:
            try:
                self.conn.execute(alias_sql)
                logger.info("✓ Created alias views: fact_prices, dim_security")
                self.created_views.extend(["futures.fact_prices", "futures.dim_security"])
            except Exception as e:
                logger.warning(f"⚠ Could not create alias views: {e}")

    def create_forecast_views(self, dry_run: bool = False):
        """Create views for forecast model."""
        logger.info("\n" + "="*80)
        logger.info("FORECAST MODEL VIEWS")
        logger.info("="*80)

        silver_path = self.get_silver_path('forecast')

        # Dimensions (v3.0 schema)
        dimensions = [
            'dim_model_registry'
        ]

        for dim in dimensions:
            self.create_view(
                schema='forecast',
                table=dim,
                table_path=silver_path / 'dims' / dim,
                dry_run=dry_run
            )

        # Facts (v3.0 schema)
        facts = [
            'fact_forecast_price',
            'fact_forecast_volume',
            'fact_forecast_metrics'
        ]

        for fact in facts:
            self.create_view(
                schema='forecast',
                table=fact,
                table_path=silver_path / 'facts' / fact,
                dry_run=dry_run
            )

    def create_bronze_views(self, dry_run: bool = False):
        """
        Create views for all Bronze layer tables.

        Auto-discovers all Delta tables in bronze/ directory and creates views.
        Tables are organized by provider: bronze/{provider}/{table}
        Views are created as: bronze.{provider}_{table}
        """
        logger.info("\n" + "="*80)
        logger.info("BRONZE LAYER VIEWS")
        logger.info("="*80)

        bronze_path = self.get_bronze_path()

        if not bronze_path.exists():
            logger.warning(f"⚠ Bronze path not found: {bronze_path}")
            return

        # Create bronze schema
        if not dry_run:
            self.conn.execute("CREATE SCHEMA IF NOT EXISTS bronze;")

        # Auto-discover all Delta tables in bronze directory
        # Structure: bronze/{provider}/{table}/ or bronze/{table}/
        discovered_tables = []

        for item in bronze_path.iterdir():
            if not item.is_dir() or item.name.startswith('.'):
                continue

            # Check if this is a Delta table directly (bronze/{table}/)
            if (item / "_delta_log").exists():
                discovered_tables.append((None, item.name, item))
            else:
                # This might be a provider directory (bronze/{provider}/{table}/)
                for sub_item in item.iterdir():
                    if sub_item.is_dir() and not sub_item.name.startswith('.'):
                        if (sub_item / "_delta_log").exists():
                            discovered_tables.append((item.name, sub_item.name, sub_item))
                        # Also check for plain parquet files/directory
                        elif list(sub_item.glob("*.parquet")) or list(sub_item.glob("**/*.parquet")):
                            discovered_tables.append((item.name, sub_item.name, sub_item))

        if not discovered_tables:
            logger.info("No Bronze tables found to create views for")
            return

        logger.info(f"Discovered {len(discovered_tables)} Bronze tables")

        for provider, table_name, table_path in sorted(discovered_tables):
            # Create view name: provider_table or just table if no provider
            if provider:
                view_name = f"{provider}_{table_name}"
            else:
                view_name = table_name

            # Sanitize view name (replace dashes with underscores)
            view_name = view_name.replace('-', '_')

            self.create_view(
                schema='bronze',
                table=view_name,
                table_path=table_path,
                dry_run=dry_run
            )

    def create_helper_views(self, dry_run: bool = False):
        """Create helper views for common queries."""
        logger.info("\n" + "="*80)
        logger.info("HELPER VIEWS")
        logger.info("="*80)

        # First, check what columns exist in securities.fact_security_prices
        # to handle schema variations (trade_date vs date, volume_weighted may not exist)
        try:
            cols_result = self.conn.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'securities'
                AND table_name = 'fact_security_prices'
            """).fetchall()
            fact_cols = {r[0] for r in cols_result}

            # Determine date column name
            date_col = 'trade_date' if 'trade_date' in fact_cols else 'date'

            # Check if volume_weighted exists
            has_volume_weighted = 'volume_weighted' in fact_cols
        except Exception:
            # Default fallback
            date_col = 'date'
            has_volume_weighted = False

        # Build helper SQL with correct column names
        volume_weighted_col = "p.volume_weighted," if has_volume_weighted else ""

        helper_sql = f"""
CREATE OR REPLACE VIEW helpers.stock_prices_enriched AS
SELECT
    sec.ticker,
    p.{date_col} as trade_date,
    p.open,
    p.high,
    p.low,
    p.close,
    p.volume,
    {volume_weighted_col}
    c.company_name,
    c.sector,
    c.industry,
    s.market_cap,
    sec.exchange_code
FROM securities.fact_security_prices p
JOIN securities.dim_security sec ON p.security_id = sec.security_id
LEFT JOIN stocks.dim_stock s ON sec.security_id = s.security_id
LEFT JOIN company.dim_company c ON s.company_id = c.company_id
WHERE sec.asset_type = 'stocks';
"""

        if dry_run:
            print(f"\n-- helpers.stock_prices_enriched")
            print(helper_sql)
        else:
            try:
                self.conn.execute("CREATE SCHEMA IF NOT EXISTS helpers;")
                self.conn.execute(helper_sql)
                logger.info("✓ Created helper view: helpers.stock_prices_enriched")
                self.created_views.append("helpers.stock_prices_enriched")
            except Exception as e:
                logger.warning(f"⚠ Could not create stock_prices_enriched view: {e}")
                self.skipped_views.append("helpers.stock_prices_enriched")

    def validate_views(self):
        """Validate created views."""
        logger.info("\n" + "="*80)
        logger.info("VIEW VALIDATION")
        logger.info("="*80)

        for view_name in self.created_views:
            try:
                # Test query
                result = self.conn.execute(f"SELECT COUNT(*) as cnt FROM {view_name}").fetchone()
                count = result[0] if result else 0
                logger.info(f"✓ {view_name}: {count:,} rows")
            except Exception as e:
                logger.error(f"❌ {view_name}: {e}")

    def show_summary(self):
        """Show setup summary."""
        logger.info("\n" + "="*80)
        logger.info("SETUP SUMMARY")
        logger.info("="*80)
        logger.info(f"Database path: {self.db_path}")
        logger.info(f"Created views: {len(self.created_views)}")
        logger.info(f"Skipped views: {len(self.skipped_views)}")

        if self.created_views:
            logger.info("\n✓ Created:")
            for view in sorted(self.created_views):
                logger.info(f"  - {view}")

        if self.skipped_views:
            logger.info("\n⚠ Skipped (missing Parquet files):")
            for view in sorted(self.skipped_views):
                logger.info(f"  - {view}")

        logger.info("\n✓ DuckDB setup complete!")
        logger.info(f"\nConnect with:")
        logger.info(f"  python -c \"import duckdb; conn = duckdb.connect('{self.db_path}')\"")
        logger.info(f"\nQuery examples:")
        logger.info(f"  -- Silver layer (v3.0 normalized architecture)")
        logger.info(f"  SELECT * FROM securities.fact_security_prices LIMIT 10;")
        logger.info(f"  SELECT * FROM securities.dim_security LIMIT 10;")
        logger.info(f"  SELECT * FROM stocks.dim_stock LIMIT 10;")
        logger.info(f"  SELECT * FROM company.dim_company LIMIT 10;")
        logger.info(f"")
        logger.info(f"  -- Bronze layer (raw ingested data)")
        logger.info(f"  SELECT * FROM bronze.alpha_vantage_securities_prices_daily LIMIT 10;")
        logger.info(f"  SELECT * FROM bronze.chicago_crimes LIMIT 10;")

    def setup_all(self, dry_run: bool = False, include_bronze: bool = True):
        """Create all views.

        Args:
            dry_run: If True, show SQL without executing
            include_bronze: If True, create Bronze layer views (default: True)
        """
        if not dry_run:
            self.connect()

        try:
            # Bronze layer views (raw data)
            if include_bronze:
                self.create_bronze_views(dry_run=dry_run)

            # v3.0 Silver models (normalized architecture)
            self.create_temporal_views(dry_run=dry_run)
            self.create_geospatial_views(dry_run=dry_run)
            self.create_securities_views(dry_run=dry_run)  # Master securities - must be before stocks
            self.create_company_views(dry_run=dry_run)
            self.create_stocks_views(dry_run=dry_run)  # Stocks FKs to securities
            self.create_forecast_views(dry_run=dry_run)
            self.create_options_views(dry_run=dry_run)
            self.create_etfs_views(dry_run=dry_run)
            self.create_futures_views(dry_run=dry_run)

            # Helper views
            if not dry_run:
                self.create_helper_views(dry_run=dry_run)

            # Validate
            if not dry_run:
                self.validate_views()

            # Summary
            self.show_summary()

        finally:
            if not dry_run:
                self.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Setup DuckDB views for de_Funk v2.0 models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--db-path',
        type=Path,
        help='Path to DuckDB database (default: from config)'
    )

    parser.add_argument(
        '--storage-path',
        type=Path,
        help='Path to storage root (e.g., /shared/storage). Default: from run_config.json'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show SQL without executing'
    )

    parser.add_argument(
        '--update',
        action='store_true',
        help='Update existing database (recreate views)'
    )

    args = parser.parse_args()

    # Load configuration
    config = ConfigLoader().load()

    # Get storage path from run_config.json if not provided
    storage_root = None
    if args.storage_path:
        storage_root = args.storage_path
    else:
        # Try to load from run_config.json
        run_config_path = repo_root / 'configs' / 'pipelines' / 'run_config.json'
        if run_config_path.exists():
            import json
            with open(run_config_path) as f:
                run_config = json.load(f)
            storage_path_str = run_config.get('defaults', {}).get('storage_path')
            if storage_path_str:
                storage_root = Path(storage_path_str)
                logger.info(f"Using storage_path from run_config.json: {storage_root}")

    # Get database path
    if args.db_path:
        db_path = args.db_path
    else:
        # Use from config (DuckDB config or default)
from de_funk.config.constants import DEFAULT_DUCKDB_PATH
        db_path_str = config.connection.duckdb.database_path if hasattr(config.connection, 'duckdb') else DEFAULT_DUCKDB_PATH
        db_path = Path(db_path_str)

    logger.info("="*80)
    logger.info("DUCKDB VIEW SETUP (v2.0)")
    logger.info("="*80)
    logger.info(f"Database: {db_path}")
    logger.info(f"Storage root: {storage_root or 'repo-relative'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Mode: {'UPDATE' if args.update else 'CREATE'}")
    logger.info("")

    # Check if database exists
    if db_path.exists() and not args.update and not args.dry_run:
        logger.warning(f"⚠ Database already exists: {db_path}")
        logger.warning("Use --update to recreate views or --db-path to specify a different location")
        response = input("Continue and recreate views? [y/N]: ")
        if response.lower() != 'y':
            logger.info("Aborted")
            return

    # Setup views
    setup = DuckDBViewSetup(db_path=db_path, config=config, repo_root=repo_root, storage_root=storage_root)
    setup.setup_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
