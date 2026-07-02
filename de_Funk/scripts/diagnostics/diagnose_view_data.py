#!/usr/bin/env python3
"""
Diagnose what data is actually in the vw_price_predictions view.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("VIEW DATA DIAGNOSTIC")
print("=" * 80)

from de_funk.core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type="duckdb")
conn = ctx.connection.conn

# Check if view exists
print("\n[1] Checking if view exists...")
try:
    views = conn.execute("""
        SELECT table_schema, table_name
        FROM information_schema.views
        WHERE table_schema = 'forecast' AND table_name = 'vw_price_predictions'
    """).fetchdf()

    if len(views) > 0:
        print("✓ View exists: forecast.vw_price_predictions")
    else:
        print("✗ View does NOT exist!")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error checking view: {e}")
    sys.exit(1)

# Check view schema
print("\n[2] View schema:")
try:
    result = conn.execute("SELECT * FROM forecast.vw_price_predictions LIMIT 0").description
    columns = [col[0] for col in result]
    print(f"Columns: {columns}")
except Exception as e:
    print(f"✗ Error getting schema: {e}")

# Check row counts
print("\n[3] Row counts:")
try:
    total = conn.execute("SELECT COUNT(*) as cnt FROM forecast.vw_price_predictions").fetchdf()['cnt'][0]
    print(f"Total rows: {total}")

    actuals = conn.execute("SELECT COUNT(*) as cnt FROM forecast.vw_price_predictions WHERE actual IS NOT NULL").fetchdf()['cnt'][0]
    print(f"Rows with actuals: {actuals}")

    predicted = conn.execute("SELECT COUNT(*) as cnt FROM forecast.vw_price_predictions WHERE predicted IS NOT NULL").fetchdf()['cnt'][0]
    print(f"Rows with predictions: {predicted}")

    bounds = conn.execute("SELECT COUNT(*) as cnt FROM forecast.vw_price_predictions WHERE upper_bound IS NOT NULL").fetchdf()['cnt'][0]
    print(f"Rows with confidence bounds: {bounds}")
except Exception as e:
    print(f"✗ Error getting counts: {e}")

# Sample data
print("\n[4] Sample data (first 5 rows):")
try:
    sample = conn.execute("""
        SELECT * FROM forecast.vw_price_predictions
        ORDER BY date, ticker
        LIMIT 5
    """).fetchdf()

    print(sample.to_string())
except Exception as e:
    print(f"✗ Error getting sample: {e}")

# Check date column type
print("\n[5] Date column analysis:")
try:
    date_info = conn.execute("""
        SELECT
            MIN(date) as min_date,
            MAX(date) as max_date,
            COUNT(DISTINCT date) as unique_dates,
            typeof(date) as date_type
        FROM forecast.vw_price_predictions
    """).fetchdf()

    print(date_info.to_string())
except Exception as e:
    print(f"✗ Error analyzing dates: {e}")

# Check for model_name values
print("\n[6] Available model names:")
try:
    models = conn.execute("""
        SELECT model_name, COUNT(*) as cnt
        FROM forecast.vw_price_predictions
        WHERE model_name IS NOT NULL
        GROUP BY model_name
    """).fetchdf()

    if len(models) > 0:
        print(models.to_string())
    else:
        print("⚠ No model_name values found")
except Exception as e:
    print(f"✗ Error checking models: {e}")

# Check for ticker values
print("\n[7] Available tickers:")
try:
    tickers = conn.execute("""
        SELECT ticker, COUNT(*) as cnt
        FROM forecast.vw_price_predictions
        GROUP BY ticker
    """).fetchdf()

    print(tickers.to_string())
except Exception as e:
    print(f"✗ Error checking tickers: {e}")

# Check source tables
print("\n[8] Checking source table: fact_forecasts")
try:
    forecast_count = conn.execute("SELECT COUNT(*) as cnt FROM fact_forecasts").fetchdf()['cnt'][0]
    print(f"fact_forecasts rows: {forecast_count}")

    if forecast_count > 0:
        sample_forecast = conn.execute("""
            SELECT * FROM fact_forecasts LIMIT 3
        """).fetchdf()
        print("\nSample from fact_forecasts:")
        print(sample_forecast.to_string())
except Exception as e:
    print(f"⚠ Error checking fact_forecasts: {e}")

print("\n[9] Checking source table: fact_prices")
try:
    prices_count = conn.execute("SELECT COUNT(*) as cnt FROM fact_prices").fetchdf()['cnt'][0]
    print(f"fact_prices rows: {prices_count}")

    if prices_count > 0:
        sample_prices = conn.execute("""
            SELECT * FROM fact_prices LIMIT 3
        """).fetchdf()
        print("\nSample from fact_prices:")
        print(sample_prices.to_string())

        # Check if this is the full table or just AADR
        ticker_count = conn.execute("SELECT COUNT(DISTINCT ticker) as cnt FROM fact_prices").fetchdf()['cnt'][0]
        print(f"\nDistinct tickers in fact_prices: {ticker_count}")

        if ticker_count == 1:
            print("⚠ WARNING: fact_prices only has 1 ticker! It should have many.")
            print("   This means the table creation copied only forecast data, not the full company data.")
except Exception as e:
    print(f"⚠ Error checking fact_prices: {e}")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
