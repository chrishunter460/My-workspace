#!/usr/bin/env python3
"""
Real Bronze->Silver build validation for v4 domain models.

Uses the actual Spark cluster and existing build pipeline to build v4
models from real Bronze Delta Lake data, writing Silver output as Delta.

This script is a thin wrapper around build_models.py that:
1. Connects to the Spark cluster via get_spark()
2. Discovers v4 builders from domains/ markdown configs
3. Builds models using GraphBuilder (Bronze Delta -> Spark DataFrames)
4. Writes Silver output as Delta via ModelWriter

Usage:
    # Dry run — see what v4 models would be built
    python -m scripts.validate.validate_v4_build_real --dry-run

    # Build all v4 models (last 30 days of data)
    python -m scripts.validate.validate_v4_build_real --storage-root /shared/storage

    # Build specific model with date filter
    python -m scripts.validate.validate_v4_build_real --model county_property \\
        --storage-root /shared/storage --date-from 2025-02-01 --date-to 2025-02-28

    # Build with verbose output
    python -m scripts.validate.validate_v4_build_real --storage-root /shared/storage --verbose
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import sys
import argparse
import logging
from pathlib import Path
from datetime import date, timedelta

_script_dir = Path(__file__).resolve().parent
_repo_root = _script_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def discover_v4_models(repo_root: Path):
    """List all v4 models that would be discovered by the build pipeline."""
    from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader

    domains_dir = repo_root / "domains"
    loader = get_domain_loader(domains_dir)

    if not isinstance(loader, DomainConfigLoaderV4):
        logger.error(f"{domains_dir} is not a v4 domain directory")
        return []

    models = sorted(loader.list_models())
    logger.info(f"Found {len(models)} v4 models: {', '.join(models)}")
    return models


def check_bronze_coverage(repo_root: Path, storage_root: Path):
    """
    Check which v4 source 'from:' specs map to real Bronze data.

    Returns dict of model -> {found: [...], missing: [...]}
    """
    from de_funk.config.domain import DomainConfigLoaderV4, get_domain_loader
    from de_funk.config.domain.config_translator import translate_domain_config

    domains_dir = repo_root / "domains"
    loader = get_domain_loader(domains_dir)
    bronze_root = storage_root / "bronze"

    coverage = {}

    for model_name in sorted(loader.list_models()):
        try:
            v4_config = loader.load_model_config(model_name)
            translated = translate_domain_config(v4_config)
            nodes = translated.get("graph", {}).get("nodes", {})

            found = []
            missing = []

            for node_id, node_config in nodes.items():
                from_spec = node_config.get("from", "")
                if not from_spec.startswith("bronze."):
                    continue

                # Resolve bronze path (after _normalize_from, format is bronze.provider.table)
                raw = from_spec.replace("bronze.", "", 1)
                # Convert dots to slashes for filesystem path
                rel_path = raw.replace(".", "/")
                path = bronze_root / rel_path
                if path.exists():
                    found.append(f"{node_id} <- {from_spec} ({path})")
                else:
                    missing.append(f"{node_id} <- {from_spec}")

            coverage[model_name] = {"found": found, "missing": missing}

        except Exception as e:
            coverage[model_name] = {"found": [], "missing": [], "error": str(e)}

    return coverage


def run_build(
    models: list,
    storage_root: Path,
    date_from: str,
    date_to: str,
    dry_run: bool = False,
    verbose: bool = False,
    silver_subdir: str = "silver_v4",
):
    """
    Run the build pipeline for v4 models using the Spark cluster.

    Uses the existing build_models infrastructure which handles:
    - Spark session with Delta Lake support
    - GraphBuilder for node building (Bronze -> Spark DataFrames)
    - ModelWriter for Delta writes to Silver
    """
    from scripts.build.build_models import build_models

    # Write v4 Silver output to a separate directory to avoid clobbering v3
    v4_silver_root = storage_root / silver_subdir
    v4_silver_root.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building {len(models)} v4 models")
    logger.info(f"  Date range: {date_from} to {date_to}")
    logger.info(f"  Storage root: {storage_root}")
    logger.info(f"  Silver output: {v4_silver_root}")
    logger.info(f"  Dry run: {dry_run}")

    results = build_models(
        models=models,
        dry_run=dry_run,
        verbose=verbose,
        date_from=date_from,
        date_to=date_to,
        storage_root=storage_root,
        skip_deps=True,  # v4 models may reference v3 deps that don't exist yet
    )

    return results


def validate_silver_output(storage_root: Path, silver_subdir: str = "silver_v4"):
    """Validate Silver Delta output after build."""
    silver_root = storage_root / silver_subdir

    if not silver_root.exists():
        logger.warning(f"Silver output directory not found: {silver_root}")
        return

    logger.info(f"\nValidating Silver output at {silver_root}")

    for model_dir in sorted(silver_root.iterdir()):
        if not model_dir.is_dir():
            continue

        logger.info(f"\n  Model: {model_dir.name}")

        for subdir in ["dims", "facts"]:
            sub_path = model_dir / subdir
            if not sub_path.exists():
                continue

            for table_dir in sorted(sub_path.iterdir()):
                if not table_dir.is_dir():
                    continue

                # Check for Delta log
                delta_log = table_dir / "_delta_log"
                has_delta = delta_log.exists()

                # Count data files
                data_files = list(table_dir.glob("*.parquet"))

                format_str = "Delta" if has_delta else "Parquet"
                logger.info(
                    f"    {subdir}/{table_dir.name}: "
                    f"{len(data_files)} files ({format_str})"
                )


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Build v4 models from real Bronze data using Spark cluster + Delta"
    )
    parser.add_argument(
        "--model", type=str, nargs="+",
        help="Specific model(s) to build (default: all v4 models with Bronze data)"
    )
    parser.add_argument(
        "--storage-root", type=Path, default=Path("/shared/storage"),
        help="Storage root with bronze/ directory (default: /shared/storage)"
    )
    parser.add_argument(
        "--date-from", type=str,
        default=(date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),
        help="Start date filter (default: 30 days ago)"
    )
    parser.add_argument(
        "--date-to", type=str,
        default=date.today().strftime("%Y-%m-%d"),
        help="End date filter (default: today)"
    )
    parser.add_argument(
        "--silver-subdir", type=str, default="silver_v4",
        help="Silver output subdirectory (default: silver_v4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be built without executing"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show detailed build output"
    )
    parser.add_argument(
        "--check-coverage", action="store_true",
        help="Only check Bronze data coverage, don't build"
    )
    args = parser.parse_args()

    repo_root_path = Path(repo_root)

    # Step 1: Discover v4 models
    all_models = discover_v4_models(repo_root_path)

    if args.check_coverage:
        # Just show Bronze coverage and exit
        coverage = check_bronze_coverage(repo_root_path, args.storage_root)

        buildable = []
        for model, info in sorted(coverage.items()):
            if info.get("error"):
                logger.info(f"  {model}: ERROR — {info['error']}")
                continue

            found = len(info["found"])
            missing = len(info["missing"])
            status = "READY" if found > 0 and missing == 0 else (
                "PARTIAL" if found > 0 else "NO DATA"
            )

            logger.info(f"  {model}: {status} ({found} found, {missing} missing)")

            if info["missing"]:
                for m in info["missing"]:
                    logger.info(f"    MISSING: {m}")

            if found > 0:
                buildable.append(model)

        logger.info(f"\nBuildable models: {len(buildable)}/{len(coverage)}")
        logger.info(f"  {', '.join(buildable)}")
        return 0

    # Step 2: Determine which models to build
    if args.model:
        models_to_build = args.model
    else:
        # Auto-select models with Bronze data coverage
        coverage = check_bronze_coverage(repo_root_path, args.storage_root)
        models_to_build = [
            model for model, info in coverage.items()
            if len(info.get("found", [])) > 0 and not info.get("error")
        ]

    if not models_to_build:
        logger.error("No models to build (no Bronze data found)")
        return 1

    logger.info(f"\nModels to build: {', '.join(models_to_build)}")

    # Step 3: Run build
    results = run_build(
        models=models_to_build,
        storage_root=args.storage_root,
        date_from=args.date_from,
        date_to=args.date_to,
        dry_run=args.dry_run,
        verbose=args.verbose,
        silver_subdir=args.silver_subdir,
    )

    # Step 4: Validate output
    if not args.dry_run and results:
        validate_silver_output(args.storage_root, args.silver_subdir)

    # Summary
    if results:
        successful = sum(1 for r in results.values() if r.success)
        failed = len(results) - successful
        logger.info(f"\nBuild complete: {successful} succeeded, {failed} failed")

        if failed > 0:
            for name, r in results.items():
                if not r.success:
                    logger.error(f"  FAILED: {name} — {r.error}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
