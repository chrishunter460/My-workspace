#!/usr/bin/env python3
"""
UI integration test for Streamlit app and query patterns.

Tests UI components, query performance, and data access patterns
used by the Streamlit application.

Usage:
    # Test all UI components
    python -m scripts.test_ui_integration --model equity

    # Test specific components
    python -m scripts.test_ui_integration --model equity --components filters charts

    # Performance benchmarking
    python -m scripts.test_ui_integration --model equity --benchmark

    # Test with specific tickers
    python -m scripts.test_ui_integration --model equity --tickers AAPL GOOGL MSFT
"""

import sys
from pathlib import Path

import argparse
from typing import List, Dict, Optional
import logging
import time
from datetime import datetime, timedelta

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


class UIIntegrationTester:
    """Test UI integration and query patterns."""

    def __init__(self, model_name: str, config_dir: str = "configs/models"):
        """
        Initialize UI tester.

        Args:
            model_name: Model name
            config_dir: Model config directory
        """
        self.model_name = model_name
        self.config_dir = Path(config_dir)

        # Load model
        self.registry = ModelRegistry(str(self.config_dir))
        self.model_cfg = self.registry.get_model_config(model_name)

        # Initialize connection
        self.conn = None
        if DUCKDB_AVAILABLE:
            self.conn = DuckDBConnection()

        self.test_results = {}

        logger.info(f"Initialized UI tester for model: {model_name}")

    def test_all_components(
        self,
        components: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,
        benchmark: bool = False
    ) -> bool:
        """
        Test all UI components.

        Args:
            components: Specific components to test
            tickers: Test tickers
            benchmark: Run performance benchmarks

        Returns:
            True if all tests pass
        """
        logger.info("=" * 70)
        logger.info("UI INTEGRATION TEST")
        logger.info("=" * 70)

        if not components:
            components = ['filters', 'selectors', 'charts', 'tables', 'measures']

        all_passed = True

        # Test each component
        if 'filters' in components:
            logger.info("\n--- Testing Filter Components ---")
            if not self._test_filter_queries(tickers):
                all_passed = False

        if 'selectors' in components:
            logger.info("\n--- Testing Selector Components ---")
            if not self._test_selector_queries():
                all_passed = False

        if 'charts' in components:
            logger.info("\n--- Testing Chart Data Queries ---")
            if not self._test_chart_queries(tickers):
                all_passed = False

        if 'tables' in components:
            logger.info("\n--- Testing Table Display Queries ---")
            if not self._test_table_queries(tickers):
                all_passed = False

        if 'measures' in components:
            logger.info("\n--- Testing Measure Calculations ---")
            if not self._test_measure_queries(tickers):
                all_passed = False

        # Performance benchmarks
        if benchmark:
            logger.info("\n--- Performance Benchmarks ---")
            self._run_benchmarks(tickers)

        # Summary
        self._print_test_summary()

        return all_passed

    def _test_filter_queries(self, tickers: Optional[List[str]] = None) -> bool:
        """Test filter-style queries used in UI."""
        logger.info("Testing filter queries...")

        if not self.conn:
            return False

        table_path = self._get_primary_fact_table()
        if not table_path:
            return False

        # Determine table reference
        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        # Test queries
        filter_queries = {
            'date_range_filter': f"""
                SELECT ticker, trade_date, close
                FROM {table_ref}
                WHERE trade_date BETWEEN DATE '2024-01-01' AND DATE '2024-01-31'
                LIMIT 100
            """,
            'ticker_filter': f"""
                SELECT ticker, trade_date, close, volume
                FROM {table_ref}
                WHERE ticker IN ('AAPL', 'GOOGL', 'MSFT')
                ORDER BY trade_date DESC
                LIMIT 100
            """,
            'volume_threshold': f"""
                SELECT ticker, trade_date, close, volume
                FROM {table_ref}
                WHERE volume > 50000000
                ORDER BY volume DESC
                LIMIT 50
            """,
        }

        all_passed = True
        for query_name, query in filter_queries.items():
            try:
                start = time.time()
                result = self.conn.execute(query).df()
                elapsed = time.time() - start

                if len(result) > 0:
                    logger.info(f"  ✓ {query_name}: {len(result)} results ({elapsed:.3f}s)")
                    self.test_results[f'filter_{query_name}'] = {
                        'success': True,
                        'rows': len(result),
                        'time': elapsed
                    }
                else:
                    logger.warning(f"  ⚠ {query_name}: No results (may be expected for test data)")
                    self.test_results[f'filter_{query_name}'] = {
                        'success': True,
                        'rows': 0,
                        'time': elapsed
                    }

            except Exception as e:
                logger.error(f"  ✗ {query_name}: {e}")
                self.test_results[f'filter_{query_name}'] = {'success': False, 'error': str(e)}
                all_passed = False

        return all_passed

    def _test_selector_queries(self) -> bool:
        """Test selector/dropdown queries used in UI."""
        logger.info("Testing selector queries...")

        if not self.conn:
            return False

        table_path = self._get_primary_fact_table()
        if not table_path:
            return False

        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        # Queries for dropdowns/selectors
        selector_queries = {
            'unique_tickers': f"""
                SELECT DISTINCT ticker
                FROM {table_ref}
                ORDER BY ticker
            """,
            'date_range': f"""
                SELECT MIN(trade_date) as min_date, MAX(trade_date) as max_date
                FROM {table_ref}
            """,
            'ticker_with_counts': f"""
                SELECT ticker, COUNT(*) as record_count
                FROM {table_ref}
                GROUP BY ticker
                ORDER BY record_count DESC
            """,
        }

        all_passed = True
        for query_name, query in selector_queries.items():
            try:
                start = time.time()
                result = self.conn.execute(query).df()
                elapsed = time.time() - start

                logger.info(f"  ✓ {query_name}: {len(result)} results ({elapsed:.3f}s)")
                self.test_results[f'selector_{query_name}'] = {
                    'success': True,
                    'rows': len(result),
                    'time': elapsed
                }

            except Exception as e:
                logger.error(f"  ✗ {query_name}: {e}")
                self.test_results[f'selector_{query_name}'] = {'success': False, 'error': str(e)}
                all_passed = False

        return all_passed

    def _test_chart_queries(self, tickers: Optional[List[str]] = None) -> bool:
        """Test chart data queries used in UI."""
        logger.info("Testing chart data queries...")

        if not self.conn:
            return False

        table_path = self._get_primary_fact_table()
        if not table_path:
            return False

        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        # Chart-specific queries
        chart_queries = {
            'time_series': f"""
                SELECT trade_date, ticker, close
                FROM {table_ref}
                WHERE ticker IN ('AAPL', 'GOOGL')
                ORDER BY trade_date
                LIMIT 500
            """,
            'ohlc_data': f"""
                SELECT trade_date, open, high, low, close, volume
                FROM {table_ref}
                WHERE ticker = 'AAPL'
                ORDER BY trade_date DESC
                LIMIT 90
            """,
            'volume_bars': f"""
                SELECT trade_date, ticker, volume
                FROM {table_ref}
                WHERE ticker IN ('AAPL', 'GOOGL', 'MSFT')
                ORDER BY trade_date DESC
                LIMIT 200
            """,
            'price_distribution': f"""
                SELECT
                    FLOOR(close / 10) * 10 as price_bucket,
                    COUNT(*) as frequency
                FROM {table_ref}
                GROUP BY price_bucket
                ORDER BY price_bucket
            """,
        }

        all_passed = True
        for query_name, query in chart_queries.items():
            try:
                start = time.time()
                result = self.conn.execute(query).df()
                elapsed = time.time() - start

                if len(result) > 0:
                    logger.info(f"  ✓ {query_name}: {len(result)} results ({elapsed:.3f}s)")
                    self.test_results[f'chart_{query_name}'] = {
                        'success': True,
                        'rows': len(result),
                        'time': elapsed
                    }
                else:
                    logger.warning(f"  ⚠ {query_name}: No results")
                    self.test_results[f'chart_{query_name}'] = {
                        'success': True,
                        'rows': 0,
                        'time': elapsed
                    }

            except Exception as e:
                logger.error(f"  ✗ {query_name}: {e}")
                self.test_results[f'chart_{query_name}'] = {'success': False, 'error': str(e)}
                all_passed = False

        return all_passed

    def _test_table_queries(self, tickers: Optional[List[str]] = None) -> bool:
        """Test table display queries used in UI."""
        logger.info("Testing table display queries...")

        if not self.conn:
            return False

        table_path = self._get_primary_fact_table()
        if not table_path:
            return False

        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        # Table display queries
        table_queries = {
            'recent_data': f"""
                SELECT ticker, trade_date, open, high, low, close, volume
                FROM {table_ref}
                ORDER BY trade_date DESC
                LIMIT 50
            """,
            'sorted_by_volume': f"""
                SELECT ticker, trade_date, close, volume
                FROM {table_ref}
                ORDER BY volume DESC
                LIMIT 50
            """,
            'summary_stats': f"""
                SELECT
                    ticker,
                    COUNT(*) as records,
                    MIN(trade_date) as first_date,
                    MAX(trade_date) as last_date,
                    ROUND(AVG(close), 2) as avg_price,
                    ROUND(AVG(volume), 0) as avg_volume
                FROM {table_ref}
                GROUP BY ticker
                ORDER BY ticker
            """,
        }

        all_passed = True
        for query_name, query in table_queries.items():
            try:
                start = time.time()
                result = self.conn.execute(query).df()
                elapsed = time.time() - start

                if len(result) > 0:
                    logger.info(f"  ✓ {query_name}: {len(result)} results ({elapsed:.3f}s)")
                    self.test_results[f'table_{query_name}'] = {
                        'success': True,
                        'rows': len(result),
                        'time': elapsed
                    }
                else:
                    logger.warning(f"  ⚠ {query_name}: No results")
                    self.test_results[f'table_{query_name}'] = {
                        'success': True,
                        'rows': 0,
                        'time': elapsed
                    }

            except Exception as e:
                logger.error(f"  ✗ {query_name}: {e}")
                self.test_results[f'table_{query_name}'] = {'success': False, 'error': str(e)}
                all_passed = False

        return all_passed

    def _test_measure_queries(self, tickers: Optional[List[str]] = None) -> bool:
        """Test measure calculation queries used in UI."""
        logger.info("Testing measure calculations...")

        try:
