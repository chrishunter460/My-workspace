"""
UniversalSession Query Examples for de_Funk

This example demonstrates how to use UniversalSession for ad-hoc data analysis.

UniversalSession provides:
- Model-agnostic data access
- Cross-model queries and joins
- Pandas integration for analysis
- Flexible filtering and aggregation

Based on: models/api/session.py

Author: de_Funk Team
Date: 2024-11-08
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from pyspark.sql import SparkSession, functions as F
from de_funk.models.api.session import UniversalSession


# ============================================================
# SETUP
# ============================================================

def create_session():
    """
    Initialize Spark and UniversalSession for examples.

    Returns:
        UniversalSession instance
    """
    # Initialize Spark
    spark = SparkSession.builder \
        .appName("SessionQueryExamples") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()

    # Storage configuration
    storage_cfg = {
        "roots": {
            "bronze": "storage/bronze",
            "company_silver": "storage/silver/company",
            "macro_silver": "storage/silver/macro",
            "city_finance_silver": "storage/silver/city_finance",
            "forecast_silver": "storage/silver/forecast"
        }
    }

    # Repository root
    repo_root = get_repo_root()

    # Create UniversalSession
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root,
        models=['company', 'macro', 'city_finance']  # Pre-load these models
    )

    return session


# ============================================================
# EXAMPLE 1: BASIC TABLE ACCESS
# ============================================================

def example_1_basic_table_access(session: UniversalSession):
    """
    Example 1: Basic table access from single model.

    Demonstrates:
    - Loading models
    - Getting tables
    - Basic filtering
    - Displaying results
    """
    print("=" * 70)
    print("EXAMPLE 1: Basic Table Access")
    print("=" * 70)

    # Access a table from company model
    print("\n1. Get stock prices from company model...")
    prices = session.get_table('company', 'fact_prices')

    print(f"   Total records: {prices.count():,}")
    print("\n   Schema:")
    prices.printSchema()

    print("\n   Sample data:")
    prices.show(5)

    # Filter by ticker
    print("\n2. Filter by ticker (AAPL)...")
    aapl_prices = prices.filter(prices.ticker == 'AAPL')
    print(f"   AAPL records: {aapl_prices.count():,}")
    aapl_prices.show(5)

    # Filter by date range
    print("\n3. Filter by date range...")
    recent_prices = prices.filter(
        (prices.trade_date >= '2024-01-01') &
        (prices.trade_date <= '2024-01-31')
    )
    print(f"   Records in date range: {recent_prices.count():,}")
    recent_prices.show(5)

    # Get dimension data
    print("\n4. Get company dimension...")
    companies = session.get_table('company', 'dim_company')
    print(f"   Companies: {companies.count():,}")
    companies.show(5)


# ============================================================
# EXAMPLE 2: AGGREGATIONS AND GROUPING
# ============================================================

def example_2_aggregations(session: UniversalSession):
    """
    Example 2: Aggregations and grouping.

    Demonstrates:
    - Group by operations
    - Aggregation functions
    - Sorting results
    - Window functions
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Aggregations and Grouping")
    print("=" * 70)

    prices = session.get_table('company', 'fact_prices')

    # Example 2.1: Average price by ticker
    print("\n1. Calculate average price by ticker...")
    avg_prices = prices.groupBy('ticker').agg(
        F.avg('close').alias('avg_close'),
        F.count('*').alias('trade_days')
    ).orderBy(F.desc('avg_close'))

    print("\n   Top 10 by average price:")
    avg_prices.show(10)

    # Example 2.2: Daily statistics
    print("\n2. Calculate daily statistics across all stocks...")
    daily_stats = prices.groupBy('trade_date').agg(
        F.count('ticker').alias('stocks_traded'),
        F.avg('close').alias('avg_close'),
        F.sum('volume').alias('total_volume')
    ).orderBy('trade_date')

    print("\n   Daily market statistics:")
    daily_stats.show(10)

    # Example 2.3: Moving average using window functions
    print("\n3. Calculate 5-day moving average...")
    from pyspark.sql.window import Window

    window_spec = Window.partitionBy('ticker').orderBy('trade_date').rowsBetween(-4, 0)

    prices_with_ma = prices.withColumn(
        'ma_5d',
        F.avg('close').over(window_spec)
    ).select('trade_date', 'ticker', 'close', 'ma_5d')

    print("\n   Prices with 5-day moving average:")
    prices_with_ma.filter(prices_with_ma.ticker == 'AAPL').show(10)

    # Example 2.4: Rank stocks by volume
    print("\n4. Rank stocks by total volume...")
    volume_ranks = prices.groupBy('ticker').agg(
        F.sum('volume').alias('total_volume')
    ).withColumn(
        'rank',
        F.dense_rank().over(Window.orderBy(F.desc('total_volume')))
    ).orderBy('rank')

    print("\n   Top 10 stocks by volume:")
    volume_ranks.show(10)


