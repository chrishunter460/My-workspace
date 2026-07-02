"""
Technical Indicators Module for Stocks Domain.

Computes technical indicators (SMA, RSI, Bollinger Bands, etc.) using
native Spark window functions. Spark handles memory management automatically
via partitioning - no Python-level batching needed.

This module is part of the stocks domain and is called by StocksBuilder.post_build().
A CLI wrapper exists at scripts/build/compute_technicals.py for manual runs.

Architecture Note:
    Spark's window functions with partitionBy("ticker") handle memory automatically.
    Each partition is processed independently, allowing Spark to spill to disk
    if needed. This scales to millions of rows without manual batching.
"""
from __future__ import annotations

from pathlib import Path
import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger(__name__)


def compute_technicals(
    storage_path: Path,
    dry_run: bool = False,
    spark: SparkSession = None
) -> int:
    """
    Compute technical indicators for all stocks using native Spark windowing.

    Spark handles memory automatically via partitioning. No Python batching needed.

    Args:
        storage_path: Root storage path
        dry_run: If True, just show what would be done
        spark: Optional Spark session (creates one if not provided)

    Returns:
        Total rows processed
    """
    from de_funk.orchestration.common.spark_session import get_spark

    # Paths - fact_stock_prices is in silver layer
    silver_root = storage_path / "silver" / "stocks" / "facts"
    prices_path = silver_root / "fact_stock_prices"

    if not prices_path.exists():
        logger.error(f"Prices table not found: {prices_path}")
        return 0

    logger.info(f"Computing technical indicators for {prices_path}")

    # Check if Delta or Parquet
    is_delta = (prices_path / "_delta_log").exists()
    format_type = "delta" if is_delta else "parquet"
    logger.debug(f"Format: {format_type}")

    # Use provided spark session or create one
    owns_spark = spark is None
    if owns_spark:
        spark = get_spark("TechnicalsCompute")

    try:
        # Read the prices table
        logger.info("Loading price data...")
        if is_delta:
            df = spark.read.format("delta").load(str(prices_path))
        else:
            df = spark.read.parquet(str(prices_path))

        # Check what columns we have
        cols = df.columns

        # Determine the partition column and order column
        # New schema (post-refactor): security_id, date_id
        # Old schema (pre-refactor): ticker, trade_date
        if 'security_id' in cols and 'date_id' in cols:
            partition_col = "security_id"
            order_col = "date_id"
            logger.debug(f"Using new schema: partition by {partition_col}, order by {order_col}")
        elif 'ticker' in cols and 'trade_date' in cols:
            partition_col = "ticker"
            order_col = "trade_date"
            logger.debug(f"Using legacy schema: partition by {partition_col}, order by {order_col}")
        else:
            logger.error(f"Cannot determine partition/order columns from schema: {cols}")
            return 0

        row_count = df.count()
        distinct_count = df.select(partition_col).distinct().count()

        logger.info(f"Total rows: {row_count:,}, distinct {partition_col}s: {distinct_count:,}")

        if dry_run:
            logger.info("DRY RUN - would compute technicals for all securities")
            return 0

        # Compute the indicators
        df = _add_technical_indicators(df, partition_col, order_col)

        # Write back to same location (overwrite)
        logger.info(f"Writing {row_count:,} rows with technical indicators...")

        if is_delta:
            df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(prices_path))
        else:
            df.write.mode("overwrite").parquet(str(prices_path))

        logger.info(f"Technical indicators complete: {row_count:,} rows, {distinct_count:,} securities")
        return row_count

    finally:
        if owns_spark:
            spark.stop()


