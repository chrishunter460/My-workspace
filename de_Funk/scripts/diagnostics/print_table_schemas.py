#!/usr/bin/env python3
"""
Print Table Schemas - Display columns for all tables in Bronze and Silver layers.

Usage:
    python -m scripts.diagnostics.print_table_schemas
    python -m scripts.diagnostics.print_table_schemas --storage-path /shared/storage
    python -m scripts.diagnostics.print_table_schemas --layer bronze
    python -m scripts.diagnostics.print_table_schemas --table securities_prices_daily
    python -m scripts.diagnostics.print_table_schemas --format csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def get_table_schema_spark(spark, table_path: Path) -> List[Tuple[str, str]]:
    """Get schema using Spark (handles both parquet and delta)."""
    try:
        # Try delta first
        if (table_path / "_delta_log").exists():
            df = spark.read.format("delta").load(str(table_path))
        else:
            df = spark.read.parquet(str(table_path))

        return [(field.name, str(field.dataType)) for field in df.schema.fields]
    except Exception as e:
        return [("ERROR", str(e))]


def get_table_schema_pyarrow(table_path: Path) -> List[Tuple[str, str]]:
    """Get schema using PyArrow (faster, no Spark needed)."""
    import pyarrow.parquet as pq

    try:
        # Find a parquet file
        parquet_files = list(table_path.glob("*.parquet"))
        if not parquet_files:
            parquet_files = list(table_path.glob("**/*.parquet"))

        if not parquet_files:
            return [("NO_FILES", "No parquet files found")]

        # Read schema from first file
        schema = pq.read_schema(parquet_files[0])
        return [(field.name, str(field.type)) for field in schema]
    except Exception as e:
        return [("ERROR", str(e))]


def discover_tables(storage_path: Path, layer: str) -> Dict[str, Path]:
    """Discover all tables in a layer."""
    layer_path = storage_path / layer
    tables = {}

    if not layer_path.exists():
        return tables

    # Bronze: storage/bronze/{table}/
    # Silver: storage/silver/{model}/{dims|facts}/{table}/

    if layer == "bronze":
        for item in layer_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it contains parquet files or _delta_log
                if list(item.glob("*.parquet")) or (item / "_delta_log").exists():
                    tables[item.name] = item
    else:  # silver
        for model_dir in layer_path.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                # Check dims/
                dims_dir = model_dir / "dims"
                if dims_dir.exists():
                    for dim in dims_dir.iterdir():
                        if dim.is_dir():
                            tables[f"{model_dir.name}.{dim.name}"] = dim

                # Check facts/
                facts_dir = model_dir / "facts"
                if facts_dir.exists():
                    for fact in facts_dir.iterdir():
                        if fact.is_dir():
                            tables[f"{model_dir.name}.{fact.name}"] = fact

                # Check root level tables (for models that don't use dims/facts structure)
                for item in model_dir.iterdir():
                    if item.is_dir() and item.name not in ('dims', 'facts') and not item.name.startswith('.'):
                        if list(item.glob("*.parquet")) or (item / "_delta_log").exists():
                            tables[f"{model_dir.name}.{item.name}"] = item

    return tables


def print_schemas(
    storage_path: Path,
    layer: Optional[str] = None,
    table_filter: Optional[str] = None,
    use_spark: bool = False,
    output_format: str = "table"
):
    """Print schemas for all discovered tables."""

    layers = [layer] if layer else ["bronze", "silver"]

    # Initialize Spark if needed
    spark = None
    if use_spark:
from de_funk.orchestration.common.spark_session import get_spark
        spark = get_spark("SchemaPrinter", config={"spark.driver.memory": "2g"})

    all_results = []

    for lyr in layers:
        tables = discover_tables(storage_path, lyr)

        if not tables:
            print(f"\n⚠ No tables found in {lyr} layer at {storage_path / lyr}")
            continue

        # Filter tables if specified
        if table_filter:
            tables = {k: v for k, v in tables.items() if table_filter.lower() in k.lower()}

        if not tables:
            print(f"\n⚠ No tables matching '{table_filter}' in {lyr} layer")
            continue

        print(f"\n{'='*70}")
        print(f"  {lyr.upper()} LAYER ({len(tables)} tables)")
        print(f"{'='*70}")

        for table_name, table_path in sorted(tables.items()):
            # Get schema
            if spark:
                columns = get_table_schema_spark(spark, table_path)
            else:
                columns = get_table_schema_pyarrow(table_path)

            # Get row count estimate
            try:
                import pyarrow.parquet as pq
                parquet_files = list(table_path.glob("*.parquet")) or list(table_path.glob("**/*.parquet"))
                row_count = sum(pq.read_metadata(str(f)).num_rows for f in parquet_files[:10])  # Sample first 10 files
                if len(parquet_files) > 10:
                    row_count = f"~{row_count * len(parquet_files) // 10:,}+"
                else:
                    row_count = f"{row_count:,}"
            except:
                row_count = "?"

            if output_format == "csv":
                for col_name, col_type in columns:
                    all_results.append(f"{lyr},{table_name},{col_name},{col_type}")
            else:
                print(f"\n┌─ {table_name} ({row_count} rows)")
                print(f"│  Path: {table_path}")
                print(f"│")

                # Print columns
                max_name_len = max(len(c[0]) for c in columns) if columns else 10
                for col_name, col_type in columns:
                    print(f"│  {col_name:<{max_name_len}}  {col_type}")

                print(f"└─ ({len(columns)} columns)")

    if output_format == "csv":
        print("\nlayer,table,column,type")
        for row in all_results:
            print(row)

    if spark:
        spark.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Print table schemas for Bronze and Silver layers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Print all schemas
    python -m scripts.diagnostics.print_table_schemas

    # Print only bronze layer
    python -m scripts.diagnostics.print_table_schemas --layer bronze

    # Filter to specific table
    python -m scripts.diagnostics.print_table_schemas --table prices

    # Use Spark for reading (slower but handles complex schemas)
    python -m scripts.diagnostics.print_table_schemas --use-spark

    # Output as CSV
    python -m scripts.diagnostics.print_table_schemas --format csv > schemas.csv
        """
    )

    parser.add_argument(
        "--storage-path",
        type=str,
        default="/shared/storage",
        help="Storage root path (default: /shared/storage)"
    )
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver"],
        help="Only show tables from this layer"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="Filter to tables containing this string"
    )
    parser.add_argument(
        "--use-spark",
        action="store_true",
        help="Use Spark to read schemas (slower but more accurate for complex types)"
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv"],
        default="table",
        help="Output format (default: table)"
    )

    args = parser.parse_args()

    storage_path = Path(args.storage_path)
    if not storage_path.exists():
        # Try repo-local storage
        storage_path = project_root / "storage"
        if not storage_path.exists():
            print(f"Error: Storage path not found: {args.storage_path}")
            sys.exit(1)

    print(f"Storage path: {storage_path}")

    print_schemas(
        storage_path=storage_path,
        layer=args.layer,
        table_filter=args.table,
        use_spark=args.use_spark,
        output_format=args.format
    )


if __name__ == "__main__":
    main()
