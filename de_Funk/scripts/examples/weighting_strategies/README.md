# Weighting Strategies Examples

This directory contains examples of using parameter-driven calculations for weighted price indices.

## Overview

These examples show how to calculate weighted prices using simple parameter dictionaries. No complex code needed - just specify your tickers, dates, and weighting strategy, and get results!

## Quick Start

```python
from scripts.examples.parameter_interface import MeasureCalculator

# Initialize calculator
calc = MeasureCalculator(backend='duckdb')

# Define parameters
params = {
    'model': 'equity',
    'measure': 'volume_weighted_index',
    'tickers': ['AAPL', 'MSFT', 'GOOGL'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
}

# Run calculation
result = calc.calculate(params)

# Access results
print(result.data)
print(result.summary())
```

## Available Weighting Strategies

| Strategy | Measure Name | Description | Use Case |
|----------|--------------|-------------|----------|
| **Equal** | `equal_weighted_index` | Simple average, all stocks weighted equally | Unbiased portfolio view |
| **Volume** | `volume_weighted_index` | Weighted by trading volume | Understand market participation |
| **Market Cap** | `market_cap_weighted_index` | Weighted by company size (like S&P 500) | Large-cap focused analysis |
| **Price** | `price_weighted_index` | Weighted by stock price (like DJIA) | Price-sensitive portfolios |
| **Volume Deviation** | `volume_deviation_weighted_index` | Weighted by unusual trading activity | Detect market anomalies |
| **Volatility** | `volatility_weighted_index` | Inverse volatility (risk-adjusted) | Risk-balanced portfolios |

## Example Files

### 01_basic_weighted_price.py
Basic examples showing how to:
- Calculate volume-weighted price for tickers
- Use single or multiple tickers
- Apply date filters
- Compare weighted vs unweighted

**Run it:**
```bash
python -m scripts.examples.weighting_strategies.01_basic_weighted_price
```

### 02_compare_all_strategies.py
Advanced examples showing how to:
- Compare all weighting strategies
- Find best performing strategy
- Test different portfolios
- Use built-in comparison methods

**Run it:**
```bash
python -m scripts.examples.weighting_strategies.02_compare_all_strategies
```

## Parameter Reference

### Required Parameters
- `model`: Model name (typically `'equity'`)
- `measure`: Weighting strategy measure name (see table above)

### Optional Parameters
- `tickers`: List of ticker symbols (e.g., `['AAPL', 'MSFT']`) or single ticker string
- `start_date`: Start date in YYYY-MM-DD format (e.g., `'2024-01-01'`)
- `end_date`: End date in YYYY-MM-DD format (e.g., `'2024-12-31'`)
- `limit`: Maximum number of results
- `backend`: `'duckdb'` (default, fast) or `'spark'`

## Common Use Cases

### Portfolio Analysis
Compare different weighting methods for your portfolio:
```python
results = calc.calculate_with_comparison(
    model='equity',
    measures=[
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index'
    ],
    tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

### Risk-Adjusted Returns
Use volatility weighting for risk-adjusted portfolios:
```python
params = {
    'model': 'equity',
    'measure': 'volatility_weighted_index',
    'tickers': ['AAPL', 'MSFT', 'GOOGL'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
}
result = calc.calculate(params)
```

### Market Participation Analysis
Track trading activity with volume weighting:
```python
params = {
    'model': 'equity',
    'measure': 'volume_weighted_index',
    'tickers': ['AAPL', 'MSFT'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
}
result = calc.calculate(params)
```

## Tips

1. **Start simple**: Use `equal_weighted_index` first to understand the data
2. **Compare strategies**: Different strategies can produce very different results
3. **Watch for data gaps**: Not all tickers have data for all dates
4. **Use appropriate time ranges**: Longer ranges may have missing data
5. **Check for errors**: Always check `result.error` before using `result.data`

## Need Help?

- **Discover measures**: `calc.list_measures('equity')`
- **Get measure info**: `calc.get_measure_info('equity', 'volume_weighted_index')`
- **See parameter help**: Use the parameter discovery module

```python
from scripts.examples.parameter_interface.discovery import print_parameter_help
print_parameter_help('equity', 'volume_weighted_index')
```

## Related Examples

- `../measure_calculations/` - Basic measure calculation examples
- `../parameter_interface/` - Core parameter interface modules
- `../backend_comparison/` - Compare DuckDB vs Spark performance