def _add_technical_indicators(
    df: DataFrame,
    partition_col: str,
    order_col: str,
    price_col: str = "adjusted_close"
) -> DataFrame:
    """
    Add technical indicator columns to a price DataFrame.

    Args:
        df: DataFrame with price data (must have price_col and 'volume' columns)
        partition_col: Column to partition by (ticker or security_id)
        order_col: Column to order by (trade_date or date_id)
        price_col: Column to use for price calculations (default: adjusted_close)
                   Use adjusted_close for split-adjusted prices, close for raw prices.

    Returns:
        DataFrame with technical indicator columns added
    """
    # Verify price column exists, fallback to 'close' if adjusted_close not available
    if price_col not in df.columns:
        if 'close' in df.columns:
            logger.warning(f"Price column '{price_col}' not found, falling back to 'close'")
            price_col = 'close'
        else:
            raise ValueError(f"Neither '{price_col}' nor 'close' found in DataFrame columns: {df.columns}")

    logger.info(f"Computing technicals using price column: {price_col}")

    # Define window specs - Spark handles partitioning automatically
    security_window = Window.partitionBy(partition_col).orderBy(order_col)

    # Rolling windows of different sizes
    window_14 = security_window.rowsBetween(-13, 0)
    window_20 = security_window.rowsBetween(-19, 0)
    window_50 = security_window.rowsBetween(-49, 0)
    window_60 = security_window.rowsBetween(-59, 0)
    window_200 = security_window.rowsBetween(-199, 0)

    # Step 1: Daily return and price change (using adjusted prices)
    logger.debug("Computing returns...")
    df = df.withColumn(
        "prev_price",
        F.lag(price_col, 1).over(security_window)
    ).withColumn(
        "daily_return",
        F.when(F.col("prev_price").isNotNull() & (F.col("prev_price") != 0),
               (F.col(price_col) - F.col("prev_price")) / F.col("prev_price") * 100)
        .otherwise(None)
    ).withColumn(
        "price_change",
        F.col(price_col) - F.col("prev_price")
    )

    # Step 2: Simple Moving Averages (using adjusted prices)
    logger.debug("Computing SMAs (20, 50, 200)...")
    df = (df
        .withColumn("sma_20", F.avg(price_col).over(window_20))
        .withColumn("sma_50", F.avg(price_col).over(window_50))
        .withColumn("sma_200", F.avg(price_col).over(window_200))
    )

    # Step 3: RSI (Relative Strength Index)
    logger.debug("Computing RSI...")
    df = (df
        .withColumn(
            "gain",
            F.when(F.col("price_change") > 0, F.col("price_change")).otherwise(0)
        )
        .withColumn(
            "loss",
            F.when(F.col("price_change") < 0, F.abs(F.col("price_change"))).otherwise(0)
        )
        .withColumn("avg_gain_14", F.avg("gain").over(window_14))
        .withColumn("avg_loss_14", F.avg("loss").over(window_14))
        .withColumn(
            "rs_14",
            F.when(F.col("avg_loss_14") != 0, F.col("avg_gain_14") / F.col("avg_loss_14"))
            .otherwise(None)
        )
        .withColumn(
            "rsi_14",
            F.when(F.col("rs_14").isNotNull(), 100 - (100 / (1 + F.col("rs_14"))))
            .otherwise(50)  # Neutral RSI when undefined
        )
    )

    # Step 4: Volatility
    logger.debug("Computing volatility...")
    df = (df
        .withColumn("volatility_20d", F.stddev("daily_return").over(window_20) * (252 ** 0.5))
        .withColumn("volatility_60d", F.stddev("daily_return").over(window_60) * (252 ** 0.5))
    )

    # Step 5: Bollinger Bands (using adjusted prices)
    logger.debug("Computing Bollinger Bands...")
    std_20 = F.stddev(price_col).over(window_20)
    df = (df
        .withColumn("bollinger_middle", F.col("sma_20"))
        .withColumn("bollinger_upper", F.col("sma_20") + (2 * std_20))
        .withColumn("bollinger_lower", F.col("sma_20") - (2 * std_20))
    )

    # Step 6: Volume indicators
    logger.debug("Computing volume indicators...")
    df = (df
        .withColumn("volume_sma_20", F.avg("volume").over(window_20))
        .withColumn(
            "volume_ratio",
            F.when(F.col("volume_sma_20") != 0, F.col("volume") / F.col("volume_sma_20"))
            .otherwise(None)
        )
    )

    # Drop intermediate columns
    df = df.drop("prev_price", "price_change", "gain", "loss", "avg_gain_14", "avg_loss_14", "rs_14")

    return df
