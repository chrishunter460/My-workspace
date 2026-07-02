#!/usr/bin/env python3
"""
Diagnostic script for Stock Price Analysis tab.

Purpose:
    Traces through the entire data flow from Silver storage to UI queries
    to identify where data is being lost.

Usage:
    python -m scripts.test.diagnose_stocks_tab
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup repo imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb
import json
from typing import Dict, Any, List, Optional


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_subheader(title: str):
    print(f"\n--- {title} ---\n")


def check_storage_paths():
    """Check storage.json configuration and actual paths."""
    print_header("STEP 1: Storage Configuration")

    repo_root = Path(__file__).resolve().parents[2]
    storage_json = repo_root / "configs" / "storage.json"

    print(f"Repo root: {repo_root}")
    print(f"Storage config: {storage_json}")

    if storage_json.exists():
        with open(storage_json) as f:
            storage_config = json.load(f)
        print(f"\nStorage config contents:")
        print(json.dumps(storage_config, indent=2)[:2000])
    else:
        print("WARNING: storage.json not found!")
        storage_config = {}

    # Check actual paths
    print_subheader("Checking actual storage paths")

    paths_to_check = [
        ("storage/silver", "Default silver path"),
        ("storage/silver/stocks", "Legacy stocks path"),
        ("storage/silver/securities/stocks", "v2.0 stocks path"),
        ("/shared/storage/silver/securities/stocks", "Cluster stocks path"),
    ]

    for path, desc in paths_to_check:
        full_path = repo_root / path if not path.startswith('/') else Path(path)
        exists = full_path.exists()
        print(f"  {desc}: {full_path}")
        print(f"    Exists: {exists}")
        if exists:
            items = list(full_path.iterdir()) if full_path.is_dir() else []
            print(f"    Contents: {[i.name for i in items[:10]]}")

    return storage_config


def check_model_registry():
    """Check model registry loading."""
    print_header("STEP 2: Model Registry")

    try:
from de_funk.models.registry import ModelRegistry
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        domains_dir = repo_root / "domains"

        print(f"Domains directory: {domains_dir}")
        print(f"Exists: {domains_dir.exists()}")

        registry = ModelRegistry(domains_dir)

        print(f"\nAvailable models: {registry.list_models()}")

        # Check stocks model
        if registry.has_model('stocks'):
            stocks_config = registry.get_model('stocks')
            print(f"\nStocks model loaded: YES")
            print(f"  Tables: {stocks_config.list_tables()}")
            print(f"  Dimensions: {stocks_config.list_dimensions()}")
            print(f"  Facts: {stocks_config.list_facts()}")
            print(f"  Storage root: {stocks_config.storage_root}")

            # Get graph edges
            edges = stocks_config.get_edges()
            print(f"\n  Graph edges:")
            for edge in edges if isinstance(edges, list) else edges.values():
                print(f"    {edge.get('from')} -> {edge.get('to')} ON {edge.get('on')}")

            return stocks_config
        else:
            print("WARNING: stocks model not found in registry!")
            return None

    except Exception as e:
        print(f"ERROR loading registry: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_domain_loader():
    """Check domain loader directly."""
    print_header("STEP 3: Domain Loader Config")

    try:
from de_funk.config.domain import get_domain_loader
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        domains_dir = repo_root / "domains"

        loader = get_domain_loader(domains_dir)

        print(f"Models found: {loader.list_models()}")

        # Load stocks config
        config = loader.load_model_config('stocks')

        print(f"\nStocks config keys: {list(config.keys())}")
        print(f"\nStorage config:")
        print(json.dumps(config.get('storage', {}), indent=2))

        print(f"\nGraph config:")
        graph = config.get('graph', {})
        print(f"  Nodes: {list(graph.get('nodes', {}).keys())}")
        print(f"  Edges: {list(graph.get('edges', {}).keys())}")

        # Print edge details
        for edge_name, edge in graph.get('edges', {}).items():
            print(f"    {edge_name}: {edge.get('from')} -> {edge.get('to')}")

        return config

    except Exception as e:
        print(f"ERROR loading domain config: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_silver_data():
    """Search for actual silver layer data."""
    print_header("STEP 4: Finding Silver Data")

    repo_root = Path(__file__).resolve().parents[2]

    # Search patterns
    search_roots = [
        repo_root / "storage",
        Path("/shared/storage"),
    ]

    found_tables = []

    for search_root in search_roots:
        if not search_root.exists():
            print(f"  {search_root}: NOT FOUND")
            continue

        print(f"\nSearching in: {search_root}")

        # Find parquet/delta files
        parquet_files = list(search_root.rglob("*.parquet"))[:20]
        delta_logs = list(search_root.rglob("_delta_log"))[:20]

        print(f"  Parquet files found: {len(parquet_files)}")
        for pf in parquet_files[:5]:
            print(f"    - {pf.relative_to(search_root)}")

        print(f"  Delta tables found: {len(delta_logs)}")
        for dl in delta_logs[:5]:
            parent = dl.parent
            print(f"    - {parent.relative_to(search_root)}")
            found_tables.append(parent)

    return found_tables


def query_silver_directly(found_tables: List[Path]):
    """Query silver tables directly with DuckDB."""
    print_header("STEP 5: Direct DuckDB Queries")

    conn = duckdb.connect()

    # Try to install delta extension
    try:
        conn.execute("INSTALL delta")
        conn.execute("LOAD delta")
        print("Delta extension loaded")
    except Exception as e:
        print(f"Delta extension not available: {e}")

    for table_path in found_tables[:5]:
        print_subheader(f"Table: {table_path.name}")

        # Try delta first
        try:
            query = f"SELECT * FROM delta_scan('{table_path}') LIMIT 5"
            df = conn.execute(query).fetchdf()
            count = conn.execute(f"SELECT COUNT(*) FROM delta_scan('{table_path}')").fetchone()[0]

            print(f"Format: Delta")
            print(f"Row count: {count}")
            print(f"Columns: {list(df.columns)}")
            print(f"\nSample data:")
            print(df.to_string(max_colwidth=30))
            continue
        except Exception as e:
            print(f"Delta read failed: {e}")

        # Try parquet
        try:
            parquet_pattern = f"{table_path}/**/*.parquet"
            query = f"SELECT * FROM read_parquet('{parquet_pattern}') LIMIT 5"
            df = conn.execute(query).fetchdf()
            count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_pattern}')").fetchone()[0]

            print(f"Format: Parquet")
            print(f"Row count: {count}")
            print(f"Columns: {list(df.columns)}")
            print(f"\nSample data:")
            print(df.to_string(max_colwidth=30))
        except Exception as e:
            print(f"Parquet read failed: {e}")


def check_universal_session():
    """Test UniversalSession data access."""
    print_header("STEP 6: UniversalSession Query Test")

    try:
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession

        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )

        print(f"Session created with backend: duckdb")
        print(f"Available models: {session.list_models()}")

        # Try to query stocks
        print_subheader("Query: stocks.dim_stock")
        try:
            result = session.query(
                model="stocks",
                table="dim_stock",
                columns=["ticker", "security_name", "exchange_code"],
                limit=10
            )
            print(f"Result type: {type(result)}")
            if hasattr(result, 'shape'):
                print(f"Shape: {result.shape}")
            print(f"Data:\n{result}")
        except Exception as e:
            print(f"Query failed: {e}")
            import traceback
            traceback.print_exc()

        print_subheader("Query: stocks.fact_stock_prices")
        try:
            result = session.query(
                model="stocks",
                table="fact_stock_prices",
                columns=["security_id", "date_id", "close", "volume"],
                limit=10
            )
            print(f"Result type: {type(result)}")
            if hasattr(result, 'shape'):
                print(f"Shape: {result.shape}")
            print(f"Data:\n{result}")
        except Exception as e:
            print(f"Query failed: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"ERROR creating session: {e}")
        import traceback
        traceback.print_exc()


def check_auto_join():
    """Test auto-join functionality."""
    print_header("STEP 7: Auto-Join Test")

    try:
from de_funk.core.context import RepoContext
from de_funk.models.api.auto_join import AutoJoinHandler
from de_funk.models.registry import ModelRegistry
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        registry = ModelRegistry(repo_root / "domains")

        auto_join = AutoJoinHandler(registry, ctx.connection)

        # Test column index
        print_subheader("Column Index for stocks")
        try:
            col_index = auto_join.build_column_index("stocks")
            print(f"Column -> Tables mapping:")
            for col, tables in list(col_index.items())[:15]:
                print(f"  {col}: {tables}")
        except Exception as e:
            print(f"Column index failed: {e}")
            import traceback
            traceback.print_exc()

        # Test join planning
        print_subheader("Join Plan: fact_stock_prices + ticker, date, close")
        try:
            plan = auto_join.plan_auto_joins(
                model_name="securities.stocks",
                base_table="fact_stock_prices",
                requested_columns=["ticker", "date", "close", "volume"]
            )
            print(f"Table sequence: {plan.get('table_sequence')}")
            print(f"Joins: {plan.get('joins')}")
        except Exception as e:
            print(f"Join planning failed: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"ERROR in auto-join test: {e}")
        import traceback
        traceback.print_exc()


def check_exhibit_handler():
    """Test exhibit data fetching."""
    print_header("STEP 8: Exhibit Handler Test")

    try:
from de_funk.core.context import RepoContext
        from de_funk.notebook.exhibits.registry import ExhibitTypeRegistry

        ctx = RepoContext.from_repo_root(connection_type="duckdb")

        # Create exhibit config similar to notebook
        exhibit_config = {
            "type": "data_table",
            "source": "stocks.dim_stock",
            "columns": ["ticker", "security_name", "exchange_code"],
        }

        print(f"Exhibit config: {exhibit_config}")

        # Try to get the exhibit type registry
        registry = ExhibitTypeRegistry()
        print(f"Registered exhibit types: {list(registry._types.keys())}")

        # Note: Exhibit rendering happens in the Streamlit context
        # This test just verifies the registry is working

    except Exception as e:
        print(f"ERROR in exhibit test: {e}")
        import traceback
        traceback.print_exc()


def check_duckdb_views():
    """Check DuckDB views and schemas."""
    print_header("STEP 9: DuckDB Views/Schemas")

    try:
from de_funk.core.context import RepoContext

        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        conn = ctx.connection.conn

        # List schemas
        schemas = conn.execute("SELECT schema_name FROM information_schema.schemata").fetchdf()
        print(f"Schemas:\n{schemas}")

        # List tables/views in stocks schema
        print_subheader("Tables in 'stocks' schema")
        try:
            tables = conn.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'stocks'
            """).fetchdf()
            print(tables)
        except Exception as e:
            print(f"Query failed: {e}")

        # Try direct query
        print_subheader("Direct query: stocks.dim_stock")
        try:
            result = conn.execute("SELECT * FROM stocks.dim_stock LIMIT 5").fetchdf()
            print(f"Columns: {list(result.columns)}")
            print(result)
        except Exception as e:
            print(f"Query failed: {e}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("\n" + "="*60)
    print("  STOCKS TAB DIAGNOSTIC REPORT")
    print("="*60)

    # Run all checks
    storage_config = check_storage_paths()
    stocks_config = check_model_registry()
    domain_config = check_domain_loader()
    found_tables = find_silver_data()

    if found_tables:
        query_silver_directly(found_tables)

    check_duckdb_views()
    check_universal_session()
    check_auto_join()
    check_exhibit_handler()

    print_header("DIAGNOSIS COMPLETE")
    print("Review the output above to identify where data flow breaks.")
    print("\nCommon issues:")
    print("  1. Storage path mismatch - config vs actual data location")
    print("  2. Schema not registered in DuckDB")
    print("  3. Table not found at expected path")
    print("  4. Column mismatch between config and actual data")
    print("  5. Cross-model joins not resolving correctly")


if __name__ == "__main__":
    main()