from de_funk.models.implemented.stocks.model import StocksModel

            model = StocksModel(
                connection=self.conn,
                storage=None,
                repo=self.registry
            )

            # Test measures
            test_measures = [
                'avg_close_price',
                'total_volume',
                'max_high_price',
                'min_low_price',
            ]

            all_passed = True
            for measure_name in test_measures:
                try:
                    start = time.time()
                    result = model.calculate_measure(measure_name, limit=10)
                    elapsed = time.time() - start

                    if result is not None and len(result) > 0:
                        logger.info(f"  ✓ {measure_name}: {len(result)} results ({elapsed:.3f}s)")
                        self.test_results[f'measure_{measure_name}'] = {
                            'success': True,
                            'rows': len(result),
                            'time': elapsed
                        }
                    else:
                        logger.warning(f"  ⚠ {measure_name}: No results")
                        self.test_results[f'measure_{measure_name}'] = {
                            'success': True,
                            'rows': 0,
                            'time': elapsed
                        }

                except Exception as e:
                    logger.error(f"  ✗ {measure_name}: {e}")
                    self.test_results[f'measure_{measure_name}'] = {'success': False, 'error': str(e)}
                    all_passed = False

            return all_passed

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def _run_benchmarks(self, tickers: Optional[List[str]] = None):
        """Run performance benchmarks."""
        logger.info("Running performance benchmarks...")

        if not self.conn:
            return

        table_path = self._get_primary_fact_table()
        if not table_path:
            return

        is_delta = (table_path / "_delta_log").exists()
        table_ref = f"delta_scan('{table_path}')" if is_delta else f"read_parquet('{table_path}/*.parquet')"

        # Benchmark queries
        benchmarks = {
            'full_scan': f"SELECT COUNT(*) FROM {table_ref}",
            'filtered_count': f"SELECT ticker, COUNT(*) FROM {table_ref} GROUP BY ticker",
            'aggregation': f"SELECT ticker, AVG(close), MAX(high), MIN(low) FROM {table_ref} GROUP BY ticker",
        }

        for bench_name, query in benchmarks.items():
            times = []
            for i in range(3):  # Run 3 times
                try:
                    start = time.time()
                    self.conn.execute(query)
                    elapsed = time.time() - start
                    times.append(elapsed)
                except Exception as e:
                    logger.error(f"  Benchmark {bench_name} failed: {e}")
                    break

            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                logger.info(f"  {bench_name}: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
                self.test_results[f'benchmark_{bench_name}'] = {
                    'avg': avg_time,
                    'min': min_time,
                    'max': max_time
                }

    def _get_primary_fact_table(self) -> Optional[Path]:
        """Get primary fact table path."""
        schema = self.model_cfg.get('schema', {})
        facts = schema.get('facts', {})

        if not facts:
            logger.error("No fact tables defined")
            return None

        # Use first fact table
        fact_table = list(facts.keys())[0]
        relative_path = facts[fact_table]['path']
        storage_root = Path(self.model_cfg['storage']['root'])

        return storage_root / relative_path

    def _print_test_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("UI TEST SUMMARY")
        logger.info("=" * 70)

        # Group by category
        categories = {}
        for test_name, result in self.test_results.items():
            category = test_name.split('_')[0]
            if category not in categories:
                categories[category] = []
            categories[category].append((test_name, result))

        # Print by category
        for category, tests in categories.items():
            passed = sum(1 for _, r in tests if r.get('success', False))
            total = len(tests)
            logger.info(f"\n{category.upper()}: {passed}/{total} passed")

            for test_name, result in tests:
                if result.get('success'):
                    time_str = f" ({result.get('time', 0):.3f}s)" if 'time' in result else ""
                    rows_str = f" - {result.get('rows', 0)} rows" if 'rows' in result else ""
                    logger.info(f"  ✓ {test_name}{rows_str}{time_str}")
                else:
                    logger.info(f"  ✗ {test_name}: {result.get('error', 'Unknown error')}")

        # Overall
        all_passed = all(r.get('success', False) for r in self.test_results.values())
        logger.info("\n" + "=" * 70)
        if all_passed:
            logger.info("✓ ALL UI TESTS PASSED")
        else:
            logger.info("✗ SOME UI TESTS FAILED")
        logger.info("=" * 70)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="UI integration test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--model',
        required=True,
        help='Model name (e.g., equity)'
    )

    parser.add_argument(
        '--components',
        nargs='+',
        choices=['filters', 'selectors', 'charts', 'tables', 'measures'],
        help='Components to test (default: all)'
    )

    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Test tickers'
    )

    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run performance benchmarks'
    )

    parser.add_argument(
        '--config-dir',
        default='configs/models',
        help='Model config directory'
    )

    args = parser.parse_args()

    try:
        if not DUCKDB_AVAILABLE:
            logger.error("DuckDB not installed. Install with: pip install duckdb")
            sys.exit(1)

        # Initialize tester
        tester = UIIntegrationTester(
            model_name=args.model,
            config_dir=args.config_dir
        )

        # Run tests
        success = tester.test_all_components(
            components=args.components,
            tickers=args.tickers,
            benchmark=args.benchmark
        )

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
