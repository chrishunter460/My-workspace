"""
Example: Using GraphQueryPlanner for Dynamic Joins

Demonstrates how to use the query planner to get enriched tables
without requiring materialized views.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


def example_basic_enrichment():
    """Example 1: Basic table enrichment with dynamic joins."""
    print("=" * 80)
    print("Example 1: Basic Table Enrichment")
    print("=" * 80)
    print()

    # Initialize session (works with both Spark and DuckDB)
    ctx = RepoContext.from_repo_root(connection_type="duckdb")

    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Load equity model
    equity_model = session.get_model_instance('equity')

    # Get prices enriched with company info
    # Uses graph edges: fact_equity_prices -> dim_equity
    print("Getting fact_equity_prices enriched with dim_equity...")
    df = equity_model.get_table_enriched(
        'fact_equity_prices',
        enrich_with=['dim_equity'],
        columns=['ticker', 'trade_date', 'close', 'company_name']
    )

    print(f"Result: {len(df)} rows")
    print("Columns:", list(df.columns))
    print(df.head(5))
    print()


def example_multi_hop_join():
    """Example 2: Multi-hop join through multiple tables."""
    print("=" * 80)
    print("Example 2: Multi-Hop Join")
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

    # Get prices with company AND exchange info
    # Uses graph edges: fact_equity_prices -> dim_equity -> dim_exchange
    print("Getting fact_equity_prices enriched with dim_equity + dim_exchange...")
    df = equity_model.get_table_enriched(
        'fact_equity_prices',
        enrich_with=['dim_equity', 'dim_exchange'],
        columns=[
            'ticker',
            'trade_date',
            'close',
            'company_name',
            'exchange_code',
            'exchange_name'
        ]
    )

    print(f"Result: {len(df)} rows")
    print("Columns:", list(df.columns))
    print(df.head(5))
    print()


def example_query_planner_inspection():
    """Example 3: Inspecting query planner capabilities."""
    print("=" * 80)
    print("Example 3: Query Planner Inspection")
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

    # Get query planner
    planner = equity_model.query_planner
    print(f"Query Planner: {planner}")
    print()

    # Find join path
    print("Join path from fact_equity_prices to dim_exchange:")
    path = planner.get_join_path('fact_equity_prices', 'dim_exchange')
    if path:
        print("  " + " -> ".join(path))
    else:
        print("  No path found")
    print()

    # Get table relationships
    print("Relationships for fact_equity_prices:")
    rels = planner.get_table_relationships('fact_equity_prices')
    print(f"  Can join to: {rels.get('can_join_to', [])}")
    print(f"  Can be joined from: {rels.get('can_be_joined_from', [])}")
    print()


def example_fallback_to_materialized():
    """Example 4: Demonstrates fallback to materialized view."""
    print("=" * 80)
    print("Example 4: Materialized View Fallback")
    print("=" * 80)
    print()

    # NOTE: This example requires paths to be enabled in equity.yaml
    print("If paths are enabled in equity.yaml:")
    print("  1. Query planner checks for equity_prices_with_company")
    print("  2. If found, reads materialized view (fast)")
    print("  3. If not found, builds join dynamically (still works)")
    print()
    print("Currently paths are disabled, so all joins are built dynamically.")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  GraphQueryPlanner Examples".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    try:
        # Example 1: Basic enrichment
        example_basic_enrichment()

        # Example 2: Multi-hop join
        example_multi_hop_join()

        # Example 3: Query planner inspection
        example_query_planner_inspection()

        # Example 4: Materialized view fallback
        example_fallback_to_materialized()

        print("=" * 80)
        print("✓ All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
