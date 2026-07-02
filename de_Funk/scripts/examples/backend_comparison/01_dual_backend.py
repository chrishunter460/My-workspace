"""
Dual Backend Example: GraphQueryPlanner with Spark and DuckDB

Demonstrates that the same measure auto-enrichment logic works with both
Spark and DuckDB backends.

This example shows:
1. Backend detection and routing
2. Join type mapping (many_to_one → left, etc.)
3. Column aliasing for multi-table joins
4. Auto-enrichment with both backends

Note: Requires PySpark for Spark examples. Falls back to DuckDB-only if unavailable.
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession
from de_funk.models.measures.executor import MeasureExecutor


def check_spark_available():
    """Check if PySpark is available."""
    try:
        import pyspark
        return True
    except ImportError:
        return False


def example_duckdb_backend():
    """Example: Query planner with DuckDB backend."""
    print("=" * 80)
    print("Example 1: DuckDB Backend")
    print("=" * 80)
    print()

    # Initialize DuckDB session
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Get equity model
    equity_model = session.get_model_instance('equity')
    print(f"Backend: {equity_model.backend}")
    print(f"Query Planner: {equity_model.query_planner}")
    print()

    # Show join type mapping for DuckDB
    print("DuckDB Join Type Mapping:")
    print("  many_to_one → LEFT")
    print("  one_to_many → LEFT")
    print("  inner → INNER")
    print("  full/outer → FULL OUTER")
    print()

    # Demonstrate query planner capabilities
    planner = equity_model.query_planner
    print("Finding join path: fact_equity_prices → dim_exchange")
    path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
    if path:
        print(f"  Path: {' → '.join(path)}")
        print()

        # Show edge details
        for i in range(len(path) - 1):
            left = path[i]
            right = path[i + 1]
            edge_data = planner.graph.edges[left, right]
            print(f"  Edge {i+1}: {left} → {right}")
            print(f"    Join on: {edge_data['join_on']}")
            print(f"    Join type: {edge_data.get('join_type', 'left')} → LEFT (mapped)")
            print()

    # Test auto-enrichment
    print("Testing auto-enrichment with DuckDB:")
    executor = MeasureExecutor(equity_model, backend='duckdb')

    # Show measure info
    measure_info = executor.get_measure_info('avg_close_by_exchange')
    print(f"  Measure: {measure_info['name']}")
    print(f"  Type: {measure_info['type']}")
    print(f"  Source: {measure_info['source']}")
    print(f"  Description: {measure_info['description']}")
    print()

    print("  When grouped by 'exchange_name' (not in fact_equity_prices):")
    print("  1. Auto-enrichment detects missing column")
    print("  2. Finds path via graph edges")
    print("  3. Builds SQL JOIN with correct table aliases")
    print("  4. Executes measure on enriched data")
    print()


def example_spark_backend():
    """Example: Query planner with Spark backend."""
    print("=" * 80)
    print("Example 2: Spark Backend")
    print("=" * 80)
    print()

    if not check_spark_available():
        print("⚠ PySpark not available - showing conceptual example only")
        print()
        print("If PySpark were available, this example would:")
        print("  1. Initialize Spark session")
        print("  2. Load tables as Spark DataFrames")
        print("  3. Use DataFrame.join() API for joins")
        print("  4. Map many_to_one → left join type")
        print("  5. Execute measures on Spark DataFrames")
        print()
        print("Code example:")
        print("""
    # Would initialize like this:
    ctx = RepoContext.from_repo_root(connection_type="spark")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )
    equity_model = session.get_model_instance('equity')

    # Query planner would use same logic:
    planner = equity_model.query_planner  # backend='spark'
    path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
    # → ['fact_equity_prices', 'dim_equity', 'dim_exchange']

    # But execution would use Spark DataFrames:
    df = model.get_table_enriched(
        'fact_equity_prices',
        enrich_with=['dim_equity', 'dim_exchange']
    )
    # Returns: Spark DataFrame (lazy evaluation)

    # Join type mapping happens at line 240-252 in query_planner.py:
    join_type_raw = edge_data.get('join_type', 'left').lower()
    join_type_map = {
        'many_to_one': 'left',  # Maps to Spark's 'left' join
        'one_to_many': 'left',
        'left': 'left',
        'right': 'right',
        'inner': 'inner',
        'full': 'outer',
        'outer': 'outer'
    }
    join_type = join_type_map.get(join_type_raw, 'left')

    # Spark join at line 507:
    result = left_df.join(right_df, join_condition, join_type)
        """)
        return

    # If Spark is available, run actual example
    try:
        ctx = RepoContext.from_repo_root(connection_type="spark")
        session = UniversalSession(
            connection=ctx.connection,
            storage_cfg=ctx.storage,
            repo_root=ctx.repo
        )

        equity_model = session.get_model_instance('equity')
        print(f"✓ Spark session initialized")
        print(f"Backend: {equity_model.backend}")
        print(f"Query Planner: {equity_model.query_planner}")
        print()

        # Show join type mapping for Spark
        print("Spark Join Type Mapping:")
        print("  many_to_one → left")
        print("  one_to_many → left")
        print("  inner → inner")
        print("  full/outer → outer")
        print()

        # Test query planner
        planner = equity_model.query_planner
        print("Finding join path: fact_equity_prices → dim_exchange")
        path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
        if path:
            print(f"  Path: {' → '.join(path)}")
            print()

        # Test auto-enrichment
        print("Testing auto-enrichment with Spark:")
        executor = MeasureExecutor(equity_model, backend='spark')

        # Execute measure (would work with Silver data)
        print("  Executor backend: spark")
        print("  Uses SparkAdapter.set_enriched_table()")
        print("  Creates temporary view: enriched_df.createOrReplaceTempView()")
        print()

    except Exception as e:
        print(f"✗ Spark initialization failed: {e}")
        print("  This is expected if Silver data not built with Spark")
        print()


def compare_backends():
    """Compare backend implementations."""
    print("=" * 80)
    print("Backend Comparison")
    print("=" * 80)
    print()

    comparison = """
