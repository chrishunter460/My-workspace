#!/usr/bin/env python3
"""
Clear storage and refresh all data from scratch.

This script will:
1. Delete all bronze and silver storage
2. Re-ingest data from Alpha Vantage API
3. Rebuild silver layer models

WARNING: This will delete all existing data!

Usage:
    python -m scripts.clear_and_refresh

    # Skip confirmation prompt
    python -m scripts.clear_and_refresh --yes

    # Only clear bronze (keep silver)
    python -m scripts.clear_and_refresh --bronze-only

    # Only clear silver (keep bronze)
    python -m scripts.clear_and_refresh --silver-only
"""

import sys
import traceback
from pathlib import Path

import argparse
import shutil
from datetime import datetime, timedelta

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def confirm_action(prompt: str) -> bool:
    """Ask user for confirmation."""
    response = input(f"{prompt} (yes/no): ").strip().lower()
    return response in ['yes', 'y']


def clear_storage(bronze: bool = True, silver: bool = True, skip_confirm: bool = False):
    """Clear bronze and/or silver storage for v2.0 unified architecture."""
from de_funk.core.context import RepoContext

    print("=" * 80)
    print("CLEAR STORAGE AND REFRESH DATA")
    print("=" * 80)
    print()

    # Initialize context to get storage paths
    # NOTE: Use Spark for entire data pipeline (facets + model builds require PySpark)
    print("Initializing context with Spark (required for data pipeline)...")
    ctx = RepoContext.from_repo_root(connection_type="spark")

    storage_root = ctx.repo / "storage"

    # v2.0 unified bronze tables
    bronze_paths = [
        storage_root / "bronze" / "securities_reference",
        storage_root / "bronze" / "securities_prices_daily"
    ]

    # v2.0 silver model directories
    silver_paths = [
        storage_root / "silver" / "company",
        storage_root / "silver" / "stocks"
    ]

    # Show what will be deleted
    items_to_delete = []
    if bronze:
        for path in bronze_paths:
            if path.exists():
                items_to_delete.append(f"  - Bronze: {path}")
    if silver:
        for path in silver_paths:
            if path.exists():
                items_to_delete.append(f"  - Silver: {path}")

    if not items_to_delete:
        print("No data to clear.")
        return ctx

    print("The following directories will be DELETED:")
    for item in items_to_delete:
        print(item)
    print()

    # Confirm
    if not skip_confirm:
        if not confirm_action("Are you sure you want to delete this data?"):
            print("Aborted.")
            sys.exit(0)

    # Delete
    print("\nDeleting storage...")
    print("-" * 80)

    if bronze:
        for path in bronze_paths:
            if path.exists():
                print(f"  → Deleting bronze: {path}")
                shutil.rmtree(path)
                print(f"  ✓ Deleted: {path.name}")

    if silver:
        for path in silver_paths:
            if path.exists():
                print(f"  → Deleting silver: {path}")
                shutil.rmtree(path)
                print(f"  ✓ Deleted: {path.name}")

    print()
    return ctx


def reingest_bronze(ctx, date_from: str, date_to: str, max_tickers: int = None):
    """Re-ingest bronze data from Alpha Vantage API."""
