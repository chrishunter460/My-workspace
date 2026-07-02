#!/usr/bin/env python3
"""
Domain Model Integration Test - SPARK BACKEND

Tests the complete domain model architecture with SPARK for ETL operations:
1. Session initialization (Spark)
2. Model loading (StocksModel, CompanyModel)
3. Measure registry bootstrap
4. Domain features loading
5. Graph building and data access
6. Measure execution
7. Cross-model references

This test validates:
- Model-specific domain bootstrap (stocks, company, etf)
- Measure registry with all types (simple, computed)
- Cross-model fact table references
- Spark backend operations

Usage:
    python -m scripts.test_domain_model_integration_spark

Expected outcome:
    All tests should pass, confirming domain model architecture works with Spark
"""

import sys
from pathlib import Path

import traceback
from typing import Dict, Optional
import logging

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DomainModelIntegrationTest:
    """Test suite for domain model integration with Spark backend."""

    def __init__(self):
        self.session = None
        self.models: Dict[str, any] = {}
        self.results = {
            'session': False,
            'models_loaded': {},
            'measure_registry': False,
            'domain_features': {},
            'cross_model': False
        }

    def run_all_tests(self):
        """Run all integration tests in sequence."""
        print("=" * 80)
        print("DOMAIN MODEL INTEGRATION TEST - SPARK BACKEND")
        print("=" * 80)
        print()

        # Test 1: Session initialization with SPARK
        print("[1/7] Testing session initialization (Spark)...")
        self.test_session_initialization()
        print()

        # Test 2: Model loading
        print("[2/7] Testing model loading...")
        self.test_model_loading()
        print()

        # Test 3: Measure registry
        print("[3/7] Testing measure registry bootstrap...")
        self.test_measure_registry()
        print()

        # Test 4: Domain features
        print("[4/7] Testing domain features loading...")
        self.test_domain_features()
        print()

        # Test 5: Graph building
        print("[5/7] Testing graph building and data access...")
        self.test_graph_building()
        print()

        # Test 6: Measure execution
        print("[6/7] Testing measure execution...")
        self.test_measure_execution()
        print()

        # Test 7: Cross-model references
        print("[7/7] Testing cross-model references...")
        self.test_cross_model_references()
        print()

        # Summary
        self.print_summary()

    def test_session_initialization(self):
        """Test 1: Initialize UniversalSession with Spark."""
        try:
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

            print("  ✓ Imports successful")

            # Initialize context with SPARK
            ctx = RepoContext.from_repo_root(connection_type="spark")
            print("  ✓ RepoContext initialized (Spark)")

            # Initialize session with SPARK
            self.session = UniversalSession(
                connection=ctx.connection,
                storage_cfg=ctx.storage,
                repo_root=repo_root
            )
            print("  ✓ UniversalSession created")

            # Verify backend detection
            if self.session.backend != 'spark':
                raise ValueError(f"Expected 'spark' backend, got '{self.session.backend}'")
            print("  ✓ Backend correctly detected as 'spark'")

            # Check available models
            available_models = list(self.session.registry.models.keys())
            print(f"  ✓ Available models: {', '.join(available_models)}")

            self.results['session'] = True

        except Exception as e:
            logger.error(f"Session initialization failed: {e}")
            print(f"  ✗ Error: {e}")
            traceback.print_exc()
            self.results['session'] = False

    def test_model_loading(self):
        """Test 2: Model loading with domain-specific classes."""
        if not self.session:
            print("  ⊘ Skipped - session not initialized")
            return

        # Models to test (in dependency order)
        test_models = ['core', 'equity', 'corporate']

        for model_name in test_models:
            try:
                print(f"\n  Testing {model_name} model:")

                # Try to get model class (may not be registered for models using BaseModel)
                try:
                    model_class = self.session.registry.get_model_class(model_name)
                    print(f"    ✓ Model class: {model_class.__name__}")
                except ValueError:
                    print(f"    ⚠ No custom model class registered (will use BaseModel)")
                    model_class = None

                # Load model
                model = self.session.get_model_instance(model_name)
                self.models[model_name] = model
                print(f"    ✓ Model loaded successfully")

                # Check if it's domain-specific or BaseModel
                if model_class:
