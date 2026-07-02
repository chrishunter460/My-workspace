#!/usr/bin/env python3
"""
Seed Tickers from Alpha Vantage LISTING_STATUS.

Fetches ALL active US tickers from Alpha Vantage in ONE API call and writes
to Bronze layer. This seeds the securities_reference table that the
distributed pipeline uses for ticker discovery.

Usage:
    python -m scripts.seed.seed_tickers
    python -m scripts.seed.seed_tickers --storage-path /shared/storage

This should be run BEFORE the distributed pipeline to populate the ticker list.
"""

import argparse
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from de_funk.orchestration.common.spark_session import get_spark
from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def seed_tickers(storage_path: Path = None, force: bool = False) -> int:
    """
    Seed tickers from Alpha Vantage LISTING_STATUS.

    Args:
        storage_path: Optional storage root (default: repo_root/storage)
        force: Force re-seed even if data exists

    Returns:
        Number of tickers seeded
    """
    setup_logging()

    # Determine storage path
    if storage_path is None:
        storage_path = repo_root / "storage"
    storage_path = Path(storage_path)

    bronze_path = storage_path / "bronze" / "securities_reference"

    # If force, delete existing table to avoid schema conflicts
    if force and bronze_path.exists():
        import shutil
        print(f"Force mode: Deleting existing table at {bronze_path}")
        shutil.rmtree(bronze_path)
        print("  ✓ Deleted existing table")
        print()

    # Check if already exists (unless force)
    if not force and bronze_path.exists() and (bronze_path / "_delta_log").exists():
        spark = get_spark("TickerSeedCheck")
        try:
            existing_df = spark.read.format("delta").load(str(bronze_path))
            existing_count = existing_df.count()
            if existing_count > 100:  # More than just test data
                print(f"✓ Tickers already seeded: {existing_count:,} tickers at {bronze_path}")
                print("  Use --force to re-seed")
                spark.stop()
                return existing_count
        except Exception:
            pass
        finally:
            spark.stop()

    print("=" * 70)
    print("Seeding Tickers from Alpha Vantage LISTING_STATUS")
    print("=" * 70)
    print()
    print("This makes ONE API call to fetch ALL active US tickers.")
    print()

    # Initialize Spark
    print("1. Initializing Spark...")
    spark = get_spark("TickerSeed")
    print()

    # Initialize provider (new v2.6 pattern)
    print("2. Initializing Alpha Vantage provider...")
from de_funk.pipelines.providers.alpha_vantage.alpha_vantage_provider import create_alpha_vantage_provider

    provider = create_alpha_vantage_provider(spark=spark, docs_path=repo_root)
    print()

    # Fetch bulk listing using provider's seed_tickers method
    print("3. Fetching ALL tickers from LISTING_STATUS (1 API call)...")
    print("-" * 70)

    # Call the seed_tickers method - returns a DataFrame
    df = provider.seed_tickers(state="active", filter_us_exchanges=True)

    if df is None or df.count() == 0:
        print("ERROR: No tickers returned from LISTING_STATUS")
        spark.stop()
        return 0

    ticker_count = df.count()
    print()
    print(f"   Fetched {ticker_count:,} US exchange tickers")
    print()

    # Write to Bronze layer
    print("4. Writing to Bronze layer...")
    bronze_path.parent.mkdir(parents=True, exist_ok=True)

    df.write.format("delta").mode("overwrite").partitionBy("asset_type").save(str(bronze_path))

    print(f"   ✓ Written {ticker_count:,} tickers to {bronze_path}")
    print()

    # Show sample
    print("5. Sample tickers:")
    df.select("ticker", "security_name", "exchange_code", "asset_type").show(10, truncate=False)

    # Show exchange breakdown
    print("6. Exchange breakdown:")
    df.groupBy("exchange_code").count().orderBy("count", ascending=False).show()

    print("=" * 70)
    print("Ticker seed complete!")
    print("=" * 70)
    print()
    print(f"Total US tickers available: {ticker_count:,}")
    print()
    print("You can now run the full pipeline:")
    print("  ./scripts/test/test_pipeline.sh --profile dev")
    print()

    spark.stop()
    return ticker_count


def main():
    parser = argparse.ArgumentParser(description="Seed tickers from Alpha Vantage LISTING_STATUS")
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Storage root path (default: repo_root/storage)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-seed even if data exists"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path) if args.storage_path else None
    seed_tickers(storage_path, force=args.force)


if __name__ == "__main__":
    main()
