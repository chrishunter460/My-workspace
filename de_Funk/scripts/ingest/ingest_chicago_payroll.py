#!/usr/bin/env python3
"""
Ingest Chicago FMPS Payroll Costing into bronze.

Reads the raw CSV, normalizes column names to snake_case, and writes
a clean Delta table partitioned by payroll_year.

Usage:
    python -m scripts.ingest.ingest_chicago_payroll
    python -m scripts.ingest.ingest_chicago_payroll --storage-path /shared/storage
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from de_funk.config.logging import setup_logging, get_logger
logger = get_logger(__name__)

RAW_FILE = "fmps_payroll_dawh-m56b.csv"
BRONZE_TABLE = "chicago/fmps_payroll"


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--storage-path', type=str, default='/shared/storage')
    args = parser.parse_args()

    storage = Path(args.storage_path)
    raw_path = storage / 'raw' / 'chicago' / RAW_FILE
    bronze_path = str(storage / 'bronze' / BRONZE_TABLE)

    if not raw_path.exists():
        logger.error(f"Raw CSV not found: {raw_path}")
        sys.exit(1)

    logger.info(f"Reading {raw_path}")

    from de_funk.orchestration.common.spark_session import get_spark
    spark = get_spark("IngestPayroll")

    df = (spark.read
          .option("header", "true")
          .option("inferSchema", "true")
          .csv(str(raw_path)))

    logger.info(f"Raw columns: {df.columns}")
    logger.info(f"Raw row count: {df.count():,}")

    # Normalize column names to snake_case
    for col_name in df.columns:
        snake = col_name.lower().replace(' ', '_')
        if snake != col_name:
            df = df.withColumnRenamed(col_name, snake)

    logger.info(f"Normalized columns: {df.columns}")

    # Verify key columns exist
    required = ['record_id', 'payroll_year', 'payroll_period', 'amount',
                'employee_dataset_id', 'department_code']
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error(f"Missing required columns: {missing}")
        logger.error(f"Available: {df.columns}")
        spark.stop()
        sys.exit(1)

    # Cast types
    from pyspark.sql import functions as F
    df = (df
          .withColumn("payroll_year", F.col("payroll_year").cast("int"))
          .withColumn("payroll_period", F.col("payroll_period").cast("int"))
          .withColumn("amount", F.col("amount").cast("double")))

    # Delete existing to avoid schema merge conflicts
    import shutil
    if Path(bronze_path).exists():
        shutil.rmtree(bronze_path)

    # Write to bronze
    logger.info(f"Writing to {bronze_path}")
    df.write.format("delta").mode("overwrite").partitionBy("payroll_year").save(bronze_path)

    # Verify
    verify = spark.read.format("delta").load(bronze_path)
    verify.groupBy("payroll_year").agg(
        F.count("*").alias("rows"),
        F.sum("amount").alias("total_amount"),
        F.countDistinct("employee_dataset_id").alias("employees"),
        F.countDistinct("department_code").alias("departments"),
    ).orderBy("payroll_year").show()

    total = verify.count()
    logger.info(f"Done: {total:,} rows written to {bronze_path}")

    spark.stop()


if __name__ == "__main__":
    main()
