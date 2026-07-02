#!/usr/bin/env python
"""
Debug script to isolate the Spark session issue when reading stocks from forecast.

This simulates what happens in the pipeline:
1. Do a Delta WRITE (like StocksBuilder does)
2. Then try to READ (like ForecastBuilder does)

The hypothesis is that Delta Lake 4.x clears the session after writes.

Usage:
    spark-submit --packages io.delta:delta-spark_2.13:4.0.0 scripts/debug/debug_forecast_read.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))


def check_session(spark, label: str):
    """Check JVM session state."""
    try:
        jvm = spark._jvm
        active = jvm.org.apache.spark.sql.SparkSession.getActiveSession()
        default = jvm.org.apache.spark.sql.SparkSession.getDefaultSession()
        active_ok = active.isDefined() if active else False
        default_ok = default.isDefined() if default else False
        status = "OK" if (active_ok and default_ok) else "MISSING"
        print(f"    [{status}] {label}: active={active_ok}, default={default_ok}")
        return active_ok and default_ok
    except Exception as e:
        print(f"    [ERROR] {label}: {e}")
        return False


def main():
    print("=" * 60)
    print("DEBUG: Simulate Write-then-Read (like stocks→forecast)")
    print("=" * 60)

    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = repo_root / "storage"

    # Step 1: Get Spark session
    print("\n[1] Getting Spark session...")
from de_funk.orchestration.common.spark_session import get_spark
    spark = get_spark()
    print(f"    Got: {spark}")
    check_session(spark, "Initial")

    # Step 2: Create a test Delta table and WRITE to it (simulating StocksBuilder)
    print("\n[2] Writing test Delta table (simulating StocksBuilder write)...")
    test_path = str(storage_root / "tmp" / "debug_write_test")

    # Create test data
    test_df = spark.createDataFrame([
        (1, "AAPL", 150.0),
        (2, "MSFT", 300.0),
        (3, "GOOGL", 140.0),
    ], ["id", "ticker", "price"])

    check_session(spark, "Before write")

    # Write to Delta (this is what StocksBuilder does)
    test_df.write.format("delta").mode("overwrite").save(test_path)
    print(f"    Wrote to: {test_path}")

    check_session(spark, "After write")

    # Step 3: Now try to READ from the stocks Silver layer (like ForecastBuilder)
    print("\n[3] Reading stocks Silver layer (like ForecastBuilder does)...")

    # Create StocksModel the same way ForecastBuilder does
from de_funk.core.connection import get_spark_connection
    connection = get_spark_connection(spark)

    storage_cfg = {
        'root': str(storage_root),
        'silver_root': str(storage_root / 'silver'),
        'bronze_root': str(storage_root / 'bronze'),
    }

from de_funk.config.domain import get_domain_loader
    domains_dir = repo_root / "domains"
    loader = get_domain_loader(domains_dir)
    stocks_config = loader.load_model_config("securities.stocks")

from de_funk.models.domains.securities.stocks.model import StocksModel
    stocks_model = StocksModel(
        connection=connection,
        storage_cfg=storage_cfg,
        model_cfg=stocks_config,
        params={},
        repo_root=repo_root
    )

    check_session(spark, "Before ensure_built")

    try:
        stocks_model.ensure_built()
        print("    ensure_built() SUCCESS")
    except Exception as e:
        print(f"    ensure_built() FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    check_session(spark, "After ensure_built")

    # Step 4: Get tickers (the actual failing call)
    print("\n[4] Getting tickers (like ForecastBuilder.get_available_tickers)...")

    check_session(spark, "Before list_tickers")

    try:
        tickers = stocks_model.list_tickers(active_only=False)
        print(f"    Got {len(tickers)} tickers: {tickers[:5]}")
    except Exception as e:
        print(f"    FAILED: {e}")
        import traceback
        traceback.print_exc()

    check_session(spark, "Final")

    # Cleanup
    print("\n[5] Cleanup...")
    import shutil
    shutil.rmtree(test_path, ignore_errors=True)
    print(f"    Removed: {test_path}")

    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
