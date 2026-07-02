# de_Funk Examples - Parameter-Driven Calculations

Welcome to the de_Funk examples directory! This is your guide to using the parameter-driven calculation interface for measure calculations.

## 🚀 Quick Start

```python
from scripts.examples.parameter_interface import MeasureCalculator

# Initialize calculator
calc = MeasureCalculator(backend='duckdb')

# Calculate weighted price for stocks
result = calc.calculate({
    'model': 'equity',
    'measure': 'volume_weighted_index',
    'tickers': ['AAPL', 'MSFT', 'GOOGL'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
})

# Access results
print(result.data)
print(result.summary())
```

**Start here:** Run `python -m scripts.examples.00_QUICKSTART` for a guided tour!

## 📁 Directory Structure

```
scripts/examples/
├── 00_QUICKSTART.py                 # ⭐ START HERE - Guided examples
├── README.md                        # This file
│
├── parameter_interface/             # Core calculation interface
│   ├── __init__.py                 # Main exports
│   ├── calculator.py               # MeasureCalculator class
│   ├── validators.py               # Parameter validation
│   └── discovery.py                # Measure discovery tools
│
├── weighting_strategies/            # Weighted calculations
│   ├── README.md                   # Weighting guide
│   ├── 01_basic_weighted_price.py  # Basic weighted examples
│   └── 02_compare_all_strategies.py # Compare strategies
│
├── measure_calculations/            # Measure framework examples
│   ├── 01_basic_measures.py        # Simple calculations
│   ├── 02_troubleshooting.py       # Debug guide
│   ├── 03_domain_strategies.py     # Domain-specific measures
│   ├── 04_auto_enrich_demo.py      # Auto-enrichment demo
│   └── 05_auto_enrich_example.py   # Auto-enrichment examples
│
├── queries/                         # Query system examples
│   ├── README.md                   # Query examples guide
│   ├── 01_auto_join.py             # Transparent auto-join
│   ├── 02_query_planner.py         # Dynamic join planning
│   └── 03_session_queries.py       # UniversalSession queries
│
├── extending/                       # Developer extension examples
│   ├── README.md                   # Extension guide
│   ├── custom_facet.py             # Custom data transformations
│   ├── custom_model.py             # Custom domain models
│   ├── custom_provider.py          # Custom data providers
│   └── custom_notebook.md          # Custom notebooks
│
├── backend_comparison/              # DuckDB vs Spark
│   └── 01_dual_backend.py          # Backend compatibility
│
└── model_usage/                     # Model-specific examples
    └── (model-specific examples)
```

## 📚 What's New

This reorganization introduces:

1. **Parameter-Driven Interface**: Use simple dictionaries instead of complex code
2. **Easy Discovery**: Find available models, measures, and parameters
3. **Built-in Validation**: Parameter validation with helpful error messages
4. **Weighted Calculations**: Simplified interface for weighting strategies
5. **Testing Integration**: All examples are tested automatically

## 🎯 Key Features

### Parameter-Driven Calculations

**Before:**
```python
# Old way - complex code
from models.implemented.equity.model import EquityModel
model = EquityModel(connection, storage, repo)
result = model.calculate_measure(
    'volume_weighted_index',
    filters={'ticker': ['AAPL', 'MSFT']},
    # ... more complex setup
)
```

**After:**
```python
# New way - simple parameters
calc = MeasureCalculator(backend='duckdb')
result = calc.calculate({
    'model': 'equity',
    'measure': 'volume_weighted_index',
    'tickers': ['AAPL', 'MSFT'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
})
```

### Easy Discovery

```python
# What models are available?
models = calc.list_models()
print(models)  # ['equity', 'corporate', 'macro', ...]

# What can I calculate with the equity model?
measures = calc.list_measures('equity')
print(measures)  # ['avg_close_price', 'volume_weighted_index', ...]

# What parameters does this measure need?
from scripts.examples.parameter_interface.discovery import print_parameter_help
print_parameter_help('equity', 'volume_weighted_index')
```

### Compare Strategies Easily

