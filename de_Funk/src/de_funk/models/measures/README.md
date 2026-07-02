# Measures Framework

This directory contains the de_Funk measure calculation framework. Measures are reusable calculations that can be applied to model data.

**IMPORTANT: Spark-First Design**

All domain measures use Spark DataFrames and window functions by default. Only convert to pandas at the final step when needed for UI display. This ensures scalability with large datasets.

## Architecture Overview

```
models/measures/
├── README.md              # This file
├── __init__.py            # Public exports
├── base_measure.py        # BaseMeasure abstract class, MeasureType enum
├── registry.py            # MeasureRegistry - discovers and stores measures
├── executor.py            # MeasureExecutor - runs measure calculations
├── simple.py              # SimpleMeasure - single-column aggregations
├── computed.py            # ComputedMeasure - multi-column expressions
└── domain_measures.py     # DomainMeasures - Spark-first base class for complex measures
```

## Measure Types

### 1. YAML Measures (Simple & Computed)

Defined in `configs/models/{model}/measures.yaml`. Best for declarative, SQL-expressible calculations.

**Simple Measures** - Single column aggregations:
```yaml
simple_measures:
  avg_close:
    type: simple
    source: fact_prices.close
    aggregation: avg
    format: "#,##0.00"

  total_volume:
    type: simple
    source: fact_prices.volume
    aggregation: sum
```

**Computed Measures** - Multi-column expressions:
```yaml
computed_measures:
  price_range:
    type: computed
    expression: "high - low"
    sources:
      - fact_prices.high
      - fact_prices.low

  volume_weighted_price:
    type: computed
    expression: "(close * volume) / SUM(volume)"
    sources:
      - fact_prices.close
      - fact_prices.volume
```

### 2. Python Measures (Domain-Specific)

Defined in `models/domains/{category}/{model}/measures.py`. Best for complex calculations requiring:
- Rolling windows with custom logic
- Cross-ticker calculations (correlations, rankings)
- Multi-step algorithms (technical indicators, risk metrics)
- External library integrations (numpy, scipy, sklearn)

**YAML Reference:**
```yaml
python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
      window_days: 252
```

**Python Implementation:**
```python
from models.measures import DomainMeasures

class StocksMeasures(DomainMeasures):
    def calculate_sharpe_ratio(self, ticker=None, risk_free_rate=0.045, **kwargs):
        # Implementation here
        pass
```

## When to Use Each Type

| Scenario | Measure Type | Why |
|----------|--------------|-----|
| SUM, AVG, MIN, MAX on a column | Simple | Declarative, no code needed |
| Column math (A + B, A / B) | Computed | SQL handles it efficiently |
| Rolling calculations | **Python** | Window functions need custom logic |
| Cross-entity comparisons | **Python** | Requires pivoting/grouping |
| Risk metrics (Sharpe, Beta) | **Python** | Statistical libraries needed |
| Composite scores | **Python** | Multi-step normalization |
| External API calls | **Python** | Can't do in SQL |

## Creating Domain Measures (Spark-First)

### Step 1: Create the measures.py file

Location: `models/domains/{category}/{model}/measures.py`