# ============================================================
# EXAMPLE 3: CROSS-MODEL QUERIES
# ============================================================

def example_3_cross_model_queries(session: UniversalSession):
    """
    Example 3: Querying data from multiple models.

    Demonstrates:
    - Accessing multiple models
    - Joining data across models
    - Cross-model analysis
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Cross-Model Queries")
    print("=" * 70)

    # Example 3.1: Get data from different models
    print("\n1. Access data from multiple models...")

    prices = session.get_table('company', 'fact_prices')
    macro = session.get_table('macro', 'fact_employment')

    print(f"   Stock prices: {prices.count():,} records")
    print(f"   Macro indicators: {macro.count():,} records")

    # Example 3.2: Join stock prices with macro indicators
    print("\n2. Join stock prices with unemployment rate...")

    # Prepare company data (aggregate by date)
    daily_market = prices.groupBy('trade_date').agg(
        F.avg('close').alias('avg_stock_price'),
        F.sum('volume').alias('total_volume')
    )

    # Prepare macro data
    unemployment = macro.filter(
        macro.indicator_name == 'unemployment_rate'
    ).select(
        F.col('report_date').alias('trade_date'),
        F.col('value').alias('unemployment_rate')
    )

    # Join on date
    combined = daily_market.join(
        unemployment,
        on='trade_date',
        how='left'
    ).orderBy('trade_date')

    print("\n   Market performance with unemployment rate:")
    combined.show(10)

    # Example 3.3: Correlation analysis
    print("\n3. Calculate correlation between stocks and macro indicators...")

    # Calculate correlation
    correlation = combined.stat.corr('avg_stock_price', 'unemployment_rate')
    print(f"\n   Correlation (stock price vs unemployment): {correlation:.4f}")


# ============================================================
# EXAMPLE 4: COMPLEX FILTERS
# ============================================================

def example_4_complex_filters(session: UniversalSession):
    """
    Example 4: Complex filtering patterns.

    Demonstrates:
    - Multiple conditions
    - OR conditions
    - IN filters
    - Null handling
    - String matching
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Complex Filters")
    print("=" * 70)

    prices = session.get_table('company', 'fact_prices')
    companies = session.get_table('company', 'dim_company')

    # Example 4.1: Multiple AND conditions
    print("\n1. Filter with multiple AND conditions...")
    filtered = prices.filter(
        (prices.ticker == 'AAPL') &
        (prices.trade_date >= '2024-01-01') &
        (prices.volume > 50000000)
    )
    print(f"   Matching records: {filtered.count():,}")
    filtered.show(5)

    # Example 4.2: OR conditions
    print("\n2. Filter with OR conditions...")
    tech_stocks = prices.filter(
        (prices.ticker == 'AAPL') |
        (prices.ticker == 'MSFT') |
        (prices.ticker == 'GOOGL')
    )
    print(f"   Tech stock records: {tech_stocks.count():,}")

    # Example 4.3: IN filter (more concise)
    print("\n3. Filter with IN clause...")
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    tech_stocks_in = prices.filter(prices.ticker.isin(tickers))
    print(f"   Records for {len(tickers)} tickers: {tech_stocks_in.count():,}")

    # Example 4.4: Range filters
    print("\n4. Filter by value range...")
    mid_priced = prices.filter(
        (prices.close >= 100) &
        (prices.close <= 200)
    )
    print(f"   Mid-priced stocks ($100-$200): {mid_priced.count():,}")

    # Example 4.5: String matching
    print("\n5. String pattern matching...")
    apple_companies = companies.filter(
        companies.company_name.contains('Apple')
    )
    print(f"   Companies with 'Apple' in name: {apple_companies.count():,}")
    apple_companies.show()

    # Example 4.6: Null handling
    print("\n6. Handle null values...")
    non_null = prices.filter(prices.close.isNotNull())
    print(f"   Records with non-null close: {non_null.count():,}")


# ============================================================
# EXAMPLE 5: PANDAS INTEGRATION
# ============================================================

