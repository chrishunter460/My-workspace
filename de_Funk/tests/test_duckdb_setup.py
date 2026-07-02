#!/usr/bin/env python3
"""
Test DuckDB Setup - Validate views and run sample queries

This script validates that DuckDB views are properly configured and can query Silver data.

Usage:
    # Test default database
    python -m scripts.test.test_duckdb_setup

    # Test custom database
    python -m scripts.test.test_duckdb_setup --db-path custom/analytics.db

    # Show available views only
    python -m scripts.test.test_duckdb_setup --list-views

    # Run specific model tests
    python -m scripts.test.test_duckdb_setup --models stocks company

Tests:
1. Connection to database
2. View availability
3. Row counts per view
4. Sample queries
5. Cross-model joins
6. Performance benchmarks
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
import time
import logging

# Add repo root to path
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import duckdb
    import pandas as pd
except ImportError as e:
    print(f"❌ ERROR: Missing dependency: {e}")
    print("Install with: pip install duckdb pandas")
    sys.exit(1)

from de_funk.config import ConfigLoader
from de_funk.config.constants import DEFAULT_DUCKDB_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DuckDBTester:
    """Test DuckDB setup and views."""

    def __init__(self, db_path: Path):
        """
        Initialize DuckDB tester.

        Args:
            db_path: Path to DuckDB database
        """
        self.db_path = db_path
        self.conn = None
        self.test_results = {
            'connection': False,
            'views_found': [],
            'views_missing': [],
            'row_counts': {},
            'queries_passed': 0,
            'queries_failed': 0
        }

    def connect(self) -> bool:
        """Connect to DuckDB database."""
        if not self.db_path.exists():
            logger.error(f"❌ Database not found: {self.db_path}")
            logger.error("\nCreate it first with:")
            logger.error("  python -m scripts.setup.setup_duckdb_views")
            return False

        try:
            logger.info(f"Connecting to: {self.db_path}")
            self.conn = duckdb.connect(str(self.db_path), read_only=True)
            logger.info("✓ Connected successfully")
            self.test_results['connection'] = True
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def list_views(self) -> List[str]:
        """List all views in database."""
        try:
            result = self.conn.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'VIEW'
                ORDER BY table_schema, table_name
            """).fetchall()

            views = [f"{schema}.{table}" for schema, table in result]
            return views
        except Exception as e:
            logger.error(f"❌ Failed to list views: {e}")
            return []

    def check_view_exists(self, view_name: str) -> bool:
        """Check if a view exists."""
        try:
            self.conn.execute(f"SELECT 1 FROM {view_name} LIMIT 1")
            return True
        except:
            return False

    def count_rows(self, view_name: str) -> Optional[int]:
        """Count rows in a view."""
        try:
            result = self.conn.execute(f"SELECT COUNT(*) as cnt FROM {view_name}").fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.warning(f"⚠ Could not count {view_name}: {e}")
            return None

    def test_view(self, view_name: str) -> bool:
        """Test a single view."""
        try:
            # Check exists
            if not self.check_view_exists(view_name):
                logger.warning(f"⚠ View not found: {view_name}")
                self.test_results['views_missing'].append(view_name)
                return False

            # Count rows
            count = self.count_rows(view_name)
            if count is not None:
                self.test_results['row_counts'][view_name] = count
                logger.info(f"✓ {view_name}: {count:,} rows")
                self.test_results['views_found'].append(view_name)
                return True
            else:
                self.test_results['views_missing'].append(view_name)
                return False

        except Exception as e:
            logger.error(f"❌ {view_name}: {e}")
            self.test_results['views_missing'].append(view_name)
            return False

    def test_core_model(self):
        """Test core model views."""
        logger.info("\n" + "="*80)
        logger.info("CORE MODEL")
        logger.info("="*80)

        views = ['core.dim_calendar']
        for view in views:
            self.test_view(view)

    def test_company_model(self):
        """Test company model views."""
        logger.info("\n" + "="*80)
        logger.info("COMPANY MODEL")
        logger.info("="*80)

        views = [
            'company.dim_company',
            'company.dim_exchange',
            'company.fact_company_fundamentals',
            'company.fact_company_metrics'
        ]
        for view in views:
            self.test_view(view)

    def test_stocks_model(self):
        """Test stocks model views."""
        logger.info("\n" + "="*80)
        logger.info("STOCKS MODEL")
        logger.info("="*80)

        views = [
            'stocks.dim_stock',
            'stocks.fact_stock_prices',
            'stocks.fact_stock_technicals',
            'stocks.fact_stock_fundamentals'
        ]
        for view in views:
            self.test_view(view)

    def test_options_model(self):
        """Test options model views."""
        logger.info("\n" + "="*80)
        logger.info("OPTIONS MODEL")
        logger.info("="*80)

        views = [
            'options.dim_option',
            'options.fact_option_prices',
            'options.fact_option_greeks'
        ]
        for view in views:
            self.test_view(view)

    def test_etfs_model(self):
        """Test ETFs model views."""
        logger.info("\n" + "="*80)
        logger.info("ETFS MODEL")
        logger.info("="*80)

        views = [
            'etfs.dim_etf',
            'etfs.fact_etf_prices',
            'etfs.fact_etf_holdings'
        ]
        for view in views:
            self.test_view(view)

    def test_futures_model(self):
        """Test futures model views."""
        logger.info("\n" + "="*80)
        logger.info("FUTURES MODEL")
        logger.info("="*80)

        views = [
            'futures.dim_future',
            'futures.fact_future_prices',
            'futures.fact_future_margins'
        ]
        for view in views:
            self.test_view(view)

    def run_sample_query(self, name: str, sql: str):
        """Run a sample query and time it."""
        logger.info(f"\n--- {name} ---")
        logger.info(f"SQL: {sql[:100]}...")

        try:
            start = time.time()
            result = self.conn.execute(sql).fetchdf()
            elapsed = time.time() - start

            logger.info(f"✓ Returned {len(result):,} rows in {elapsed:.3f}s")

            # Show sample
            if len(result) > 0:
                print("\nSample (first 5 rows):")
                print(result.head(5))

            self.test_results['queries_passed'] += 1

        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            self.test_results['queries_failed'] += 1

    def test_sample_queries(self):
        """Run sample analytical queries."""
        logger.info("\n" + "="*80)
        logger.info("SAMPLE QUERIES")
        logger.info("="*80)

        # Query 1: Latest stock prices
        if self.check_view_exists('stocks.fact_stock_prices'):
            sql = """
SELECT
    ticker,
    trade_date,
    close,
    volume
FROM stocks.fact_stock_prices
ORDER BY trade_date DESC, ticker
LIMIT 10
"""
            self.run_sample_query("Latest Stock Prices", sql)

        # Query 2: Top companies by market cap
        if self.check_view_exists('company.dim_company'):
            sql = """
SELECT
    company_name,
    sector,
    market_cap,
    exchange_code
FROM company.dim_company
WHERE market_cap IS NOT NULL
ORDER BY market_cap DESC
LIMIT 10
"""
            self.run_sample_query("Top Companies by Market Cap", sql)

        # Query 3: Stock prices with company info (cross-model join)
        if (self.check_view_exists('stocks.fact_stock_prices') and
            self.check_view_exists('stocks.dim_stock') and
            self.check_view_exists('company.dim_company')):
            sql = """
SELECT
    p.ticker,
    p.trade_date,
    p.close,
    p.volume,
    c.company_name,
    c.sector,
    c.market_cap
FROM stocks.fact_stock_prices p
JOIN stocks.dim_stock s ON p.ticker = s.ticker
JOIN company.dim_company c ON s.company_id = c.company_id
WHERE p.trade_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY p.trade_date DESC, p.ticker
LIMIT 10
"""
            self.run_sample_query("Stock Prices with Company Info", sql)

        # Query 4: Helper view test (if available)
        if self.check_view_exists('helpers.stock_prices_enriched'):
            sql = """
SELECT *
FROM helpers.stock_prices_enriched
WHERE trade_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY trade_date DESC
LIMIT 10
"""
            self.run_sample_query("Helper View: Stock Prices Enriched", sql)

    def show_summary(self):
        """Show test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)

        logger.info(f"Database: {self.db_path}")
        logger.info(f"Connection: {'✓' if self.test_results['connection'] else '❌'}")
        logger.info(f"Views found: {len(self.test_results['views_found'])}")
        logger.info(f"Views missing: {len(self.test_results['views_missing'])}")
        logger.info(f"Queries passed: {self.test_results['queries_passed']}")
        logger.info(f"Queries failed: {self.test_results['queries_failed']}")

        if self.test_results['views_found']:
            logger.info("\n✓ Available views:")
            for view in sorted(self.test_results['views_found']):
                count = self.test_results['row_counts'].get(view, 0)
                logger.info(f"  {view}: {count:,} rows")

        if self.test_results['views_missing']:
            logger.info("\n⚠ Missing views (build models first):")
            for view in sorted(self.test_results['views_missing']):
                logger.info(f"  {view}")

        # Overall status
        if self.test_results['views_found']:
            logger.info("\n✓ DuckDB setup is working!")
        else:
            logger.warning("\n⚠ No views found - run setup first:")
            logger.warning("  python -m scripts.setup.setup_duckdb_views")

    def run_all_tests(self, models: Optional[List[str]] = None):
        """Run all tests."""
        if not self.connect():
            return False

        try:
            # Test models
            if models is None or 'core' in models:
                self.test_core_model()

            if models is None or 'company' in models:
                self.test_company_model()

            if models is None or 'stocks' in models:
                self.test_stocks_model()

            if models is None or 'options' in models:
                self.test_options_model()

            if models is None or 'etfs' in models:
                self.test_etfs_model()

            if models is None or 'futures' in models:
                self.test_futures_model()

            # Sample queries
            self.test_sample_queries()

            # Summary
            self.show_summary()

            return True

        finally:
            self.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test DuckDB setup and views",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--db-path',
        type=Path,
        help='Path to DuckDB database (default: from config)'
    )

    parser.add_argument(
        '--models',
        nargs='+',
        choices=['core', 'company', 'stocks', 'options', 'etfs', 'futures'],
        help='Test specific models only'
    )

    parser.add_argument(
        '--list-views',
        action='store_true',
        help='List available views and exit'
    )

    args = parser.parse_args()

    # Load configuration
    config = ConfigLoader().load()

    # Get database path
    if args.db_path:
        db_path = args.db_path
    else:
        db_path_str = getattr(config.connection.duckdb, 'database_path', DEFAULT_DUCKDB_PATH) if hasattr(config.connection, 'duckdb') else DEFAULT_DUCKDB_PATH
        db_path = Path(db_path_str)

    logger.info("="*80)
    logger.info("DUCKDB SETUP TEST")
    logger.info("="*80)
    logger.info(f"Database: {db_path}")
    logger.info("")

    # Create tester
    tester = DuckDBTester(db_path=db_path)

    # List views only
    if args.list_views:
        if tester.connect():
            views = tester.list_views()
            logger.info(f"\nAvailable views ({len(views)}):")
            for view in views:
                logger.info(f"  {view}")
            tester.close()
        return

    # Run tests
    tester.run_all_tests(models=args.models)


if __name__ == "__main__":
    main()
