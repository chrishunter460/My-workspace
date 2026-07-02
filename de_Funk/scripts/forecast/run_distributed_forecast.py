#!/usr/bin/env python3
"""
Distributed ARIMA Forecasting with Spark.

Uses pandas_udf to distribute ARIMA model fitting across Spark workers.
Each worker processes a subset of tickers in parallel.

Usage:
    python -m scripts.forecast.run_distributed_forecast
    python -m scripts.forecast.run_distributed_forecast --horizon 30 --max-tickers 1000

Spark Submit:
    spark-submit --master spark://192.168.1.212:7077 \
        scripts/forecast/run_distributed_forecast.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Iterator

import pandas as pd
import numpy as np

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def get_spark():
    """Get Spark session with Delta Lake support."""
    from pyspark.sql import SparkSession

    return SparkSession.builder \
        .appName("DistributedForecast") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "6g") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()


def create_forecast_udf(horizon: int = 30):
    """
    Create a pandas_udf for distributed ARIMA forecasting.

    Args:
        horizon: Number of days to forecast

    Returns:
        pandas_udf function
    """
    from pyspark.sql.functions import pandas_udf
    from pyspark.sql.types import (
        StructType, StructField, StringType, DateType,
        DoubleType, IntegerType, TimestampType
    )

    # Output schema for forecasts
    forecast_schema = StructType([
        StructField("ticker", StringType(), False),
        StructField("forecast_date", DateType(), False),
        StructField("horizon_days", IntegerType(), False),
        StructField("predicted_close", DoubleType(), True),
        StructField("predicted_low", DoubleType(), True),
        StructField("predicted_high", DoubleType(), True),
        StructField("model_type", StringType(), False),
        StructField("created_at", TimestampType(), False),
    ])

    @pandas_udf(forecast_schema)
    def forecast_ticker_udf(iterator: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        """
        Distributed ARIMA forecasting UDF.

        Processes batches of ticker data, fitting ARIMA and generating forecasts.
        Runs on Spark workers in parallel.
        """
        import warnings
        warnings.filterwarnings('ignore')

        from statsmodels.tsa.arima.model import ARIMA

        for pdf in iterator:
            if pdf.empty:
                continue

            results = []

            # Group by ticker within this partition
            for ticker, group in pdf.groupby('ticker'):
                try:
                    # Prepare time series
                    ts = group.sort_values('trade_date').set_index('trade_date')['close']
                    ts.index = pd.to_datetime(ts.index)

                    # Need at least 60 days of data
                    if len(ts) < 60:
                        continue

                    # Use last 252 trading days (1 year)
                    ts = ts.tail(252)

                    # Fit ARIMA(5,1,0) - fast and reasonable for stocks
                    model = ARIMA(ts, order=(5, 1, 0))
                    fitted = model.fit()

                    # Forecast
                    forecast = fitted.get_forecast(steps=horizon)
                    pred_mean = forecast.predicted_mean
                    conf_int = forecast.conf_int(alpha=0.1)  # 90% CI

                    # Build results
                    last_date = ts.index[-1]
                    created_at = datetime.now()

                    for i in range(horizon):
                        forecast_date = last_date + timedelta(days=i+1)
                        results.append({
                            'ticker': ticker,
                            'forecast_date': forecast_date.date(),
                            'horizon_days': i + 1,
                            'predicted_close': float(pred_mean.iloc[i]),
                            'predicted_low': float(conf_int.iloc[i, 0]),
                            'predicted_high': float(conf_int.iloc[i, 1]),
                            'model_type': 'arima_5_1_0',
                            'created_at': created_at,
                        })

                except Exception as e:
                    # Log but continue - don't fail entire partition
                    print(f"Warning: Failed to forecast {ticker}: {e}")
                    continue

            if results:
                yield pd.DataFrame(results)
            else:
                # Yield empty DataFrame with correct schema
                yield pd.DataFrame(columns=[
                    'ticker', 'forecast_date', 'horizon_days',
                    'predicted_close', 'predicted_low', 'predicted_high',
                    'model_type', 'created_at'
                ])

    return forecast_ticker_udf


def run_distributed_forecast(
    storage_path: Path,
    horizon: int = 30,
    max_tickers: int = None,
):
    """
    Run distributed ARIMA forecasting across Spark cluster.

    Args:
        storage_path: Path to storage root
        horizon: Days to forecast
        max_tickers: Limit number of tickers (for testing)
    """
    from pyspark.sql import functions as F
    from pyspark.sql.functions import col

    spark = get_spark()

    # Load price data from Silver
    prices_path = storage_path / "silver" / "stocks" / "facts" / "fact_stock_prices"

    if not prices_path.exists():
        # Try Bronze fallback
        prices_path = storage_path / "bronze" / "securities_prices_daily"

    logger.info(f"Loading prices from: {prices_path}")

    prices_df = spark.read.format("delta").load(str(prices_path))

    # Filter to recent data (last 2 years)
    cutoff_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
    prices_df = prices_df.filter(col("trade_date") >= cutoff_date)

    # Limit tickers if specified - sort by market cap proxy (close × volume)
    if max_tickers:
        from pyspark.sql.window import Window

        # Get latest price per ticker and calculate market cap proxy
        window = Window.partitionBy("ticker").orderBy(col("trade_date").desc())

        top_tickers_df = (
            prices_df
            .filter(col("close").isNotNull() & col("volume").isNotNull() & (col("volume") > 0))
            .withColumn("rn", F.row_number().over(window))
            .filter(col("rn") == 1)
            .withColumn("market_cap_proxy", col("close") * col("volume"))
            .orderBy(col("market_cap_proxy").desc())
            .select("ticker")
            .limit(max_tickers)
        )

        ticker_list = [row.ticker for row in top_tickers_df.collect()]
        prices_df = prices_df.filter(col("ticker").isin(ticker_list))
        logger.info(f"Selected top {len(ticker_list)} tickers by market cap")

    # Get ticker count
    ticker_count = prices_df.select("ticker").distinct().count()
    logger.info(f"Forecasting {ticker_count} tickers with horizon={horizon} days")

    # Repartition by ticker for efficient grouping
    # Use ~100 tickers per partition for balance
    num_partitions = max(1, ticker_count // 100)
    prices_df = prices_df.repartition(num_partitions, "ticker")

    logger.info(f"Using {num_partitions} partitions across cluster")

    # Create and apply forecast UDF
    forecast_udf = create_forecast_udf(horizon=horizon)

    # Select only needed columns and apply UDF
    prices_subset = prices_df.select("ticker", "trade_date", "close")

    logger.info("Running distributed ARIMA forecasting...")
    start_time = datetime.now()

    # Apply UDF using mapInPandas (more efficient than groupBy.apply for this pattern)
    forecasts_df = prices_subset.mapInPandas(forecast_udf, forecast_udf.returnType)

    # Write results to Silver
    output_path = storage_path / "silver" / "forecast" / "fact_price_forecasts"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing forecasts to: {output_path}")

    forecasts_df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(str(output_path))

    # Stats
    duration = (datetime.now() - start_time).total_seconds()
    forecast_count = spark.read.format("delta").load(str(output_path)).count()

    logger.info(f"")
    logger.info(f"=" * 60)
    logger.info(f"Distributed Forecast Complete")
    logger.info(f"=" * 60)
    logger.info(f"  Tickers: {ticker_count}")
    logger.info(f"  Horizon: {horizon} days")
    logger.info(f"  Forecasts: {forecast_count:,}")
    logger.info(f"  Duration: {duration:.1f}s")
    logger.info(f"  Rate: {ticker_count / duration:.1f} tickers/sec")
    logger.info(f"  Output: {output_path}")
    logger.info(f"")

    spark.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage root path')
    parser.add_argument('--horizon', type=int, default=30,
                        help='Forecast horizon in days')
    parser.add_argument('--max-tickers', type=int,
                        help='Limit tickers (for testing)')

    args = parser.parse_args()
    setup_logging()

    run_distributed_forecast(
        storage_path=Path(args.storage_path),
        horizon=args.horizon,
        max_tickers=args.max_tickers,
    )


if __name__ == "__main__":
    main()
