#!/usr/bin/env python3
"""
Explore DuckDB Tables - Print top 10 rows from each table

This script connects to the DuckDB analytics database and displays
the top 10 rows from each available view/table.

Usage:
    python -m scripts.test.explore_tables
    python -m scripts.test.explore_tables --limit 5
    python -m scripts.test.explore_tables --schema stocks
"""

import argparse
import sys
from pathlib import Path

# Add repo root to path
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

try:
    import duckdb
    import pandas as pd
except ImportError as e:
    print(f"❌ ERROR: Missing dependency: {e}")
    print("Install with: pip install duckdb pandas")
    sys.exit(1)


def explore_tables(db_path: Path, limit: int = 10, schema_filter: str = None):
    """
    Explore all tables in DuckDB database.

    Args:
        db_path: Path to DuckDB database file
        limit: Number of rows to show per table
        schema_filter: Optional schema name to filter (e.g., 'stocks', 'company')
    """
    print(f"{'='*80}")
    print(f"DUCKDB TABLE EXPLORER")
    print(f"{'='*80}")
    print(f"Database: {db_path}")
    print(f"Rows per table: {limit}")
    if schema_filter:
        print(f"Schema filter: {schema_filter}")
    print()

    # Connect to database
    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        print(f"✓ Connected successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)

    # Get list of all views/tables
    query = """
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name
    """

    try:
        tables_df = conn.execute(query).fetchdf()
    except Exception as e:
        print(f"❌ Failed to get table list: {e}")
        conn.close()
        sys.exit(1)

    if len(tables_df) == 0:
        print("⚠ No tables found in database")
        print("Run setup script first: python -m scripts.setup.setup_duckdb_views")
        conn.close()
        sys.exit(0)

    # Filter by schema if requested
    if schema_filter:
        tables_df = tables_df[tables_df['table_schema'] == schema_filter]
        if len(tables_df) == 0:
            print(f"⚠ No tables found in schema: {schema_filter}")
            conn.close()
            sys.exit(0)

    print(f"Found {len(tables_df)} table(s)")
    print()

    # Explore each table
    for idx, row in tables_df.iterrows():
        schema = row['table_schema']
        table = row['table_name']
        table_type = row['table_type']
        full_name = f"{schema}.{table}"

        print(f"{'='*80}")
        print(f"TABLE: {full_name} ({table_type})")
        print(f"{'='*80}")

        try:
            # Get row count
            count_query = f"SELECT COUNT(*) as count FROM {full_name}"
            count = conn.execute(count_query).fetchone()[0]
            print(f"Total rows: {count:,}")
            print()

            # Get column info
            columns_query = f"""
                SELECT
                    column_name,
                    data_type
                FROM information_schema.columns
                WHERE table_schema = '{schema}'
                  AND table_name = '{table}'
                ORDER BY ordinal_position
            """
            columns_df = conn.execute(columns_query).fetchdf()
            print(f"Columns ({len(columns_df)}):")
            for _, col_row in columns_df.iterrows():
                print(f"  - {col_row['column_name']}: {col_row['data_type']}")
            print()

            # Get sample data
            sample_query = f"SELECT * FROM {full_name} LIMIT {limit}"
            sample_df = conn.execute(sample_query).fetchdf()

            if len(sample_df) == 0:
                print("⚠ Table is empty")
            else:
                print(f"Sample data (first {min(limit, len(sample_df))} rows):")
                print()

                # Set pandas display options for better formatting
                pd.set_option('display.max_columns', None)
                pd.set_option('display.width', None)
                pd.set_option('display.max_colwidth', 50)

                print(sample_df.to_string(index=False))

            print()

        except Exception as e:
            print(f"❌ Error exploring table: {e}")
            print()

    # Summary
    print(f"{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total tables explored: {len(tables_df)}")
    print()

    # Group by schema
    schema_counts = tables_df.groupby('table_schema').size()
    print("Tables by schema:")
    for schema, count in schema_counts.items():
        print(f"  {schema}: {count} table(s)")

    conn.close()
    print()
    print("✓ Exploration complete")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Explore DuckDB tables - show top N rows from each table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of rows to show per table (default: 10)'
    )

    parser.add_argument(
        '--schema',
        type=str,
        help='Filter to specific schema (e.g., stocks, company, core)'
    )

    parser.add_argument(
        '--db-path',
        type=str,
        help='Path to DuckDB database (default: storage/duckdb/analytics.db)'
    )

    args = parser.parse_args()

    # Determine database path
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        # Default path relative to repo root
        db_path = repo_root / "storage" / "duckdb" / "analytics.db"

    if not db_path.exists():
        print(f"❌ ERROR: Database not found: {db_path}")
        print()
        print("Create database first:")
        print("  python -m scripts.setup.setup_duckdb_views")
        sys.exit(1)

    explore_tables(db_path, limit=args.limit, schema_filter=args.schema)


if __name__ == "__main__":
    main()