def example_5_pandas_integration(session: UniversalSession):
    """
    Example 5: Converting to Pandas for analysis.

    Demonstrates:
    - Spark to Pandas conversion
    - Pandas operations
    - Plotting with matplotlib/seaborn
    - Statistical analysis
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Pandas Integration")
    print("=" * 70)

    prices = session.get_table('company', 'fact_prices')

    # Example 5.1: Convert to Pandas
    print("\n1. Convert Spark DataFrame to Pandas...")

    # Filter to manageable size first
    aapl_prices = prices.filter(
        (prices.ticker == 'AAPL') &
        (prices.trade_date >= '2024-01-01') &
        (prices.trade_date <= '2024-01-31')
    )

    # Convert to Pandas
    pdf = aapl_prices.toPandas()
    print(f"   Pandas DataFrame shape: {pdf.shape}")
    print("\n   First few rows:")
    print(pdf.head())

    # Example 5.2: Pandas operations
    print("\n2. Pandas statistical analysis...")
    print("\n   Descriptive statistics:")
    print(pdf[['open', 'high', 'low', 'close', 'volume']].describe())

    # Example 5.3: Calculate daily returns
    print("\n3. Calculate daily returns...")
    pdf = pdf.sort_values('trade_date')
    pdf['daily_return'] = pdf['close'].pct_change()
    print("\n   Daily returns:")
    print(pdf[['trade_date', 'close', 'daily_return']].head(10))

    # Example 5.4: Rolling statistics
    print("\n4. Calculate rolling statistics...")
    pdf['ma_5d'] = pdf['close'].rolling(window=5).mean()
    pdf['volatility'] = pdf['daily_return'].rolling(window=5).std()
    print("\n   With rolling statistics:")
    print(pdf[['trade_date', 'close', 'ma_5d', 'volatility']].tail(10))

    # Example 5.5: Correlation matrix
    print("\n5. Correlation matrix...")
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    correlation = pdf[numeric_cols].corr()
    print("\n   Correlation matrix:")
    print(correlation)


# ============================================================
# EXAMPLE 6: MEASURE CALCULATIONS
# ============================================================

def example_6_measure_calculations(session: UniversalSession):
    """
    Example 6: Using pre-defined measures.

    Demonstrates:
    - Calculating measures
    - Measure by entity
    - Custom aggregations
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Measure Calculations")
    print("=" * 70)

    # Load company model
    company_model = session.load_model('company')

    # Example 6.1: Calculate a measure
    print("\n1. Calculate total trading volume...")
    # Note: This assumes 'total_volume' measure is defined in company.yaml
    # If not defined, this section would show how to define it

    # Example 6.2: Measure by entity
    print("\n2. Calculate average price by ticker...")
    avg_prices = company_model.calculate_measure_by_entity(
        measure_name='avg_close_price',
        entity_column='ticker',
        limit=10
    )
    print("\n   Top 10 tickers by average close:")
    avg_prices.show()

    # Example 6.3: Custom calculations
    print("\n3. Custom metric calculations...")
    prices = company_model.get_fact_df('fact_prices')

    # Calculate market cap proxy
    market_cap = prices.groupBy('ticker').agg(
        (F.avg('close') * F.sum('volume')).alias('market_cap_proxy')
    ).orderBy(F.desc('market_cap_proxy'))

    print("\n   Estimated market cap (price * volume):")
    market_cap.show(10)


# ============================================================
# EXAMPLE 7: ADVANCED QUERIES
# ============================================================

