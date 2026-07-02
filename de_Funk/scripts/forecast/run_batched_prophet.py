#!/usr/bin/env python3
"""
Batched Prophet Forecasting with Multiprocessing.

Prophet doesn't serialize well for Spark UDFs, so we use Python
multiprocessing to parallelize across CPU cores on a single node.

Usage:
    python -m scripts.forecast.run_batched_prophet
    python -m scripts.forecast.run_batched_prophet --workers 8 --max-tickers 500

For cluster: Run on head node (bigbark) which has most RAM.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from multiprocessing import Pool, cpu_count
import warnings

warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)

# Suppress Prophet/cmdstanpy logging
import logging
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
logging.getLogger('prophet').setLevel(logging.WARNING)


def forecast_single_ticker(args: Tuple[str, pd.DataFrame, int]) -> Optional[pd.DataFrame]:
    """
    Forecast a single ticker using Prophet.

    Args:
        args: Tuple of (ticker, price_data, horizon)

    Returns:
        DataFrame with forecasts or None if failed
    """
    ticker, df, horizon = args

    try:
        from prophet import Prophet

        # Prepare data for Prophet (requires 'ds' and 'y' columns)
        prophet_df = df[['trade_date', 'close']].copy()
        prophet_df.columns = ['ds', 'y']
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
        prophet_df = prophet_df.sort_values('ds')

        # Need at least 60 days
        if len(prophet_df) < 60:
            return None

        # Use last year of data
        prophet_df = prophet_df.tail(252)

        # Fit Prophet (suppress output)
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        model.fit(prophet_df)

        # Create future dataframe
        future = model.make_future_dataframe(periods=horizon)

        # Predict
        forecast = model.predict(future)

        # Get only future predictions
        forecast = forecast.tail(horizon)

        # Build result
        created_at = datetime.now()
        results = []

        for i, row in enumerate(forecast.itertuples()):
            results.append({
                'ticker': ticker,
                'forecast_date': row.ds.date(),
                'horizon_days': i + 1,
                'predicted_close': float(row.yhat),
                'predicted_low': float(row.yhat_lower),
                'predicted_high': float(row.yhat_upper),
                'model_type': 'prophet',
                'created_at': created_at,
            })

        return pd.DataFrame(results)

    except Exception as e:
        # Silent fail for individual tickers
        return None


def load_price_data(storage_path: Path, max_tickers: int = None) -> Dict[str, pd.DataFrame]:
    """
    Load price data from Silver/Bronze layer.

    When max_tickers is specified, returns top N tickers sorted by market cap
    proxy (close × volume from most recent trade date).

    Returns:
        Dict mapping ticker -> DataFrame
    """
    from deltalake import DeltaTable

    # Try Silver first
    prices_path = storage_path / "silver" / "stocks" / "facts" / "fact_stock_prices"

    if not prices_path.exists():
        prices_path = storage_path / "bronze" / "securities_prices_daily"

    logger.info(f"Loading prices from: {prices_path}")

    dt = DeltaTable(str(prices_path))
    df = dt.to_pandas()

    # Filter to recent data
    cutoff_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df[df['trade_date'] >= cutoff_date]

    # Select tickers - sort by market cap proxy if max_tickers specified
    if max_tickers:
        # Filter valid data for market cap calculation
        valid_df = df.dropna(subset=['close', 'volume'])
        valid_df = valid_df[valid_df['volume'] > 0]

        # Get latest price per ticker
        latest = valid_df.sort_values('trade_date').groupby('ticker').tail(1).copy()

        # Calculate market cap proxy and sort
        latest['market_cap_proxy'] = latest['close'] * latest['volume']
        latest = latest.sort_values('market_cap_proxy', ascending=False)

        # Get top N tickers
        tickers = latest['ticker'].head(max_tickers).tolist()
        logger.info(f"Selected top {len(tickers)} tickers by market cap")
    else:
        tickers = df['ticker'].unique().tolist()
        logger.info(f"Loaded {len(tickers)} tickers")

    # Group by ticker
    ticker_data = {}
    for ticker in tickers:
        ticker_data[ticker] = df[df['ticker'] == ticker][['trade_date', 'close']].copy()

    return ticker_data


def run_batched_prophet(
    storage_path: Path,
    horizon: int = 30,
    max_tickers: int = None,
    workers: int = None,
):
    """
    Run Prophet forecasting in parallel batches.

    Args:
        storage_path: Path to storage root
        horizon: Days to forecast
        max_tickers: Limit tickers (for testing)
        workers: Number of parallel workers (default: CPU count - 1)
    """
    if workers is None:
        workers = max(1, cpu_count() - 1)

    logger.info(f"Using {workers} parallel workers")

    # Load data
    ticker_data = load_price_data(storage_path, max_tickers)
    tickers = list(ticker_data.keys())

    logger.info(f"Forecasting {len(tickers)} tickers with Prophet")
    logger.info(f"Horizon: {horizon} days")

    # Prepare args for multiprocessing
    args_list = [(ticker, ticker_data[ticker], horizon) for ticker in tickers]

    # Run in parallel
    start_time = datetime.now()

    with Pool(workers) as pool:
        results = pool.map(forecast_single_ticker, args_list)

    # Filter out None results and combine
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        logger.error("No successful forecasts!")
        return

    forecasts_df = pd.concat(valid_results, ignore_index=True)

    # Write results
    output_path = storage_path / "silver" / "forecast" / "fact_prophet_forecasts"
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing forecasts to: {output_path}")

    # Write as Delta
    from deltalake import write_deltalake

    write_deltalake(
        str(output_path),
        forecasts_df,
        mode='overwrite',
        schema_mode='overwrite',
    )

    # Stats
    duration = (datetime.now() - start_time).total_seconds()
    success_count = len(valid_results)
    fail_count = len(tickers) - success_count

    logger.info(f"")
    logger.info(f"=" * 60)
    logger.info(f"Prophet Batch Forecast Complete")
    logger.info(f"=" * 60)
    logger.info(f"  Tickers: {len(tickers)}")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {fail_count}")
    logger.info(f"  Horizon: {horizon} days")
    logger.info(f"  Forecasts: {len(forecasts_df):,}")
    logger.info(f"  Duration: {duration:.1f}s")
    logger.info(f"  Rate: {success_count / duration:.1f} tickers/sec")
    logger.info(f"  Workers: {workers}")
    logger.info(f"  Output: {output_path}")
    logger.info(f"")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage root path')
    parser.add_argument('--horizon', type=int, default=30,
                        help='Forecast horizon in days')
    parser.add_argument('--max-tickers', type=int,
                        help='Limit tickers (for testing)')
    parser.add_argument('--workers', type=int,
                        help='Number of parallel workers (default: CPU-1)')

    args = parser.parse_args()
    setup_logging()

    run_batched_prophet(
        storage_path=Path(args.storage_path),
        horizon=args.horizon,
        max_tickers=args.max_tickers,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
