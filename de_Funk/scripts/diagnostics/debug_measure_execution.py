#!/usr/bin/env python3
"""
Debug Measure Execution Flow

This script traces through the entire flow of executing a base inherited measure
to understand where table name resolution happens and how filters are applied.

Usage:
    python -m scripts.test.debug_measure_execution
"""

import sys
import logging
from pathlib import Path

# Setup imports
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_inherited_measure():
    """Test a base inherited measure to see how it resolves tables."""

    print("=" * 80)
    print("DEBUG: Inherited Measure Execution Flow")
    print("=" * 80)

    # Step 1: Load configuration
    print("\n[1] LOADING CONFIGURATION")
    print("-" * 80)

from de_funk.config.domain import get_domain_loader
    loader = get_domain_loader(Path("domains"))
    config = loader.load_model_config("securities.stocks")

    print(f"✓ Loaded stocks model config")

    # Check what measures are available
    measures = config.get('measures', {})
    simple_measures = measures.get('simple_measures', {})

    print(f"\n[2] CHECKING INHERITED MEASURES")
    print("-" * 80)

    if 'avg_close_price' in simple_measures:
        meas = simple_measures['avg_close_price']
        print(f"✓ Found inherited measure: avg_close_price")
        print(f"  Source: {meas.get('source')}")
        print(f"  Aggregation: {meas.get('aggregation')}")
        print(f"  Description: {meas.get('description')}")
    else:
        print("✗ avg_close_price NOT found in inherited measures!")
        return

    # Step 2: Check schema for table paths
    print(f"\n[3] CHECKING SCHEMA FOR TABLE PATHS")
    print("-" * 80)

    schema = config.get('schema', {})
    facts = schema.get('facts', {})

    # Check for both generic and specific names
    for table_name in ['fact_prices', 'fact_stock_prices']:
        if table_name in facts:
            table_def = facts[table_name]
            print(f"\n✓ Found table definition: {table_name}")
            print(f"  Keys: {list(table_def.keys())}")
            if 'path' in table_def:
                print(f"  Path: {table_def['path']}")
            else:
                print(f"  ⚠ NO 'path' KEY - this will cause _resolve_table_path to fail!")
        else:
            print(f"✗ Table NOT in schema: {table_name}")

    # Step 3: Check graph for table definitions
    print(f"\n[4] CHECKING GRAPH FOR TABLE DEFINITIONS")
    print("-" * 80)

    graph = config.get('graph', {})
    nodes = graph.get('nodes', {})

    print(f"Available graph nodes: {list(nodes.keys())}")

    # Check for filter definitions in graph
    for node_name in ['fact_prices', 'fact_stock_prices']:
        if node_name in nodes:
            node_def = nodes[node_name]
            print(f"\n✓ Found graph node: {node_name}")
            print(f"  Keys: {list(node_def.keys())}")
            if 'filters' in node_def:
                print(f"  Filters: {node_def['filters']}")
            else:
                print(f"  No filters defined")

    # Step 4: Try to instantiate the model (will this fail?)
    print(f"\n[5] ATTEMPTING TO INSTANTIATE MODEL")
    print("-" * 80)

    try:
        import json
from de_funk.core.duckdb_connection import DuckDBConnection

        # Load storage config
        with open(repo_root / "configs" / "storage.json") as f:
            storage_cfg = json.load(f)

        # Create DuckDB connection
        conn = DuckDBConnection(db_path=":memory:")

        # Instantiate model
from de_funk.models.implemented.stocks.model import StocksModel

        model = StocksModel(
            connection=conn,
            storage_cfg=storage_cfg,
            model_cfg=config
        )

        print(f"✓ Model instantiated successfully")
        print(f"  Model name: {model.model_name}")
        print(f"  Backend: {model.backend}")

        # Step 5: Check if model is built
        print(f"\n[6] CHECKING MODEL BUILD STATE")
        print("-" * 80)

        print(f"  Is built: {model._is_built}")
        print(f"  Tables cached: {model._dims is not None or model._facts is not None}")

        # Step 6: Try to get table reference
        print(f"\n[7] TESTING TABLE REFERENCE RESOLUTION")
        print("-" * 80)

from de_funk.models.base.backend.duckdb_adapter import DuckDBAdapter
        adapter = DuckDBAdapter(conn, model)

        # Try to resolve different table names
        for table_name in ['fact_prices', 'fact_stock_prices']:
            print(f"\nAttempting to resolve: {table_name}")
            try:
                table_ref = adapter.get_table_reference(table_name)
                print(f"  ✓ Resolved to: {table_ref}")
            except Exception as e:
                print(f"  ✗ ERROR: {type(e).__name__}: {e}")

        # Step 7: Check if DuckDB views exist
        print(f"\n[8] CHECKING FOR DUCKDB VIEWS")
        print("-" * 80)

        db_path = Path("storage/duckdb/analytics.db")
        if db_path.exists():
            import duckdb
            db_conn = duckdb.connect(str(db_path), read_only=True)

            # Check for schemas
            schemas = db_conn.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name IN ('stocks', 'options', 'etfs', 'futures')
            """).fetchall()

            print(f"Available schemas: {[s[0] for s in schemas]}")

            # Check for views in stocks schema
            if any(s[0] == 'stocks' for s in schemas):
                views = db_conn.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'stocks' AND table_type = 'VIEW'
                """).fetchall()

                print(f"\nViews in stocks schema: {[v[0] for v in views]}")

                # Check if alias views exist
                for view_name in ['fact_prices', 'dim_security']:
                    if any(v[0] == view_name for v in views):
                        print(f"  ✓ Alias view exists: stocks.{view_name}")
                    else:
                        print(f"  ✗ Missing alias view: stocks.{view_name}")

            db_conn.close()
        else:
            print(f"⚠ DuckDB database not found: {db_path}")
            print(f"  Run: python -m scripts.setup.setup_duckdb_views")

        # Step 8: Test measure execution (will it work?)
        print(f"\n[9] TESTING MEASURE EXECUTION")
        print("-" * 80)

        print(f"\nAttempting to calculate inherited measure: avg_close_price")

        try:
            result = model.calculate_measure("avg_close_price")
            print(f"  ✓ Measure executed successfully!")
            print(f"  Result type: {type(result)}")
            if hasattr(result, 'data'):
                print(f"  Result data shape: {result.data.shape}")
                print(f"  Result preview:\n{result.data.head()}")
            else:
                print(f"  Result preview:\n{result.head()}")
        except Exception as e:
            print(f"  ✗ ERROR executing measure:")
            print(f"     {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n[10] FILTER ENGINE INVESTIGATION")
    print("-" * 80)

from de_funk.core.session.filters import FilterEngine
    print(f"✓ FilterEngine exists in core.session.filters")
    print(f"  Purpose: Runtime filter application (query-time)")
    print(f"  Methods: apply_filters(), apply_from_session()")
    print(f"  Used by: UniversalSession, BaseModel query methods")

    print(f"\n[11] BUILD-TIME FILTER INVESTIGATION")
    print("-" * 80)

    # Check if my filter code is even used
from de_funk.models.base.model import BaseModel
    if hasattr(BaseModel, '_apply_filters'):
        print(f"✓ BaseModel._apply_filters() exists (my addition)")
        print(f"  Purpose: Build-time filter application (in _build_nodes)")
        print(f"  Question: Is this redundant with graph-level filtering?")
    else:
        print(f"✗ BaseModel._apply_filters() NOT found")

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_inherited_measure()
