"""
Forecast Execution Script

This script orchestrates the execution of time series forecasting models for
stock prices and volumes. It:
1. Refreshes recent data using the ingestion pipeline
2. Loads the forecast model configuration
3. Runs forecasts for specified tickers using multiple model types
4. Stores forecast results and accuracy metrics in the Silver layer

Usage:
    python -m scripts.forecast.run_forecasts [--tickers AAPL,GOOGL] [--refresh-days 7] [--models arima_30d,prophet_30d]
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse
from datetime import datetime
import yaml
import json
import traceback

from de_funk.utils.repo import setup_repo_imports, get_repo_root
repo_root = setup_repo_imports()

from de_funk.config import ConfigLoader
from de_funk.config.logging import get_logger, setup_logging
from de_funk.models.domains.securities.forecast import ForecastModel
from de_funk.models.api.session import UniversalSession
from de_funk.pipelines.base.progress_tracker import StepProgressTracker

logger = get_logger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration file (YAML or JSON)."""
    config_path = Path(config_path)

    with open(config_path, 'r') as f:
        if config_path.suffix == '.json':
            return json.load(f)
        else:
            return yaml.safe_load(f)


def read_table(spark_session, path: Path):
    """
    Read a table using Spark with proper Delta/Parquet detection.

    Uses spark.read.format("delta") for Delta tables (batch processing best practice).
    Falls back to spark.read.parquet() for plain Parquet.

    Args:
        spark_session: Active Spark session
        path: Path to the table directory

    Returns:
        Spark DataFrame
    """
    delta_log = path / "_delta_log"
    if delta_log.exists():
        return spark_session.read.format("delta").load(str(path))
    else:
        return spark_session.read.parquet(str(path))


