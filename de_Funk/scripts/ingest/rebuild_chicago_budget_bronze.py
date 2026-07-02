#!/usr/bin/env python3
"""
Rebuild Chicago budget bronze tables from raw CSVs.

Reads the raw year-per-file CSVs, normalizes wide-format year columns
into a single 'amount' field, and writes clean Delta tables to bronze.

Usage:
    python -m scripts.ingest.rebuild_chicago_budget_bronze
    python -m scripts.ingest.rebuild_chicago_budget_bronze --storage-path /shared/storage
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger
logger = get_logger(__name__)

# Budget endpoints and their raw CSV naming patterns
BUDGET_ENDPOINTS = {
    "budget_appropriations": {
        "bronze_table": "chicago/budget_appropriations",
        "csv_prefix": "budget_appropriations_",
    },
    "budget_revenue": {
        "bronze_table": "chicago/budget_revenue",
        "csv_prefix": "budget_revenue_",
    },
    "budget_positions_salaries": {
        "bronze_table": "chicago/budget_positions_salaries",
        "csv_prefix": "budget_positions_salaries_",
    },
}


def _find_amount(record: dict, year: str) -> None:
    """Find the amount value from whatever column the CSV uses.

    Chicago budget CSVs use inconsistent column names across years:
      - 2011: 'AMOUNT'
      - 2012: '2012 ORDINANCE (AMOUNT $)'
      - 2013: '2013 APPROPRIATION ORDINANCE (AMOUNT $)' or similar
      - 2016+: '2016 ORDINANCE (AMOUNT $)'
      - Positions: 'TOTAL BUDGETED AMOUNT' or 'Total Budgeted Amount'
      - Revenue: 'ESTIMATED REVENUE' or similar
    """
    # Normalize all keys to lowercase for matching
    lower_map = {k.lower(): k for k in record.keys()}

    # Already have 'amount'?
    if 'amount' in lower_map:
        val = record[lower_map['amount']]
        if val is not None and str(val).strip():
            record['amount'] = val
            return

    # Look for year-specific columns (case-insensitive)
    for key_lower, key_orig in lower_map.items():
        if key_lower.startswith(year) and ('ordinance' in key_lower or 'appropriation' in key_lower):
            val = record[key_orig]
            if val is not None and str(val).strip():
                record['amount'] = val
                return

    # Fallback candidates
    for candidate in ('total budgeted amount', 'total_budgeted_amount',
                       'estimated revenue', 'estimated_revenue',
                       'ordinance amount', 'ordinance_amount'):
        if candidate in lower_map:
            val = record[lower_map[candidate]]
            if val is not None and str(val).strip():
                record['amount'] = val
                return


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--storage-path', type=str, default='/shared/storage')
    parser.add_argument('--endpoints', type=str, default=None,
                        help='Comma-separated endpoints (default: all three budget)')
    args = parser.parse_args()

    storage = Path(args.storage_path)
    raw_dir = storage / 'raw' / 'chicago'
    bronze_dir = storage / 'bronze'

    if not raw_dir.exists():
        logger.error(f"Raw directory not found: {raw_dir}")
        sys.exit(1)

    endpoints = BUDGET_ENDPOINTS
    if args.endpoints:
        selected = {e.strip() for e in args.endpoints.split(',')}
        endpoints = {k: v for k, v in endpoints.items() if k in selected}

    from de_funk.orchestration.common.spark_session import get_spark
    spark = get_spark("RebuildBudgetBronze")

    for endpoint_id, config in endpoints.items():
        csv_prefix = config["csv_prefix"]
        bronze_path = str(bronze_dir / config["bronze_table"])

        # Find all raw CSVs for this endpoint
        csv_files = sorted(raw_dir.glob(f"{csv_prefix}*.csv"))
        if not csv_files:
            logger.warning(f"No CSVs found for {endpoint_id} in {raw_dir}")
            continue

        logger.info(f"Processing {endpoint_id}: {len(csv_files)} CSV files")

        all_dfs = []
        for csv_file in csv_files:
            # Extract year from filename: budget_appropriations_2016_36y7-5nnf.csv
            parts = csv_file.stem.split('_')
            year = None
            for p in parts:
                if p.isdigit() and len(p) == 4:
                    year = p
                    break
            if not year:
                logger.warning(f"  Skipping {csv_file.name}: can't extract year")
                continue

            # Read CSV
            df = spark.read.option("header", "true").option("inferSchema", "true").csv(str(csv_file))
            row_count = df.count()

            # Collect, normalize column names to snake_case and fix amounts
            rows = [row.asDict() for row in df.collect()]
            for row in rows:
                _find_amount(row, year)
                # Normalize keys to snake_case
                normalized = {}
                for k, v in row.items():
                    snake = k.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('$', '').strip('_')
                    normalized[snake] = v
                normalized['year'] = int(year)
                # Ensure 'amount' is in the normalized row
                if 'amount' not in normalized:
                    normalized['amount'] = row.get('amount')
                row.clear()
                row.update(normalized)

            # Build clean DataFrame with only canonical columns, all as strings
            if rows:
                df_clean = spark.createDataFrame(rows)

                # Drop wide year columns
                drop_cols = [c for c in df_clean.columns
                             if c[0].isdigit() and ('ordinance' in c or 'appropriation' in c)]
                if drop_cols:
                    df_clean = df_clean.drop(*drop_cols)

                # Cast everything to string to avoid type conflicts across years
                from pyspark.sql.functions import col as spark_col
                for c in df_clean.columns:
                    df_clean = df_clean.withColumn(c, spark_col(c).cast("string"))

                all_dfs.append(df_clean)
                amount_count = sum(1 for r in rows if r.get('amount') is not None)
                logger.info(f"  {year}: {row_count} rows, {amount_count} with amount")

        if not all_dfs:
            logger.warning(f"No data for {endpoint_id}")
            continue

        # Union all years
        result = all_dfs[0]
        for df in all_dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)

        total = result.count()

        # Delete existing Delta table to avoid schema merge conflicts
        import shutil
        if Path(bronze_path).exists():
            shutil.rmtree(bronze_path)

        # Write to bronze
        result.write.format("delta").mode("overwrite").partitionBy("year").save(bronze_path)
        logger.info(f"  Wrote {total:,} rows to {bronze_path}")

        # Verify
        verify = spark.read.format("delta").load(bronze_path)
        from pyspark.sql.functions import count, col
        verify.groupBy("year").agg(
            count("*").alias("rows"),
            count(col("amount")).alias("with_amount")
        ).orderBy("year").show(50)

    spark.stop()
    logger.info("Done")


if __name__ == "__main__":
    main()
