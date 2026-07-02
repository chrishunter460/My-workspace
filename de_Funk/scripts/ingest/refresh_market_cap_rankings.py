"""
Refresh Market Cap Data

Fetches OVERVIEW for ALL US tickers to populate market cap in securities_reference.

Memory-optimized: Writes data in batches to avoid accumulating all responses in memory.

Usage:
    python -m scripts.ingest.refresh_market_cap_rankings
    python -m scripts.ingest.refresh_market_cap_rankings --yes  # Skip confirmation
    python -m scripts.ingest.refresh_market_cap_rankings --batch-size 200  # Smaller batches for low memory
    python -m scripts.ingest.refresh_market_cap_rankings --max-tickers 1000  # Limit to top N tickers
"""

from __future__ import annotations

import argparse

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def main():
    parser = argparse.ArgumentParser(
        description="Refresh market cap data for all US tickers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--batch-size", type=int, default=500,
        help="Number of tickers to fetch before writing to disk (default: 500). "
             "Lower values use less memory but may be slightly slower."
    )
    parser.add_argument(
        "--max-tickers", type=int, default=None,
        help="Maximum number of tickers to process (default: all US tickers)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("REFRESH MARKET CAP DATA (OVERVIEW endpoint)")
    print("=" * 80)
    print(f"Batch size: {args.batch_size} (memory optimization)")

from de_funk.core.context import RepoContext
from de_funk.pipelines.providers.alpha_vantage import AlphaVantageIngestor

    ctx = RepoContext.from_repo_root(connection_type="spark")
    ingestor = AlphaVantageIngestor(
        alpha_vantage_cfg=ctx.get_api_config('alpha_vantage'),
        storage_cfg=ctx.storage,
        spark=ctx.spark
    )

    # Get ALL tickers
    print("\nFetching ticker list via LISTING_STATUS...")
    _, all_tickers, ticker_exchanges = ingestor.ingest_bulk_listing()

    us_exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
    us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]
    print(f"Found {len(us_tickers)} US tickers")

    # Apply max_tickers limit if specified
    if args.max_tickers and args.max_tickers < len(us_tickers):
        us_tickers = us_tickers[:args.max_tickers]
        print(f"Limited to first {args.max_tickers} tickers")

    # Estimate time
    rate_limit = ingestor.registry.rate_limit  # calls per second
    estimated_seconds = len(us_tickers) / rate_limit
    estimated_minutes = estimated_seconds / 60
    estimated_hours = estimated_minutes / 60

    # Calculate number of batches
    num_batches = (len(us_tickers) + args.batch_size - 1) // args.batch_size

    print(f"\n⏱️  Estimated time: {estimated_hours:.1f} hours ({estimated_minutes:.0f} minutes)")
    print(f"   Rate limit: {rate_limit} calls/sec")
    print(f"   API calls needed: {len(us_tickers)}")
    print(f"   Batches: {num_batches} (writing to disk after each)")
    print(f"   Memory usage: ~{args.batch_size * 5 / 1024:.1f} MB per batch (approx)")

    if not args.yes:
        response = input("\nProceed? (y/n): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    # Fetch OVERVIEW for all (with batch writing)
    print(f"\nFetching OVERVIEW for {len(us_tickers)} tickers...")
    ingestor.ingest_reference_data(
        tickers=us_tickers,
        show_progress=True,
        batch_size=args.batch_size
    )

    # Show top results
    print("\nTop 20 by market cap:")
    ranked = ingestor.get_tickers_by_market_cap(max_tickers=20)
    for i, t in enumerate(ranked, 1):
        print(f"  {i:3}. {t}")

    print("\n" + "=" * 80)
    print("Done.")
    print("=" * 80)


if __name__ == "__main__":
    main()
