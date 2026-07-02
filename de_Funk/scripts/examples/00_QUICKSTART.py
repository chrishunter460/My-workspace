#!/usr/bin/env python3
"""
QUICKSTART: Parameter-Driven Measure Calculations

This is your starting point for using the parameter-driven calculation interface.
All examples show how to use simple parameter dictionaries to get calculation results.

NO COMPLEX CODE REQUIRED - Just provide tickers, dates, and what you want to calculate!
"""

import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from scripts.examples.parameter_interface import MeasureCalculator
from scripts.examples.parameter_interface.discovery import (
    list_models,
    list_weighting_strategies,
    print_measure_catalog,
    print_parameter_help
)


def quickstart_1_basic_calculation():
    """
    QUICKSTART 1: Run your first calculation

    The simplest possible example - calculate average close price for AAPL.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 1: Your First Calculation")
    print("=" * 80)

    # Step 1: Initialize calculator
    calc = MeasureCalculator(backend='duckdb')

    # Step 2: Define what you want
    params = {
        'model': 'equity',              # Which model (equity = stock market)
        'measure': 'avg_close_price',   # What to calculate
        'tickers': ['AAPL'],            # Which stocks
        'entity_column': 'ticker',      # Group by ticker
        'limit': 1                      # Just show top 1
    }

    print("\n📋 What we're calculating:")
    print(f"   Model: {params['model']}")
    print(f"   Measure: {params['measure']}")
    print(f"   Tickers: {params['tickers']}")

    # Step 3: Run calculation
    result = calc.calculate(params)

    # Step 4: Check results
    if result.error:
        print(f"\n❌ Error: {result.error}")
        print("\n💡 Note: Make sure you have built the equity model:")
        print("   python -m scripts.build.build_all_models")
        return

    print(f"\n✅ Success!")
    print(f"\n{result.summary()}")
    print("\n📊 Results:")
    print(result.data)


def quickstart_2_weighted_price():
    """
    QUICKSTART 2: Calculate weighted price for multiple tickers

    This is the most requested feature - get weighted price for a list of stocks.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 2: Weighted Price Calculation")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Calculate volume-weighted price for tech stocks
    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': ['AAPL', 'MSFT', 'GOOGL'],
        'start_date': '2024-01-01',
        'end_date': '2024-12-31'
    }

    print("\n📋 Calculating volume-weighted index for:")
    print(f"   Tickers: {', '.join(params['tickers'])}")
    print(f"   Date range: {params['start_date']} to {params['end_date']}")

    result = calc.calculate(params)

    if result.error:
        print(f"\n❌ Error: {result.error}")
        return

    print(f"\n✅ Got {result.rows} data points in {result.query_time_ms:.2f}ms")
    print("\n📊 First 5 days:")
    print(result.data.head())
    print("\n📊 Last 5 days:")
    print(result.data.tail())


def quickstart_3_compare_strategies():
    """
    QUICKSTART 3: Compare multiple weighting strategies

    See how different strategies produce different results.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 3: Compare Weighting Strategies")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Compare three different weighting methods
    strategies = [
        'equal_weighted_index',         # Simple average
        'volume_weighted_index',        # Volume-weighted
        'market_cap_weighted_index',    # Market cap weighted
    ]

    print("\n📋 Comparing strategies:")
    for s in strategies:
        print(f"   - {s}")

    # Use built-in comparison method
    results = calc.calculate_with_comparison(
        model='equity',
        measures=strategies,
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        start_date='2024-01-01',
        end_date='2024-03-31'
    )

    print("\n📊 Results:")
    for strategy, result in results.items():
        if result.error:
            print(f"   ❌ {strategy}: {result.error}")
        else:
            # Get mean value
            val_col = [col for col in result.data.columns if col != 'trade_date'][0]
            mean_val = result.data[val_col].mean()
            print(f"   ✅ {strategy}:")
            print(f"      Mean value: {mean_val:.2f}")
            print(f"      Data points: {result.rows}")


def quickstart_4_discovery():
    """
    QUICKSTART 4: Discover what's available

    Learn how to find models, measures, and parameters.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 4: Discovery - What Can You Calculate?")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # List available models
    print("\n📚 Available Models:")
    models = calc.list_models()
    for model in models:
        print(f"   - {model}")

    # List measures for equity model
    print("\n📊 Available Measures in 'equity' model:")
    measures = calc.list_measures('equity')
    for measure in measures[:10]:  # Show first 10
        print(f"   - {measure}")
    if len(measures) > 10:
        print(f"   ... and {len(measures) - 10} more")

    # Show weighting strategies
    print("\n⚖️  Available Weighting Strategies:")
    strategies = list_weighting_strategies()
    for name, description in strategies.items():
        print(f"   - {name}: {description}")