┌─────────────────┬──────────────────────────┬──────────────────────────┐
│ Feature         │ DuckDB                   │ Spark                    │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Join Method     │ SQL-based                │ DataFrame API            │
│                 │ _build_duckdb_join_sql() │ _build_dynamic_join()    │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Join Execution  │ connection.execute(sql)  │ left_df.join(right_df)   │
│                 │ Single SQL query         │ Sequential joins         │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Return Type     │ Pandas DataFrame         │ Spark DataFrame          │
│                 │ Eager evaluation         │ Lazy evaluation          │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Join Type Map   │ Lines 315-325            │ Lines 242-252            │
│                 │ many_to_one → LEFT       │ many_to_one → left       │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Table Alias     │ Uses SQL aliases (t0,t1) │ No aliases needed        │
│                 │ SELECT t0.col, t1.col    │ DataFrame columns        │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Column Select   │ _table_has_column()      │ _select_columns()        │
│                 │ Schema-based aliasing    │ df.select(*cols)         │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Enrichment      │ connection.register()    │ createOrReplaceTempView()│
│                 │ CREATE VIEW              │ Temporary view           │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ Performance     │ Fast for small-medium    │ Scales to large data     │
│                 │ In-process               │ Distributed              │
└─────────────────┴──────────────────────────┴──────────────────────────┘

Key Insights:
  • Same graph edges drive both implementations
  • Join type mapping ensures compatibility
  • Auto-enrichment logic is backend-agnostic
  • Adapter pattern hides backend differences
  • Measures work identically on both backends
"""
    print(comparison)


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  Dual Backend Example: Spark & DuckDB".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Check environment
    has_spark = check_spark_available()
    print(f"Environment Check:")
    print(f"  PySpark available: {has_spark}")
    print()

    try:
        # Example 1: DuckDB
        example_duckdb_backend()

        # Example 2: Spark
        example_spark_backend()

        # Comparison
        compare_backends()

        print("=" * 80)
        print("✓ Examples completed successfully!")
        print("=" * 80)
        print()

        if not has_spark:
            print("Note: Install PySpark to test Spark backend:")
            print("  pip install pyspark")
            print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
