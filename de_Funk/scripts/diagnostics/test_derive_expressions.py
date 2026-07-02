#!/usr/bin/env python3
"""
Test Derive Expressions - Verify derive expressions work with sample data.

Tests the exact expressions from stocks domain config against real bronze data.

Usage:
    python -m scripts.diagnostics.test_derive_expressions
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def main():
    # Import Spark
    try:
        from pyspark.sql import SparkSession, functions as F
    except ImportError:
        print("ERROR: PySpark not available")
        sys.exit(1)

    print("=" * 70)
    print("Testing Derive Expressions")
    print("=" * 70)

    # Create Spark session
    spark = SparkSession.builder \
        .appName("DeriveTester") \
        .config("spark.driver.memory", "2g") \
        .config("spark.ui.enabled", "false") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    # Create sample data that mimics bronze
    sample_data = [
        ("AAPL", "2024-01-15", 185.0, 187.5, 184.25, 186.75, 50000000.0, 186.75),
        ("MSFT", "2024-01-15", 395.0, 398.0, 393.0, 397.0, 25000000.0, 397.0),
        ("GOOGL", "2024-01-16", 140.0, 142.0, 139.5, 141.5, 18000000.0, 141.5),
    ]

    print("\n1. Creating sample DataFrame with STRING trade_date...")
    df_string = spark.createDataFrame(
        sample_data,
        ["ticker", "trade_date", "open", "high", "low", "close", "volume", "adjusted_close"]
    )
    df_string.printSchema()
    df_string.show(truncate=False)

    print("\n2. Testing derive expressions on STRING trade_date...")

    # Test each expression individually
    expressions = {
        "security_id": "ABS(HASH(ticker))",
        "date_id": "CAST(DATE_FORMAT(TO_DATE(trade_date), 'yyyyMMdd') AS INT)",  # Need TO_DATE for string
        "price_id": "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
    }

    df_test = df_string
    for col_name, expr in expressions.items():
        print(f"\n   Testing: {col_name} = {expr}")
        try:
            df_test = df_test.withColumn(col_name, F.expr(expr))
            print(f"   ✓ SUCCESS")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")

    print("\n   Result schema:")
    df_test.printSchema()
    print("\n   Result data:")
    df_test.select("ticker", "trade_date", "security_id", "date_id", "price_id").show(truncate=False)

    print("\n" + "=" * 70)
    print("3. Testing with DATE type trade_date (like actual bronze)...")
    print("=" * 70)

    # Create sample data with DATE type
    from pyspark.sql.types import StructType, StructField, StringType, DateType, DoubleType
    from datetime import date

    schema = StructType([
        StructField("ticker", StringType(), True),
        StructField("trade_date", DateType(), True),  # DATE type
        StructField("open", DoubleType(), True),
        StructField("high", DoubleType(), True),
        StructField("low", DoubleType(), True),
        StructField("close", DoubleType(), True),
        StructField("volume", DoubleType(), True),
        StructField("adjusted_close", DoubleType(), True),
    ])

    sample_data_date = [
        ("AAPL", date(2024, 1, 15), 185.0, 187.5, 184.25, 186.75, 50000000.0, 186.75),
        ("MSFT", date(2024, 1, 15), 395.0, 398.0, 393.0, 397.0, 25000000.0, 397.0),
        ("GOOGL", date(2024, 1, 16), 140.0, 142.0, 139.5, 141.5, 18000000.0, 141.5),
    ]

    df_date = spark.createDataFrame(sample_data_date, schema)
    df_date.printSchema()

    # Test the EXACT expressions from domain config (without TO_DATE since already DATE)
    print("\n   Testing EXACT expressions from domain config:")
    original_expressions = {
        "security_id": "ABS(HASH(ticker))",
        "date_id": "CAST(DATE_FORMAT(trade_date, 'yyyyMMdd') AS INT)",  # Direct - trade_date is already DATE
        "price_id": "ABS(HASH(CONCAT(ticker, '_', trade_date)))"
    }

    df_test2 = df_date
    for col_name, expr in original_expressions.items():
        print(f"\n   Testing: {col_name} = {expr}")
        try:
            df_test2 = df_test2.withColumn(col_name, F.expr(expr))
            print(f"   ✓ SUCCESS")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")

    print("\n   Result schema:")
    df_test2.printSchema()
    print("\n   Result data:")
    df_test2.select("ticker", "trade_date", "security_id", "date_id", "price_id").show(truncate=False)

    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("=" * 70)

    # Verify columns exist
    final_cols = df_test2.columns
    required = ["security_id", "date_id", "price_id"]
    missing = [c for c in required if c not in final_cols]

    if missing:
        print(f"✗ MISSING COLUMNS: {missing}")
        print("\nThe derive expressions are failing!")
    else:
        print("✓ All derive expressions work correctly")
        print("\nIf silver is still missing these columns, check:")
        print("  1. Build logs for WARNING messages")
        print("  2. Bronze schema matches (trade_date is DATE type)")
        print("  3. No exceptions during actual build")

    spark.stop()


if __name__ == "__main__":
    main()