def quickstart_5_get_help():
    """
    QUICKSTART 5: Get help with parameters

    Learn what parameters are available for a measure.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 5: Get Parameter Help")
    print("=" * 80)

    # Get help for a specific measure
    print("\n📖 Parameter help for 'volume_weighted_index':")
    print_parameter_help('equity', 'volume_weighted_index')


def quickstart_6_practical_example():
    """
    QUICKSTART 6: Practical example - Portfolio analysis

    A realistic use case: analyze your portfolio's weighted performance.
    """
    print("\n" + "=" * 80)
    print("QUICKSTART 6: Practical Portfolio Analysis")
    print("=" * 80)

    calc = MeasureCalculator(backend='duckdb')

    # Your portfolio
    my_portfolio = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']

    print(f"\n💼 Analyzing portfolio: {', '.join(my_portfolio)}")

    # Get volume-weighted performance
    params = {
        'model': 'equity',
        'measure': 'volume_weighted_index',
        'tickers': my_portfolio,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31'
    }

    result = calc.calculate(params)

    if result.error:
        print(f"\n❌ Error: {result.error}")
        return

    if result.data is not None and not result.data.empty:
        # Calculate portfolio performance
        value_col = [col for col in result.data.columns if col != 'trade_date'][0]

        first_value = result.data[value_col].iloc[0]
        last_value = result.data[value_col].iloc[-1]
        returns = (last_value / first_value - 1) * 100

        print(f"\n📈 Portfolio Performance:")
        print(f"   Start value: ${first_value:.2f}")
        print(f"   End value: ${last_value:.2f}")
        print(f"   Return: {returns:+.2f}%")
        print(f"   Data points: {result.rows}")

        # Show recent performance
        print("\n📊 Recent prices (last 5 days):")
        print(result.data.tail())


def main():
    """Run all quickstart examples."""
    print("\n" + "=" * 80)
    print("🚀 PARAMETER-DRIVEN CALCULATIONS QUICKSTART")
    print("=" * 80)
    print("\nWelcome to the easiest way to calculate measures in de_Funk!")
    print("\nThis guide will show you how to:")
    print("  1. Run basic calculations")
    print("  2. Calculate weighted prices for tickers")
    print("  3. Compare different strategies")
    print("  4. Discover what's available")
    print("  5. Get parameter help")
    print("  6. Analyze a portfolio (practical example)")
    print("\n" + "=" * 80)

    examples = [
        quickstart_1_basic_calculation,
        quickstart_2_weighted_price,
        quickstart_3_compare_strategies,
        quickstart_4_discovery,
        quickstart_5_get_help,
        quickstart_6_practical_example,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n❌ Error in {example.__name__}: {e}")
            print("\n💡 Make sure you have:")
            print("   1. Built the models: python -m scripts.build.build_all_models")
            print("   2. Installed dependencies: pip install -r requirements.txt")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("🎉 Quickstart Complete!")
    print("=" * 80)
    print("\n📚 Next Steps:")
    print("   - Explore weighting_strategies/ for more examples")
    print("   - See measure_calculations/ for basic measure examples")
    print("   - Check parameter_interface/ for advanced usage")
    print("\n💡 Need help?")
    print("   - Use print_parameter_help(model, measure) for any measure")
    print("   - Check the README files in each directory")
    print("   - See CLAUDE.md for comprehensive documentation")
    print("=" * 80)


if __name__ == '__main__':
    main()