def get_active_tickers(storage_cfg: dict, spark_session, limit: int = None) -> list:
    """
    Get list of tickers that have price data for forecasting.

    Only returns tickers that have actual price data in fact_stock_prices,
    NOT just reference data. This prevents forecast errors for tickers
    without price history.

    When limit is specified, returns top N tickers sorted by market cap proxy
    (close × volume from most recent trade date).

    Args:
        storage_cfg: Storage configuration
        spark_session: Active Spark session
        limit: Optional limit on number of tickers (returns top by market cap)

    Returns:
        List of ticker symbols with price data, sorted by market cap if limit specified
    """
    from pathlib import Path
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    # Try stocks Silver fact_stock_prices first (tickers with actual price data)
    # Paths are already resolved by ConfigLoader - no fallback needed
    stocks_root = storage_cfg["roots"].get("stocks_silver")
    if not stocks_root:
        logger.warning("stocks_silver not configured in storage roots")
        stocks_root = storage_cfg["roots"]["silver"] + "/stocks"
    fact_prices_path = Path(stocks_root) / "facts" / "fact_stock_prices"
    dim_stock_path = Path(stocks_root) / "dims" / "dim_stock"

    if fact_prices_path.exists() and dim_stock_path.exists():
        try:
            # fact_stock_prices uses security_id/date_id, need to join with dim_stock for ticker
            # Use read_table() for proper Delta/Parquet handling (Spark for batch processing)
            prices_df = read_table(spark_session, fact_prices_path)
            dim_df = read_table(spark_session, dim_stock_path)

            # Join to get ticker from dimension table
            df = prices_df.alias('p').join(
                dim_df.select('security_id', 'ticker').alias('d'),
                F.col('p.security_id') == F.col('d.security_id'),
                'inner'
            ).select(
                'p.*',
                F.col('d.ticker')
            )

            if limit:
                # Sort by market cap proxy (close × volume) using Spark SQL
                # Get latest price per ticker, then sort by market cap proxy
                # Use date_id for ordering (YYYYMMDD integer format)
                window = Window.partitionBy("ticker").orderBy(F.col("date_id").desc())

                tickers_df = (
                    df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull() & (F.col("volume") > 0))
                    .withColumn("rn", F.row_number().over(window))
                    .filter(F.col("rn") == 1)
                    .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                    .orderBy(F.col("market_cap_proxy").desc())
                    .select("ticker")
                    .limit(limit)
                )
                tickers = [row.ticker for row in tickers_df.collect()]
                logger.info(f"Loaded top {len(tickers)} tickers by market cap from stocks Silver")
            else:
                # No limit - just get all unique tickers
                tickers = [row.ticker for row in df.select("ticker").distinct().collect()]
                logger.info(f"Loaded {len(tickers)} tickers with price data from stocks Silver")
            return tickers
        except Exception as e:
            logger.warning(f"Could not load tickers from stocks Silver fact_stock_prices: {e}")

    # Fallback: v2.0 Bronze securities_prices_daily
    bronze_root = storage_cfg["roots"]["bronze"]  # Always resolved by ConfigLoader
    prices_path = Path(bronze_root) / "securities_prices_daily"

    if prices_path.exists():
        try:
            df = read_table(spark_session, prices_path)

            if limit:
                # Sort by market cap proxy using Spark SQL
                window = Window.partitionBy("ticker").orderBy(F.col("trade_date").desc())

                tickers_df = (
                    df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull() & (F.col("volume") > 0))
                    .withColumn("rn", F.row_number().over(window))
                    .filter(F.col("rn") == 1)
                    .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                    .orderBy(F.col("market_cap_proxy").desc())
                    .select("ticker")
                    .limit(limit)
                )
                tickers = [row.ticker for row in tickers_df.collect()]
                logger.info(f"Loaded top {len(tickers)} tickers by market cap from v2.0 Bronze layer")
            else:
                tickers = [row.ticker for row in df.select("ticker").distinct().collect()]
                logger.info(f"Loaded {len(tickers)} tickers from v2.0 Bronze layer")
            return tickers
        except Exception as e:
            logger.warning(f"Could not load tickers from v2.0 Bronze layer: {e}")

    # Legacy fallback: v1.x Bronze prices_daily
    legacy_prices_path = Path(bronze_root) / "prices_daily"
    if legacy_prices_path.exists():
        try:
            df = read_table(spark_session, legacy_prices_path)

            if limit:
                window = Window.partitionBy("ticker").orderBy(F.col("trade_date").desc())

                tickers_df = (
                    df.filter(F.col("close").isNotNull() & F.col("volume").isNotNull() & (F.col("volume") > 0))
                    .withColumn("rn", F.row_number().over(window))
                    .filter(F.col("rn") == 1)
                    .withColumn("market_cap_proxy", F.col("close") * F.col("volume"))
                    .orderBy(F.col("market_cap_proxy").desc())
                    .select("ticker")
                    .limit(limit)
                )
                tickers = [row.ticker for row in tickers_df.collect()]
                logger.info(f"Loaded top {len(tickers)} tickers by market cap from legacy Bronze layer")
            else:
                tickers = [row.ticker for row in df.select("ticker").distinct().collect()]
                logger.info(f"Loaded {len(tickers)} tickers from legacy Bronze layer")
            return tickers
        except Exception as e:
            logger.warning(f"Could not load tickers from legacy Bronze layer: {e}")

    # Return empty list if no data sources available
    logger.warning("No ticker data sources available")
    return []


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header line."""
    line = char * 80
    print(line)
    print(text)
    print(line)


def run_forecast_pipeline(
    tickers: list = None,
    refresh_data: bool = True,
    refresh_days: int = 7,
    models: list = None,
    max_tickers: int = None,
    minimal_progress: bool = True
) -> dict:
    """
    Run the complete forecast pipeline.

    Args:
        tickers: List of ticker symbols to forecast (None = all active)
        refresh_data: Whether to refresh data before forecasting
        refresh_days: Number of days to refresh
        models: List of model names to run (None = all configured)
        max_tickers: Maximum number of tickers to process
        minimal_progress: Use clean single-line progress bar (default: True). False for verbose logging.

    Returns:
        Dictionary with pipeline results
    """
    # Suppress cmdstanpy INFO logging early (Prophet's MCMC backend)
    # This must be done before any Prophet imports
    import logging
    logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
    logging.getLogger('prophet').setLevel(logging.WARNING)

    if not minimal_progress:
        print_header("TIME SERIES FORECAST PIPELINE")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
    logger.info("Starting time series forecast pipeline")

    # Initialize Spark connection (required for ETL operations)
from de_funk.orchestration.common.spark_session import get_spark
from de_funk.core.connection import ConnectionFactory
    spark_session = get_spark("ForecastPipeline")
    spark = ConnectionFactory.create("spark", spark_session=spark_session)

    # Load configurations
    if not minimal_progress:
        print("Loading configurations...")

    # Use ConfigLoader for properly resolved storage paths
    config = ConfigLoader().load()
    storage_cfg = config.storage

    # v3.0: Load forecast config from domain markdown file
from de_funk.config.domain import get_domain_loader
    domains_root = get_repo_root() / "domains"
    domain_loader = get_domain_loader(domains_root)
    forecast_cfg = domain_loader.load_model_config("securities.forecast")

    logger.debug("Configurations loaded")
    if not minimal_progress:
        print(f"  Loaded storage config")
        print(f"  Loaded forecast config")
        print()

    # Step 1: Refresh data if requested
    if refresh_data:
        if not minimal_progress:
            print("Step 1: Refreshing recent data...")
            print("-" * 80)
        logger.info(f"Refreshing data for {refresh_days} days")
        try:
            from scripts.refresh_data import refresh_recent_data
            refresh_recent_data(days=refresh_days, max_tickers=max_tickers)
        except Exception as e:
            logger.warning(f"Data refresh failed: {e}")
            if not minimal_progress:
                print(f"Warning: Data refresh failed: {e}")
                print("Continuing with existing data...")
        if not minimal_progress:
            print()

    # Step 2: Get tickers to process
    if not minimal_progress:
        print("Step 2: Determining tickers to forecast...")
        print("-" * 80)

    if tickers is None:
        tickers = get_active_tickers(storage_cfg, spark_session, limit=max_tickers)

    logger.info(f"Processing {len(tickers)} tickers")
    if not minimal_progress:
        print(f"  Processing {len(tickers)} tickers: {', '.join(tickers[:5])}")
        if len(tickers) > 5:
            print(f"    ... and {len(tickers) - 5} more")
        print()

    # Step 3: Initialize forecast model
    if not minimal_progress:
        print("Step 3: Initializing forecast model...")
        print("-" * 80)

    # Create universal session for cross-model access
    repo_root_path = get_repo_root()
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root_path
    )

    forecast_model = ForecastModel(
        connection=spark,
        storage_cfg=storage_cfg,
        model_cfg=forecast_cfg,
        params={},
        quiet=minimal_progress  # Suppress verbose output in minimal mode
    )

    # Set session for cross-model data access
    forecast_model.set_session(session)

    # Get output directory from storage config (resolved by ConfigLoader)
    forecast_root = storage_cfg['roots'].get('forecast_silver')
    if not forecast_root:
        forecast_root = storage_cfg['roots']['silver'] + "/forecast"

    logger.info(f"Forecast model initialized, output: {forecast_root}")
    if not minimal_progress:
        print(f"  Forecast model initialized")
        print(f"  Session configured for cross-model access")
        print(f"  Output directory: {forecast_root}")
        print()

    # Step 4: Run forecasts for each ticker
    if not minimal_progress:
        print("Step 4: Running forecasts...")
        print("-" * 80)

    results = {
        'start_time': datetime.now(),
        'tickers_processed': 0,
        'tickers_failed': 0,
        'total_forecasts': 0,
        'total_models': 0,
        'errors': []
    }

    # Initialize progress tracker
    tracker = StepProgressTracker(
        total_steps=len(tickers),
        description="Forecasting",
        silent=not minimal_progress
    )

    for i, ticker in enumerate(tickers, 1):
        # Update progress tracker
        tracker.update(i, f"Forecasting {ticker}...")

        if not minimal_progress:
            print(f"\n[{i}/{len(tickers)}] Processing {ticker}...")
            print("-" * 40)
        logger.debug(f"Processing ticker {i}/{len(tickers)}: {ticker}")

        try:
            ticker_results = forecast_model.run_forecast_for_ticker(
                ticker=ticker,
                model_configs=models
            )

            results['tickers_processed'] += 1
            results['total_forecasts'] += ticker_results['forecasts_generated']
            results['total_models'] += ticker_results['models_trained']

            if ticker_results['errors']:
                results['errors'].extend(ticker_results['errors'])

            if minimal_progress:
                tracker.step_complete(f"{ticker} ✓ ({ticker_results['models_trained']} models)")
            else:
                print(f"  {ticker}: {ticker_results['models_trained']} models, {ticker_results['forecasts_generated']} forecasts")
            logger.info(f"{ticker}: {ticker_results['models_trained']} models, {ticker_results['forecasts_generated']} forecasts")

        except Exception as e:
            error_msg = f"{ticker}: {str(e)}"
            logger.error(f"Forecast failed for {ticker}: {e}")
            if minimal_progress:
                tracker.step_complete(f"{ticker} ✗ (error)")
            else:
                print(f"  Error: {error_msg}")
            results['tickers_failed'] += 1
            results['errors'].append(error_msg)

    # Finish progress tracking
    tracker.finish(success=results['tickers_failed'] == 0)

    results['end_time'] = datetime.now()
    results['duration'] = (results['end_time'] - results['start_time']).total_seconds()

    # Step 5: Print summary (always show, even in minimal mode)
    print()
    print("=" * 60)
    print("✓ FORECAST COMPLETE")
    print("=" * 60)
    print(f"  Tickers: {results['tickers_processed']}/{len(tickers)}")
    print(f"  Models: {results['total_models']}")
    print(f"  Forecasts: {results['total_forecasts']}")
    print(f"  Errors: {results['tickers_failed']}")
    print(f"  Elapsed: {results['duration']:.0f}s")
    print("=" * 60)

    logger.info(f"Pipeline complete: {results['tickers_processed']}/{len(tickers)} tickers, "
               f"{results['total_forecasts']} forecasts in {results['duration']:.1f}s")

    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors'][:10]:  # Show first 10
            print(f"  - {error}")
        if len(results['errors']) > 10:
            print(f"  ... and {len(results['errors']) - 10} more")

    # Clean up
    spark.stop()
    logger.debug("Spark session stopped")

    return results


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Run time series forecasts for stock prices and volumes"
    )
    parser.add_argument(
        '--tickers',
        type=str,
        default=None,
        help='Comma-separated list of tickers (default: all active tickers)'
    )
    parser.add_argument(
        '--no-refresh',
        action='store_true',
        help='Skip data refresh step'
    )
    parser.add_argument(
        '--refresh-days',
        type=int,
        default=7,
        help='Number of days to refresh (default: 7)'
    )
    parser.add_argument(
        '--models',
        type=str,
        default=None,
        help='Comma-separated list of model names to run (default: all configured)'
    )
    parser.add_argument(
        '--max-tickers',
        type=int,
        default=None,
        help='Maximum number of tickers to process (default: all)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output (detailed logging instead of progress bar)'
    )

    args = parser.parse_args()
    logger.info(f"Starting forecast script with args: {args}")

    # Parse comma-separated lists
    tickers = args.tickers.split(',') if args.tickers else None
    models = args.models.split(',') if args.models else None

    # Run pipeline
    try:
        results = run_forecast_pipeline(
            tickers=tickers,
            refresh_data=not args.no_refresh,
            refresh_days=args.refresh_days,
            models=models,
            max_tickers=args.max_tickers,
            minimal_progress=not args.verbose
        )

        # Exit with error code if there were failures
        if results['tickers_failed'] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\nPipeline failed with error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
