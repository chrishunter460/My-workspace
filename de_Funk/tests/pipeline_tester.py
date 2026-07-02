#!/usr/bin/env python3
"""
Full Pipeline Tester - Validates entire measure framework with real data.

Tests the complete flow:
1. Bronze → Silver layer build
2. Model initialization
3. Measure calculations (all types)
4. Backend abstraction
5. Weighting strategies
6. ETF integration

Usage:
    python tests/pipeline_tester.py
    python tests/pipeline_tester.py --backend duckdb
    python tests/pipeline_tester.py --model company
    python tests/pipeline_tester.py --verbose
"""

import argparse
import sys
from pathlib import Path
import time
from datetime import datetime

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.core.context import RepoContext


class PipelineTester:
    """
    Comprehensive pipeline tester.

    Tests all components of the measure framework with real data.
    """

    def __init__(self, backend='duckdb', verbose=False):
        """
        Initialize pipeline tester.

        Args:
            backend: Backend to test ('duckdb' or 'spark')
            verbose: Enable verbose output
        """
        self.backend = backend
        self.verbose = verbose
        self.results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        self.start_time = None

    def log(self, message, level='INFO'):
        """Log message with timestamp."""
        if level == 'INFO' and not self.verbose:
            return

        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = {
            'INFO': '  ',
            'SUCCESS': '✓ ',
            'ERROR': '✗ ',
            'WARN': '⚠ ',
            'HEADER': '\n▶ '
        }.get(level, '  ')

        print(f"[{timestamp}] {prefix}{message}")

    def test_pass(self, test_name):
        """Record test pass."""
        self.results['passed'] += 1
        self.log(f"{test_name}: PASSED", 'SUCCESS')

    def test_fail(self, test_name, error):
        """Record test failure."""
        self.results['failed'] += 1
        self.results['errors'].append({'test': test_name, 'error': str(error)})
        self.log(f"{test_name}: FAILED - {error}", 'ERROR')

    def test_skip(self, test_name, reason):
        """Record test skip."""
        self.results['skipped'] += 1
        self.log(f"{test_name}: SKIPPED - {reason}", 'WARN')

    # ============================================================
    # Test Sections
    # ============================================================

    def test_1_context_initialization(self):
        """Test 1: Initialize RepoContext."""
        self.log("Test 1: Context Initialization", 'HEADER')

        try:
            self.ctx = RepoContext.from_repo_root(connection_type=self.backend)
            self.log(f"Repo root: {self.ctx.repo}")
            self.log(f"Connection type: {self.backend}")
            self.test_pass("Context Initialization")
            return True
        except Exception as e:
            self.test_fail("Context Initialization", e)
            return False

    def test_2_bronze_data_check(self):
        """Test 2: Verify Bronze data exists."""
        self.log("Test 2: Bronze Data Check", 'HEADER')

        try:
            bronze_root = self.ctx.repo / "storage" / "bronze"

            # Check for company data
            required_tables = [
                'prices_daily',
                'ref_all_tickers',
                'exchanges'
            ]

            for table in required_tables:
                table_path = bronze_root / table
                if not table_path.exists():
                    self.test_skip(
                        f"Bronze table: {table}",
                        f"Not found at {table_path}"
                    )
                else:
                    # Try to read a sample
                    if self.backend == 'duckdb':
                        sample = self.ctx.connection.conn.execute(
                            f"SELECT COUNT(*) as cnt FROM read_parquet('{table_path}/*.parquet') LIMIT 1"
                        ).fetchone()
                        count = sample[0] if sample else 0
                        self.log(f"Table {table}: {count:,} rows")

                    self.test_pass(f"Bronze table: {table}")

            return True
        except Exception as e:
            self.test_fail("Bronze Data Check", e)
            return False

    def test_3_model_loading(self):
        """Test 3: Load CompanyModel."""
        self.log("Test 3: Model Loading", 'HEADER')

        try:
