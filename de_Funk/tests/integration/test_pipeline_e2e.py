#!/usr/bin/env python3
"""
End-to-end pipeline test: Ingestion → Silver → Gold → UI

This script tests the complete data pipeline:
1. Bronze: Generate/validate test data (ingestion)
2. Silver: Build model tables (transformation)
3. Gold: Calculate measures (aggregation)
4. UI: Test query patterns (visualization ready)

Usage:
    # Full pipeline test
    python -m scripts.test_pipeline_e2e --model equity

    # Test specific stages
    python -m scripts.test_pipeline_e2e --model equity --stages bronze silver

    # Generate sample data and run pipeline
    python -m scripts.test_pipeline_e2e --model equity --generate-sample

    # Quick test with minimal data
    python -m scripts.test_pipeline_e2e --model equity --quick

    # Verbose output
    python -m scripts.test_pipeline_e2e --model equity --verbose
"""

import sys
from pathlib import Path

import argparse
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta
import time
import json

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
from de_funk.core.duckdb_connection import DuckDBConnection
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

from de_funk.models.registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineE2ETester:
    """End-to-end pipeline tester."""

    def __init__(
        self,
        model_name: str,
        config_dir: str = "configs/models",
        bronze_path: Optional[str] = None
    ):
        """
        Initialize pipeline tester.

        Args:
            model_name: Model name (e.g., 'equity')
            config_dir: Model config directory
            bronze_path: Bronze layer path (optional)
        """
        self.model_name = model_name
        self.config_dir = Path(config_dir)
        self.bronze_path = Path(bronze_path) if bronze_path else Path("storage/bronze/test")

        # Load model
        self.registry = ModelRegistry(str(self.config_dir))
        self.model_cfg = self.registry.get_model_config(model_name)

        # Initialize connection
        self.conn = None
        if DUCKDB_AVAILABLE:
            self.conn = DuckDBConnection()

        # Test results
        self.results = {
            'bronze': {},
            'silver': {},
            'gold': {},
            'ui': {},
            'overall': {'start_time': None, 'end_time': None, 'success': False}
        }

        logger.info(f"Initialized E2E tester for model: {model_name}")

    def run_full_pipeline(
        self,
        stages: List[str] = None,
        generate_sample: bool = False,
        quick: bool = False,
        verbose: bool = False
    ) -> bool:
        """
        Run full pipeline test.

        Args:
            stages: Stages to test (default: all)
            generate_sample: Generate sample data before testing
            quick: Quick test with minimal data
            verbose: Verbose output

        Returns:
            True if all tests pass, False otherwise
        """
        if verbose:
            logger.setLevel(logging.DEBUG)

        self.results['overall']['start_time'] = datetime.now()

        logger.info("=" * 70)
        logger.info("END-TO-END PIPELINE TEST")
        logger.info("=" * 70)
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Quick mode: {quick}")
        logger.info(f"Generate sample: {generate_sample}")

        # Default to all stages
        if not stages:
            stages = ['bronze', 'silver', 'gold', 'ui']

        try:
            # Stage 1: Bronze (Ingestion)
            if 'bronze' in stages:
                logger.info("\n" + "=" * 70)
                logger.info("STAGE 1: BRONZE LAYER (Ingestion)")
                logger.info("=" * 70)

                if generate_sample:
                    logger.info("Generating sample data...")
                    self._generate_sample_data(quick=quick)

                bronze_success = self._test_bronze_layer()
                self.results['bronze']['success'] = bronze_success

                if not bronze_success:
                    logger.error("Bronze layer test failed - stopping pipeline")
                    return False

            # Stage 2: Silver (Transformation)
            if 'silver' in stages:
                logger.info("\n" + "=" * 70)
                logger.info("STAGE 2: SILVER LAYER (Transformation)")
                logger.info("=" * 70)

                silver_success = self._test_silver_layer()
                self.results['silver']['success'] = silver_success

                if not silver_success:
                    logger.error("Silver layer test failed - stopping pipeline")
                    return False

            # Stage 3: Gold (Aggregation)
            if 'gold' in stages:
                logger.info("\n" + "=" * 70)
                logger.info("STAGE 3: GOLD LAYER (Aggregation)")
                logger.info("=" * 70)

                gold_success = self._test_gold_layer()
                self.results['gold']['success'] = gold_success

                if not gold_success:
                    logger.error("Gold layer test failed - stopping pipeline")
                    return False

            # Stage 4: UI (Queries)
            if 'ui' in stages:
                logger.info("\n" + "=" * 70)
                logger.info("STAGE 4: UI LAYER (Query Patterns)")
                logger.info("=" * 70)

                ui_success = self._test_ui_layer()
                self.results['ui']['success'] = ui_success

                if not ui_success:
                    logger.error("UI layer test failed")
                    return False

            # All tests passed
            self.results['overall']['success'] = True
            return True

        except Exception as e:
            logger.error(f"Pipeline test failed: {e}", exc_info=True)
            return False

        finally:
            self.results['overall']['end_time'] = datetime.now()
            self._print_summary()

    def _generate_sample_data(self, quick: bool = False):
        """Generate sample Bronze data for testing."""
        if not PANDAS_AVAILABLE:
            logger.warning("Pandas not available - cannot generate sample data")
            return

        logger.info("Generating sample Bronze data...")

        # Sample size
        n_tickers = 5 if quick else 20
        n_days = 30 if quick else 90

        # Generate tickers
        tickers = [f"TEST{i:02d}" for i in range(n_tickers)]

        # Generate dates
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=n_days)
        dates = pd.date_range(start_date, end_date, freq='D')

        # Generate price data
        prices_data = []
        for ticker in tickers:
            base_price = np.random.uniform(50, 500)
            for date in dates:
                # Random walk
                change = np.random.normal(0, 0.02)
                base_price *= (1 + change)

                prices_data.append({
                    'ticker': ticker,
                    'trade_date': date.strftime('%Y-%m-%d'),
                    'open': round(base_price * 0.99, 2),
                    'high': round(base_price * 1.02, 2),
                    'low': round(base_price * 0.98, 2),
                    'close': round(base_price, 2),
                    'volume': int(np.random.uniform(1e6, 1e8)),
                })

        prices_df = pd.DataFrame(prices_data)

        # Generate company data
        companies_data = []
        for i, ticker in enumerate(tickers):
            companies_data.append({
                'ticker': ticker,
                'company_id': f'COMP{i:04d}',
                'company_name': f'Test Company {i}',
                'exchange_code': np.random.choice(['NYSE', 'NASDAQ', 'AMEX']),
                'security_type': 'CS',
                'sector': np.random.choice(['Technology', 'Finance', 'Healthcare', 'Energy']),
                'industry': f'Test Industry {i % 5}',
            })

        companies_df = pd.DataFrame(companies_data)

        # Write to Bronze layer
        bronze_prices_path = self.bronze_path / "prices_daily"
        bronze_companies_path = self.bronze_path / "company"

        bronze_prices_path.mkdir(parents=True, exist_ok=True)
        bronze_companies_path.mkdir(parents=True, exist_ok=True)

        # Write as Parquet
        prices_df.to_parquet(bronze_prices_path / "data.parquet", index=False)
        companies_df.to_parquet(bronze_companies_path / "data.parquet", index=False)

        logger.info(f"  Generated {len(prices_df):,} price records")
        logger.info(f"  Generated {len(companies_df):,} company records")
        logger.info(f"  Bronze path: {self.bronze_path}")

    def _test_bronze_layer(self) -> bool:
        """Test Bronze layer (raw data ingestion)."""
        logger.info("Testing Bronze layer...")

        if not self.conn:
            logger.error("  No database connection available")
            return False

        bronze_tables = {
            'prices_daily': self.bronze_path / "prices_daily",
            'company': self.bronze_path / "company"
        }

        all_valid = True
        for table_name, table_path in bronze_tables.items():
            logger.info(f"  Checking {table_name}...")

            if not table_path.exists():
                logger.warning(f"    {table_name} not found at {table_path}")
                self.results['bronze'][table_name] = {'exists': False}
                continue

            try:
                # Read Bronze data
                df = self.conn.read_table(str(table_path), format='parquet').df()

                row_count = len(df)
                col_count = len(df.columns)

                # Basic validation
                checks = {
                    'exists': True,
                    'row_count': row_count,
                    'col_count': col_count,
                    'has_data': row_count > 0,
                    'no_nulls_in_keys': True  # Would check key columns
                }

                # Check for nulls in expected key columns
                if table_name == 'prices_daily' and 'ticker' in df.columns:
                    checks['no_nulls_in_keys'] = not df['ticker'].isnull().any()
                elif table_name == 'company' and 'ticker' in df.columns:
                    checks['no_nulls_in_keys'] = not df['ticker'].isnull().any()

                is_valid = all([
                    checks['has_data'],
                    checks['no_nulls_in_keys']
                ])

                status = "✓" if is_valid else "✗"
                logger.info(f"    {status} {table_name}: {row_count:,} rows, {col_count} columns")

                self.results['bronze'][table_name] = checks

                if not is_valid:
                    all_valid = False

            except Exception as e:
                logger.error(f"    Error reading {table_name}: {e}")
                self.results['bronze'][table_name] = {'exists': True, 'error': str(e)}
                all_valid = False

        return all_valid

    def _test_silver_layer(self) -> bool:
        """Test Silver layer (transformed model tables)."""
        logger.info("Testing Silver layer...")

        if not self.conn:
            logger.error("  No database connection available")
            return False

        # Get Silver tables from model config
        schema = self.model_cfg.get('schema', {})
        dimensions = list(schema.get('dimensions', {}).keys())
        facts = list(schema.get('facts', {}).keys())
        silver_tables = dimensions + facts

        if not silver_tables:
            logger.warning("  No Silver tables defined in model schema")
            return False

        all_valid = True
        for table_name in silver_tables:
            logger.info(f"  Checking {table_name}...")

            try:
                table_path = self._get_table_path(table_name)

                if not table_path.exists():
                    logger.warning(f"    {table_name} not found at {table_path}")
                    self.results['silver'][table_name] = {'exists': False}
                    continue

                # Determine format
                is_delta = (table_path / "_delta_log").exists()
                format_type = 'delta' if is_delta else 'parquet'

                # Read Silver data
                df = self.conn.read_table(str(table_path), format=format_type).df()

                row_count = len(df)
                col_count = len(df.columns)

                # Validation checks
                checks = {
                    'exists': True,
                    'format': format_type,
                    'row_count': row_count,
                    'col_count': col_count,
                    'has_data': row_count > 0
                }

                is_valid = checks['has_data']

                status = "✓" if is_valid else "✗"
                logger.info(f"    {status} {table_name}: {row_count:,} rows ({format_type})")

                self.results['silver'][table_name] = checks

                if not is_valid:
                    all_valid = False

            except Exception as e:
                logger.error(f"    Error reading {table_name}: {e}")
                self.results['silver'][table_name] = {'exists': False, 'error': str(e)}
                all_valid = False

        return all_valid

    def _test_gold_layer(self) -> bool:
        """Test Gold layer (measures/aggregations)."""
        logger.info("Testing Gold layer (measures)...")

        try:
            # Load model instance
