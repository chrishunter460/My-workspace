"""
Seed Synthetic Bronze - Generate minimal synthetic Bronze data for v4 model testing.

Scans all v4 source configs to discover Bronze table references,
generates synthetic rows with the columns referenced by aliases,
and writes them as Parquet files (or DuckDB tables) for testing.

Usage:
    python -m scripts.seed.seed_synthetic_bronze --storage-root storage/
    python -m scripts.seed.seed_synthetic_bronze --format duckdb --db-path :memory:
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

# Bootstrap
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

logger = logging.getLogger(__name__)


def extract_source_columns(expression: str) -> Set[str]:
    """
    Extract raw column names referenced in a SQL expression.

    Uses simple heuristics:
    - Identifiers that look like column names (lowercase, underscores)
    - Excludes SQL keywords and string literals
    """
    # Remove string literals
    expr = re.sub(r"'[^']*'", "", expression)

    # Remove function calls (but keep their arguments)
    # Find all identifiers (word chars not starting with digit)
    identifiers = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", expr)

    # Exclude SQL keywords and functions
    sql_keywords = {
        "AS", "CAST", "CONCAT", "HASH", "ABS", "INT", "STRING", "DOUBLE",
        "FLOAT", "BOOLEAN", "DATE", "TIMESTAMP", "REGEXP_REPLACE",
        "REGEXP_EXTRACT", "LPAD", "REPLACE", "CASE", "WHEN", "THEN",
        "ELSE", "END", "AND", "OR", "NOT", "IS", "NULL", "LIKE", "IN",
        "BETWEEN", "TRUE", "FALSE", "DATE_FORMAT", "ADD_MONTHS",
        "COALESCE", "IFNULL", "NULLIF", "LENGTH", "TRIM", "UPPER",
        "LOWER", "SUBSTR", "SUBSTRING", "LEFT", "RIGHT",
    }

    columns = set()
    for ident in identifiers:
        if ident.upper() not in sql_keywords:
            columns.add(ident)

    return columns


def collect_bronze_tables(
    domains_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """
    Scan all v4 source configs and collect Bronze table references.

    Returns:
        Dict of bronze_path → {columns: set, sources: list}
    """
    from de_funk.config.domain import DomainConfigLoaderV4

    loader = DomainConfigLoaderV4(domains_dir)
    bronze_tables: Dict[str, Dict[str, Any]] = {}

    for model_name in loader.list_models():
        config = loader.load_model_config(model_name)
        for source_name, source_cfg in config.get("sources", {}).items():
            from_spec = source_cfg.get("from", "")
            if not from_spec.startswith("bronze."):
                continue

            if from_spec not in bronze_tables:
                bronze_tables[from_spec] = {
                    "columns": set(),
                    "sources": [],
                }

            # Extract column names from aliases
            aliases = source_cfg.get("aliases", [])
            for alias in aliases:
                if isinstance(alias, list) and len(alias) >= 2:
                    expression = str(alias[1])
                    cols = extract_source_columns(expression)
                    bronze_tables[from_spec]["columns"].update(cols)

            bronze_tables[from_spec]["sources"].append(
                f"{model_name}.{source_name}"
            )

    return bronze_tables


def generate_synthetic_rows(
    columns: Set[str],
    num_rows: int = 10,
) -> List[Dict[str, Any]]:
    """
    Generate synthetic data rows for given columns.

    Uses simple heuristics based on column names to generate
    plausible values.
    """
    import random
    import string
    from datetime import datetime, timedelta

    rows = []
    base_date = datetime(2024, 1, 1)

    for i in range(num_rows):
        row = {}
        for col in sorted(columns):
            col_lower = col.lower()

            # Date columns
            if "date" in col_lower or col_lower.endswith("_dt"):
                dt = base_date + timedelta(days=i * 30)
                row[col] = dt.strftime("%Y-%m-%d")

            # ID columns
            elif col_lower.endswith("_id") or col_lower == "id":
                row[col] = str(1000 + i)

            # Ticker / symbol columns
            elif col_lower in ("ticker", "symbol"):
                tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META",
                          "TSLA", "NVDA", "JPM", "V", "WMT"]
                row[col] = tickers[i % len(tickers)]

            # Numeric columns
            elif any(k in col_lower for k in [
                "amount", "price", "value", "revenue", "profit",
                "cost", "income", "expense", "volume", "cap",
                "outstanding", "eps", "dividend", "rate",
                "open", "high", "low", "close",
            ]):
                row[col] = round(random.uniform(10.0, 1000.0), 2)

            # Boolean columns
            elif col_lower.startswith("is_") or col_lower.startswith("has_"):
                row[col] = random.choice([True, False])

            # Type / category columns
            elif "type" in col_lower or "category" in col_lower or "class" in col_lower:
                row[col] = f"type_{i % 3}"

            # CIK
            elif col_lower == "cik":
                row[col] = str(1000000 + i).zfill(10)

            # Name columns
            elif "name" in col_lower:
                row[col] = f"Name_{i}"

            # Code columns
            elif "code" in col_lower:
                row[col] = f"CODE_{i:03d}"

            # Default: string
            else:
                row[col] = f"{col}_{i}"

        rows.append(row)

    return rows


def seed_as_parquet(
    bronze_tables: Dict[str, Dict[str, Any]],
    storage_root: Path,
    num_rows: int = 10,
) -> Dict[str, int]:
    """Write synthetic Bronze data as Parquet files."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    results = {}
    bronze_root = storage_root / "bronze"

    for bronze_path, info in sorted(bronze_tables.items()):
        # bronze.provider.table → bronze/provider/table/
        parts = bronze_path.split(".")
        if len(parts) < 2:
            continue

        # Handle both "bronze.provider_table" and "bronze.provider.table"
        rel_path = "/".join(parts[1:])
        table_dir = bronze_root / rel_path
        table_dir.mkdir(parents=True, exist_ok=True)

        columns = info["columns"]
        if not columns:
            continue

        rows = generate_synthetic_rows(columns, num_rows)

        # Write as Parquet
        table = pa.Table.from_pylist(rows)
        output_file = table_dir / "part-0000.parquet"
        pq.write_table(table, str(output_file))

        results[bronze_path] = len(rows)
        logger.info(f"Seeded {bronze_path}: {len(rows)} rows, {len(columns)} columns")

    return results