```python
"""
Complex measures for {model} model - Spark-first implementation.

These functions are referenced from {model}/measures.yaml via python_measures.
All calculations use Spark DataFrames and window functions.
"""

from typing import Dict, Any, Optional, List
import logging

from pyspark.sql import DataFrame as SparkDataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from models.measures import DomainMeasures

logger = logging.getLogger(__name__)


class {Model}Measures(DomainMeasures):
    """
    Complex measure calculations for {model} using Spark.

    Inherits from DomainMeasures which provides:
    - get_table(): Returns Spark DataFrame
    - ticker_window(), rolling_window(): Window helpers
    - add_returns(), add_rolling_mean(), add_rolling_std(): Calculation helpers
    - to_pandas(): Final conversion (use sparingly, only for UI)
    - log_start/log_result: Logging helpers
    """

    def calculate_my_measure(
        self,
        ticker: Optional[str] = None,
        filters: Optional[List[Dict]] = None,
        param1: float = 1.0,
        as_pandas: bool = False,  # Only True when needed for UI
        **kwargs
    ) -> SparkDataFrame:
        """
        Calculate my custom measure using Spark.

        Args:
            ticker: Optional ticker filter
            filters: Optional additional filters
            param1: Example parameter from YAML
            as_pandas: Convert to pandas (default: False)
            **kwargs: Additional runtime parameters

        Returns:
            Spark DataFrame (or pandas if as_pandas=True)
        """
        self.log_start("my_measure", ticker=ticker, param1=param1)

        # 1. Get data as Spark DataFrame
        df = self.get_table('fact_prices', ticker=ticker, filters=filters)

        # 2. Perform calculation using Spark operations
        df = df.withColumn('result', F.col('close') * param1)

        # 3. Select output columns
        result = df.select('ticker', 'trade_date', 'result')

        self.log_result("my_measure", result)

        if as_pandas:
            return self.to_pandas(result)
        return result
```

### Step 2: Reference in YAML

Add to `configs/models/{model}/measures.yaml`:

```yaml
python_measures:
  my_measure:
    function: "{model}.measures.calculate_my_measure"
    description: "Description of what this measure calculates"
    params:
      param1: 1.0
    output_columns:
      - ticker
      - trade_date
      - result
```

### Step 3: Wire up in model (if needed)

If your model doesn't auto-load measures, add to the model class:

```python
from models.domains.{category}.{model}.measures import {Model}Measures

class {Model}Model(BaseModel):
    def __init__(self, ...):
        super().__init__(...)
        self._measures = {Model}Measures(self)

    def calculate_measure(self, measure_name: str, **kwargs):
        method = getattr(self._measures, f"calculate_{measure_name}", None)
        if method:
            return method(**kwargs)
        return super().calculate_measure(measure_name, **kwargs)
```

## DomainMeasures Base Class (Spark-First)

The `DomainMeasures` class provides Spark-native utilities:

### Data Access

```python
# Get table as Spark DataFrame (NOT pandas)
df = self.get_table('fact_prices', ticker='AAPL')

# Get table with filters
filters = [{'column': 'trade_date', 'operator': '>=', 'value': '2024-01-01'}]
df = self.get_table('fact_prices', filters=filters)

# Get Spark session
spark = self.get_spark()
```

### Window Helpers

```python
# Basic ticker window (partition by ticker, order by date)
window = self.ticker_window()

# Rolling window (e.g., 20-day)
window = self.rolling_window(window_size=20)

# Expanding (cumulative) window
window = self.expanding_window()
```

### Spark Calculation Utilities

```python
# Add returns column
df = self.add_returns(df, price_col='close', log_returns=False)

# Add rolling mean
df = self.add_rolling_mean(df, 'close', window_size=20)
# Creates column: close_sma_20

# Add rolling std
df = self.add_rolling_std(df, 'returns', window_size=20)
# Creates column: returns_std_20

# Add rolling/cumulative max (for drawdown)
df = self.add_rolling_max(df, 'close', window_size=252)
df = self.add_cumulative_max(df, 'close')

# Normalize column to [0, 1]
df = self.normalize_column(df, 'rsi', min_val=0, max_val=1)
```

### Final Conversion (for UI)

```python
# When needed for UI (Streamlit, Plotly)
pandas_df = self.to_pandas(spark_df)

# With optional limit
pandas_df = self.to_pandas(spark_df, limit=1000)
```

### Logging

```python
# Log start with parameters
self.log_start("sharpe_ratio", ticker=ticker, window=252)

# Log result summary (accepts Spark DataFrame)
self.log_result("sharpe_ratio", result_df)
# Output: "sharpe_ratio: 1,234 rows, columns: ['ticker', 'trade_date', 'sharpe_ratio']"
```

## Best Practices

### 1. Use Spark Throughout (No Early Pandas Conversion)

