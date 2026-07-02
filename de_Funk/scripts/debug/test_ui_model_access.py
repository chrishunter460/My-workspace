#!/usr/bin/env python
"""
Quick test to verify UI can access models via the same code path.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from de_funk.config.logging import setup_logging, get_logger
setup_logging()

logger = get_logger(__name__)


def test_ui_model_access():
    """Test the same code path the UI uses to access models."""
    print("=" * 60)
    print("TESTING UI MODEL ACCESS")
    print("=" * 60)

    # 1. Load RepoContext (same as UI)
    print("\n1. Creating RepoContext...")
from de_funk.core.context import RepoContext
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    print(f"   Repo root: {ctx.repo}")
    print(f"   Connection type: {type(ctx.connection).__name__}")

    # 2. Load ModelRegistry (same as UI)
    print("\n2. Creating ModelRegistry...")
from de_funk.models.registry import ModelRegistry
    registry = ModelRegistry(ctx.repo / "domains")
    models = registry.list_models()
    print(f"   Found {len(models)} models: {sorted(models)}")

    # 3. Create UniversalSession (same as UI)
    print("\n3. Creating UniversalSession...")
from de_funk.models.api.session import UniversalSession
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    print(f"   Session created with connection: {type(session.connection).__name__}")

    # 4. Test get_table method (correct API for UniversalSession)
    print("\n4. Testing get_table method...")

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
            print(f"   ✅ {model_name}.{table_name}: {count:,} rows")
        except Exception as e:
            print(f"   ❌ {model_name}.{table_name}: ERROR - {e}")

    # 5. Test direct SQL via connection (for raw queries)
    print("\n5. Testing direct SQL via connection...")
    try:
        result = ctx.connection.conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()
        print(f"   ✅ Direct SQL works: {result[0]:,} rows")
    except Exception as e:
        print(f"   ❌ Direct SQL failed: {e}")

    # 6. Test notebook manager
    print("\n6. Testing NotebookManager...")
    from de_funk.notebook.managers import NotebookManager

    notebooks_root = ctx.repo / "configs" / "notebooks"
    nm = NotebookManager(session, ctx.repo, notebooks_root)

    # List available notebooks
    try:
        notebooks = list(notebooks_root.glob("**/*.md"))
        print(f"   Found {len(notebooks)} notebook files")

        # Try to load one
        if notebooks:
            sample = notebooks[0]
            print(f"   Trying to load: {sample.name}")
            config = nm.load_notebook(str(sample))
            print(f"   ✅ Loaded notebook: {config.notebook.title}")
    except Exception as e:
        print(f"   ❌ NotebookManager error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_ui_model_access()