def seed_as_duckdb(
    bronze_tables: Dict[str, Dict[str, Any]],
    db_path: str = ":memory:",
    num_rows: int = 10,
) -> Any:
    """Write synthetic Bronze data as DuckDB tables. Returns the connection."""
    import duckdb

    conn = duckdb.connect(db_path)

    for bronze_path, info in sorted(bronze_tables.items()):
        columns = info["columns"]
        if not columns:
            continue

        rows = generate_synthetic_rows(columns, num_rows)

        # Create table name from bronze path
        table_name = bronze_path.replace(".", "_")

        # Create table from rows
        import pandas as pd
        df = pd.DataFrame(rows)
        conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")

        logger.info(
            f"Seeded {table_name}: {len(rows)} rows, {len(columns)} columns"
        )

    return conn


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Generate synthetic Bronze data for v4 model testing"
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path("storage"),
        help="Storage root directory (default: storage/)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "duckdb"],
        default="parquet",
        help="Output format (default: parquet)",
    )
    parser.add_argument(
        "--db-path",
        default=":memory:",
        help="DuckDB database path (default: :memory:)",
    )
    parser.add_argument(
        "--num-rows",
        type=int,
        default=10,
        help="Number of rows per table (default: 10)",
    )
    parser.add_argument(
        "--domains-dir",
        type=Path,
        default=None,
        help="Path to domains/ directory (default: auto-detect)",
    )
    args = parser.parse_args()

    # Find domains directory
    domains_dir = args.domains_dir
    if domains_dir is None:
        domains_dir = project_root / "domains"

    if not domains_dir.exists():
        logger.error(f"Domains directory not found: {domains_dir}")
        sys.exit(1)

    # Collect Bronze table references
    logger.info("Scanning v4 domain configs for Bronze table references...")
    bronze_tables = collect_bronze_tables(domains_dir)
    logger.info(f"Found {len(bronze_tables)} unique Bronze tables")

    # Generate and write synthetic data
    if args.format == "parquet":
        results = seed_as_parquet(bronze_tables, args.storage_root, args.num_rows)
        logger.info(
            f"Seeded {len(results)} Parquet tables to {args.storage_root / 'bronze'}"
        )
    else:
        conn = seed_as_duckdb(bronze_tables, args.db_path, args.num_rows)
        tables = conn.execute("SHOW TABLES").fetchall()
        logger.info(f"Seeded {len(tables)} DuckDB tables")
        conn.close()

    logger.info("Done!")


if __name__ == "__main__":
    main()
