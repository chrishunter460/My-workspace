"""
Generate realistic sample data for testing.

Provides utilities to create test datasets that mimic real market data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_price_data(
    tickers: list,
    start_date: str = '2024-01-01',
    num_days: int = 30,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate realistic stock price data.

    Args:
        tickers: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        num_days: Number of trading days
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(seed)

    records = []
    base_date = datetime.strptime(start_date, '%Y-%m-%d')

    # Base prices for each ticker
    base_prices = {
        'AAPL': 150.0,
        'MSFT': 350.0,
        'GOOGL': 120.0,
        'AMZN': 140.0,
        'TSLA': 200.0,
        'META': 300.0,
        'NVDA': 450.0,
        'JPM': 150.0,
        'JNJ': 160.0,
        'V': 250.0
    }

    for ticker in tickers:
        base_price = base_prices.get(ticker, 100.0)
        price = base_price

        for day in range(num_days):
            trade_date = base_date + timedelta(days=day)

            # Random walk with drift
            daily_return = np.random.normal(0.001, 0.02)
            price = price * (1 + daily_return)

            # OHLC generation
            daily_range = abs(np.random.normal(0, 0.015)) * price
            open_price = price + np.random.uniform(-daily_range/2, daily_range/2)
            high = max(open_price, price) + np.random.uniform(0, daily_range/2)
            low = min(open_price, price) - np.random.uniform(0, daily_range/2)
            close = price

            # Volume (log-normal distribution)
            base_volume = 1_000_000 if ticker in ['AAPL', 'MSFT'] else 500_000
            volume = int(np.random.lognormal(np.log(base_volume), 0.3))

            # VWAP approximation
            vwap = (high + low + close) / 3

            records.append({
                'trade_date': trade_date.strftime('%Y-%m-%d'),
                'ticker': ticker,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume,
                'volume_weighted': round(vwap, 2)
            })

    return pd.DataFrame(records)


def generate_company_data(tickers: list) -> pd.DataFrame:
    """
    Generate company dimension data.

    Args:
        tickers: List of ticker symbols

    Returns:
        DataFrame with company info
    """
    company_names = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corporation',
        'GOOGL': 'Alphabet Inc.',
        'AMZN': 'Amazon.com Inc.',
        'TSLA': 'Tesla Inc.',
        'META': 'Meta Platforms Inc.',
        'NVDA': 'NVIDIA Corporation',
        'JPM': 'JPMorgan Chase & Co.',
        'JNJ': 'Johnson & Johnson',
        'V': 'Visa Inc.'
    }

    records = []
    for ticker in tickers:
        records.append({
            'ticker': ticker,
            'company_name': company_names.get(ticker, f'{ticker} Corporation'),
            'exchange_code': 'NASDAQ',
            'company_id': f'sha1_{ticker.lower()}'
        })

    return pd.DataFrame(records)


def generate_etf_holdings(
    etf_ticker: str,
    holdings_tickers: list,
    as_of_date: str = '2024-01-01',
    total_aum: float = 1_000_000_000
) -> pd.DataFrame:
    """
    Generate ETF holdings data with realistic weights.

    Args:
        etf_ticker: ETF ticker symbol
        holdings_tickers: List of underlying holdings
        as_of_date: Holdings snapshot date
        total_aum: Total assets under management

    Returns:
        DataFrame with holdings data
    """
    # Generate random weights that sum to ~100%
    num_holdings = len(holdings_tickers)
    weights = np.random.dirichlet(np.ones(num_holdings)) * 100

    records = []
    for ticker, weight in zip(holdings_tickers, weights):
        market_value = total_aum * (weight / 100)

        records.append({
            'etf_ticker': etf_ticker,
            'holding_ticker': ticker,
            'as_of_date': as_of_date,
            'weight_percent': round(weight, 2),
            'shares_held': int(market_value / 150),  # Assume $150 avg price
            'market_value': round(market_value, 2)
        })

    return pd.DataFrame(records)


def generate_etf_prices(
    etf_ticker: str,
    start_date: str = '2024-01-01',
    num_days: int = 30,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate ETF price data with NAV.

    Args:
        etf_ticker: ETF ticker symbol
        start_date: Start date
        num_days: Number of trading days
        seed: Random seed

    Returns:
        DataFrame with ETF price data
    """
    # Generate base prices
    price_data = generate_price_data([etf_ticker], start_date, num_days, seed)

    # Add NAV and premium/discount
    np.random.seed(seed)
    price_data['nav'] = price_data['close'] * (1 + np.random.normal(0, 0.001, len(price_data)))
    price_data['premium_discount'] = ((price_data['close'] - price_data['nav']) / price_data['nav'] * 100).round(4)

    # Rename ticker column
    price_data = price_data.rename(columns={'ticker': 'etf_ticker'})

    return price_data


def save_test_data(output_dir: str):
    """
    Generate and save complete test dataset.

    Args:
        output_dir: Directory to save test data

    Example:
        save_test_data('tests/fixtures/data')
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Generate data
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

    prices = generate_price_data(tickers, num_days=60)
    companies = generate_company_data(tickers)
    etf_holdings = generate_etf_holdings('SPY', tickers)
    etf_prices = generate_etf_prices('SPY', num_days=60)

    # Save to CSV
    prices.to_csv(f'{output_dir}/prices.csv', index=False)
    companies.to_csv(f'{output_dir}/companies.csv', index=False)
    etf_holdings.to_csv(f'{output_dir}/etf_holdings.csv', index=False)
    etf_prices.to_csv(f'{output_dir}/etf_prices.csv', index=False)

    print(f"✓ Generated test data in {output_dir}/")
    print(f"  - {len(prices)} price records")
    print(f"  - {len(companies)} companies")
    print(f"  - {len(etf_holdings)} ETF holdings")
    print(f"  - {len(etf_prices)} ETF price records")


if __name__ == '__main__':
    # Generate sample data when run directly
    save_test_data('tests/fixtures/data')