```python
# Compare multiple weighting strategies in one call
results = calc.calculate_with_comparison(
    model='equity',
    measures=[
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index'
    ],
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)

for strategy, result in results.items():
    print(f"{strategy}: {result.summary()}")
```

## 📖 Example Categories

### 1. Weighting Strategies (`weighting_strategies/`)

**Focus:** Calculate weighted prices for stocks using different strategies

**Examples:**
- Volume-weighted prices (high volume = high weight)
- Market cap weighted (like S&P 500)
- Equal weighted (simple average)
- Volatility weighted (risk-adjusted)
- Compare all strategies

**Use Cases:**
- Portfolio analysis
- Index construction
- Risk-adjusted returns
- Market participation tracking

**Run:** `python -m scripts.examples.weighting_strategies.01_basic_weighted_price`

### 2. Measure Calculations (`measure_calculations/`)

**Focus:** Basic measure framework usage

**Examples:**
- Simple measures (AVG, SUM, COUNT)
- Computed measures (expressions)
- Weighted measures
- Domain-specific strategies
- Troubleshooting guide

**Use Cases:**
- Understanding the measure framework
- Debugging measure calculations
- Learning measure types

**Run:** `python -m scripts.examples.measure_calculations.01_basic_measures`

### 3. Parameter Interface (`parameter_interface/`)

**Focus:** Core calculation interface modules

**Contents:**
- `calculator.py` - Main MeasureCalculator class
- `validators.py` - Parameter validation
- `discovery.py` - Measure and parameter discovery

**Use Cases:**
- Building custom tools on top of de_Funk
- Parameter validation
- Dynamic measure discovery

**Import:** `from scripts.examples.parameter_interface import MeasureCalculator`

### 4. Query System (`queries/`)

**Focus:** Query capabilities and cross-model joins

**Examples:**
- Transparent auto-join functionality
- Dynamic join planning with GraphQueryPlanner
- UniversalSession for ad-hoc queries
- Cross-model queries and joins

**Use Cases:**
- Understanding query system architecture
- Building complex analytical queries
- Leveraging automatic join detection
- Model-agnostic data access

**Run:** `python -m scripts.examples.queries.01_auto_join`

### 5. Extending de_Funk (`extending/`)

**Focus:** Developer examples for extending the framework

**Examples:**
- Custom facets for data transformations
- Custom domain models
- Custom data providers
- Custom analysis notebooks

**Use Cases:**
- Adding new data sources
- Implementing domain-specific models
- Creating custom pipelines
- Building specialized analytics

**See:** `scripts/examples/extending/README.md` for detailed guide

### 6. Backend Comparison (`backend_comparison/`)

**Focus:** Compare DuckDB vs Spark performance

**Examples:**
- Dual backend calculations
- Performance benchmarking
- Backend-specific features

**Use Cases:**
- Choosing the right backend
- Performance optimization
- Understanding backend differences

## 🔧 Parameter Reference

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `model` | str | Model name | `'equity'`, `'corporate'` |
| `measure` | str | Measure to calculate | `'avg_close_price'` |

### Optional Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `tickers` | list[str] or str | Stock tickers | `['AAPL', 'MSFT']` |
| `start_date` | str | Start date (YYYY-MM-DD) | `'2024-01-01'` |
| `end_date` | str | End date (YYYY-MM-DD) | `'2024-12-31'` |
| `entity_column` | str | Column to group by | `'ticker'` |
| `limit` | int | Max results | `10` |
| `backend` | str | Backend to use | `'duckdb'`, `'spark'` |
| `additional_filters` | dict | Extra filters | `{'sector': 'tech'}` |

## 🎓 Learning Path

### Beginner: Start Here
1. **Run `00_QUICKSTART.py`** - Guided examples
2. **Explore `weighting_strategies/01_basic_weighted_price.py`** - Simple weighted calculations
3. **Read `weighting_strategies/README.md`** - Understanding weighting

### Intermediate: Deep Dive
1. **Study `measure_calculations/01_basic_measures.py`** - Measure framework
2. **Run `weighting_strategies/02_compare_all_strategies.py`** - Strategy comparison
3. **Review `measure_calculations/02_troubleshooting.py`** - Debug skills

