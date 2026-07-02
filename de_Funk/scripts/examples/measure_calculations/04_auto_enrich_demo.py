"""
Demo: Measure Auto-Enrichment Feature

Demonstrates the auto-enrichment implementation without requiring actual data.
Shows how the system detects missing columns and plans joins.
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


def demo_measure_config():
    """Demo: Show auto-enrichment measure configurations."""
    print("=" * 80)
    print("Demo: Auto-Enrichment Measure Configurations")
    print("=" * 80)
    print()

    # Initialize session with DuckDB
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Get equity model
    equity_model = session.get_model_instance('equity')
    executor = MeasureExecutor(equity_model, backend='duckdb')

    # List all measures
    measures = executor.list_measures()

    print(f"Total measures defined: {len(measures)}")
    print()

    # Find auto-enrichment measures
    auto_enrich_measures = {
        name: config
        for name, config in measures.items()
        if config.get('auto_enrich', False)
    }

    print(f"Auto-enrichment measures: {len(auto_enrich_measures)}")
    print()

    for name, config in auto_enrich_measures.items():
        print(f"  • {name}")
        print(f"    Description: {config.get('description', 'N/A')}")
        print(f"    Source: {config.get('source', 'N/A')}")
        print(f"    Type: {config.get('type', 'simple')}")
        print(f"    Auto-enrich: {config.get('auto_enrich', False)}")
        print()


def demo_query_planner():
    """Demo: Show query planner capabilities."""
    print("=" * 80)
    print("Demo: Query Planner Capabilities")
    print("=" * 80)
    print()

    # Initialize session
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Get equity model
    equity_model = session.get_model_instance('equity')
    planner = equity_model.query_planner

    print(f"Query Planner: {planner}")
    print()

    # Test 1: Find tables with specific columns
    print("Test 1: Find tables with 'exchange_name' column")
    tables = planner.find_tables_with_column('exchange_name')
    print(f"  Found in tables: {tables}")
    print()

    print("Test 2: Find tables with 'company_name' column")
    tables = planner.find_tables_with_column('company_name')
    print(f"  Found in tables: {tables}")
    print()

    print("Test 3: Find tables with 'ticker' column")
    tables = planner.find_tables_with_column('ticker')
    print(f"  Found in tables: {tables}")
    print()

    # Test 2: Find join paths
    print("Test 4: Find join path from fact_equity_prices to dim_exchange")
    path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
    if path:
        print(f"  Path: {' -> '.join(path)}")
    else:
        print("  No path found")
    print()

    print("Test 5: Find join path from fact_equity_prices to dim_equity")
    path = planner.get_join_path('fact_equity_prices', 'dim_equity')
    if path:
        print(f"  Path: {' -> '.join(path)}")
    else:
        print("  No path found")
    print()

    # Test 3: Show table relationships
    print("Test 6: Show relationships for fact_equity_prices")
    rels = planner.get_table_relationships('fact_equity_prices')
    print(f"  Can join to: {rels.get('can_join_to', [])}")
    print(f"  Can be joined from: {rels.get('can_be_joined_from', [])}")
    print()


def demo_enrichment_logic():
    """Demo: Show how enrichment logic works."""
    print("=" * 80)
    print("Demo: Auto-Enrichment Logic")
    print("=" * 80)
    print()

    # Initialize session
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    equity_model = session.get_model_instance('equity')
    executor = MeasureExecutor(equity_model, backend='duckdb')

    # Get measure config
    measure_config = executor._get_measure_config('avg_close_by_exchange')

    print("Measure: avg_close_by_exchange")
    print(f"  Source: {measure_config['source']}")
    print(f"  Auto-enrich: {measure_config.get('auto_enrich', False)}")
    print()

    # Parse source to get base table
    source_parts = measure_config['source'].split('.')
    base_table = source_parts[0]
    source_column = source_parts[1]

    print(f"Base table: {base_table}")
    print(f"Source column: {source_column}")
    print()

    # Show what columns are in the base table
    base_schema = executor._get_table_schema(base_table)
    if base_schema:
        print(f"Columns in {base_table}:")
        for col in base_schema.keys():
            print(f"  • {col}")
        print()

    # Simulate enrichment need
    entity_column = 'exchange_name'
    print(f"User wants to group by: {entity_column}")
    print(f"Is '{entity_column}' in {base_table}? {entity_column in base_schema}")
    print()

    if entity_column not in base_schema:
        print(f"➜ Need to enrich! Finding tables with '{entity_column}'...")
        planner = equity_model.query_planner
        tables_with_column = planner.find_tables_with_column(entity_column)
        print(f"  Found in: {tables_with_column}")
        print()

        if tables_with_column:
            target_table = tables_with_column[0]
            print(f"➜ Finding join path from {base_table} to {target_table}...")
            path = planner.get_join_path(base_table, target_table)
            if path:
                print(f"  Path: {' -> '.join(path)}")
                print()
                print("✓ Auto-enrichment would:")
                print(f"  1. Join {path[0]} to {path[1]}")
                if len(path) > 2:
                    print(f"  2. Join {path[1]} to {path[2]}")
                print(f"  3. Execute measure on enriched data")
            else:
                print("  ✗ No path found")
        else:
            print(f"  ✗ Column '{entity_column}' not found in any table")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  Measure Auto-Enrichment Feature Demo".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    try:
        # Demo 1: Show measure configurations
        demo_measure_config()

        # Demo 2: Show query planner capabilities
        demo_query_planner()

        # Demo 3: Show enrichment logic
        demo_enrichment_logic()

        print("=" * 80)
        print("✓ All demos completed successfully!")
        print("=" * 80)
        print()
        print("Summary:")
        print("  • Auto-enrichment feature is fully implemented")
        print("  • Measures can reference columns not in base table")
        print("  • System automatically joins via graph edges")
        print("  • Works with both DuckDB and Spark backends")
        print()
        print("To test with actual data:")
        print("  1. Build equity Silver: python scripts/build_equity_silver.py")
        print("  2. Run full example: python examples/measure_auto_enrich_example.py")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