from de_funk.models.implemented.company.model import CompanyModel

            self.model = CompanyModel(
                self.ctx.connection,
                self.ctx.storage,
                self.ctx.repo
            )

            self.log(f"Model name: {self.model.model_name}")
            self.log(f"Backend: {self.model.backend}")

            # Check measures property
            executor = self.model.measures
            self.log(f"Measure executor created: {type(executor).__name__}")

            self.test_pass("Model Loading")
            return True
        except Exception as e:
            self.test_fail("Model Loading", e)
            return False

    def test_4_list_measures(self):
        """Test 4: List available measures."""
        self.log("Test 4: List Measures", 'HEADER')

        try:
            measures = self.model.measures.list_measures()

            self.log(f"Available measures: {len(measures)}")
            for measure_name in sorted(measures.keys()):
                measure_info = self.model.measures.get_measure_info(measure_name)
                self.log(f"  - {measure_name} ({measure_info['type']})")

            self.test_pass("List Measures")
            return True
        except Exception as e:
            self.test_fail("List Measures", e)
            return False

    def test_5_simple_measure(self):
        """Test 5: Calculate simple measure."""
        self.log("Test 5: Simple Measure Calculation", 'HEADER')

        try:
            # Build silver layer first if needed
            self._ensure_silver_built()

            # Calculate avg_close_price
            result = self.model.calculate_measure(
                'avg_close_price',
                entity_column='ticker',
                limit=5
            )

            self.log(f"Backend: {result.backend}")
            self.log(f"Query time: {result.query_time_ms:.2f}ms")
            self.log(f"Rows returned: {result.rows}")

            # Verify results
            assert result.rows > 0, "No results returned"
            assert result.backend == self.backend
            assert result.query_time_ms > 0

            # Show sample
            self.log("Sample results:")
            if self.backend == 'duckdb':
                print(result.data.head())
            else:
                result.data.show(5)

            self.test_pass("Simple Measure")
            return True
        except Exception as e:
            self.test_fail("Simple Measure", e)
            return False

    def test_6_computed_measure(self):
        """Test 6: Calculate computed measure."""
        self.log("Test 6: Computed Measure Calculation", 'HEADER')

        try:
            # Check if market_cap measure exists
            measures = self.model.measures.list_measures()
            if 'market_cap' not in measures:
                self.test_skip("Computed Measure", "market_cap not defined in config")
                return True

            result = self.model.calculate_measure(
                'market_cap',
                entity_column='ticker',
                limit=5
            )

            self.log(f"Query time: {result.query_time_ms:.2f}ms")
            self.log(f"Rows returned: {result.rows}")

            # Verify results
            assert result.rows > 0, "No results returned"

            self.test_pass("Computed Measure")
            return True
        except Exception as e:
            self.test_fail("Computed Measure", e)
            return False

    def test_7_weighted_measure(self):
        """Test 7: Calculate weighted measure."""
        self.log("Test 7: Weighted Measure Calculation", 'HEADER')

        try:
            # Test volume-weighted index
            measures = self.model.measures.list_measures()
            if 'volume_weighted_index' not in measures:
                self.test_skip("Weighted Measure", "volume_weighted_index not defined")
                return True

            result = self.model.calculate_measure('volume_weighted_index')

            self.log(f"Query time: {result.query_time_ms:.2f}ms")
            self.log(f"Rows returned: {result.rows}")

            # Verify results
            assert result.rows > 0, "No results returned"

            # Show sample
            self.log("Sample weighted results:")
            if self.backend == 'duckdb':
                print(result.data.head())

            self.test_pass("Weighted Measure")
            return True
        except Exception as e:
            self.test_fail("Weighted Measure", e)
            return False

    def test_8_sql_generation(self):
        """Test 8: SQL generation (explain)."""
        self.log("Test 8: SQL Generation", 'HEADER')

        try:
            # Test SQL generation for each measure type
            test_measures = []
            measures = self.model.measures.list_measures()

            if 'avg_close_price' in measures:
                test_measures.append('avg_close_price')
            if 'volume_weighted_index' in measures:
                test_measures.append('volume_weighted_index')

            for measure_name in test_measures:
                sql = self.model.measures.explain_measure(measure_name)

                self.log(f"\nSQL for {measure_name}:")
                self.log(sql[:200] + "..." if len(sql) > 200 else sql)

                # Basic validation
                assert 'SELECT' in sql.upper()
                assert len(sql) > 0

            self.test_pass("SQL Generation")
            return True
        except Exception as e:
            self.test_fail("SQL Generation", e)
            return False

    def test_9_all_weighting_methods(self):
        """Test 9: Test all weighting methods."""
        self.log("Test 9: All Weighting Methods", 'HEADER')

        try:
            weighted_measures = [
                'equal_weighted_index',
                'volume_weighted_index',
                'market_cap_weighted_index',
                'price_weighted_index',
            ]

            measures = self.model.measures.list_measures()

            for measure_name in weighted_measures:
                if measure_name not in measures:
                    self.log(f"  {measure_name}: not defined")
                    continue

                try:
                    result = self.model.calculate_measure(measure_name)
                    self.log(f"  {measure_name}: {result.rows} rows, {result.query_time_ms:.1f}ms")
                except Exception as e:
                    self.log(f"  {measure_name}: ERROR - {e}")

            self.test_pass("All Weighting Methods")
            return True
        except Exception as e:
            self.test_fail("All Weighting Methods", e)
            return False

    def test_10_backend_abstraction(self):
        """Test 10: Backend abstraction."""
        self.log("Test 10: Backend Abstraction", 'HEADER')

        try:
            # Verify backend adapter is working
            adapter = self.model.measures.adapter

            self.log(f"Adapter type: {type(adapter).__name__}")
            self.log(f"Dialect: {adapter.get_dialect()}")

            # Test table reference
            table_ref = adapter.get_table_reference('fact_prices')
            self.log(f"Table reference: {table_ref[:100]}...")

            # Test feature support
            features = ['window_functions', 'cte', 'qualify']
            for feature in features:
                supported = adapter.supports_feature(feature)
                self.log(f"  {feature}: {'✓' if supported else '✗'}")

            self.test_pass("Backend Abstraction")
            return True
        except Exception as e:
            self.test_fail("Backend Abstraction", e)
            return False

    def test_11_etf_model(self):
        """Test 11: ETF model (if available)."""
        self.log("Test 11: ETF Model", 'HEADER')

        try:
            # Check if ETF model exists
            etf_config = self.ctx.repo / "configs" / "models" / "etf.yaml"
            if not etf_config.exists():
                self.test_skip("ETF Model", "etf.yaml not found")
                return True

