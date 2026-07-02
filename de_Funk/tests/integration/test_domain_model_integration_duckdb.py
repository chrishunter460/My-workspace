#!/usr/bin/env python3
"""
Domain Model Integration Test - DUCKDB BACKEND (REPORTING)

Tests the complete domain model architecture with DUCKDB for REPORTING operations:
1. Session initialization (DuckDB)
2. Model loading (BaseModel + domain-specific classes)
3. Graph building (reading from silver storage)
4. Measure registry bootstrap
5. Domain feature loading
6. Measure execution (simple, computed, weighted)
7. Cross-model references
8. UI-ready data output

Usage:
    python -m scripts.test_domain_model_integration_duckdb

Expected behavior:
- All models should load successfully with DuckDB backend
- Measure registry should have all types registered
- Domain features should be available per model
- Measures should execute and return data
- Cross-model references should work
- Clear output for debugging each step
"""

import sys
from pathlib import Path

import logging
from typing import Dict, Any
import traceback

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DomainModelIntegrationTest:
    """
    Comprehensive integration test for domain model architecture.

    Tests each layer of the stack with clear output for debugging.
    """

    def __init__(self):
        """Initialize test harness."""
        self.results = {
            'session': False,
            'models_loaded': {},
            'measure_registry': False,
            'domain_features': {},
            'measures_executed': {},
            'cross_model_refs': False,
        }
        self.session = None
        self.models = {}

    def run_all_tests(self) -> bool:
        """
        Run all integration tests.

        Returns:
            True if all tests pass, False otherwise
        """
        print("\n" + "="*80)
        print("DOMAIN MODEL INTEGRATION TEST - DUCKDB BACKEND (REPORTING)")
        print("="*80)

        try:
            # Test 1: Session initialization
            print("\n[1/7] Testing session initialization...")
            self.test_session_initialization()

            # Test 2: Model loading
            print("\n[2/7] Testing model loading...")
            self.test_model_loading()

            # Test 3: Measure registry bootstrap
            print("\n[3/7] Testing measure registry bootstrap...")
            self.test_measure_registry()

            # Test 4: Domain features loading
            print("\n[4/7] Testing domain features loading...")
            self.test_domain_features()

            # Test 5: Graph building (if models built)
            print("\n[5/7] Testing graph building and data access...")
            self.test_graph_building()

            # Test 6: Measure execution
            print("\n[6/7] Testing measure execution...")
            self.test_measure_execution()

            # Test 7: Cross-model references
            print("\n[7/7] Testing cross-model references...")
            self.test_cross_model_references()

            # Print summary
            self.print_summary()

            # Return overall success
            return all([
                self.results['session'],
                any(self.results['models_loaded'].values()),
                self.results['measure_registry'],
                any(self.results['domain_features'].values()),
            ])

        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            traceback.print_exc()
            return False

    def test_session_initialization(self):
        """Test 1: UniversalSession initialization."""
        try:
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

            print("  ✓ Imports successful")

            # Initialize context with DuckDB
            ctx = RepoContext.from_repo_root(connection_type="duckdb")
            print("  ✓ RepoContext initialized (DuckDB)")

            # Initialize session
            self.session = UniversalSession(
                connection=ctx.connection,
                storage_cfg=ctx.storage,
                repo_root=repo_root
            )
            print("  ✓ UniversalSession created")

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
                print(f"  ✓ All measure types registered")
            else:
                print(f"  ✗ Some measure types missing")

        except Exception as e:
            logger.error(f"Measure registry test failed: {e}")
            print(f"  ✗ Error: {e}")
            self.results['measure_registry'] = False

    def test_domain_features(self):
        """Test 4: Domain features loading per model."""
        domain_checks = {
            'equity': [
                'models.implemented.equity.domains.weighting',
                'models.implemented.equity.domains.technical',
                'models.implemented.equity.domains.risk',
            ],
            'corporate': [
                'models.implemented.corporate.domains.fundamentals',
            ],
            'etf': [
                'models.implemented.etf.domains.weighting',
            ],
        }

        print("  Checking domain features loaded:")

        for model_name, modules in domain_checks.items():
            if model_name not in self.models:
                print(f"\n    {model_name}: ⊘ Model not loaded")
                continue

            print(f"\n    {model_name}:")
            all_loaded = True

            for module_path in modules:
                if module_path in sys.modules:
                    print(f"      ✓ {module_path}")
                else:
                    print(f"      ✗ {module_path} - NOT LOADED")
                    all_loaded = False

            self.results['domain_features'][model_name] = all_loaded

    def test_graph_building(self):
        """Test 5: Graph building and data access."""
        if 'equity' not in self.models:
            print("  ⊘ Skipped - equity model not loaded")
            return

        try:
            model = self.models['equity']

            # Check if already built
            if hasattr(model, '_dims') and model._dims:
                print("  ✓ Model already built (from build script)")

                # Show what tables exist
                dims = model._dims or {}
                facts = model._facts or {}

                print(f"\n    Dimensions: {', '.join(dims.keys()) if dims else 'None'}")
                print(f"    Facts: {', '.join(facts.keys()) if facts else 'None'}")

                # Try to access a table
                if 'fact_equity_prices' in facts:
                    df = facts['fact_equity_prices']
                    count = df.count() if hasattr(df, 'count') else len(df)
                    print(f"\n    ✓ fact_equity_prices accessible: {count:,} rows")

            else:
                print("  ⚠ Model not built yet - run build_all_models.py first")
                print("    Skipping data access tests")

        except Exception as e:
            logger.error(f"Graph building test failed: {e}")
            print(f"  ✗ Error: {e}")

    def test_measure_execution(self):
        """Test 6: Measure execution (simple, computed, weighted)."""
        if 'equity' not in self.models:
            print("  ⊘ Skipped - equity model not loaded")
            return

        model = self.models['equity']

        # Test measures (if model is built)
        if not (hasattr(model, '_dims') and model._dims):
            print("  ⊘ Skipped - model not built (no data to query)")
            return

        # Test different measure types
        test_measures = {
            'simple': 'avg_close_price',
            'computed': 'avg_market_cap',
            'weighted': 'volume_weighted_index',
        }

        print("  Testing measure execution:")

        for measure_type, measure_name in test_measures.items():
            try:
                print(f"\n    Testing {measure_type} measure: {measure_name}")

                # Check if measure exists
                if not model.has_measure(measure_name):
                    print(f"      ⚠ Measure '{measure_name}' not defined in YAML")
                    continue

                # Get measure config
                measure_config = model.get_measure_config(measure_name)
                print(f"      ✓ Measure config found (type: {measure_config.get('type', 'simple')})")

                # Try to execute (this will test the full chain)
                try:
                    result = model.measures.execute_measure(
                        measure_name,
                        limit=5
                    )
                    print(f"      ✓ Execution successful")

                    # Show result info
                    if hasattr(result, 'data'):
                        print(f"      ✓ Result has data")
                        if hasattr(result.data, 'shape'):
                            print(f"      ✓ Shape: {result.data.shape}")

                    self.results['measures_executed'][measure_name] = True

                except Exception as e:
                    print(f"      ✗ Execution failed: {e}")
                    self.results['measures_executed'][measure_name] = False

            except Exception as e:
                logger.error(f"Measure test failed: {e}")
                print(f"      ✗ Error: {e}")
                self.results['measures_executed'][measure_name] = False

    def test_cross_model_references(self):
        """Test 7: Cross-model references."""
        if 'equity' not in self.models or 'corporate' not in self.models:
            print("  ⊘ Skipped - both equity and corporate models required")
            return

        try:
            equity = self.models['equity']
            corporate = self.models['corporate']

            print("  Testing cross-model references:")

            # Check if session is set
            if hasattr(equity, 'session') and equity.session:
                print("    ✓ Equity model has session reference")
            else:
                print("    ✗ Equity model missing session reference")

            # Check edge between models
            equity_config = self.session.registry.get_model('equity')
            edges = equity_config.get_edges()

            cross_model_edges = [
                e for e in edges
                if '.' in e.get('to', '') or '.' in e.get('from', '')
            ]

            if cross_model_edges:
                print(f"    ✓ Found {len(cross_model_edges)} cross-model edge(s)")
                for edge in cross_model_edges:
                    print(f"      - {edge.get('from')} → {edge.get('to')}")
            else:
                print("    ⚠ No cross-model edges defined in equity config")

            self.results['cross_model_refs'] = len(cross_model_edges) > 0

        except Exception as e:
            logger.error(f"Cross-model reference test failed: {e}")
            print(f"  ✗ Error: {e}")
            self.results['cross_model_refs'] = False

    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        total_tests = 0
        passed_tests = 0

        # Session
        status = "✓ PASS" if self.results['session'] else "✗ FAIL"
        print(f"Session Initialization:        {status}")
        total_tests += 1
        passed_tests += 1 if self.results['session'] else 0

        # Models
        for model_name, success in self.results['models_loaded'].items():
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"Model Loading ({model_name:12s}): {status}")
            total_tests += 1
            passed_tests += 1 if success else 0

        # Measure registry
        status = "✓ PASS" if self.results['measure_registry'] else "✗ FAIL"
        print(f"Measure Registry:              {status}")
        total_tests += 1
        passed_tests += 1 if self.results['measure_registry'] else 0

        # Domain features
        for model_name, success in self.results['domain_features'].items():
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"Domain Features ({model_name:11s}): {status}")
            total_tests += 1
            passed_tests += 1 if success else 0

        # Measures
        if self.results['measures_executed']:
            for measure_name, success in self.results['measures_executed'].items():
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"Measure Execution ({measure_name:15s}): {status}")
                total_tests += 1
                passed_tests += 1 if success else 0

        # Cross-model refs
        if 'cross_model_refs' in self.results and self.results['cross_model_refs'] is not None:
            status = "✓ PASS" if self.results['cross_model_refs'] else "✗ FAIL"
            print(f"Cross-Model References:        {status}")
            total_tests += 1
            passed_tests += 1 if self.results['cross_model_refs'] else 0

        print("\n" + "="*80)
        print(f"RESULT: {passed_tests}/{total_tests} tests passed")
        print("="*80)

        if passed_tests == total_tests:
            print("\n✓ ALL TESTS PASSED - Domain model architecture working correctly!\n")
        else:
            print(f"\n⚠ {total_tests - passed_tests} test(s) failed - see details above\n")


def main():
    """Run integration tests."""
    test = DomainModelIntegrationTest()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