```python
# GOOD: Keep as Spark DataFrame, use Spark operations
df = self.get_table('fact_prices')
df = df.withColumn('result', F.col('close') * 2)
df = df.select('ticker', 'trade_date', 'result')

# BAD: Converting to pandas early
df = self.get_table('fact_prices')
pandas_df = df.toPandas()  # DON'T DO THIS
pandas_df['result'] = pandas_df['close'] * 2
```

### 2. Use Window Functions (Not Pandas Rolling)

```python
# GOOD: Spark window functions
window = self.rolling_window(window_size=20)
df = df.withColumn('sma', F.avg('close').over(window))

# BAD: Pandas rolling (defeats Spark parallelism)
pdf = df.toPandas()
pdf['sma'] = pdf.groupby('ticker')['close'].rolling(20).mean()
```

### 3. Support Filtering Consistently

```python
def calculate_measure(
    self,
    ticker: Optional[str] = None,         # Single ticker filter
    filters: Optional[List[Dict]] = None, # General filters
    as_pandas: bool = False,              # Only True for UI
    **kwargs                              # YAML params + runtime overrides
) -> SparkDataFrame:
```

### 4. Return Spark DataFrame by Default

```python
# Return Spark DataFrame (default)
return df.select('ticker', 'trade_date', 'measure_value')

# Only convert to pandas when caller needs it for UI
if as_pandas:
    return self.to_pandas(df)
return df
```

### 5. Handle Edge Cases with Spark

```python
# Handle nulls
df = df.filter(F.col('close').isNotNull())

# Handle division by zero
df = df.withColumn(
    'ratio',
    F.when(F.col('b') != 0, F.col('a') / F.col('b')).otherwise(None)
)

# Coalesce nulls
df = df.withColumn('value', F.coalesce(F.col('value'), F.lit(0)))
```

### 6. Use YAML Params with Runtime Overrides

```yaml
# YAML default
params:
  window_days: 252
```

```python
# Runtime override
result = model.calculate_measure('sharpe_ratio', window_days=60, as_pandas=True)
```

## Real-World Examples

See `models/domains/securities/stocks/measures.py` for complete Spark implementations:

- `calculate_sharpe_ratio()` - Rolling Sharpe using window functions
- `calculate_drawdown()` - Peak-to-trough using cumulative max
- `calculate_rolling_beta()` - Beta via covariance/variance windows
- `calculate_momentum_score()` - Composite score with normalization
- `calculate_volatility_regime()` - Regime classification (LOW/NORMAL/HIGH)
- `calculate_relative_strength()` - Relative performance vs benchmark

## Testing Measures

```python
# Unit test example with Spark
def test_sharpe_ratio_calculation():
    # Arrange
    model = create_test_model()
    measures = StocksMeasures(model)

    # Act - returns Spark DataFrame by default
    result = measures.calculate_sharpe_ratio(ticker='AAPL', window_days=60)

    # Assert on Spark DataFrame
    assert 'ticker' in result.columns
    assert 'sharpe_ratio' in result.columns
    assert result.count() > 0

    # Or convert to pandas for detailed assertions
    pdf = result.toPandas()
    assert pdf['sharpe_ratio'].notna().any()
```

## Troubleshooting

### "Table not found" error

Check that the table name matches your model's schema:
```python
# Check available tables
print(self.model.tables.keys())
```

### Spark session issues

Ensure Spark is available:
```python
spark = self.get_spark()
# This will create a session if not available
```

### Filter not applying

Filters require a session with filter engine:
```python
if self.model.session:
    df = self.model.session.apply_filters(df, filters)
else:
    # Manual Spark filtering fallback
    for f in filters:
        df = df.filter(F.col(f['column']) == f['value'])
```

### Performance issues

Use Spark operations, not pandas:
```python
# GOOD: Let Spark handle parallelism
df = df.withColumn('sma', F.avg('close').over(window))

# BAD: Converting to pandas kills parallelism
pdf = df.toPandas()
pdf['sma'] = pdf['close'].rolling(20).mean()
```