from de_funk.models.implemented.stocks.model import StocksModel

            model = StocksModel(
                connection=self.conn,
                storage=None,  # Not needed for read-only
                repo=self.registry
            )

            # Get available measures
            measures = self.model_cfg.get('measures', {})

            if not measures:
                logger.warning("  No measures defined in model config")
                return False

            # Test a few key measures
            test_measures = list(measures.keys())[:5]  # Test first 5

            all_valid = True
            for measure_name in test_measures:
                logger.info(f"  Testing measure: {measure_name}")

                try:
                    # Calculate measure
                    start_time = time.time()
                    result = model.calculate_measure(measure_name, limit=10)
                    elapsed = time.time() - start_time

                    if result is not None and len(result) > 0:
                        logger.info(f"    ✓ {measure_name}: {len(result)} results ({elapsed:.2f}s)")
                        self.results['gold'][measure_name] = {
                            'success': True,
                            'row_count': len(result),
                            'query_time': elapsed
                        }
                    else:
                        logger.warning(f"    ✗ {measure_name}: No results")
                        self.results['gold'][measure_name] = {
                            'success': False,
                            'error': 'No results'
                        }
                        all_valid = False

                except Exception as e:
                    logger.error(f"    ✗ {measure_name}: {e}")
                    self.results['gold'][measure_name] = {
                        'success': False,
                        'error': str(e)
                    }
                    all_valid = False

            return all_valid

        except Exception as e:
            logger.error(f"  Failed to load model: {e}")
            return False

    def _test_ui_layer(self) -> bool:
        """Test UI layer (query patterns for visualization)."""
        logger.info("Testing UI layer (query patterns)...")

        if not self.conn:
            logger.error("  No database connection available")
            return False

        # Common UI query patterns
        ui_queries = {
            'latest_prices': """
                SELECT ticker, trade_date, close, volume
                FROM {table}
                ORDER BY trade_date DESC
                LIMIT 10
            """,
            'price_summary': """
                SELECT ticker,
                    COUNT(*) as record_count,
                    MIN(trade_date) as first_date,
                    MAX(trade_date) as last_date,
                    AVG(close) as avg_price,
                    AVG(volume) as avg_volume
                FROM {table}
                GROUP BY ticker
                LIMIT 5
            """,
            'recent_high_volume': """
                SELECT ticker, trade_date, close, volume
                FROM {table}
                WHERE volume > (SELECT AVG(volume) FROM {table})
                ORDER BY volume DESC
                LIMIT 10
            """
        }

        # Get a fact table to query
        schema = self.model_cfg.get('schema', {})
        facts = schema.get('facts', {})

        if not facts:
            logger.warning("  No fact tables to query")
            return False

        # Use first fact table
        fact_table = list(facts.keys())[0]
        table_path = self._get_table_path(fact_table)

        # Determine format
        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        all_valid = True
        for query_name, query_template in ui_queries.items():
            logger.info(f"  Testing query: {query_name}")

            try:
                # Execute query
                query = query_template.format(table=table_ref)
                start_time = time.time()
                result_df = self.conn.execute(query).df()
                elapsed = time.time() - start_time

                row_count = len(result_df)

                if row_count > 0:
                    logger.info(f"    ✓ {query_name}: {row_count} results ({elapsed:.3f}s)")
                    self.results['ui'][query_name] = {
                        'success': True,
                        'row_count': row_count,
                        'query_time': elapsed,
                        'sample': result_df.head(3).to_dict('records')
                    }
                else:
                    logger.warning(f"    ✗ {query_name}: No results")
                    self.results['ui'][query_name] = {
                        'success': False,
                        'error': 'No results'
                    }
                    all_valid = False

            except Exception as e:
                logger.error(f"    ✗ {query_name}: {e}")
                self.results['ui'][query_name] = {
                    'success': False,
                    'error': str(e)
                }
                all_valid = False

        return all_valid

    def _get_table_path(self, table_name: str) -> Path:
        """Get physical path for a table."""
        schema = self.model_cfg.get('schema', {})

        if table_name in schema.get('dimensions', {}):
            relative_path = schema['dimensions'][table_name]['path']
        elif table_name in schema.get('facts', {}):
            relative_path = schema['facts'][table_name]['path']
        else:
            raise ValueError(f"Table {table_name} not found in schema")

        storage_root = Path(self.model_cfg['storage']['root'])
        return storage_root / relative_path

    def _print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)

        # Overall timing
        start = self.results['overall']['start_time']
        end = self.results['overall']['end_time']
        if start and end:
            duration = (end - start).total_seconds()
            logger.info(f"\nTotal duration: {duration:.2f}s")

        # Stage results
        stages = ['bronze', 'silver', 'gold', 'ui']
        for stage in stages:
            if not self.results[stage]:
                continue

            stage_results = self.results[stage]
            if isinstance(stage_results, dict) and 'success' in stage_results:
                success = stage_results['success']
            else:
                success = all(
                    v.get('success', v.get('exists', False))
                    for v in stage_results.values()
                    if isinstance(v, dict)
                )

            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"\n{stage.upper()}: {status}")

            # Details
            for name, result in stage_results.items():
                if name == 'success':
                    continue
                if isinstance(result, dict):
                    if 'error' in result:
                        logger.info(f"  ✗ {name}: {result['error']}")
                    elif 'row_count' in result:
                        logger.info(f"  ✓ {name}: {result['row_count']:,} rows")
                    elif result.get('exists'):
                        logger.info(f"  ✓ {name}")

        # Overall result
        logger.info("\n" + "=" * 70)
        if self.results['overall']['success']:
            logger.info("✓ ALL TESTS PASSED")
        else:
            logger.info("✗ SOME TESTS FAILED")
        logger.info("=" * 70)

        # Save results to file
        results_file = Path("test_results") / f"pipeline_e2e_{self.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.parent.mkdir(exist_ok=True)

        # Convert datetime objects for JSON serialization
        serializable_results = self._make_serializable(self.results)
        with open(results_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        logger.info(f"\nResults saved to: {results_file}")

    def _make_serializable(self, obj):
        """Make object JSON serializable."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--model',
        required=True,
        help='Model name (e.g., equity, corporate)'
    )

    parser.add_argument(
        '--stages',
        nargs='+',
        choices=['bronze', 'silver', 'gold', 'ui'],
        help='Stages to test (default: all)'
    )

    parser.add_argument(
        '--bronze-path',
        help='Bronze layer path (default: storage/bronze/test)'
    )

    parser.add_argument(
        '--generate-sample',
        action='store_true',
        help='Generate sample data before testing'
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test with minimal data'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )

    parser.add_argument(
        '--config-dir',
        default='configs/models',
        help='Model config directory (default: configs/models)'
    )

    args = parser.parse_args()

    try:
        # Check dependencies
        if not PANDAS_AVAILABLE:
            logger.error("Pandas not installed. Install with: pip install pandas")
            sys.exit(1)

        if not DUCKDB_AVAILABLE:
            logger.error("DuckDB not installed. Install with: pip install duckdb")
            sys.exit(1)

        # Initialize tester
        tester = PipelineE2ETester(
            model_name=args.model,
            config_dir=args.config_dir,
            bronze_path=args.bronze_path
        )

        # Run tests
        success = tester.run_full_pipeline(
            stages=args.stages,
            generate_sample=args.generate_sample,
            quick=args.quick,
            verbose=args.verbose
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
