"""
Check volatility data quality in silver layer.

Usage:
    python -m scripts.diagnostics.check_volatility
"""

from __future__ import annotations

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from pathlib import Path
import json


def main():
    print("=" * 80)
    print("VOLATILITY DATA QUALITY CHECK")
    print("=" * 80)

    # Load storage config
    config_path = repo_root / "configs" / "storage.json"
    with open(config_path) as f:
        storage = json.load(f)

    silver_path = Path(storage["roots"]["silver"])
    prices_path = silver_path / "stocks" / "facts" / "fact_stock_prices"

    if not prices_path.exists():
        print(f"\n❌ Prices table not found at {prices_path}")
        return

    import pandas as pd

    print(f"\nLoading price data from {prices_path}...")
    df = pd.read_parquet(prices_path)

    print(f"Total rows: {len(df):,}")
    print(f"Unique tickers: {df['ticker'].nunique()}")

    # Check volatility columns
    vol_cols = ['volatility_20d', 'volatility_60d']

    print("\n" + "-" * 60)
    print("VOLATILITY NULL/NAN ANALYSIS:")
    print("-" * 60)

    for col in vol_cols:
        if col in df.columns:
            total = len(df)
            null_count = df[col].isna().sum()
            valid_count = total - null_count
            null_pct = null_count / total * 100

            print(f"\n{col}:")
            print(f"  Total rows:    {total:,}")
            print(f"  Valid values:  {valid_count:,} ({100-null_pct:.1f}%)")
            print(f"  NULL/NaN:      {null_count:,} ({null_pct:.1f}%)")

            # Check by ticker - how many rows needed before valid volatility
            if valid_count > 0:
                # Sample a few tickers to see warm-up period
                sample_tickers = df['ticker'].unique()[:5]
                print(f"\n  Warm-up analysis (first 5 tickers):")

                for ticker in sample_tickers:
                    ticker_df = df[df['ticker'] == ticker].sort_values('trade_date')
                    first_valid_idx = ticker_df[col].first_valid_index()

                    if first_valid_idx is not None:
                        first_valid_row = ticker_df.loc[first_valid_idx]
                        first_date = ticker_df['trade_date'].iloc[0]
                        valid_date = first_valid_row['trade_date']
                        row_num = ticker_df.index.get_loc(first_valid_idx) + 1

                        print(f"    {ticker}: First valid at row {row_num} ({valid_date})")
                    else:
                        print(f"    {ticker}: NO VALID VALUES!")
        else:
            print(f"\n{col}: Column not found!")

    # Check a specific ticker in detail
    print("\n" + "-" * 60)
    print("SAMPLE: AAPL volatility over time")
    print("-" * 60)

    if 'AAPL' in df['ticker'].values:
        aapl = df[df['ticker'] == 'AAPL'].sort_values('trade_date')

        print(f"\nAAPL rows: {len(aapl)}")
        print(f"Date range: {aapl['trade_date'].min()} to {aapl['trade_date'].max()}")

        # Show first 25 rows (where we'd expect NaN)
        print("\nFirst 25 rows (expecting NaN for volatility_20d):")
        cols_to_show = ['trade_date', 'close', 'daily_return', 'volatility_20d', 'volatility_60d']
        cols_available = [c for c in cols_to_show if c in aapl.columns]
        print(aapl[cols_available].head(25).to_string())

        # Show some rows after warm-up
        print("\nRows 50-55 (should have valid volatility_20d):")
        print(aapl[cols_available].iloc[50:56].to_string())

        # Show recent data
        print("\nLast 5 rows (recent data):")
        print(aapl[cols_available].tail(5).to_string())
    else:
        print("\nAAPL not found - showing sample ticker instead")
        sample_ticker = df['ticker'].iloc[0]
        sample = df[df['ticker'] == sample_ticker].sort_values('trade_date')
        print(f"\nTicker: {sample_ticker}, rows: {len(sample)}")

        cols_to_show = ['trade_date', 'close', 'daily_return', 'volatility_20d']
        cols_available = [c for c in cols_to_show if c in sample.columns]

        print("\nFirst 25 rows:")
        print(sample[cols_available].head(25).to_string())

        print("\nRows 50-55:")
        print(sample[cols_available].iloc[50:56].to_string())

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("- NaN in first ~20 rows is EXPECTED (need 20 days for volatility_20d)")
    print("- NaN in first ~60 rows is EXPECTED for volatility_60d")
    print("- If ALL rows are NaN, there's a calculation issue")
    print("=" * 80)


if __name__ == "__main__":
    main()
