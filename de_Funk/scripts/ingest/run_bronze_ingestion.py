#!/usr/bin/env python3
"""
Bronze Ingestion Script.

Fetches data from Alpha Vantage APIs and writes to Bronze layer.
Uses AlphaVantageProvider + IngestorEngine for proper API handling and Delta Lake writes.

NOTE: For full pipeline testing, prefer using ./scripts/test/test_pipeline.sh
This script is for standalone Bronze ingestion only.

Usage:
    python -m scripts.ingest.run_bronze_ingestion
    python -m scripts.ingest.run_bronze_ingestion --max-tickers 100
    python -m scripts.ingest.run_bronze_ingestion --endpoints prices
    python -m scripts.ingest.run_bronze_ingestion --endpoints reference,income_statement

Raw Layer Caching (default behavior):
    By default, raw API responses are cached to storage/raw/alpha_vantage/{endpoint}/{ticker}.json
    On subsequent runs, cached raw files are used instead of making API calls.

    --force-api         Force API calls even if cache exists (refresh data)
    --no-raw-cache      Disable raw layer entirely (no read, no write)

Endpoints (work item names):
    prices             - Daily OHLCV prices (time_series_daily_adjusted)
    reference          - Company overview data (company_overview)
    income_statement   - Income statements (income)
    balance_sheet      - Balance sheets (balance)
    cash_flow          - Cash flow statements (cashflow)
    earnings           - Earnings reports
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)

# Map user-friendly endpoint names to DataType values used by provider
ENDPOINT_TO_WORK_ITEM = {
    'time_series_daily': 'prices',
    'time_series_daily_adjusted': 'prices',
    'prices': 'prices',
    'company_overview': 'reference',
    'overview': 'reference',
    'reference': 'reference',
    'income_statement': 'income',
    'income': 'income',
    'balance_sheet': 'balance',
    'balance': 'balance',
    'cash_flow': 'cashflow',
    'cashflow': 'cashflow',
    'earnings': 'earnings',
    'dividends': 'dividends',
    'splits': 'splits',
}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path (default: /shared/storage)')
    parser.add_argument('--max-tickers', type=int, help='Max tickers to process')
    parser.add_argument('--endpoints', type=str, default='prices,reference',
                        help='Comma-separated endpoints (default: prices,reference)')
    parser.add_argument('--use-market-cap', action='store_true',
                        help='Select tickers by market cap instead of alphabetically')
    parser.add_argument('--force-api', action='store_true',
                        help='Force API calls even if raw cache exists (refresh data)')
    parser.add_argument('--no-raw-cache', action='store_true',
                        help='Disable raw layer entirely (no read, no write)')
    parser.add_argument('--tickers', type=str,
                        help='Comma-separated list of specific tickers to process')
    # Legacy alias for backward compatibility
    parser.add_argument('--save-raw', action='store_true',
                        help=argparse.SUPPRESS)  # Hidden, now default behavior

    args = parser.parse_args()
    setup_logging()

    storage_path = Path(args.storage_path)
    endpoints_input = [e.strip().lower() for e in args.endpoints.split(',')]

    # Resolve endpoint names to work item types
    work_items = []
    for ep in endpoints_input:
        if ep in ENDPOINT_TO_WORK_ITEM:
            work_item = ENDPOINT_TO_WORK_ITEM[ep]
            if work_item not in work_items:
                work_items.append(work_item)
        else:
            logger.warning(f"Unknown endpoint: {ep}, skipping")

    if not work_items:
        logger.error("No valid endpoints specified")
        return 1

    # Determine raw layer behavior
    use_raw_layer = not args.no_raw_cache
    force_api = args.force_api

    logger.info("Starting Bronze ingestion")
    logger.info(f"Storage path: {storage_path}")
    logger.info(f"Work items: {work_items}")
    if args.max_tickers:
        logger.info(f"Max tickers: {args.max_tickers}")

    if use_raw_layer:
        if force_api:
            logger.info("Raw layer: ENABLED (write-only, forcing API calls)")
        else:
            logger.info("Raw layer: ENABLED (read from cache if available, write new)")
    else:
        logger.info("Raw layer: DISABLED")

    try:
        # Initialize Spark
from de_funk.orchestration.common.spark_session import get_spark
        spark = get_spark(app_name='run_bronze_ingestion')

        # Load storage config
        with open(repo_root / 'configs' / 'storage.json') as f:
            storage_cfg = json.load(f)
        storage_cfg['roots'] = {
            k: str(storage_path / v.replace('storage/', ''))
            for k, v in storage_cfg['roots'].items()
        }

        # Initialize provider
        # Pass storage_path to enable raw layer (caching)
from de_funk.pipelines.providers.alpha_vantage import create_alpha_vantage_provider
from de_funk.pipelines.base.ingestor_engine import IngestorEngine

        raw_storage = storage_path if use_raw_layer else None
        provider = create_alpha_vantage_provider(spark=spark, docs_path=repo_root, storage_path=raw_storage)
        if use_raw_layer:
            logger.info(f"Raw cache path: {storage_path}/raw/alpha_vantage/")

        # Get tickers
        if args.tickers:
            tickers = [t.strip().upper() for t in args.tickers.split(',')]
            logger.info(f"Using {len(tickers)} explicit tickers")
        else:
            tickers = _get_tickers(
                storage_path=storage_path,
                spark=spark,
                max_tickers=args.max_tickers,
                use_market_cap=args.use_market_cap
            )

        if not tickers:
            logger.error("No tickers available. Run seed_tickers first or provide --tickers")
            spark.stop()
            return 1

        logger.info(f"Processing {len(tickers)} tickers")
        provider.set_tickers(tickers)

        # Create engine and run
        engine = IngestorEngine(provider, storage_cfg)
        results = engine.run(work_items=work_items, silent=False, force_api=force_api)

        spark.stop()

        return 0 if results.total_errors == 0 else 1

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


def _get_tickers(
    storage_path: Path,
    spark,
    max_tickers: int = None,
    use_market_cap: bool = False
) -> list:
    """Get tickers from Bronze layer."""

    # Try listing_status first (new path)
    listing_path = storage_path / 'bronze' / 'alpha_vantage' / 'listing_status'
    if not listing_path.exists():
        # Fall back to old path
        listing_path = storage_path / 'bronze' / 'securities_reference'

    if not listing_path.exists():
        logger.error(f"No ticker data at {listing_path}")
        return []

    logger.info(f"Loading tickers from {listing_path}")

    # Read with Spark
    if (listing_path / '_delta_log').exists():
        df = spark.read.format('delta').load(str(listing_path))
    else:
        df = spark.read.parquet(str(listing_path))

    # Filter to stocks
    if 'asset_type' in df.columns:
        df = df.filter(df.asset_type == 'stocks')

    # Get unique tickers
    ticker_rows = df.select('ticker').distinct().collect()
    all_tickers = [row.ticker for row in ticker_rows]

    logger.info(f"Found {len(all_tickers)} unique stock tickers")

    # Sort by market cap if requested
    if use_market_cap and max_tickers:
        sorted_tickers = _sort_by_market_cap(storage_path, spark, max_tickers)
        if sorted_tickers:
            return sorted_tickers
        logger.warning("Market cap ranking unavailable, using alphabetical")

    # Apply limit
    if max_tickers:
        return all_tickers[:max_tickers]

    return all_tickers


def _sort_by_market_cap(storage_path: Path, spark, max_tickers: int) -> list:
    """Sort tickers by market cap."""
    # Try new path first
    company_path = storage_path / 'bronze' / 'alpha_vantage' / 'company_overview'
    if not company_path.exists():
        company_path = storage_path / 'bronze' / 'company_reference'

    if not company_path.exists():
        return []

    try:
        from pyspark.sql.functions import col, desc, isnan

        if (company_path / '_delta_log').exists():
            df = spark.read.format('delta').load(str(company_path))
        else:
            df = spark.read.parquet(str(company_path))

        ranked = (df
                  .filter((col('market_cap').isNotNull()) &
                          (~isnan(col('market_cap'))) &
                          (col('market_cap') > 0))
                  .select('ticker', 'market_cap')
                  .dropDuplicates(['ticker'])
                  .orderBy(desc('market_cap'))
                  .limit(max_tickers))

        rows = ranked.collect()
        tickers = [row.ticker for row in rows]
        logger.info(f"Selected {len(tickers)} tickers by market cap")
        return tickers

    except Exception as e:
        logger.warning(f"Failed to sort by market cap: {e}")
        return []


if __name__ == "__main__":
    sys.exit(main())
