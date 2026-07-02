#!/usr/bin/env python
"""
Seed Market Cap Rankings from Bronze Data.

Calculates market cap from existing Bronze data:
  market_cap = latest_close_price × shares_outstanding

Creates/updates a market_cap_rankings table that can be used for ticker selection.

Usage:
    python -m scripts.seed.seed_market_cap --storage-path /shared/storage
    python -m scripts.seed.seed_market_cap --top 400 --sector Technology
    python -m scripts.seed.seed_market_cap --top 100 --industry "Software"

Prerequisites:
    - securities_prices_daily (has close prices)
    - company_reference (has shares_outstanding, sector, industry)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-path', type=str, default='/shared/storage',
                        help='Storage path (default: /shared/storage)')
    parser.add_argument('--top', type=int, default=400,
                        help='Top N tickers by market cap (default: 400)')
    parser.add_argument('--sector', type=str, default=None,
                        help='Filter by sector (e.g., "Technology", "Healthcare")')
    parser.add_argument('--industry', type=str, default=None,
                        help='Filter by industry (e.g., "Software", "Biotechnology")')
    parser.add_argument('--min-market-cap', type=float, default=None,
                        help='Minimum market cap in billions (e.g., 10 for $10B)')
    parser.add_argument('--output-table', type=str, default='market_cap_rankings',
                        help='Output table name (default: market_cap_rankings)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show results without writing')

    args = parser.parse_args()
    setup_logging()

    storage_path = Path(args.storage_path)
    bronze_path = storage_path / 'bronze'

    logger.info(f"Seeding market cap rankings from {storage_path}")
    logger.info(f"Top {args.top} tickers" +
                (f" in sector '{args.sector}'" if args.sector else "") +
                (f" in industry '{args.industry}'" if args.industry else ""))

    # Check prerequisites
    prices_path = bronze_path / 'securities_prices_daily'
    company_path = bronze_path / 'company_reference'

    if not prices_path.exists():
        logger.error(f"No securities_prices_daily at {prices_path}")
        logger.error("Run pipeline first to ingest price data")
        return 1

    if not company_path.exists():
        logger.error(f"No company_reference at {company_path}")
        logger.error("Run pipeline with company_overview endpoint first")
        return 1

    # Initialize Spark
from de_funk.orchestration.common.spark_session import get_spark
    spark = get_spark("MarketCapSeeder")

    try:
        # Register Delta tables as temp views
        spark.read.format("delta").load(str(prices_path)).createOrReplaceTempView("prices")
        spark.read.format("delta").load(str(company_path)).createOrReplaceTempView("company")

        # Build the query with window functions
        filters = []
        if args.sector:
            filters.append(f"c.sector = '{args.sector}'")
        if args.industry:
            filters.append(f"c.industry = '{args.industry}'")
        if args.min_market_cap:
            min_cap = args.min_market_cap * 1_000_000_000  # Convert billions to raw
            filters.append(f"calculated_market_cap >= {min_cap}")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        query = f"""
        WITH latest_prices AS (
            -- Get most recent price for each ticker using window function
            SELECT
                ticker,
                close,
                trade_date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) as rn
            FROM prices
            WHERE close IS NOT NULL AND close > 0
        ),
        market_caps AS (
            -- Join with company data and calculate market cap
            SELECT
                c.ticker,
                c.company_name,
                c.sector,
                c.industry,
                c.exchange_code,
                c.shares_outstanding,
                lp.close as latest_price,
                lp.trade_date as price_date,
                -- Use Alpha Vantage market_cap if available, otherwise calculate
                COALESCE(
                    c.market_cap,
                    CAST(lp.close AS DOUBLE) * CAST(c.shares_outstanding AS DOUBLE)
                ) as calculated_market_cap
            FROM company c
            INNER JOIN latest_prices lp ON c.ticker = lp.ticker AND lp.rn = 1
            WHERE c.shares_outstanding IS NOT NULL AND c.shares_outstanding > 0
        ),
        ranked AS (
            -- Rank by market cap
            SELECT
                *,
                ROW_NUMBER() OVER (ORDER BY calculated_market_cap DESC) as market_cap_rank,
                -- Also calculate percentile for reference
                PERCENT_RANK() OVER (ORDER BY calculated_market_cap DESC) as market_cap_percentile
            FROM market_caps
            {where_clause}
        )
        SELECT
            ticker,
            company_name,
            sector,
            industry,
            exchange_code,
            shares_outstanding,
            latest_price,
            price_date,
            calculated_market_cap as market_cap,
            market_cap_rank,
            ROUND(market_cap_percentile * 100, 2) as percentile
        FROM ranked
        WHERE market_cap_rank <= {args.top}
        ORDER BY market_cap_rank
        """

        logger.info("Executing market cap ranking query...")
        result_df = spark.sql(query)

        # Cache and count
        result_df.cache()
        count = result_df.count()

        if count == 0:
            logger.warning("No results! Check if company_reference has shares_outstanding data.")
            logger.info("You may need to run company_overview ingestion first.")
            return 1

        logger.info(f"Found {count} tickers")

        # Show top results
        print("\n" + "="*80)
        print(f"Top {min(10, count)} by Market Cap:")
        print("="*80)

        top_rows = result_df.limit(10).collect()
        for row in top_rows:
            cap_b = row['market_cap'] / 1e9 if row['market_cap'] else 0
            print(f"  {row['market_cap_rank']:3}. {row['ticker']:6} - {row['company_name'][:30]:30} "
                  f"${cap_b:,.1f}B  [{row['sector']}]")

        if count > 10:
            print(f"  ... and {count - 10} more")

        # Show sector breakdown
        print("\n" + "="*80)
        print("Sector Breakdown:")
        print("="*80)
        sector_counts = result_df.groupBy("sector").count().orderBy("count", ascending=False).collect()
        for row in sector_counts[:10]:
            print(f"  {row['sector']:30} {row['count']:4} tickers")

        if args.dry_run:
            print("\n[DRY RUN] Results not written to disk")
        else:
            # Write to Delta table
            output_path = bronze_path / args.output_table
            logger.info(f"Writing to {output_path}...")

            result_df.write.format("delta").mode("overwrite").save(str(output_path))

            logger.info(f"✓ Written {count} tickers to {args.output_table}")

        # Return ticker list for easy consumption
        print("\n" + "="*80)
        print("Ticker List (copy-paste ready):")
        print("="*80)
        tickers = [row['ticker'] for row in result_df.select("ticker").collect()]
        print(", ".join(tickers[:50]))
        if len(tickers) > 50:
            print(f"... and {len(tickers) - 50} more")

        return 0

    except Exception as e:
        logger.error(f"Failed to seed market cap: {e}", exc_info=True)
        return 1

    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