def example_7_advanced_queries(session: UniversalSession):
    """
    Example 7: Advanced query patterns.

    Demonstrates:
    - Subqueries
    - CTEs (Common Table Expressions)
    - Pivot operations
    - Complex joins
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Advanced Queries")
    print("=" * 70)

    prices = session.get_table('company', 'fact_prices')

    # Example 7.1: Find stocks with highest volatility
    print("\n1. Find stocks with highest price volatility...")

    volatility = prices.groupBy('ticker').agg(
        F.stddev('close').alias('price_stddev'),
        F.avg('close').alias('avg_price')
    ).withColumn(
        'coefficient_of_variation',
        F.col('price_stddev') / F.col('avg_price')
    ).orderBy(F.desc('coefficient_of_variation'))

    print("\n   Most volatile stocks:")
    volatility.show(10)

    # Example 7.2: Daily high/low/close pivot
    print("\n2. Pivot price data...")

    pivoted = prices.filter(
        (prices.ticker.isin(['AAPL', 'MSFT'])) &
        (prices.trade_date >= '2024-01-01') &
        (prices.trade_date <= '2024-01-05')
    ).select(
        'trade_date',
        'ticker',
        'close'
    )

    print("\n   Pivoted close prices:")
    pivoted.show(10)

    # Example 7.3: Self-join for price changes
    print("\n3. Calculate price change vs previous day...")
    from pyspark.sql.window import Window

    window = Window.partitionBy('ticker').orderBy('trade_date')

    price_changes = prices.withColumn(
        'prev_close',
        F.lag('close').over(window)
    ).withColumn(
        'price_change',
        F.col('close') - F.col('prev_close')
    ).withColumn(
        'price_change_pct',
        ((F.col('close') - F.col('prev_close')) / F.col('prev_close')) * 100
    ).filter(F.col('prev_close').isNotNull())

    print("\n   Biggest daily gains:")
    price_changes.orderBy(F.desc('price_change_pct')).show(10)

    # Example 7.4: Quantiles
    print("\n4. Calculate price quantiles...")

    quantiles = prices.approxQuantile('close', [0.25, 0.5, 0.75, 0.95], 0.01)
    print(f"\n   Price quantiles:")
    print(f"   25th percentile: ${quantiles[0]:.2f}")
    print(f"   50th percentile (median): ${quantiles[1]:.2f}")
    print(f"   75th percentile: ${quantiles[2]:.2f}")
    print(f"   95th percentile: ${quantiles[3]:.2f}")


# ============================================================
# EXAMPLE 8: PERFORMANCE OPTIMIZATION
# ============================================================

def example_8_performance_optimization(session: UniversalSession):
    """
    Example 8: Query performance optimization.

    Demonstrates:
    - Caching
    - Partitioning
    - Broadcast joins
    - Query planning
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 8: Performance Optimization")
    print("=" * 70)

    prices = session.get_table('company', 'fact_prices')

    # Example 8.1: Caching frequently-used data
    print("\n1. Cache frequently-used tables...")
    prices.cache()
    print("   ✓ Prices table cached")

    # Trigger cache by counting
    count = prices.count()
    print(f"   Cached {count:,} records")

    # Example 8.2: Partition-aware queries
    print("\n2. Use partition pruning...")
    # Query should read only specific partitions
    jan_prices = prices.filter(
        (prices.trade_date >= '2024-01-01') &
        (prices.trade_date < '2024-02-01')
    )
    print(f"   January prices: {jan_prices.count():,} records")

    # Example 8.3: Broadcast join for small dimensions
    print("\n3. Broadcast join for small tables...")
    companies = session.get_table('company', 'dim_company')

    # Explicitly broadcast the small dimension table
    joined = prices.join(
        F.broadcast(companies),
        on='ticker',
        how='left'
    )
    print("   ✓ Joined with broadcast")

    # Example 8.4: Explain query plan
    print("\n4. View query execution plan...")
    print("\n   Query plan for filtered join:")
    jan_prices.explain(extended=True)

    # Uncache when done
    prices.unpersist()
    print("\n   ✓ Unpersisted cache")


# ============================================================
# MAIN RUNNER
# ============================================================

def main():
    """
    Run all examples.
    """
    print("\n" + "=" * 70)
    print("UNIVERSALSESSION QUERY EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates various patterns for querying")
    print("data using UniversalSession in de_Funk.")
    print("\nNote: Some examples require actual data in the Silver layer.")
    print("Run the full pipeline first if you get empty results.")
    print("\n" + "=" * 70)

    # Create session
    print("\nInitializing UniversalSession...")
    session = create_session()
    print("✓ Session initialized")

    # Run examples
    examples = [
        ("Basic Table Access", example_1_basic_table_access),
        ("Aggregations and Grouping", example_2_aggregations),
        ("Cross-Model Queries", example_3_cross_model_queries),
        ("Complex Filters", example_4_complex_filters),
        ("Pandas Integration", example_5_pandas_integration),
        ("Measure Calculations", example_6_measure_calculations),
        ("Advanced Queries", example_7_advanced_queries),
        ("Performance Optimization", example_8_performance_optimization)
    ]

    for name, example_func in examples:
        try:
            print(f"\n\n{'=' * 70}")
            print(f"Running: {name}")
            print('=' * 70)
            example_func(session)
        except Exception as e:
            print(f"\n⚠️  Error in {name}: {e}")
            print("This may be due to missing data. Run the pipeline first.")
            import traceback
            traceback.print_exc()
            continue

    print("\n\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETE")
    print("=" * 70)