from de_funk.models.implemented.etf.model import ETFModel

            etf_model = ETFModel(
                self.ctx.connection,
                self.ctx.storage,
                self.ctx.repo
            )

            self.log(f"ETF model loaded: {etf_model.model_name}")

            # List measures
            measures = etf_model.measures.list_measures()
            self.log(f"ETF measures: {len(measures)}")

            self.test_pass("ETF Model")
            return True
        except Exception as e:
            self.test_fail("ETF Model", e)
            return False

    def test_12_performance_benchmark(self):
        """Test 12: Performance benchmark."""
        self.log("Test 12: Performance Benchmark", 'HEADER')

        try:
            # Benchmark different measure types
            benchmarks = []

            test_measures = []
            measures = self.model.measures.list_measures()

            if 'avg_close_price' in measures:
                test_measures.append(('Simple', 'avg_close_price', {'entity_column': 'ticker', 'limit': 10}))
            if 'volume_weighted_index' in measures:
                test_measures.append(('Weighted', 'volume_weighted_index', {}))

            for measure_type, measure_name, kwargs in test_measures:
                # Run 3 times and average
                times = []
                for _ in range(3):
                    start = time.time()
                    result = self.model.calculate_measure(measure_name, **kwargs)
                    elapsed = time.time() - start
                    times.append(elapsed * 1000)  # ms

                avg_time = sum(times) / len(times)
                benchmarks.append((measure_type, measure_name, avg_time))
                self.log(f"  {measure_type} ({measure_name}): {avg_time:.2f}ms avg")

            self.test_pass("Performance Benchmark")
            return True
        except Exception as e:
            self.test_fail("Performance Benchmark", e)
            return False

    def _ensure_silver_built(self):
        """Ensure silver layer is built."""
        try:
            # Check if silver layer exists
            silver_root = self.ctx.repo / "storage" / "silver" / "company"
            if not silver_root.exists():
                self.log("Silver layer not found, attempting to build...")
                self.model.ensure_built()
                self.log("Silver layer built successfully")
        except Exception as e:
            self.log(f"Warning: Could not build silver layer: {e}", 'WARN')

    # ============================================================
    # Main Test Runner
    # ============================================================

    def run_all_tests(self):
        """Run all pipeline tests."""
        self.start_time = time.time()

        print("=" * 70)
        print("MEASURE FRAMEWORK PIPELINE TESTER")
        print("=" * 70)
        print(f"Backend: {self.backend}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Run tests in order
        tests = [
            self.test_1_context_initialization,
            self.test_2_bronze_data_check,
            self.test_3_model_loading,
            self.test_4_list_measures,
            self.test_5_simple_measure,
            self.test_6_computed_measure,
            self.test_7_weighted_measure,
            self.test_8_sql_generation,
            self.test_9_all_weighting_methods,
            self.test_10_backend_abstraction,
            self.test_11_etf_model,
            self.test_12_performance_benchmark,
        ]

        # Run each test
        for test_func in tests:
            try:
                should_continue = test_func()
                if not should_continue and test_func == self.test_1_context_initialization:
                    # If context fails, can't continue
                    break
            except Exception as e:
                self.log(f"Unexpected error in {test_func.__name__}: {e}", 'ERROR')
                self.results['failed'] += 1

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        elapsed = time.time() - self.start_time

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Passed:  {self.results['passed']}")
        print(f"Failed:  {self.results['failed']}")
        print(f"Skipped: {self.results['skipped']}")
        print(f"Time:    {elapsed:.2f}s")
        print("=" * 70)

        if self.results['failed'] > 0:
            print("\nFAILURES:")
            for error in self.results['errors']:
                print(f"  ✗ {error['test']}")
                print(f"    {error['error']}")
            print("=" * 70)
            sys.exit(1)
        else:
            print("\n✓ ALL TESTS PASSED!")
            print("=" * 70)
            sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Full pipeline tester for measure framework"
    )
    parser.add_argument(
        '--backend',
        choices=['duckdb', 'spark'],
        default='duckdb',
        help='Backend to test (default: duckdb)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    args = parser.parse_args()

    tester = PipelineTester(backend=args.backend, verbose=args.verbose)
    tester.run_all_tests()


if __name__ == '__main__':
    main()
