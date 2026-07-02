"""
Check Bronze Layer Ticker Counts

Quick diagnostic to see how many tickers and market cap data exists in bronze.

Usage:
    python -m scripts.diagnostics.check_bronze_tickers
"""

from __future__ import annotations

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from pathlib import Path
import json


def main():
    print("=" * 80)
    print("BRONZE LAYER TICKER DIAGNOSTICS")
    print("=" * 80)

    # Load storage config
    config_path = repo_root / "configs" / "storage.json"
    with open(config_path) as f:
        storage = json.load(f)

    bronze_path = Path(storage["roots"]["bronze"])

    # Check for both new (Alpha Vantage) and old (Polygon) table names
    possible_paths = [
        ("securities_reference", bronze_path / "securities_reference"),  # New AV
        ("ref_ticker", bronze_path / "ref_ticker"),  # Old Polygon
        ("ref_all_tickers", bronze_path / "ref_all_tickers"),  # Old Polygon
    ]

    print(f"\nBronze path: {bronze_path}")
    print("\nChecking for reference data tables:")

    ref_path = None
    table_name = None
    for name, path in possible_paths:
        exists = path.exists()
        print(f"  {name}: {path} - {'✓ EXISTS' if exists else '✗ not found'}")
        if exists and ref_path is None:
            ref_path = path
            table_name = name

    if ref_path is None:
        print("\n❌ No reference data table found in bronze!")
        return

    print(f"\nUsing table: {table_name}")

    # Use pandas + pyarrow for reading
    import pandas as pd

    print("\n" + "-" * 60)
    print(f"Loading {table_name} with pandas...")

    # Read all parquet files
    df = pd.read_parquet(ref_path)

    total_rows = len(df)
    print(f"\nTotal rows: {total_rows:,}")

    # Show columns
    print(f"\nColumns: {list(df.columns)}")

    # Count unique tickers
    unique_tickers = df['ticker'].nunique()
    print(f"\nUnique tickers: {unique_tickers:,}")

    # Check market cap data
    if 'market_cap' in df.columns:
        df_with_cap = df[(df['market_cap'].notna()) & (df['market_cap'] > 0)]
        rows_with_cap = len(df_with_cap)
        unique_with_cap = df_with_cap['ticker'].nunique()

        print(f"\nRows with valid market_cap: {rows_with_cap:,}")
        print(f"Unique tickers with market_cap: {unique_with_cap:,}")
    else:
        print("\n⚠️  market_cap column not found!")
        unique_with_cap = 0

    # Check by asset_type if column exists
    if "asset_type" in df.columns:
        print("\n" + "-" * 60)
        print("Breakdown by asset_type:")
        asset_summary = df.groupby('asset_type', observed=True).size().rename('total_rows')
        if 'market_cap' in df.columns:
            cap_summary = df[df['market_cap'].notna() & (df['market_cap'] > 0)].groupby('asset_type', observed=True).size().rename('with_market_cap')
            asset_summary = pd.concat([asset_summary, cap_summary], axis=1).fillna(0).astype(int)
        print(asset_summary.to_string())

    # Check by snapshot_dt if column exists
    if "snapshot_dt" in df.columns:
        print("\n" + "-" * 60)
        print("Breakdown by snapshot_dt (last 5):")
        snapshot_summary = df.groupby('snapshot_dt', observed=True).size().rename('rows')
        snapshot_summary = snapshot_summary.sort_index(ascending=False).head(5)
        print(snapshot_summary.to_string())

    # Show sample of tickers with market cap
    if 'market_cap' in df.columns:
        print("\n" + "-" * 60)
        print("Top 10 tickers by market cap:")
        top_10 = df_with_cap.nlargest(10, 'market_cap')[['ticker', 'security_name', 'market_cap', 'asset_type']]
        top_10['market_cap_B'] = top_10['market_cap'] / 1e9
        print(top_10[['ticker', 'security_name', 'market_cap_B', 'asset_type']].to_string())

        # Show sample of tickers WITHOUT market cap
        print("\nSample tickers WITHOUT market cap (first 10):")
        no_cap = df[(df['market_cap'].isna()) | (df['market_cap'] == 0)][['ticker', 'security_name', 'asset_type']].head(10)
        print(no_cap.to_string())

    # Check if there's duplicate tickers
    print("\n" + "-" * 60)
    print("Checking for duplicate tickers...")
    ticker_counts = df['ticker'].value_counts()
    dups = ticker_counts[ticker_counts > 1]
    if len(dups) > 0:
        print(f"⚠️  Found {len(dups)} tickers with multiple rows:")
        print(dups.head(10).to_string())
    else:
        print("✓ No duplicate tickers found")

    print("\n" + "=" * 80)
    print("Summary:")
    print(f"  Total rows in bronze: {total_rows:,}")
    print(f"  Unique tickers: {unique_tickers:,}")
    print(f"  Tickers with market cap: {unique_with_cap:,}")
    print(f"  Tickers missing market cap: {unique_tickers - unique_with_cap:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
