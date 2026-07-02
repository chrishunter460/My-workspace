#!/usr/bin/env python3
"""
Validate All Scripts - Comprehensive Script Runner

Runs all scripts across all categories with minimal test parameters to
validate they work correctly after changes.

This is a "smoke test" that executes scripts with small sample data to
catch breaking changes, import errors, and runtime issues.

Usage:
    python -m scripts.validate_all_scripts
    python -m scripts.validate_all_scripts --category build
    python -m scripts.validate_all_scripts --include-maintenance
    python -m scripts.validate_all_scripts --verbose
    python -m scripts.validate_all_scripts --report report.json
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import get_logger, setup_logging

logger = get_logger(__name__)


@dataclass
class ScriptRunResult:
    """Result of running a single script."""
    script: str
    category: str
    command: List[str]
    success: bool
    duration: float
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class ValidationSummary:
    """Summary of all script validations."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[ScriptRunResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


class ScriptValidator:
    """Validates all scripts by running them with minimal parameters."""

    # Script configurations with test parameters
    SCRIPT_CONFIGS = {
        'build': {
            'build_all_models.py': {
                'args': ['--max-tickers', '5', '--days', '7', '--skip-ingestion'],
                'timeout': 120,
            },
            'build_equity_silver.py': {
                'args': [],
                'timeout': 60,
                'skip': True,  # Requires specific Bronze data
                'skip_reason': 'Requires Bronze data - tested by build_all_models'
            },
            'build_silver_layer.py': {
                'args': [],
                'timeout': 60,
            },
            'build_weighted_aggregates_duckdb.py': {
                'args': [],
                'timeout': 60,
                'skip': True,
                'skip_reason': 'Requires Silver data - tested in integration'
            },
            'build_weighted_views.py': {
                'args': [],
                'timeout': 60,
                'skip': True,
                'skip_reason': 'Requires Silver data - tested in integration'
            },
            'rebuild_model.py': {
                'args': ['--model', 'core', '--dry-run'],
                'timeout': 60,
            },
        },
        'ingest': {
            'Bronze_pull.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Simple script with no args - syntax validated'
            },
            'run_full_pipeline.py': {
                'args': ['--days', '7', '--max-tickers', '5'],
                'timeout': 180,
                'skip': True,
                'skip_reason': 'Long-running - use for full validation only'
            },
            'reingest_exchanges.py': {
                'args': ['--help'],
                'timeout': 30,
            },
        },
        'maintenance': {
            'clear_and_refresh.py': {
                'args': ['--help'],
                'timeout': 30,
                'requires_flag': True,  # Don't run without explicit flag
            },
            'clear_silver.py': {
                'args': ['--help'],
                'timeout': 30,
                'requires_flag': True,
            },
            'reset_model.py': {
                'args': ['--help'],
                'timeout': 30,
                'requires_flag': True,
            },
        },
        'forecast': {
            'run_forecasts.py': {
                'args': ['--help'],
                'timeout': 60,
            },
            'run_forecasts_large_cap.py': {
                'args': ['--help'],
                'timeout': 60,
            },
            'verify_forecast_config.py': {
                'args': ['--help'],
                'timeout': 30,
            },
        },
        'debug': {
            'check_parquet_path.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Requires specific path argument'
            },
            'debug_exchange_data.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Debug tool - requires data'
            },
            'debug_forecast_view.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Debug tool - requires data'
            },
            'debug_session_injection.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Debug tool - requires data'
            },
            'debug_weighted_views.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Debug tool - requires data'
            },
            'diagnose_view_data.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Debug tool - requires data'
            },
            'drop_view.py': {
                'args': [],
                'timeout': 30,
                'skip': True,
                'skip_reason': 'Empty file - utility placeholder'
            },
        },
    }

    def __init__(self, verbose: bool = False, include_maintenance: bool = False):
        """
        Initialize script validator.

        Args:
            verbose: Enable verbose output
            include_maintenance: Include destructive maintenance scripts
        """
        self.verbose = verbose
        self.include_maintenance = include_maintenance
        self.summary = ValidationSummary()

    def run_script(self, category: str, script: str, config: dict) -> ScriptRunResult:
        """
        Run a single script with configured parameters.

        Args:
            category: Script category
            script: Script filename
            config: Script configuration

        Returns:
            ScriptRunResult
        """
        # Check if script should be skipped
        if config.get('skip', False):
            logger.debug(f"Skipping {category}/{script}: {config.get('skip_reason', 'configured')}")
            return ScriptRunResult(
                script=script,
                category=category,
                command=[],
                success=True,
                duration=0,
                skipped=True,
                skip_reason=config.get('skip_reason', 'Skipped by configuration')
            )

        # Check if maintenance script without flag
        if config.get('requires_flag', False) and not self.include_maintenance:
            logger.debug(f"Skipping maintenance script {category}/{script}")
            return ScriptRunResult(
                script=script,
                category=category,
                command=[],
                success=True,
                duration=0,
                skipped=True,
                skip_reason='Maintenance script - use --include-maintenance to run'
            )

        # Build command
        script_path = f"scripts.{category}.{script[:-3]}"  # Remove .py
        command = [sys.executable, '-m', script_path] + config.get('args', [])
        timeout = config.get('timeout', 60)

        result = ScriptRunResult(
            script=script,
            category=category,
            command=command,
            success=False,
            duration=0
        )

        if self.verbose:
            print(f"\n{'='*70}")
            print(f"Running: {category}/{script}")
            print(f"Command: {' '.join(command)}")
            print(f"Timeout: {timeout}s")
            print(f"{'='*70}")

        logger.info(f"Running {category}/{script} with timeout={timeout}s")

        try:
            start = datetime.now()
            proc = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout,
                text=True,
                cwd=repo_root
            )
            end = datetime.now()

            result.duration = (end - start).total_seconds()
            result.stdout = proc.stdout
            result.stderr = proc.stderr
            result.success = proc.returncode == 0

            if result.success:
                logger.info(f"{category}/{script} PASSED ({result.duration:.2f}s)")
            else:
                logger.warning(f"{category}/{script} FAILED (exit code {proc.returncode})")
                logger.debug(f"stderr: {proc.stderr[:500] if proc.stderr else 'none'}")

            if self.verbose:
                print(f"Duration: {result.duration:.2f}s")
                print(f"Return Code: {proc.returncode}")
                if proc.stdout:
                    print(f"STDOUT:\n{proc.stdout[:500]}")
                if proc.stderr:
                    print(f"STDERR:\n{proc.stderr[:500]}")

        except subprocess.TimeoutExpired:
            result.error = f"Timeout after {timeout}s"
            result.success = False
            logger.error(f"{category}/{script} TIMEOUT after {timeout}s")
        except Exception as e:
            result.error = str(e)
            result.success = False
            logger.error(f"{category}/{script} ERROR: {e}", exc_info=True)

        return result

    def validate_category(self, category: str) -> List[ScriptRunResult]:
        """
        Validate all scripts in a category.

        Args:
            category: Category name

        Returns:
            List of results
        """
        results = []

        if category not in self.SCRIPT_CONFIGS:
            logger.warning(f"Unknown category: {category}")
            print(f"Unknown category: {category}")
            return results

        scripts = self.SCRIPT_CONFIGS[category]
        print(f"\n{'='*70}")
        print(f"Validating {category.upper()} scripts ({len(scripts)} scripts)")
        print(f"{'='*70}")
        logger.info(f"Validating {category} category ({len(scripts)} scripts)")

        for script, config in scripts.items():
            if not self.verbose:
                print(f"  {script}...", end=" ", flush=True)

            result = self.run_script(category, script, config)
            results.append(result)

            if not self.verbose:
                if result.skipped:
                    print("SKIP")
                elif result.success:
                    print(f"PASS ({result.duration:.1f}s)")
                else:
                    print(f"FAIL ({result.error or 'non-zero exit'})")

        return results

    def validate_all(self, category_filter: Optional[str] = None) -> ValidationSummary:
        """
        Validate all scripts (or filtered by category).

        Args:
            category_filter: Optional category to filter

        Returns:
            ValidationSummary
        """
        self.summary.start_time = datetime.now()
        logger.info(f"Starting validation (filter={category_filter or 'all'})")

        categories = [category_filter] if category_filter else self.SCRIPT_CONFIGS.keys()

        for category in categories:
            results = self.validate_category(category)
            self.summary.results.extend(results)

        # Update summary stats
        for result in self.summary.results:
            self.summary.total += 1
            if result.skipped:
                self.summary.skipped += 1
            elif result.success:
                self.summary.passed += 1
            else:
                self.summary.failed += 1

        self.summary.end_time = datetime.now()
        logger.info(f"Validation complete: {self.summary.passed}/{self.summary.total} passed, "
                   f"{self.summary.failed} failed, {self.summary.skipped} skipped")
        return self.summary

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        print()

        print(f"Total Scripts:   {self.summary.total}")
        print(f"Passed:          {self.summary.passed}")
        print(f"Failed:          {self.summary.failed}")
        print(f"Skipped:         {self.summary.skipped}")
        print(f"Pass Rate:       {self.summary.pass_rate:.1f}%")
        print(f"Duration:        {self.summary.duration:.1f}s")
        print()

        # Failed scripts
        if self.summary.failed > 0:
            print("="*70)
            print("FAILED SCRIPTS")
            print("="*70)
            print()

            for result in self.summary.results:
                if not result.success and not result.skipped:
                    print(f"  {result.category}/{result.script}")
                    print(f"   Command: {' '.join(result.command)}")
                    print(f"   Error: {result.error or 'Non-zero exit code'}")
                    if result.stderr:
                        print(f"   Stderr: {result.stderr[:200]}...")
                    print()

        # Skipped scripts
        if self.verbose and self.summary.skipped > 0:
            print("="*70)
            print("SKIPPED SCRIPTS")
            print("="*70)
            print()

            for result in self.summary.results:
                if result.skipped:
                    print(f"  {result.category}/{result.script}")
                    print(f"   Reason: {result.skip_reason}")
                    print()

        # Final status
        print("="*70)
        if self.summary.failed == 0:
            print("ALL SCRIPTS VALIDATED SUCCESSFULLY")
        else:
            print(f"{self.summary.failed} SCRIPT(S) FAILED VALIDATION")
        print("="*70)

    def save_report(self, output_file: Path):
        """
        Save validation report to JSON.

        Args:
            output_file: Output file path
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': self.summary.total,
                'passed': self.summary.passed,
                'failed': self.summary.failed,
                'skipped': self.summary.skipped,
                'pass_rate': self.summary.pass_rate,
                'duration': self.summary.duration,
            },
            'results': [
                {
                    'category': r.category,
                    'script': r.script,
                    'command': ' '.join(r.command),
                    'success': r.success,
                    'duration': r.duration,
                    'skipped': r.skipped,
                    'skip_reason': r.skip_reason,
                    'error': r.error,
                    'stderr_preview': r.stderr[:500] if r.stderr else None,
                }
                for r in self.summary.results
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved to: {output_file}")
        print(f"\nReport saved to: {output_file}")


def main():
    """Main entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Validate all scripts by running them with test parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--category',
        choices=['build', 'ingest', 'maintenance', 'forecast', 'debug'],
        help='Validate only scripts in specific category'
    )

    parser.add_argument(
        '--include-maintenance',
        action='store_true',
        help='Include destructive maintenance scripts (clear, reset, etc.)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output with full command output'
    )

    parser.add_argument(
        '--report',
        type=Path,
        help='Save validation report to JSON file'
    )

    args = parser.parse_args()

    # Warning for maintenance scripts
    if args.include_maintenance:
        print("WARNING: Including maintenance scripts!")
        print("   These scripts may modify or delete data.")
        print("   Press Ctrl+C within 3 seconds to cancel...")
        logger.warning("Including maintenance scripts - waiting for confirmation")
        import time
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            print("\nCancelled")
            logger.info("Cancelled by user")
            sys.exit(1)

    # Run validation
    print("Validating all scripts with test parameters...")
    print()
    logger.info("Starting script validation")

    validator = ScriptValidator(
        verbose=args.verbose,
        include_maintenance=args.include_maintenance
    )

    validator.validate_all(category_filter=args.category)
    validator.print_summary()

    if args.report:
        validator.save_report(args.report)

    # Exit with appropriate code
    sys.exit(0 if validator.summary.failed == 0 else 1)


if __name__ == '__main__':
    main()