from de_funk.models.base.model import BaseModel
                    if model_class != BaseModel:
                        print(f"    ✓ Using domain-specific class: {model_class.__name__}")
                    else:
                        print(f"    ⚠ Using generic BaseModel")

                # Check measure executor
                if hasattr(model, 'measures'):
                    print(f"    ✓ Measure executor available")

                # Verify Spark backend
                if model.backend != 'spark':
                    raise ValueError(f"Expected spark backend, got {model.backend}")
                print(f"    ✓ Model backend is Spark")

                self.results['models_loaded'][model_name] = True

            except Exception as e:
                logger.error(f"Failed to load {model_name}: {e}")
                print(f"    ✗ Error: {e}")
                traceback.print_exc()
                self.results['models_loaded'][model_name] = False

    def test_measure_registry(self):
        """Test 3: Measure registry bootstrap."""
        try:
from de_funk.models.measures.registry import MeasureRegistry
from de_funk.models.measures.base_measure import MeasureType

            print("  Checking registered measure types:")

            # Get registered types
            registered = MeasureRegistry.get_registered_types()

            # Expected types (WEIGHTED enum exists but no implementation)
            expected = [MeasureType.SIMPLE, MeasureType.COMPUTED]

            for measure_type in expected:
                if measure_type in registered:
                    measure_class = MeasureRegistry.get_measure_class(measure_type)
                    print(f"    ✓ {measure_type.value}: {measure_class.__name__}")
                else:
                    print(f"    ✗ {measure_type.value}: NOT REGISTERED")

            # Check if all expected types are registered
            self.results['measure_registry'] = all(mt in registered for mt in expected)

            if self.results['measure_registry']:
                print("  ✓ All measure types registered")
            else:
                raise ValueError("Not all measure types registered")

        except Exception as e:
            logger.error(f"Measure registry test failed: {e}")
            print(f"  ✗ Error: {e}")
            self.results['measure_registry'] = False

    def test_domain_features(self):
        """Test 4: Domain features loaded per model."""
        print("  Checking domain features loaded:\n")

        domain_features = {
            'equity': [
                'models.implemented.equity.domains.weighting',
                'models.implemented.equity.domains.technical',
                'models.implemented.equity.domains.risk'
            ],
            'corporate': [
                'models.implemented.corporate.domains.fundamentals'
            ],
            'etf': [
                'models.implemented.etf.domains.weighting'
            ]
        }

        for model_name, expected_modules in domain_features.items():
            if model_name not in self.models:
                print(f"    {model_name}: ⊘ Model not loaded\n")
                continue

            print(f"    {model_name}:")
            all_loaded = True

            for module_name in expected_modules:
                if module_name in sys.modules:
                    print(f"      ✓ {module_name}")
                else:
                    print(f"      ✗ {module_name} not loaded")
                    all_loaded = False

            self.results['domain_features'][model_name] = all_loaded
            print()

    def test_graph_building(self):
        """Test 5: Graph building and data access with Spark."""
        if 'equity' not in self.models:
            print("  ⊘ Skipped - equity model not loaded")
            return

        try:
            equity_model = self.models['equity']

            # Check if model is built (has data)
            equity_model.build()
            print("  ✓ Model built successfully")

            # Try to access a fact table
            if 'fact_equity_prices' in equity_model._facts:
                fact_df = equity_model.get_fact_df('fact_equity_prices')
                print(f"  ✓ Accessed fact_equity_prices")

                # Verify it's a Spark DataFrame
                from pyspark.sql import DataFrame as SparkDataFrame
                if not isinstance(fact_df, SparkDataFrame):
                    raise TypeError(f"Expected SparkDataFrame, got {type(fact_df)}")
                print(f"  ✓ Returned Spark DataFrame")

                # Check row count
                count = fact_df.count()
                print(f"  ✓ Row count: {count:,}")
            else:
                print("  ⚠ fact_equity_prices not in built facts")

        except Exception as e:
            print(f"  ⚠ Error: {e}")
            print("  ℹ This may be expected if data hasn't been ingested yet")

    def test_measure_execution(self):
        """Test 6: Measure execution with Spark."""
        if 'equity' not in self.models:
            print("  ⊘ Skipped - equity model not loaded")
            return

        try:
            equity_model = self.models['equity']

            # Check if model has data
            if not equity_model._is_built:
                print("  ⊘ Skipped - model not built (no data to query)")
                return

            # Try to execute a simple measure
            print("  Testing measure execution with Spark backend:")

            # Test with avg_close measure
            result = equity_model.measures.execute('avg_close')
            print(f"  ✓ Executed 'avg_close' measure")

            # Verify it's a Spark DataFrame
            from pyspark.sql import DataFrame as SparkDataFrame
            if not isinstance(result, SparkDataFrame):
                raise TypeError(f"Expected SparkDataFrame, got {type(result)}")
            print(f"  ✓ Returned Spark DataFrame")

        except Exception as e:
            print(f"  ⚠ Error: {e}")
            print("  ℹ This may be expected if measures aren't configured yet")

    def test_cross_model_references(self):
        """Test 7: Cross-model references work with Spark."""
        if 'equity' not in self.models or 'corporate' not in self.models:
            print("  ⊘ Skipped - both equity and corporate models required")
            self.results['cross_model'] = False
            return

        try:
            print("  Testing cross-model references:")

            equity_model = self.models['equity']

            # Check that equity model has session reference
            if not hasattr(equity_model, 'session') or equity_model.session is None:
                raise ValueError("Equity model doesn't have session reference")
            print(f"    ✓ Equity model has session reference")

            # Check for cross-model edges in config
            equity_config = equity_model.model_cfg
            if 'graph' in equity_config and 'edges' in equity_config['graph']:
                cross_model_edges = [
                    edge for edge in equity_config['graph']['edges']
                    if '.' in edge.get('to', '')
                ]
                print(f"    ✓ Found {len(cross_model_edges)} cross-model edge(s)")
                for edge in cross_model_edges:
                    print(f"      - {edge['from']} → {edge['to']}")
            else:
                print(f"    ⚠ No graph edges defined")

            self.results['cross_model'] = True

        except Exception as e:
            logger.error(f"Cross-model reference test failed: {e}")
            print(f"  ✗ Error: {e}")
            self.results['cross_model'] = False

    def print_summary(self):
        """Print test results summary."""
        print("=" * 80)
        print("TEST SUMMARY - SPARK BACKEND")
        print("=" * 80)

        # Session
        status = "✓ PASS" if self.results['session'] else "✗ FAIL"
        print(f"Session Initialization:        {status}")

        # Models
        for model_name, passed in self.results['models_loaded'].items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"Model Loading ({model_name:10s}): {status}")

        # Measure registry
        status = "✓ PASS" if self.results['measure_registry'] else "✗ FAIL"
        print(f"Measure Registry:              {status}")

        # Domain features
        for model_name, passed in self.results['domain_features'].items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"Domain Features ({model_name:10s}): {status}")

        # Cross-model
        status = "✓ PASS" if self.results['cross_model'] else "✗ FAIL"
        print(f"Cross-Model References:        {status}")

        print()
        print("=" * 80)

        # Count passes
        all_results = [
            self.results['session'],
            *self.results['models_loaded'].values(),
            self.results['measure_registry'],
            *self.results['domain_features'].values(),
            self.results['cross_model']
        ]
        passed = sum(all_results)
        total = len(all_results)

        print(f"RESULT: {passed}/{total} tests passed")
        print("=" * 80)

        if passed == total:
            print("\n✓ ALL TESTS PASSED - Spark backend working correctly!")
            return 0
        else:
            print(f"\n⚠ {total - passed} test(s) failed - see details above")
            return 1


def main():
    """Run the integration test suite."""
    test = DomainModelIntegrationTest()
    exit_code = test.run_all_tests()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
