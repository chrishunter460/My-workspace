#!/usr/bin/env python
"""
Diagnostic script to verify Bronze layer data accumulation.

Tests that:
1. Bulk listing doesn't overwrite OVERVIEW data
2. Multiple runs accumulate tickers with detailed data
3. MERGE/upsert is working correctly
"""
from __future__ import annotations

import sys
sys.path.insert(0, '.')

from de_funk.orchestration.common.spark_session import get_spark

def diagnose():
    spark = get_spark('diagnose')

    print("=" * 80)
    print("BRONZE LAYER DIAGNOSTIC")
    print("=" * 80)

    # Check securities_reference
    print("\n📊 securities_reference table:")
    try:
        ref = spark.read.format('delta').load('storage/bronze/securities_reference')
        total = ref.count()
        print(f"  Total rows: {total}")

        # Count by data quality
        with_cik = ref.filter('cik IS NOT NULL').count()
        with_market_cap = ref.filter('market_cap IS NOT NULL').count()
        with_sector = ref.filter('sector IS NOT NULL').count()

        print(f"  Rows with CIK (from OVERVIEW): {with_cik}")
        print(f"  Rows with market_cap: {with_market_cap}")
        print(f"  Rows with sector: {with_sector}")

        # Show tickers with detailed data
        print("\n  Tickers with CIK (company-eligible):")
        ref.filter('cik IS NOT NULL').select(
            'ticker', 'security_name', 'cik', 'market_cap', 'sector'
        ).show(20, truncate=False)

        # Show schema to see all columns
        print("\n  Schema:")
        ref.printSchema()

    except Exception as e:
        print(f"  ERROR: {e}")

    # Check prices
    print("\n📊 securities_prices_daily table:")
    try:
        prices = spark.read.format('delta').load('storage/bronze/securities_prices_daily')
        total = prices.count()
        distinct_tickers = prices.select('ticker').distinct().count()
        print(f"  Total rows: {total}")
        print(f"  Distinct tickers: {distinct_tickers}")

        # Show ticker distribution
        print("\n  Rows per ticker:")
        prices.groupBy('ticker').count().orderBy('ticker').show(20)

    except Exception as e:
        print(f"  ERROR: {e}")

    # Check Delta history for securities_reference
    print("\n📜 Delta History (securities_reference):")
    try:
        from delta.tables import DeltaTable
        dt = DeltaTable.forPath(spark, 'storage/bronze/securities_reference')
        history = dt.history(10)
        history.select('version', 'timestamp', 'operation', 'operationParameters').show(10, truncate=False)
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    diagnose()
