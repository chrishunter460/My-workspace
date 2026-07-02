#!/usr/bin/env python
"""
Diagnostic script to identify model loading issues.

Checks:
1. Model registry discovery
2. Domain loader configuration parsing
3. DuckDB view availability
4. Silver layer data presence
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def check_domain_files():
    """Check all domain markdown files for parsing issues."""
    print("\n" + "=" * 60)
    print("1. CHECKING DOMAIN FILES")
    print("=" * 60)

from de_funk.config.domain import get_domain_loader

    domains_dir = repo_root / "domains"
    loader = get_domain_loader(domains_dir)

    # List all discovered models
    models = loader.list_models()
    print(f"\nDiscovered {len(models)} domain models:")
    for model in sorted(models):
        print(f"  - {model}")

    # Check for missing templates
    missing_templates = set()
    for model in models:
        try:
            config = loader.load_model_config(model)

            # Check schema_template
            if 'schema_template' in config:
                template = config['schema_template']
                template_path = domains_dir / template
                if not template_path.with_suffix('.md').exists() and not template_path.exists():
                    missing_templates.add(template)

            # Report tables found
            tables = config.get('tables', {})
            if tables:
                print(f"\n  {model}: {len(tables)} tables")
                for table_name in tables.keys():
                    print(f"    - {table_name}")

        except Exception as e:
            print(f"\n  ERROR loading {model}: {e}")

    if missing_templates:
        print(f"\n  WARNING: Missing templates: {missing_templates}")
        print("  (This is non-fatal - models will load but may have incomplete schema)")


def check_model_registry():
    """Check the model registry."""
    print("\n" + "=" * 60)
    print("2. CHECKING MODEL REGISTRY")
    print("=" * 60)

from de_funk.models.registry import ModelRegistry

    domains_dir = repo_root / "domains"
    registry = ModelRegistry(domains_dir)

    models = registry.list_models()
    print(f"\nRegistry found {len(models)} models:")
    for model in sorted(models):
        print(f"  - {model}")

        # Check tables and measures
        try:
            model_config = registry.get_model(model)
            tables = model_config.list_tables()
            measures = model_config.list_measures()
            print(f"      Tables: {len(tables)}, Measures: {len(measures)}")
        except Exception as e:
            print(f"      ERROR: {e}")

    # Check model class registration
    print("\n  Registered model classes:")
    for name in registry._model_classes.keys():
        print(f"    - {name}")


def check_duckdb_views():
    """Check DuckDB views and Silver layer data."""
    print("\n" + "=" * 60)
    print("3. CHECKING DUCKDB VIEWS")
    print("=" * 60)

from de_funk.core.context import RepoContext

    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    conn = ctx.connection

    # Get all schemas
    schemas = conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    print(f"\nDuckDB schemas:")
    for (schema,) in schemas:
        if schema not in ['main', 'pg_catalog', 'information_schema']:
            print(f"  - {schema}")

    # Get views in each schema
    print("\nDuckDB views:")
    for (schema,) in schemas:
        if schema in ['main', 'pg_catalog', 'information_schema']:
            continue

        views = conn.execute(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_type = 'VIEW'
        """).fetchall()

        if views:
            for (view,) in views:
                # Check if view is valid
                try:
                    count = conn.execute(f'SELECT COUNT(*) FROM "{schema}"."{view}"').fetchone()[0]
                    print(f"  {schema}.{view}: {count:,} rows")
                except Exception as e:
                    print(f"  {schema}.{view}: ERROR - {e}")


def check_silver_data():
    """Check Silver layer data files."""
    print("\n" + "=" * 60)
    print("4. CHECKING SILVER LAYER DATA")
    print("=" * 60)

    from config import ConfigLoader

    loader = ConfigLoader()
    config = loader.load()

    silver_root = Path(config.storage.get('silver', '/shared/storage/silver'))
    print(f"\nSilver root: {silver_root}")

    if not silver_root.exists():
        print("  ERROR: Silver directory does not exist!")
        return

    # List model directories
    for model_dir in sorted(silver_root.iterdir()):
        if model_dir.is_dir():
            print(f"\n  {model_dir.name}/")

            # Check for Delta tables
            for table_dir in sorted(model_dir.iterdir()):
                if table_dir.is_dir():
                    is_delta = (table_dir / "_delta_log").exists()
                    parquet_files = list(table_dir.glob("*.parquet"))

                    if is_delta:
                        print(f"    {table_dir.name}/ (Delta table)")
                    elif parquet_files:
                        print(f"    {table_dir.name}/ ({len(parquet_files)} parquet files)")
                    else:
                        print(f"    {table_dir.name}/ (empty or unknown format)")


def check_universal_session():
    """Check UniversalSession can access data via get_table."""
    print("\n" + "=" * 60)
    print("5. CHECKING UNIVERSAL SESSION")
    print("=" * 60)

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

    ctx = RepoContext.from_repo_root(connection_type="duckdb")

    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Test get_table on various models
    print("\nTesting get_table (correct API)...")

    test_tables = [
        ("stocks", "dim_stock"),
        ("stocks", "fact_stock_prices"),
        ("company", "dim_company"),
        ("temporal", "dim_calendar"),
    ]

    for model_name, table_name in test_tables:
        try:
            df = session.get_table(model_name, table_name)
            # Get row count based on DataFrame type
            if hasattr(df, 'count'):
                # DuckDB relation
                count = df.count('*').fetchone()[0]
            elif hasattr(df, 'shape'):
                # pandas DataFrame
                count = len(df)
            else:
                count = "?"
            print(f"  ✅ {model_name}.{table_name}: {count:,} rows")
        except Exception as e:
            print(f"  ❌ {model_name}.{table_name}: ERROR - {e}")

    # Also test direct connection query (for raw SQL)
    print("\nTesting direct connection query...")
    try:
        result = ctx.connection.conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()
        print(f"  ✅ Direct SQL query works: {result[0]:,} rows in stocks.dim_stock")
    except Exception as e:
        print(f"  ❌ Direct SQL query failed: {e}")


def main():
    """Run all diagnostics."""
    setup_logging()

    print("=" * 60)
    print("MODEL LOADING DIAGNOSTIC")
    print(f"Repository: {repo_root}")
    print("=" * 60)

    check_domain_files()
    check_model_registry()
    check_duckdb_views()
    check_silver_data()
    check_universal_session()

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
