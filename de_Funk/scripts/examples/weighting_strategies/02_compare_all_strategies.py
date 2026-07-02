#!/usr/bin/env python3
"""
Compare All Weighting Strategies Example

Demonstrates how to compare different weighting strategies using parameter dictionaries.
This shows the real power of the parameter interface - easily switch between different
weighting methods to see which one fits your use case.

Available strategies:
- equal: Simple average (all weights equal)
- volume: Volume-weighted (high volume = high weight)
- market_cap: Market cap weighted (like S&P 500)
- price: Price-weighted (like DJIA)
- volume_deviation: Unusual trading activity weighted
- volatility: Inverse volatility (risk-adjusted)
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from scripts.examples.parameter_interface import MeasureCalculator
import pandas as pd


def example_1_all_strategies():
    """
    Example 1: Calculate all weighting strategies for the same tickers.

    This is the most useful comparison - see how different strategies
    produce different results for the same portfolio.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Compare All Weighting Strategies")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Define portfolio
    tickers = ['AAPL', 'MSFT', 'GOOGL']
    date_range = ('2024-01-01', '2024-03-31')

    # All available weighting strategies
    strategies = {
        'equal': 'equal_weighted_index',
        'volume': 'volume_weighted_index',
        'market_cap': 'market_cap_weighted_index',
        'price': 'price_weighted_index',
        'volume_deviation': 'volume_deviation_weighted_index',
        'volatility': 'volatility_weighted_index',
    }

    print(f"\nPortfolio: {', '.join(tickers)}")
    print(f"Date range: {date_range[0]} to {date_range[1]}")
    print(f"\nCalculating {len(strategies)} weighting strategies...")

    # Calculate each strategy
    results = {}
    for strategy_name, measure_name in strategies.items():
        params = {
            'model': 'equity',
            'measure': measure_name,
            'tickers': tickers,
            'start_date': date_range[0],
            'end_date': date_range[1]
        }

        result = calc.calculate(params)

        if result.error:
            print(f"  ✗ {strategy_name}: {result.error}")
        else:
            results[strategy_name] = result
            print(f"  ✓ {strategy_name}: {result.rows} rows in {result.query_time_ms:.2f}ms")

    # Combine results for comparison
    if results:
        print("\n" + "=" * 80)
        print("COMPARISON TABLE")
        print("=" * 80)

        # Merge all results on trade_date
        combined = None
        for strategy_name, result in results.items():
            if result.data is not None and not result.data.empty:
                # Get the value column (not trade_date)
                value_col = [col for col in result.data.columns if col != 'trade_date'][0]
                df = result.data[['trade_date', value_col]].rename(
                    columns={value_col: strategy_name}
                )

                if combined is None:
                    combined = df
                else:
                    combined = combined.merge(df, on='trade_date', how='outer')

        if combined is not None:
            # Sort by date
            combined = combined.sort_values('trade_date').reset_index(drop=True)

            print("\nFirst 10 days:")
            print(combined.head(10))

            print("\nLast 10 days:")
            print(combined.tail(10))

            # Calculate statistics
            print("\n" + "=" * 80)
            print("STATISTICS COMPARISON")
            print("=" * 80)

            stats = []
            for col in combined.columns:
                if col != 'trade_date':
                    stats.append({
                        'strategy': col,
                        'mean': combined[col].mean(),
                        'std': combined[col].std(),
                        'min': combined[col].min(),
                        'max': combined[col].max(),
                        'latest': combined[col].iloc[-1] if len(combined) > 0 else None
                    })

            stats_df = pd.DataFrame(stats)
            print(stats_df.to_string(index=False))


