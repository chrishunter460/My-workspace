"""
Domain Strategy Measures Example
==================================

This script demonstrates how to grab and create DataFrames with domain strategy measures
from the equities model, including:
- Weighting strategies (equal, volume, market_cap, price, volume_deviation, volatility)
- Risk metrics (beta, volatility, sharpe_ratio, max_drawdown, alpha)
- Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV)

Author: System
Created: 2025-11-14
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

# Import session and context
from de_funk.core.context import RepoContext
from de_funk.models.api.session import UniversalSession


def setup_equity_model():
    """
    Initialize the equity model with DuckDB backend.

    This creates a UniversalSession and loads the equity model with all
    domain strategies (weighting, risk, technical indicators).

    Returns:
        Equity model instance with domain strategies loaded
    """
    # Initialize repo context with DuckDB
    ctx = RepoContext.from_repo_root(connection_type="duckdb")

    # Create universal session
    session = UniversalSession(
        connection=ctx.connection,
        storage_cfg=ctx.storage,
        repo_root=ctx.repo
    )

    # Load equity model (domain strategies auto-loaded on import)
    equity_model = session.get_model_instance('equity')

    return equity_model


def get_weighted_indices(
    equity_model,
    tickers: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Get all weighted index measures for comparison.

    Args:
        equity_model: The equity model instance
        tickers: List of ticker symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
        start_date: Start date (e.g., '2024-01-01')
        end_date: End date (e.g., '2024-12-31')

    Returns:
        DataFrame with all weighted indices by trade_date
    """
    # Build filters - need to pass as separate kwargs, not nested dict
    filter_kwargs = {}

    if start_date and end_date:
        # Pass as trade_date parameter with dict value
        filter_kwargs['trade_date'] = {'start': start_date, 'end': end_date}
    elif start_date:
        filter_kwargs['trade_date'] = {'start': start_date}
    elif end_date:
        filter_kwargs['trade_date'] = {'end': end_date}

    if tickers:
        filter_kwargs['ticker'] = tickers

    # Get each weighted index measure
    weighted_measures = {
        'equal_weighted': 'equal_weighted_index',
        'volume_weighted': 'volume_weighted_index',
        'market_cap_weighted': 'market_cap_weighted_index',
        'price_weighted': 'price_weighted_index',
        'volume_deviation_weighted': 'volume_deviation_weighted_index',
        'volatility_weighted': 'volatility_weighted_index'
    }

    # Collect results
    results = {}
    for label, measure_name in weighted_measures.items():
        try:
            result = equity_model.calculate_measure(
                measure_name=measure_name,
                **filter_kwargs  # Unpack filters as kwargs
            )

            # Extract the DataFrame
            df = result.data
            if df is not None and not df.empty:
                # Find the measure column (first non-trade_date column)
                measure_col = [col for col in df.columns if col != 'trade_date'][0]
                # Keep only trade_date and measure column to avoid merge conflicts
                df = df[['trade_date', measure_col]].rename(columns={measure_col: label})
                results[label] = df

        except Exception as e:
            print(f"Warning: Could not calculate {measure_name}: {e}")

    # Merge all results on trade_date
    if not results:
        return pd.DataFrame()

    merged_df = None
    for label, df in results.items():
        if merged_df is None:
            merged_df = df
        else:
            merged_df = merged_df.merge(df, on='trade_date', how='outer')

    # Sort by date
    merged_df = merged_df.sort_values('trade_date').reset_index(drop=True)

    return merged_df


