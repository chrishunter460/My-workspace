#!/usr/bin/env python3
"""
Seed Calendar to Bronze Layer.

Generates calendar dimension data and writes to Bronze layer so the temporal model
can read it during Silver layer build.

Usage:
    python -m scripts.seed.seed_calendar
    python -m scripts.seed.seed_calendar --storage-path /shared/storage

The calendar is generated data (not ingested from an API), but we seed it to
Bronze to maintain consistent architecture (Bronze -> Silver).
"""

import sys
import argparse
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from de_funk.orchestration.common.spark_session import get_spark
from de_funk.models.domains.foundation.temporal.builders.calendar_builder import CalendarBuilder


def seed_calendar(storage_path: Path = None, spark=None) -> int:
    """
    Seed calendar to Bronze layer.

    Args:
        storage_path: Optional storage root (default: repo_root/storage)
        spark: Optional SparkSession (will create one if not provided)

    Returns:
        Number of rows written
    """
    # Determine storage path
    if storage_path is None:
        storage_path = repo_root / "storage"
    storage_path = Path(storage_path)

    bronze_path = storage_path / "bronze" / "calendar_seed"

    # Check if already exists
    if bronze_path.exists() and (bronze_path / "_delta_log").exists():
        # Check row count
        owns_spark = spark is None
        if owns_spark:
            spark = get_spark("CalendarSeedCheck")
        try:
            existing_df = spark.read.format("delta").load(str(bronze_path))
            existing_count = existing_df.count()
            if existing_count > 0:
                print(f"✓ Calendar already seeded: {existing_count:,} rows at {bronze_path}")
                return existing_count
        except Exception:
            pass  # Continue to regenerate
        finally:
            if owns_spark:
                spark.stop()

    print("=" * 70)
    print("Seeding Calendar to Bronze Layer")
    print("=" * 70)
    print()

    # Initialize Spark if not provided
    owns_spark = spark is None
    if owns_spark:
        print("1. Initializing Spark...")
        spark = get_spark("CalendarSeed")
        print()
    else:
        print("1. Using existing Spark session...")
        print()

    # Calendar configuration (matches temporal model calendar_config)
    start_date = "2000-01-01"
    end_date = "2050-12-31"
    fiscal_year_start_month = 1

    print(f"2. Generating calendar data...")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Fiscal year starts: Month {fiscal_year_start_month}")
    print()

    # Build calendar
    builder = CalendarBuilder(
        start_date=start_date,
        end_date=end_date,
        fiscal_year_start_month=fiscal_year_start_month
    )
    calendar_df = builder.build_spark_dataframe(spark)

    row_count = calendar_df.count()
    print(f"   Generated {row_count:,} calendar rows")
    print()

    # Write to Bronze layer
    print(f"3. Writing to Bronze layer...")
    print(f"   Path: {bronze_path}")
    print()

    calendar_df.write.format("delta").mode("overwrite").save(str(bronze_path))

    print(f"   Written successfully!")
    print()

    # Verify
    print("4. Verifying...")
    verify_df = spark.read.format("delta").load(str(bronze_path))
    verify_count = verify_df.count()
    print(f"   Verified: {verify_count:,} rows in Bronze")
    print()

    # Show sample
    print("5. Sample data:")
    verify_df.select("date", "year", "quarter", "month", "day_of_week_name", "is_weekday").show(5)

    print("=" * 70)
    print("Calendar seed complete!")
    print("=" * 70)
    print()

    if owns_spark:
        spark.stop()

    return verify_count


def main():
    parser = argparse.ArgumentParser(description="Seed calendar to Bronze layer")
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Storage root path (default: repo_root/storage)"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path) if args.storage_path else None
    seed_calendar(storage_path)


if __name__ == "__main__":
    main()
