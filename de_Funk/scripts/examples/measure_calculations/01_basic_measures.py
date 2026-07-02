#!/usr/bin/env python3
"""
Basic Usage Examples - Unified Measure Framework

Demonstrates basic measure calculations with the new framework.
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.core.context import RepoContext


def example_1_simple_measure():
    """Example 1: Calculate a simple measure."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Simple Measure")
    print("=" * 70)

    # Initialize context
    ctx = RepoContext.from_repo_root(connection_type='duckdb')

    # Load company model
from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Calculate average closing price by ticker
    result = model.calculate_measure(
        'avg_close_price',
        entity_column='ticker',
        limit=10
    )

    print(f"\nBackend: {result.backend}")
    print(f"Query time: {result.query_time_ms:.2f}ms")
    print(f"Rows: {result.rows}")
    print("\nResults:")
    print(result.data)


def example_2_computed_measure():
    """Example 2: Calculate a computed measure."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Computed Measure")
    print("=" * 70)

    ctx = RepoContext.from_repo_root(connection_type='duckdb')

from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Calculate market cap (close * volume) averaged by ticker
    result = model.calculate_measure(
        'market_cap',
        entity_column='ticker',
        limit=10
    )

    print(f"\nQuery time: {result.query_time_ms:.2f}ms")
    print(f"Rows: {result.rows}")
    print("\nTop 10 by market cap:")
    print(result.data)


def example_3_weighted_measure():
    """Example 3: Calculate a weighted measure."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Weighted Measure")
    print("=" * 70)

    ctx = RepoContext.from_repo_root(connection_type='duckdb')

from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Calculate volume-weighted index
    result = model.calculate_measure('volume_weighted_index')

    print(f"\nQuery time: {result.query_time_ms:.2f}ms")
    print(f"Rows: {result.rows}")
    print("\nVolume-weighted index by date:")
    print(result.data.head(10))


def example_4_list_measures():
    """Example 4: List available measures."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: List Available Measures")
    print("=" * 70)

    ctx = RepoContext.from_repo_root(connection_type='duckdb')

from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # List all measures
    measures = model.measures.list_measures()

    print(f"\nTotal measures: {len(measures)}")
    print("\nMeasure details:")

    for measure_name in sorted(measures.keys()):
        info = model.measures.get_measure_info(measure_name)
        print(f"\n  {measure_name}:")
        print(f"    Type: {info['type']}")
        print(f"    Source: {info['source']}")
        print(f"    Data type: {info['data_type']}")


def example_5_explain_sql():
    """Example 5: Explain SQL generation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Explain SQL (Debugging)")
    print("=" * 70)

    ctx = RepoContext.from_repo_root(connection_type='duckdb')

from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Generate SQL without executing
    measure_name = 'volume_weighted_index'
    sql = model.measures.explain_measure(measure_name)

    print(f"\nSQL for '{measure_name}':")
    print("-" * 70)
    print(sql)
    print("-" * 70)


def example_6_convenience_methods():
    """Example 6: Use model convenience methods."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Convenience Methods")
    print("=" * 70)

    ctx = RepoContext.from_repo_root(connection_type='duckdb')

from de_funk.models.implemented.company.model import CompanyModel
    model = CompanyModel(ctx.connection, ctx.storage, ctx.repo)

    # Use company-specific convenience wrapper
    result = model.calculate_measure_by_ticker('avg_close_price', limit=5)

    print(f"\nTop 5 tickers by average close price:")
    print(result.data)

    # Get just the ticker list
    tickers = model.get_top_tickers_by_measure('avg_close_price', limit=5)
    print(f"\nTicker symbols only: {tickers}")


def main():
    """Run all examples."""
    examples = [
        example_1_simple_measure,
        example_2_computed_measure,
        example_3_weighted_measure,
        example_4_list_measures,
        example_5_explain_sql,
        example_6_convenience_methods,
    ]

    print("\n" + "=" * 70)
    print("MEASURE FRAMEWORK - BASIC USAGE EXAMPLES")
    print("=" * 70)

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n✗ Error in {example.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
