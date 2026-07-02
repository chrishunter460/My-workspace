"""
Example: Measure Auto-Enrichment

Demonstrates how measures can automatically join across tables using graph edges.

When auto_enrich=True, the system:
1. Detects columns not in the base table (e.g., exchange_name not in fact_equity_prices)
2. Uses GraphQueryPlanner to find which tables have those columns
3. Automatically builds joins using graph edges
4. Executes the measure on the enriched data

This eliminates the need to pre-materialize all join combinations.
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


def example_simple_auto_enrich():
    """Example 1: Simple measure with auto-enrichment."""
    print("=" * 80)
    print("Example 1: Simple Measure Auto-Enrichment")
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

    # Create measure executor
from de_funk.models.measures.executor import MeasureExecutor
    executor = MeasureExecutor(equity_model, backend='duckdb')

    print("Executing: avg_close_by_exchange")
    print("  Base table: fact_equity_prices (has: ticker, close, volume)")
    print("  Grouping by: exchange_name (NOT in fact_equity_prices!)")
    print("  Auto-enrich: true → system finds exchange_name via graph edges")
    print()

    # Execute measure with entity_column not in base table
    result = executor.execute_measure(
        'avg_close_by_exchange',
        entity_column='exchange_name',
        limit=10
    )

    print(f"Result: {result.rows} rows")
    print(f"Query time: {result.query_time_ms:.2f}ms")
    print()
    print("Top 10 exchanges by average closing price:")
    print(result.data.head(10))
    print()


def example_computed_auto_enrich():
    """Example 2: Computed measure with auto-enrichment."""
    print("=" * 80)
    print("Example 2: Computed Measure Auto-Enrichment")
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

from de_funk.models.measures.executor import MeasureExecutor
    executor = MeasureExecutor(equity_model, backend='duckdb')

    print("Executing: market_cap_by_exchange")
    print("  Base table: fact_equity_prices")
    print("  Expression: close * volume")
    print("  Grouping by: exchange_name (requires join)")
    print("  Auto-enrich: true → automatic join to dim_equity → dim_exchange")
    print()

    # Execute computed measure with auto-enrichment
    result = executor.execute_measure(
        'market_cap_by_exchange',
        entity_column='exchange_name',
        limit=10
    )

    print(f"Result: {result.rows} rows")
    print(f"Query time: {result.query_time_ms:.2f}ms")
    print()
    print("Top 10 exchanges by market cap:")
    print(result.data.head(10))
    print()


def example_multi_column_enrich():
    """Example 3: Auto-enrichment with filters on enriched columns."""
    print("=" * 80)
    print("Example 3: Auto-Enrichment with Enriched Column Filters")
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

from de_funk.models.measures.executor import MeasureExecutor
    executor = MeasureExecutor(equity_model, backend='duckdb')

    print("Executing: avg_volume_by_company")
    print("  Base table: fact_equity_prices")
    print("  Grouping by: company_name (requires join to dim_equity)")
    print("  Filter by: company_name LIKE 'A%'")
    print("  Auto-enrich: true → joins to get company_name")
    print()

    # Execute with filter on enriched column
    result = executor.execute_measure(
        'avg_volume_by_company',
        entity_column='company_name',
        filters=None,  # Could add filters here
        limit=10
    )

    print(f"Result: {result.rows} rows")
    print(f"Query time: {result.query_time_ms:.2f}ms")
    print()
    print("Top 10 companies by average volume:")
    print(result.data.head(10))
    print()


def example_inspect_enrichment():
    """Example 4: Inspect what auto-enrichment is doing."""
    print("=" * 80)
    print("Example 4: Understanding Auto-Enrichment")
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

    # Inspect query planner
    planner = equity_model.query_planner
    print(f"Query Planner: {planner}")
    print()

    # Find tables with exchange_name
    print("Finding tables with 'exchange_name' column:")
    tables = planner.find_tables_with_column('exchange_name')
    print(f"  Found in: {tables}")
    print()

    # Find join path from fact_equity_prices to dim_exchange
    print("Finding join path from fact_equity_prices to dim_exchange:")
    path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
    if path:
        print(f"  Path: {' -> '.join(path)}")
    else:
        print("  No path found")
    print()

    # Show measure configuration
from de_funk.models.measures.executor import MeasureExecutor
    executor = MeasureExecutor(equity_model, backend='duckdb')

    measure_info = executor.get_measure_info('avg_close_by_exchange')
    print("Measure configuration: avg_close_by_exchange")
    for key, value in measure_info.items():
        print(f"  {key}: {value}")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  Measure Auto-Enrichment Examples".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    try:
        # Example 1: Simple auto-enrichment
        example_simple_auto_enrich()

        # Example 2: Computed measure auto-enrichment
        example_computed_auto_enrich()

        # Example 3: Multi-column enrichment with filters
        example_multi_column_enrich()

        # Example 4: Inspect auto-enrichment
        example_inspect_enrichment()

        print("=" * 80)
        print("✓ All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