def example_2_strategy_comparison_params():
    """
    Example 2: Use the calculator's built-in comparison method.

    This is even easier - just list the measures you want to compare
    and the calculator does the rest.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Using Built-in Comparison Method")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # List of measures to compare
    measures = [
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index',
    ]

    print(f"\nComparing {len(measures)} strategies...")

    # Use the built-in comparison method
    results = calc.calculate_with_comparison(
        model='equity',
        measures=measures,
        tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
        start_date='2024-01-01',
        end_date='2024-12-31'
    )

    print("\nResults:")
    for measure, result in results.items():
        if result.error:
            print(f"  ✗ {measure}: {result.error}")
        else:
            print(f"  ✓ {measure}: {result.rows} rows")
            if result.data is not None and not result.data.empty:
                # Get value column
                val_col = [col for col in result.data.columns if col != 'trade_date'][0]
                mean_val = result.data[val_col].mean()
                print(f"      Mean value: {mean_val:.2f}")


def example_3_best_strategy_for_portfolio():
    """
    Example 3: Find the best performing strategy for a portfolio.

    Calculate returns for each strategy and see which one performed best.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Find Best Performing Strategy")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']

    strategies = {
        'equal_weighted': 'equal_weighted_index',
        'volume_weighted': 'volume_weighted_index',
        'market_cap_weighted': 'market_cap_weighted_index',
    }

    print(f"\nTesting strategies on portfolio: {', '.join(tickers)}")

    # Calculate each strategy
    performance = {}
    for strategy_name, measure_name in strategies.items():
        params = {
            'model': 'equity',
            'measure': measure_name,
            'tickers': tickers,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }

        result = calc.calculate(params)

        if not result.error and result.data is not None and not result.data.empty:
            # Calculate return (last / first - 1)
            value_col = [col for col in result.data.columns if col != 'trade_date'][0]
            first_val = result.data[value_col].iloc[0]
            last_val = result.data[value_col].iloc[-1]
            returns = (last_val / first_val - 1) * 100

            performance[strategy_name] = {
                'return_pct': returns,
                'first_value': first_val,
                'last_value': last_val,
                'mean_value': result.data[value_col].mean(),
                'std_dev': result.data[value_col].std(),
            }

    # Display performance
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)

    for strategy_name, perf in sorted(performance.items(), key=lambda x: x[1]['return_pct'], reverse=True):
        print(f"\n{strategy_name}:")
        print(f"  Return: {perf['return_pct']:+.2f}%")
        print(f"  Start: {perf['first_value']:.2f}")
        print(f"  End: {perf['last_value']:.2f}")
        print(f"  Mean: {perf['mean_value']:.2f}")
        print(f"  Std Dev: {perf['std_dev']:.2f}")

    # Find best
    best = max(performance.items(), key=lambda x: x[1]['return_pct'])
    print(f"\n🏆 Best strategy: {best[0]} with {best[1]['return_pct']:+.2f}% return")


def example_4_custom_ticker_lists():
    """
    Example 4: Compare strategies across different ticker groups.

    Shows how easy it is to test different portfolios with parameter dicts.
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Compare Strategies Across Different Portfolios")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Different portfolio compositions
    portfolios = {
        'tech_giants': ['AAPL', 'MSFT', 'GOOGL'],
        'mega_cap': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
    }

    strategy = 'volume_weighted_index'

    print(f"\nTesting '{strategy}' across different portfolios...")

    for portfolio_name, tickers in portfolios.items():
        print(f"\n{portfolio_name}: {', '.join(tickers)}")

        params = {
            'model': 'equity',
            'measure': strategy,
            'tickers': tickers,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }

        result = calc.calculate(params)

        if result.error:
            print(f"  ✗ Error: {result.error}")
        else:
            value_col = [col for col in result.data.columns if col != 'trade_date'][0]
            mean_val = result.data[value_col].mean()
            print(f"  ✓ Mean value: {mean_val:.2f}")
            print(f"  ✓ Data points: {result.rows}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("COMPARING WEIGHTING STRATEGIES - PARAMETER EXAMPLES")
    print("=" * 80)
    print("\nThese examples show how to easily compare different weighting")
    print("strategies using parameter dictionaries. Switch between strategies")
    print("by just changing the measure name!")
    print("=" * 80)

    examples = [
        example_1_all_strategies,
        example_2_strategy_comparison_params,
        example_3_best_strategy_for_portfolio,
        example_4_custom_ticker_lists,
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