# ============================================================
# KEY TAKEAWAYS
# ============================================================

"""
UNIVERSALSESSION QUERY PATTERNS - KEY TAKEAWAYS:

1. INITIALIZATION:
   ```python
from de_funk.models.api.session import UniversalSession

   session = UniversalSession(
       connection=spark,
       storage_cfg=storage_cfg,
       repo_root=repo_root,
       models=['company', 'macro']  # Pre-load models
   )
   ```

2. BASIC ACCESS:
   ```python
   # Get table from model
   df = session.get_table('company', 'fact_prices')

   # Load model for advanced access
   model = session.load_model('company')
   df = model.get_fact_df('fact_prices')
   ```

3. FILTERING:
   ```python
   # Single condition
   filtered = df.filter(df.ticker == 'AAPL')

   # Multiple conditions
   filtered = df.filter(
       (df.ticker == 'AAPL') &
       (df.trade_date >= '2024-01-01')
   )

   # IN clause
   filtered = df.filter(df.ticker.isin(['AAPL', 'MSFT']))
   ```

4. AGGREGATIONS:
   ```python
   # Group by and aggregate
   result = df.groupBy('ticker').agg(
       F.avg('close').alias('avg_price'),
       F.sum('volume').alias('total_volume')
   )

   # Window functions
   from pyspark.sql.window import Window
   window = Window.partitionBy('ticker').orderBy('date')
   df.withColumn('row_num', F.row_number().over(window))
   ```

5. JOINS:
   ```python
   # Inner join
   joined = df1.join(df2, on='key', how='inner')

   # Left join
   joined = df1.join(df2, on='key', how='left')

   # Multiple keys
   joined = df1.join(df2, on=['key1', 'key2'])

   # Broadcast join (for small tables)
   joined = df1.join(F.broadcast(df2), on='key')
   ```

6. PANDAS CONVERSION:
   ```python
   # Filter first to reduce size
   small_df = df.filter(df.date >= '2024-01-01')

   # Convert to Pandas
   pdf = small_df.toPandas()

   # Pandas operations
   pdf['daily_return'] = pdf['close'].pct_change()
   ```

7. PERFORMANCE:
   ```python
   # Cache frequently-used data
   df.cache()

   # Partition pruning (filter by partition column)
   df.filter(df.trade_date >= '2024-01-01')

   # Broadcast small tables
   F.broadcast(small_df)

   # Unpersist when done
   df.unpersist()
   ```

8. CROSS-MODEL:
   ```python
   prices = session.get_table('company', 'fact_prices')
   macro = session.get_table('macro', 'fact_employment')

   # Join across models
   joined = prices.join(macro, on='date')
   ```

COMMON PATTERNS:

Pattern: Time Series Analysis
```python
from pyspark.sql.window import Window

window = Window.partitionBy('ticker').orderBy('date')
df = df.withColumn('prev_close', F.lag('close').over(window))
df = df.withColumn('return', (F.col('close') - F.col('prev_close')) / F.col('prev_close'))
```

Pattern: Top N by Group
```python
from pyspark.sql.window import Window

window = Window.partitionBy('category').orderBy(F.desc('value'))
df = df.withColumn('rank', F.dense_rank().over(window))
df = df.filter(df.rank <= 10)
```

Pattern: Rolling Aggregation
```python
window = Window.partitionBy('ticker').orderBy('date').rowsBetween(-6, 0)
df = df.withColumn('ma_7d', F.avg('close').over(window))
```

Pattern: Pivot Table
```python
pivoted = df.groupBy('row_key').pivot('column_key').agg(F.sum('value'))
```

FILES TO REFERENCE:
- models/api/session.py - UniversalSession
- models/base/model.py - BaseModel
- PySpark DataFrame docs: https://spark.apache.org/docs/latest/api/python/

TROUBLESHOOTING:

Issue: "Table not found"
→ Check model is loaded and table name is correct
→ Verify Silver layer has been written

Issue: "Out of memory"
→ Filter data before converting to Pandas
→ Use .limit() for testing
→ Increase Spark memory config

Issue: "Slow queries"
→ Cache frequently-used DataFrames
→ Use partition pruning
→ Broadcast small dimension tables
→ Check query plan with .explain()
"""


if __name__ == "__main__":
    main()
