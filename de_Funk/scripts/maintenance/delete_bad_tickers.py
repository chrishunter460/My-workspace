"""
Delete bad tickers from Silver Delta tables.

Removes all rows for tickers where adjusted_close > 100,000 due to extreme
reverse-split Alpha Vantage retroactive price adjustment. Affects 109 micro-cap
penny stocks whose historical prices are astronomically large and corrupt.

Tables cleaned:
  - fact_stock_prices  (primary — contains the bad prices)
  - fact_dividends     (secondary — may have rows for these tickers)
  - fact_splits        (secondary — these are exactly the splits that caused the issue)
  - dim_stock          (reference — remove dimension rows for defunct tickers)

Usage:
    ~/anaconda3/bin/python3 scripts/maintenance/delete_bad_tickers.py [--dry-run] [--vacuum]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root setup
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve()
_repo = _here.parent.parent.parent
sys.path.insert(0, str(_repo))

# ---------------------------------------------------------------------------
# Bad ticker list — 109 tickers with adjusted_close > 100,000
# ---------------------------------------------------------------------------
BAD_TICKERS = [
    "BINI", "NUWE", "ASTI", "UVXY", "DCTH", "GMGI", "TNXP", "ADTX", "GOVX",
    "JAGX", "SMX", "SINT", "INPX", "CLRB", "WHLR", "EJH", "BGMS", "BNBX",
    "NSPR", "PSHG", "CETX", "APVO", "HIND", "CHAI", "BDRX", "GNLN", "FRGT",
    "VLCN", "AREB", "TENX", "HSDT", "ORKA", "ALLR", "SQQQ", "VXX", "GWAV",
    "QCLS", "PHIO", "PALI", "SUNE", "RNAZ", "XXII", "CNSP", "DOMH", "AEMD",
    "WTO", "ENVB", "SLRX", "IMNN", "TRAW", "DVLT", "MTVA", "PSTV", "TGL",
    "QNRX", "VIXY", "VMAR", "ZNB", "BRK-A", "GCTK", "NXTT", "DBGI", "GRDX",
    "AIXC", "REVB", "ZTEST", "VCIG", "CELZ", "SNES", "GDHG", "GRI", "TWAV",
    "ACHV", "ACON", "VERB", "MNTS", "NTEST-G", "TANH", "KXIN", "TRNR", "NVVE",
    "AVX", "LGHL", "HURA", "IVF", "ONCO", "FCEL", "ZXZZT", "ZVZZT", "ZBZZT",
    "ZCZZT", "ZAZZT", "ZWZZT", "XTKG", "ERNA", "SXTC", "NDRA", "FFAI", "DGLY",
    "PRSO", "TPST", "GEVO", "NCNA", "AKAN", "CDT", "WKHS", "CYN", "QH", "HOLO",
]

SILVER_ROOT = Path("/shared/storage/silver")

TABLES = {
    "fact_stock_prices": SILVER_ROOT / "stocks" / "facts" / "fact_stock_prices",
    "fact_dividends":    SILVER_ROOT / "stocks" / "facts" / "fact_dividends",
    "fact_splits":       SILVER_ROOT / "stocks" / "facts" / "fact_splits",
    "dim_stock":         SILVER_ROOT / "stocks" / "dims" / "dim_stock",
}


def build_spark():
    from pyspark.sql import SparkSession
    return (
        SparkSession.builder
        .appName("delete_bad_tickers")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.jars.packages", "io.delta:delta-spark_2.13:4.0.0")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


def delete_from_table(spark, name: str, path: Path, ticker_col: str, tickers: list[str], dry_run: bool) -> int:
    from delta.tables import DeltaTable

    if not path.exists():
        print(f"  SKIP  {name}: path not found ({path})")
        return 0

    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    condition = f"`{ticker_col}` IN ({ticker_list})"

    dt = DeltaTable.forPath(spark, str(path))
    before = dt.toDF().filter(condition).count()

    if before == 0:
        print(f"  OK    {name}: 0 matching rows — nothing to delete")
        return 0

    if dry_run:
        print(f"  DRY   {name}: would delete {before:,} rows")
        return before

    print(f"  DEL   {name}: deleting {before:,} rows … ", end="", flush=True)
    dt.delete(condition)
    print("done")
    return before


def vacuum_table(spark, name: str, path: Path) -> None:
    from delta.tables import DeltaTable
    if not path.exists():
        return
    print(f"  VACUUM {name} … ", end="", flush=True)
    dt = DeltaTable.forPath(spark, str(path))
    dt.vacuum(168)   # 7-day retention
    print("done")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count rows but do not delete")
    parser.add_argument("--vacuum", action="store_true", help="Run VACUUM after deletion (removes old parquet files)")
    parser.add_argument("--skip-dim", action="store_true", help="Skip dim_stock deletion")
    args = parser.parse_args()

    print(f"{'DRY RUN — ' if args.dry_run else ''}Deleting {len(BAD_TICKERS)} bad tickers from Silver Delta tables")
    print()

    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    total_deleted = 0

    tables_to_clean = {k: v for k, v in TABLES.items() if not (args.skip_dim and k == "dim_stock")}

    # fact tables use 'ticker'; dim_stock also uses 'ticker'
    for name, path in tables_to_clean.items():
        n = delete_from_table(spark, name, path, "ticker", BAD_TICKERS, args.dry_run)
        total_deleted += n

    print()
    print(f"{'Would delete' if args.dry_run else 'Deleted'} {total_deleted:,} rows total across {len(tables_to_clean)} tables")

    if args.vacuum and not args.dry_run:
        print()
        print("Running VACUUM …")
        for name, path in tables_to_clean.items():
            vacuum_table(spark, name, path)

    spark.stop()
    print()
    print("Done. Restart the API server to clear the scan cache.")


if __name__ == "__main__":
    main()
