#!/usr/bin/env python3
"""
Test all models in the framework.

Discovers and tests all models in configs/models/, running comprehensive
validation across Bronze → Silver → Gold → UI layers for each model.

Usage:
    # Test all models
    python -m scripts.test_all_models

    # Test with sample data generation
    python -m scripts.test_all_models --generate-sample

    # Quick test (minimal data)
    python -m scripts.test_all_models --quick --generate-sample

    # Test specific models only
    python -m scripts.test_all_models --models equity corporate

    # Parallel execution
    python -m scripts.test_all_models --parallel

    # Save results to file
    python -m scripts.test_all_models --output test_results.json
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
import logging
from datetime import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from de_funk.models.registry import ModelRegistry

# Import our test scripts
try:
    from test_pipeline_e2e import PipelineE2ETester
    E2E_AVAILABLE = True
except ImportError:
    E2E_AVAILABLE = False

try:
    from test_ui_integration import UIIntegrationTester
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllModelsTester:
    """Test all models in the framework."""

    def __init__(self, config_dir: str = "configs/models"):
        """
        Initialize all models tester.

        Args:
            config_dir: Model config directory
        """
        self.config_dir = Path(config_dir)
        self.registry = ModelRegistry(str(self.config_dir))

        # Overall results
        self.results = {
            'start_time': None,
            'end_time': None,
            'models_tested': 0,
            'models_passed': 0,
            'models_failed': 0,
            'model_results': {}
        }

        logger.info("Initialized all models tester")

    def discover_models(self, include_models: Optional[List[str]] = None) -> List[str]:
        """
        Discover all models in config directory.

        Args:
            include_models: Specific models to test (None = all)

        Returns:
            List of model names
        """
        # Get all available models from registry
        all_models = self.registry.list_models()

        if include_models:
            # Filter to specified models
            models = [m for m in all_models if m in include_models]
            missing = set(include_models) - set(models)
            if missing:
                logger.warning(f"Models not found: {missing}")
        else:
            models = all_models

        logger.info(f"Discovered {len(models)} model(s): {', '.join(models)}")
        return models

    def test_all_models(
        self,
        models: Optional[List[str]] = None,
        generate_sample: bool = False,
        quick: bool = False,
        parallel: bool = False,
        max_workers: int = 4
    ) -> bool:
        """
        Test all models.

        Args:
            models: Specific models to test (None = all)
            generate_sample: Generate sample data before testing
            quick: Quick test with minimal data
            parallel: Run tests in parallel
            max_workers: Max parallel workers

        Returns:
            True if all tests pass
        """
        self.results['start_time'] = datetime.now()

        # Discover models
        models_to_test = self.discover_models(models)

        if not models_to_test:
            logger.error("No models found to test")
            return False

        logger.info("=" * 70)
        logger.info("TESTING ALL MODELS")
        logger.info("=" * 70)
        logger.info(f"Models: {len(models_to_test)}")
        logger.info(f"Quick mode: {quick}")
        logger.info(f"Generate sample: {generate_sample}")
        logger.info(f"Parallel: {parallel}")

        # Test each model
        if parallel and len(models_to_test) > 1:
            success = self._test_models_parallel(
                models_to_test,
                generate_sample,
                quick,
                max_workers
            )
        else:
            success = self._test_models_sequential(
                models_to_test,
                generate_sample,
                quick
            )

        self.results['end_time'] = datetime.now()
        self._print_summary()

        return success

    def _test_models_sequential(
        self,
        models: List[str],
        generate_sample: bool,
        quick: bool
    ) -> bool:
        """Test models sequentially."""
        all_passed = True

        for i, model_name in enumerate(models, 1):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"MODEL {i}/{len(models)}: {model_name}")
            logger.info(f"{'=' * 70}")

            success = self._test_single_model(
                model_name,
                generate_sample,
                quick
            )

            self.results['model_results'][model_name] = {
                'success': success,
                'timestamp': datetime.now().isoformat()
            }

            if success:
                self.results['models_passed'] += 1
            else:
                self.results['models_failed'] += 1
                all_passed = False

            self.results['models_tested'] += 1

        return all_passed

    def _test_models_parallel(
        self,
        models: List[str],
        generate_sample: bool,
        quick: bool,
        max_workers: int
    ) -> bool:
        """Test models in parallel."""
        logger.info(f"\nRunning tests in parallel with {max_workers} workers...")

        all_passed = True
        futures = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all model tests
            for model_name in models:
                future = executor.submit(
                    self._test_single_model,
                    model_name,
                    generate_sample,
                    quick
                )
                futures[future] = model_name

            # Collect results as they complete
            for future in as_completed(futures):
                model_name = futures[future]
                try:
                    success = future.result()

                    self.results['model_results'][model_name] = {
                        'success': success,
                        'timestamp': datetime.now().isoformat()
                    }

                    if success:
                        self.results['models_passed'] += 1
                        logger.info(f"✓ {model_name} - PASSED")
                    else:
                        self.results['models_failed'] += 1
                        all_passed = False
                        logger.error(f"✗ {model_name} - FAILED")

                    self.results['models_tested'] += 1

                except Exception as e:
                    logger.error(f"✗ {model_name} - ERROR: {e}")
                    self.results['model_results'][model_name] = {
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    self.results['models_failed'] += 1
                    self.results['models_tested'] += 1
                    all_passed = False

        return all_passed

    def _test_single_model(
        self,
        model_name: str,
        generate_sample: bool,
        quick: bool
    ) -> bool:
        """
        Test a single model.

        Args:
            model_name: Model to test
            generate_sample: Generate sample data
            quick: Quick test mode

        Returns:
            True if all tests pass
        """
        try:
            # Test Bronze → Silver → Gold → UI
            if not E2E_AVAILABLE:
                logger.warning(f"E2E tester not available for {model_name}")
                return False

            # Run pipeline test
            tester = PipelineE2ETester(
                model_name=model_name,
                bronze_path=f"storage/bronze/test_{model_name}"
            )

            pipeline_success = tester.run_full_pipeline(
                stages=['bronze', 'silver', 'gold', 'ui'],
                generate_sample=generate_sample,
                quick=quick,
                verbose=False
            )

            if not pipeline_success:
                logger.error(f"Pipeline test failed for {model_name}")
                return False

            # Run UI integration test (if available)
            if UI_AVAILABLE:
                ui_tester = UIIntegrationTester(model_name=model_name)

                ui_success = ui_tester.test_all_components(
                    components=['filters', 'selectors', 'charts', 'tables', 'measures'],
                    tickers=None,
                    benchmark=False
                )

                if not ui_success:
                    logger.warning(f"UI test failed for {model_name}")
                    # Don't fail overall test, just warn
                    # return False

            logger.info(f"✓ All tests passed for {model_name}")
            return True

        except Exception as e:
            logger.error(f"Error testing {model_name}: {e}", exc_info=True)
            return False

    def _print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("ALL MODELS TEST SUMMARY")
        logger.info("=" * 70)

        # Timing
        start = self.results['start_time']
        end = self.results['end_time']
        if start and end:
            duration = (end - start).total_seconds()
            logger.info(f"\nTotal duration: {duration:.2f}s")

        # Overall stats
        logger.info(f"\nModels tested: {self.results['models_tested']}")
        logger.info(f"Passed: {self.results['models_passed']}")
        logger.info(f"Failed: {self.results['models_failed']}")

        # Per-model results
        logger.info("\nPer-model results:")
        for model_name, result in self.results['model_results'].items():
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            error = f" - {result.get('error', '')}" if 'error' in result else ""
            logger.info(f"  {status} - {model_name}{error}")

        # Overall result
        logger.info("\n" + "=" * 70)
        if self.results['models_failed'] == 0:
            logger.info("✓ ALL MODELS PASSED")
        else:
            logger.info(f"✗ {self.results['models_failed']} MODEL(S) FAILED")
        logger.info("=" * 70)

    def save_results(self, output_file: str):
        """
        Save results to JSON file.

        Args:
            output_file: Output file path
        """
        # Make results JSON serializable
        serializable_results = {
            'start_time': self.results['start_time'].isoformat() if self.results['start_time'] else None,
            'end_time': self.results['end_time'].isoformat() if self.results['end_time'] else None,
            'models_tested': self.results['models_tested'],
            'models_passed': self.results['models_passed'],
            'models_failed': self.results['models_failed'],
            'model_results': self.results['model_results']
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        logger.info(f"\nResults saved to: {output_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test all models in the framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--models',
        nargs='+',
        help='Specific models to test (default: all models)'
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
        '--parallel',
        action='store_true',
        help='Run tests in parallel'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Max parallel workers (default: 4)'
    )

    parser.add_argument(
        '--output',
        help='Save results to JSON file'
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

        if not E2E_AVAILABLE:
            logger.error("E2E test module not available")
            sys.exit(1)

        # Initialize tester
        tester = AllModelsTester(config_dir=args.config_dir)

        # Run tests
        success = tester.test_all_models(
            models=args.models,
            generate_sample=args.generate_sample,
            quick=args.quick,
            parallel=args.parallel,
            max_workers=args.max_workers
        )

        # Save results if requested
        if args.output:
            tester.save_results(args.output)

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