### Advanced: Build Your Own
1. **Explore `parameter_interface/` modules** - Core interface
2. **Study `calculator.py`** - Calculator implementation
3. **Use `discovery.py`** - Build discovery tools

## 🧪 Testing

All examples are tested automatically:

```bash
# Run example tests
pytest scripts/test/validation/test_examples.py -v

# Run specific test class
pytest scripts/test/validation/test_examples.py::TestWeightedCalculations -v

# Run with coverage
pytest scripts/test/validation/test_examples.py --cov=scripts.examples
```

## 💡 Common Use Cases

### Portfolio Analysis
```python
# Analyze your portfolio with different strategies
calc = MeasureCalculator()
my_portfolio = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']

results = calc.calculate_with_comparison(
    model='equity',
    measures=[
        'equal_weighted_index',
        'volume_weighted_index',
        'market_cap_weighted_index'
    ],
    tickers=my_portfolio,
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

### Risk-Adjusted Returns
```python
# Use volatility weighting for risk-adjusted portfolios
result = calc.calculate({
    'model': 'equity',
    'measure': 'volatility_weighted_index',
    'tickers': ['AAPL', 'MSFT', 'GOOGL'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
})
```

### Market Participation
```python
# Track trading activity with volume weighting
result = calc.calculate({
    'model': 'equity',
    'measure': 'volume_weighted_index',
    'tickers': ['AAPL', 'MSFT'],
    'start_date': '2024-01-01',
    'end_date': '2024-12-31'
})
```

### Price Analysis
```python
# Get basic price measures by ticker
result = calc.calculate({
    'model': 'equity',
    'measure': 'avg_close_price',
    'tickers': ['AAPL', 'MSFT', 'GOOGL'],
    'entity_column': 'ticker',
    'limit': 10
})
```

## 🐛 Troubleshooting

### "Model not found" error
```python
# List available models
models = calc.list_models()
print(f"Available models: {models}")

# Build the model if missing
# python -m scripts.build.build_all_models
```

### "Measure not found" error
```python
# List measures for a model
measures = calc.list_measures('equity')
print(f"Available measures: {measures}")
```

### "No data available" error
- Ensure you have built the model: `python -m scripts.build.build_all_models`
- Check date range (data may not exist for all dates)
- Verify tickers exist in the dataset

### Parameter validation errors
```python
# Get parameter help
from scripts.examples.parameter_interface.discovery import print_parameter_help
print_parameter_help('equity', 'volume_weighted_index')

# Get validation hints
from scripts.examples.parameter_interface.validators import get_validation_hints
print(get_validation_hints('start_date'))
```

## 📝 Tips & Best Practices

1. **Start with DuckDB backend** - It's 10-100x faster than Spark for analytics
2. **Use parameter validation** - Catch errors early with `validate_params()`
3. **Check for errors first** - Always check `result.error` before using `result.data`
4. **Limit results for testing** - Use `limit` parameter to speed up testing
5. **Compare strategies** - Different strategies can produce very different results
6. **Use discovery tools** - `list_models()`, `list_measures()`, `print_parameter_help()`

## 🔗 Related Documentation

- **Main docs:** See `/CLAUDE.md` for comprehensive system documentation
- **Model reference:** See `/configs/models/*.yaml` for model definitions
- **Pipeline guide:** See `/PIPELINE_GUIDE.md` for data pipeline information
- **Testing guide:** See `/TESTING_GUIDE.md` for testing best practices

## 🤝 Contributing

When adding new examples:

1. **Follow the pattern** - Use parameter-driven interface
2. **Add tests** - Update `scripts/test/validation/test_examples.py`
3. **Document** - Add docstrings and comments
4. **Update README** - Keep this file current

## ❓ Need Help?

- **Quick help:** Run `python -m scripts.examples.00_QUICKSTART`
- **Parameter help:** Use `print_parameter_help(model, measure)`
- **Measure catalog:** Use `print_measure_catalog()` from discovery module
- **Issues:** Report in GitHub issues

---

**Happy calculating! 🎉**
