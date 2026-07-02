#!/usr/bin/env python3
"""
Basic Weighted Price Calculation Example

Demonstrates how to calculate weighted prices using parameter dictionaries.
This is the simplest way to get weighted calculations - just provide a list
of tickers and get back the weighted price.

Example use case:
    User wants to get the volume-weighted price for AAPL and MSFT stocks
    over a specific date range.
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from scripts.examples.parameter_interface import MeasureCalculator
import pandas as pd


def example_1_volume_weighted_price():
    """
    Example 1: Get volume-weighted price for a list of tickers.

    This is the most common use case - calculate a weighted index
    based on trading volume.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Volume-Weighted Price")
    print("=" * 80)

    # Initialize calculator
    calc = MeasureCalculator(backend='duckdb')

    # Define parameters as a dictionary
    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': ['AAPL', 'MSFT'],
        'start_date': '2024-01-01',
        'end_date': '2024-12-31'
    }

    print("\nParameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    # Run calculation
    print("\nRunning calculation...")
    result = calc.calculate(params)

    # Check for errors
    if result.error:
        print(f"\n✗ Error: {result.error}")
        return

    # Display results
    print(f"\n✓ Success!")
    print(result.summary())
    print("\nData:")
    print(result.data.head(10))

    # Show statistics
    if result.data is not None and not result.data.empty:
        weighted_col = [col for col in result.data.columns if 'weighted' in col.lower()][0]
        print(f"\nStatistics for {weighted_col}:")
        print(f"  Mean: {result.data[weighted_col].mean():.2f}")
        print(f"  Min: {result.data[weighted_col].min():.2f}")
        print(f"  Max: {result.data[weighted_col].max():.2f}")


def example_2_single_ticker():
    """
    Example 2: Get weighted price for a single ticker.

    Shows that you can pass a single ticker string instead of a list.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Single Ticker")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Single ticker as string
    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': ['AAPL'],  # Can also use: 'tickers': 'AAPL'
        'start_date': '2024-01-01',
        'end_date': '2024-03-31'  # Shorter date range
    }

    print("\nCalculating volume-weighted price for AAPL...")
    result = calc.calculate(params)

    if result.error:
        print(f"✗ Error: {result.error}")
        return

    print(f"✓ Got {result.rows} data points")
    print("\nFirst 5 rows:")
    print(result.data.head())


def example_3_multiple_tickers():
    """
    Example 3: Get weighted price for multiple tickers (portfolio).

    This shows a realistic portfolio scenario with 5 tech stocks.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Portfolio of Multiple Tickers")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Portfolio of tech stocks
    tech_portfolio = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']

    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': tech_portfolio,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31'
    }

    print(f"\nCalculating volume-weighted index for portfolio:")
    print(f"  Tickers: {', '.join(tech_portfolio)}")
    print(f"  Date range: {params['start_date']} to {params['end_date']}")

    result = calc.calculate(params)

    if result.error:
        print(f"✗ Error: {result.error}")
        return

    print(f"\n✓ Success! Query took {result.query_time_ms:.2f}ms")
    print(f"  Retrieved {result.rows} data points")

    if result.data is not None and not result.data.empty:
        print("\nLast 10 days:")
        print(result.data.tail(10))


def example_4_no_date_filter():
    """
    Example 4: Get weighted price without date filters (all available data).

    Shows that date filters are optional - you can get all available data.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: No Date Filter (All Data)")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # No date filters - get all available data
    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': ['AAPL', 'MSFT']
    }

    print("\nCalculating without date filters (all available data)...")
    result = calc.calculate(params)

    if result.error:
        print(f"✗ Error: {result.error}")
        return

    print(f"✓ Retrieved {result.rows} total data points")

    if result.data is not None and not result.data.empty:
        # Show date range
        date_col = [col for col in result.data.columns if 'date' in col.lower()][0]
        print(f"\nDate range in data:")
        print(f"  First date: {result.data[date_col].min()}")
        print(f"  Last date: {result.data[date_col].max()}")


def example_5_compare_with_avg():
    """
    Example 5: Compare volume-weighted price with simple average.

    Shows the difference between weighted and unweighted calculations.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Compare Weighted vs Unweighted")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    tickers = ['AAPL', 'MSFT']

    # Get volume-weighted index
    weighted_params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': tickers,
        'start_date': '2024-01-01',
        'end_date': '2024-01-31'
    }

    # Get equal-weighted (simple average)
    equal_params = {
        'model': 'equity',
        'measure': 'equal_weighted_index',
        'tickers': tickers,
        'start_date': '2024-01-01',
        'end_date': '2024-01-31'
    }

    print(f"\nComparing weighted vs unweighted for: {', '.join(tickers)}")

    weighted_result = calc.calculate(weighted_params)
    equal_result = calc.calculate(equal_params)

    if weighted_result.error or equal_result.error:
        print("✗ Error in calculation")
        return

    # Merge results for comparison
    if weighted_result.data is not None and equal_result.data is not None:
        comparison = weighted_result.data.merge(
            equal_result.data,
            on='trade_date',
            suffixes=('_volume_weighted', '_equal_weighted')
        )

        print("\nComparison (first 5 days):")
        print(comparison.head())

        # Calculate difference
        vol_col = [col for col in comparison.columns if 'volume_weighted' in col][0]
        eq_col = [col for col in comparison.columns if 'equal_weighted' in col][0]
        comparison['difference'] = comparison[vol_col] - comparison[eq_col]

        print(f"\nAverage difference: {comparison['difference'].mean():.2f}")
        print(f"Max difference: {comparison['difference'].max():.2f}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("WEIGHTED PRICE CALCULATIONS - PARAMETER EXAMPLES")
    print("=" * 80)
    print("\nThese examples show how to calculate weighted prices using")
    print("parameter dictionaries. Just provide tickers and dates,")
    print("and get back weighted calculations!")
    print("=" * 80)

    examples = [
        example_1_volume_weighted_price,
        example_2_single_ticker,
        example_3_multiple_tickers,
        example_4_no_date_filter,
        example_5_compare_with_avg,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n✗ Error in {example.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == '__main__':
    main()