def get_technical_indicators(
    equity_model,
    tickers: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by_ticker: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Get technical indicator measures.

    Args:
        equity_model: The equity model instance
        tickers: List of ticker symbols
        start_date: Start date
        end_date: End date
        group_by_ticker: If True, group by ticker; if False, aggregate across all tickers

    Returns:
        Dictionary of DataFrames with technical indicators
    """
    # Build filters as kwargs
    filter_kwargs = {}

    if start_date and end_date:
        filter_kwargs['trade_date'] = {'start': start_date, 'end': end_date}
    elif start_date:
        filter_kwargs['trade_date'] = {'start': start_date}
    elif end_date:
        filter_kwargs['trade_date'] = {'end': end_date}

    if tickers:
        filter_kwargs['ticker'] = tickers

    # Technical indicator measures
    technical_measures = {
        'avg_rsi': 'avg_rsi',
        'avg_volatility_20d': 'avg_volatility_20d',
        'avg_beta': 'avg_beta'
    }

    results = {}
    for label, measure_name in technical_measures.items():
        try:
            if group_by_ticker:
                result = equity_model.calculate_measure_by_ticker(
                    measure_name=measure_name,
                    tickers=tickers if tickers else None,
                    **filter_kwargs
                )
            else:
                result = equity_model.calculate_measure(
                    measure_name=measure_name,
                    **filter_kwargs
                )

            df = result.data
            if df is not None and not df.empty:
                results[label] = df

        except Exception as e:
            print(f"Warning: Could not calculate {measure_name}: {e}")

    return results


def get_price_measures_by_ticker(
    equity_model,
    tickers: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    Get basic price measures aggregated by ticker.

    Args:
        equity_model: The equity model instance
        tickers: List of ticker symbols
        start_date: Start date
        end_date: End date
        limit: Limit number of results

    Returns:
        DataFrame with price measures by ticker
    """
    # Build filters as kwargs
    filter_kwargs = {}

    if start_date and end_date:
        filter_kwargs['trade_date'] = {'start': start_date, 'end': end_date}
    elif start_date:
        filter_kwargs['trade_date'] = {'start': start_date}
    elif end_date:
        filter_kwargs['trade_date'] = {'end': end_date}

    # Price measures to calculate (using correct measure names from equity.yaml)
    price_measures = {
        'avg_close': 'avg_close_price',
        'total_volume': 'total_volume',
        'max_high': 'max_high',  # Corrected: was 'max_high_price'
        'min_low': 'min_low',    # Corrected: was 'min_low_price'
        'price_range': 'price_range'
    }

    results = {}
    for label, measure_name in price_measures.items():
        try:
            result = equity_model.calculate_measure_by_ticker(
                measure_name=measure_name,
                tickers=tickers,
                limit=limit,
                **filter_kwargs
            )

            df = result.data
            if df is not None and not df.empty:
                # Rename measure column
                measure_col = [col for col in df.columns if col != 'ticker'][0]
                df = df.rename(columns={measure_col: label})
                results[label] = df

        except Exception as e:
            print(f"Warning: Could not calculate {measure_name}: {e}")

    # Merge all results on ticker
    if not results:
        return pd.DataFrame()

    merged_df = None
    for label, df in results.items():
        if merged_df is None:
            merged_df = df
        else:
            merged_df = merged_df.merge(df, on='ticker', how='outer')

    return merged_df


def compare_weighting_strategies(
    equity_model,
    tickers: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Compare all weighting strategies and return summary statistics.

    Args:
        equity_model: The equity model instance
        tickers: List of ticker symbols
        start_date: Start date
        end_date: End date

    Returns:
        Dictionary with comparison results or error info
    """
    # Get weighted indices
    indices_df = get_weighted_indices(
        equity_model,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date
    )

    if indices_df is None or indices_df.empty:
        return {
            "error": "No data available",
            "summary": {},
            "data": pd.DataFrame(),
            "date_range": None,
            "num_periods": 0
        }

    # Calculate summary statistics for each index
    summary = {}
    for col in indices_df.columns:
        if col != 'trade_date':
            summary[col] = {
                'mean': indices_df[col].mean(),
                'std': indices_df[col].std(),
                'min': indices_df[col].min(),
                'max': indices_df[col].max(),
                'latest': indices_df[col].iloc[-1] if len(indices_df) > 0 else None
            }

    return {
        'data': indices_df,
        'summary': summary,
        'date_range': {
            'start': indices_df['trade_date'].min(),
            'end': indices_df['trade_date'].max()
        },
        'num_periods': len(indices_df)
    }


# ============================================================
# EXAMPLE USAGE
# ============================================================

if __name__ == "__main__":
    print("=" * 80)
    print("Domain Strategy Measures Example")
    print("=" * 80)

    # Initialize equity model
    print("\n1. Initializing equity model...")
    equity_model = setup_equity_model()
    print("   ✓ Equity model loaded successfully")

    # Define parameters
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
    start_date = '2024-01-01'
    end_date = '2024-10-20'

    print(f"\n2. Fetching data for tickers: {', '.join(tickers)}")
    print(f"   Date range: {start_date} to {end_date}")

    # Example 1: Get weighted indices
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Weighted Index Strategies")
    print("=" * 80)

    indices_df = get_weighted_indices(
        equity_model,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date
    )

    if indices_df.empty:
        print("\n   ⚠ No data available")
        print("   Note: Build the equity model with data first:")
        print("   python scripts/build_all_models.py --models equity --max-tickers 20")
    else:
        print("\nWeighted Indices DataFrame:")
        print(indices_df.head(10))
        print(f"\nShape: {indices_df.shape}")
        print(f"Columns: {list(indices_df.columns)}")

    # Example 2: Get price measures by ticker
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Price Measures by Ticker")
    print("=" * 80)

    price_df = get_price_measures_by_ticker(
        equity_model,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        limit=10
    )

    if price_df.empty:
        print("\n   ⚠ No data available")
        print("   Note: Build the equity model with data first:")
        print("   python scripts/build_all_models.py --models equity --max-tickers 20")
    else:
        print("\nPrice Measures DataFrame:")
        print(price_df)
        print(f"\nShape: {price_df.shape}")
        print(f"Columns: {list(price_df.columns)}")

    # Example 3: Get technical indicators
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Technical Indicators")
    print("=" * 80)

    tech_indicators = get_technical_indicators(
        equity_model,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        group_by_ticker=True
    )

    if not tech_indicators:
        print("\n   ⚠ No data available")
        print("   Note: Build the equity model with data first:")
        print("   python scripts/build_all_models.py --models equity --max-tickers 20")
    else:
        for indicator_name, df in tech_indicators.items():
            print(f"\n{indicator_name}:")
            print(df.head(10))

    # Example 4: Compare weighting strategies
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Weighting Strategy Comparison")
    print("=" * 80)

    comparison = compare_weighting_strategies(
        equity_model,
        tickers=tickers,
        start_date=start_date,
        end_date=end_date
    )

    if 'error' in comparison and comparison['error']:
        print(f"\n   ⚠ {comparison['error']}")
        print("   Note: Build the equity model with data first:")
        print("   python scripts/build_all_models.py --models equity --max-tickers 20")
    else:
        print("\nSummary Statistics:")
        for strategy, stats in comparison.get('summary', {}).items():
            print(f"\n{strategy}:")
            for stat_name, value in stats.items():
                print(f"  {stat_name}: {value:,.2f}" if isinstance(value, (int, float)) else f"  {stat_name}: {value}")

    print("\n" + "=" * 80)
    print("Examples completed successfully!")
    print("=" * 80)