from de_funk.pipelines.providers.alpha_vantage import AlphaVantageIngestor

    print("=" * 80)
    print("RE-INGESTING BRONZE DATA")
    print("=" * 80)
    print(f"Date range: {date_from} to {date_to}")
    if max_tickers:
        print(f"Max tickers: {max_tickers}")
    print("=" * 80)
    print()

    try:
        # Initialize Alpha Vantage ingestor
        ingestor = AlphaVantageIngestor(
            alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )

        # Run full ingestion using run_all method
        tickers = ingestor.run_all(
            date_from=date_from,
            date_to=date_to,
            max_tickers=max_tickers,
            use_concurrent=False  # Sequential for free tier
        )

        return tickers

    except Exception as e:
        print(f"✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def rebuild_silver(ctx, date_from: str, date_to: str, tickers: list):
    """Rebuild silver layer models using v2.0 modular architecture."""
from de_funk.config.domain import get_domain_loader
from de_funk.models.domains.corporate.company import CompanyModel
from de_funk.models.domains.securities.stocks import StocksModel
from de_funk.models.api.session import UniversalSession

    print("=" * 80)
    print("REBUILDING SILVER LAYER (v2.0 Models)")
    print("=" * 80)
    print()

    try:
        # Initialize model config loader (from domains/ directory)
        domains_dir = ctx.repo / "domains"
        loader = get_domain_loader(domains_dir)

        # Create session for cross-model references
        session = UniversalSession(ctx.connection, ctx.storage, ctx.repo)

        # Build parameters
        params = {
            "DATE_FROM": date_from,
            "DATE_TO": date_to,
            "UNIVERSE_SIZE": len(tickers)
        }

        # --- Build Company Model ---
        print("Building company model...")
        print("-" * 80)
        company_cfg = loader.load_model_config("corporate.entity")
        company_model = CompanyModel(
            ctx.connection,
            model_cfg=company_cfg,
            storage_cfg=ctx.storage,
            params=params
        )
        company_model.set_session(session)
        company_dims, company_facts = company_model.build()

        print("✓ Company model built")
        print("  Dimensions:")
        for name, df in company_dims.items():
            count = df.count()
            print(f"    - {name}: {count:,} rows")
        print("  Facts:")
        for name, df in company_facts.items():
            count = df.count()
            print(f"    - {name}: {count:,} rows")
        print()

        # --- Build Stocks Model ---
        print("Building stocks model...")
        print("-" * 80)
        stocks_cfg = loader.load_model_config("securities.stocks")
        stocks_model = StocksModel(
            ctx.connection,
            model_cfg=stocks_cfg,
            storage_cfg=ctx.storage,
            params=params
        )
        stocks_model.set_session(session)
        stocks_dims, stocks_facts = stocks_model.build()

        print("✓ Stocks model built")
        print("  Dimensions:")
        for name, df in stocks_dims.items():
            count = df.count()
            print(f"    - {name}: {count:,} rows")
        print("  Facts:")
        for name, df in stocks_facts.items():
            count = df.count()
            print(f"    - {name}: {count:,} rows")
        print()

        print("=" * 80)
        print("✓ SILVER LAYER BUILD COMPLETE")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  Models built: company, stocks")
        print(f"  Total dimensions: {len(company_dims) + len(stocks_dims)}")
        print(f"  Total facts: {len(company_facts) + len(stocks_facts)}")
        print()

    except Exception as e:
        print(f"✗ Silver build failed: {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Clear storage and refresh all data from scratch",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    parser.add_argument(
        '--bronze-only',
        action='store_true',
        help='Only clear and refresh bronze layer'
    )

    parser.add_argument(
        '--silver-only',
        action='store_true',
        help='Only clear and refresh silver layer (requires bronze data)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days of data to ingest (default: 30)'
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        default=None,
        help='Maximum number of tickers to process (default: all)'
    )

    args = parser.parse_args()

    # Determine what to clear
    clear_bronze = not args.silver_only
    clear_silver = not args.bronze_only

    # Clear storage
    ctx = clear_storage(
        bronze=clear_bronze,
        silver=clear_silver,
        skip_confirm=args.yes
    )

    # Calculate date range
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=args.days)
    date_from_str = date_from.isoformat()
    date_to_str = date_to.isoformat()

    # Re-ingest bronze (if cleared or bronze-only)
    tickers = []
    if clear_bronze:
        tickers = reingest_bronze(ctx, date_from_str, date_to_str, args.max_tickers)

    # Rebuild silver (if cleared or silver-only)
    if clear_silver:
        # If we didn't ingest bronze, we need to figure out tickers
        if not tickers:
            print("Determining ticker list from existing bronze data...")
from de_funk.pipelines.ingestors.bronze_sink import BronzeSink
            sink = BronzeSink(ctx.storage)
            # Get latest snapshot date
            snapshot_dt = datetime.now().date().isoformat()
            try:
                df_tickers = ctx.spark.read.parquet(
                    str(sink._path("ref_all_tickers", {"snapshot_dt": snapshot_dt}))
                )
                tickers = [r["ticker"] for r in df_tickers.collect()]
                print(f"Found {len(tickers)} tickers in bronze data")
            except Exception as e:
                print(f"Warning: Could not read tickers from bronze: {e}")
                print("Using empty ticker list for silver build")

        rebuild_silver(ctx, date_from_str, date_to_str, tickers)

    print("=" * 80)
    print("✓ REFRESH COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Run debug_exchange_data.py to verify exchange codes match")
    print("  2. Test dimensional selector exchange tab in the notebook app")
    print()


if __name__ == "__main__":
    main()
