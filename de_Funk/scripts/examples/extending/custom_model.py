"""
Custom Model Example for de_Funk

This example demonstrates how to create a custom domain model in de_Funk.

A model consists of:
1. YAML configuration - Defines structure (87% of the work)
2. Python class - Adds convenience methods (13% of the work)

All core functionality (graph building, writing, querying) is inherited from BaseModel.

Based on: models/implemented/company/model.py

Author: de_Funk Team
Date: 2024-11-08
"""

import sys
from pathlib import Path
from typing import Optional

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from pyspark.sql import DataFrame
from de_funk.models.base.model import BaseModel


# ============================================================
# CUSTOM MODEL: Portfolio Model
# ============================================================

class PortfolioModel(BaseModel):
    """
    Portfolio domain model for investment analysis.

    This model demonstrates:
    - Multiple dimensions (securities, portfolios, accounts)
    - Multiple facts (holdings, transactions, returns)
    - Measures (total value, returns, allocation)
    - Convenience methods for common queries

    ALL core functionality is inherited from BaseModel:
    - build() - Builds graph from YAML config
    - write_tables() - Writes to Silver layer
    - get_table() - Retrieves table
    - calculate_measure() - Computes metrics
    - apply_filters() - Filters data

    The YAML config (see below) defines:
    - Nodes: dim_security, dim_portfolio, fact_holdings, etc.
    - Edges: Relationships between tables
    - Paths: Materialized views (e.g., holdings_with_security)
    - Measures: Calculated metrics (e.g., total_value, daily_return)
    """

    # ============================================================
    # CONVENIENCE METHODS (Optional - adds sugar on top of BaseModel)
    # ============================================================

    def get_holdings(self, portfolio_id: Optional[str] = None,
                     as_of_date: Optional[str] = None) -> DataFrame:
        """
        Get portfolio holdings with security details.

        Args:
            portfolio_id: Filter by portfolio (optional)
            as_of_date: Get holdings as of specific date (optional)

        Returns:
            DataFrame with holdings and security info
        """
        df = self.get_table('holdings_with_security')

        if portfolio_id:
            df = df.filter(df.portfolio_id == portfolio_id)

        if as_of_date:
            df = df.filter(df.as_of_date == as_of_date)

        return df

    def get_transactions(self, portfolio_id: Optional[str] = None,
                        security_id: Optional[str] = None,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None) -> DataFrame:
        """
        Get transaction history with filters.

        Args:
            portfolio_id: Filter by portfolio
            security_id: Filter by security
            date_from: Start date
            date_to: End date

        Returns:
            DataFrame with transactions
        """
        df = self.get_fact_df('fact_transactions')

        if portfolio_id:
            df = df.filter(df.portfolio_id == portfolio_id)

        if security_id:
            df = df.filter(df.security_id == security_id)

        if date_from:
            df = df.filter(df.transaction_date >= date_from)

        if date_to:
            df = df.filter(df.transaction_date <= date_to)

        return df

    def get_portfolio_value(self, portfolio_id: str,
                           as_of_date: Optional[str] = None) -> float:
        """
        Calculate total portfolio value.

        Args:
            portfolio_id: Portfolio to calculate
            as_of_date: Date to calculate (default: latest)

        Returns:
            Total portfolio value
        """
        df = self.get_holdings(portfolio_id=portfolio_id, as_of_date=as_of_date)

        # Calculate: shares * price
        from pyspark.sql import functions as F
        df = df.withColumn("position_value", F.col("shares") * F.col("price"))

        total = df.agg(F.sum("position_value")).collect()[0][0]
        return float(total) if total else 0.0

    def get_allocation(self, portfolio_id: str,
                      by: str = "security_type") -> DataFrame:
        """
        Get portfolio allocation breakdown.

        Args:
            portfolio_id: Portfolio to analyze
            by: Grouping dimension (security_type, sector, asset_class)

        Returns:
            DataFrame with allocation percentages
        """
        df = self.get_holdings(portfolio_id=portfolio_id)

        from pyspark.sql import functions as F
        from pyspark.sql.window import Window

        # Calculate position values
        df = df.withColumn("position_value", F.col("shares") * F.col("price"))

        # Calculate total portfolio value
        total_value = df.agg(F.sum("position_value")).collect()[0][0]

        # Group by dimension and calculate allocation
        allocation_df = df.groupBy(by).agg(
            F.sum("position_value").alias("value")
        ).withColumn(
            "allocation_pct",
            (F.col("value") / total_value) * 100
        ).orderBy(F.desc("allocation_pct"))

        return allocation_df

    def get_performance(self, portfolio_id: str,
                       date_from: str, date_to: str) -> DataFrame:
        """
        Get portfolio performance over time.

        Args:
            portfolio_id: Portfolio to analyze
            date_from: Start date
            date_to: End date

        Returns:
            DataFrame with daily returns
        """
        df = self.get_table('portfolio_daily_returns')

        df = df.filter(
            (df.portfolio_id == portfolio_id) &
            (df.date >= date_from) &
            (df.date <= date_to)
        )

        return df


# ============================================================
# EXAMPLE YAML CONFIGURATION
# ============================================================

EXAMPLE_PORTFOLIO_YAML = """
# configs/models/portfolio.yaml

version: 1
model: portfolio
tags: [portfolio, investments, holdings]

# Dependencies
depends_on:
  - company  # For security prices
  - core     # For calendar dimension

# Storage
storage:
  root: storage/silver/portfolio
  format: parquet

# ============================================================
# SCHEMA - Source of truth for all tables
# ============================================================

schema:
  dimensions:
    dim_security:
      path: dims/dim_security
      description: "Securities (stocks, bonds, ETFs, etc.)"
      columns:
        security_id: string
        ticker: string
        security_name: string
        security_type: string  # stock, bond, etf, mutual_fund
        sector: string
        asset_class: string  # equity, fixed_income, alternative
      primary_key: [security_id]
      tags: [dim, entity, security]

    dim_portfolio:
      path: dims/dim_portfolio
      description: "Portfolio definitions"
      columns:
        portfolio_id: string
        portfolio_name: string
        account_id: string
        strategy: string
        benchmark: string
      primary_key: [portfolio_id]
      tags: [dim, entity, portfolio]

    dim_account:
      path: dims/dim_account
      description: "Account information"
      columns:
        account_id: string
        account_name: string
        account_type: string  # taxable, ira, 401k
        owner: string
      primary_key: [account_id]
      tags: [dim, entity, account]

  facts:
    fact_holdings:
      path: facts/fact_holdings
      description: "Daily portfolio holdings"
      columns:
        as_of_date: date
        portfolio_id: string
        security_id: string
        shares: double
        price: double
        cost_basis: double
      partitions: [as_of_date]
      tags: [fact, holdings, daily]

    fact_transactions:
      path: facts/fact_transactions
      description: "Buy/sell transactions"
      columns:
        transaction_date: date
        transaction_id: string
        portfolio_id: string
        security_id: string
        transaction_type: string  # buy, sell
        shares: double
        price: double
        fees: double
      partitions: [transaction_date]
      tags: [fact, transactions]

    fact_returns:
      path: facts/fact_returns
      description: "Daily portfolio returns"
      columns:
        date: date
        portfolio_id: string
        portfolio_value: double
        daily_return: double
        cumulative_return: double
      partitions: [date]
      tags: [fact, returns, performance]

    # Materialized views (from paths below)
    holdings_with_security:
      path: facts/holdings_with_security
      description: "Holdings with security details"
      tags: [canonical, analytics, materialized]

    portfolio_daily_returns:
      path: facts/portfolio_daily_returns
      description: "Portfolio performance with benchmarks"
      tags: [analytics, performance, materialized]

# ============================================================
# GRAPH - Defines how to build tables from Bronze
# ============================================================

graph:
  nodes:
    # Dimension: Securities
    - id: dim_security
      from: bronze.securities  # From Bronze layer
      transforms:
        - select:
            - ticker
            - name as security_name
            - type as security_type
            - sector
            - asset_class
        - add_column:
            name: security_id
            expr: sha1(ticker)

    # Dimension: Portfolios
    - id: dim_portfolio
      from: bronze.portfolios
      transforms:
        - select:
            - portfolio_id
            - name as portfolio_name
            - account_id
            - strategy
            - benchmark

    # Dimension: Accounts
    - id: dim_account
      from: bronze.accounts
      transforms:
        - select:
            - account_id
            - name as account_name
            - account_type
            - owner

    # Fact: Holdings
    - id: fact_holdings
      from: bronze.holdings_daily
      transforms:
        - select:
            - as_of_date
            - portfolio_id
            - security_id
            - shares
            - price
            - cost_basis

    # Fact: Transactions
    - id: fact_transactions
      from: bronze.transactions
      transforms:
        - select:
            - transaction_date
            - transaction_id
            - portfolio_id
            - security_id
            - transaction_type
            - shares
            - price
            - fees

    # Fact: Returns (calculated from holdings)
    - id: fact_returns
      from: bronze.holdings_daily
      transforms:
        - group_by:
            columns: [as_of_date, portfolio_id]
            aggregations:
              portfolio_value: sum(shares * price)
        - window:
            partition_by: [portfolio_id]
            order_by: [as_of_date]
            calculations:
              daily_return: (portfolio_value - lag(portfolio_value)) / lag(portfolio_value)
              cumulative_return: (portfolio_value - first(portfolio_value)) / first(portfolio_value)
        - rename:
            as_of_date: date

  # Relationships between tables
  edges:
    - from: fact_holdings
      to: dim_security
      type: many_to_one
      keys:
        - [security_id, security_id]

    - from: fact_holdings
      to: dim_portfolio
      type: many_to_one
      keys:
        - [portfolio_id, portfolio_id]

    - from: fact_transactions
      to: dim_security
      type: many_to_one
      keys:
        - [security_id, security_id]

    - from: fact_transactions
      to: dim_portfolio
      type: many_to_one
      keys:
        - [portfolio_id, portfolio_id]

    - from: dim_portfolio
      to: dim_account
      type: many_to_one
      keys:
        - [account_id, account_id]

  # Materialized paths (pre-joined views)
  paths:
    - id: holdings_with_security
      description: "Holdings joined with security details"
      hops:
        - fact_holdings
        - dim_security
        - dim_portfolio
      select:
        - fact_holdings.as_of_date
        - fact_holdings.portfolio_id
        - dim_portfolio.portfolio_name
        - fact_holdings.security_id
        - dim_security.ticker
        - dim_security.security_name
        - dim_security.security_type
        - dim_security.sector
        - fact_holdings.shares
        - fact_holdings.price
        - fact_holdings.cost_basis

    - id: portfolio_daily_returns
      description: "Portfolio returns with account info"
      hops:
        - fact_returns
        - dim_portfolio
        - dim_account
      select:
        - fact_returns.date
        - fact_returns.portfolio_id
        - dim_portfolio.portfolio_name
        - dim_portfolio.strategy
        - dim_account.account_name
        - fact_returns.portfolio_value
        - fact_returns.daily_return
        - fact_returns.cumulative_return

# ============================================================
# MEASURES - Pre-defined calculations
# ============================================================

measures:
  # Total portfolio value
  total_value:
    table: fact_holdings
    aggregation: sum
    expression: shares * price
    description: "Total portfolio market value"

  # Number of positions
  position_count:
    table: fact_holdings
    aggregation: count_distinct
    column: security_id
    description: "Number of unique securities held"

  # Average daily return
  avg_daily_return:
    table: fact_returns
    aggregation: avg
    column: daily_return
    description: "Average daily return"

  # Total return
  total_return:
    table: fact_returns
    aggregation: last
    column: cumulative_return
    description: "Total cumulative return"

  # Transaction volume
  transaction_volume:
    table: fact_transactions
    aggregation: sum
    expression: shares * price
    description: "Total transaction volume"

  # Trading fees
  total_fees:
    table: fact_transactions
    aggregation: sum
    column: fees
    description: "Total trading fees paid"
"""


# ============================================================
# EXAMPLE USAGE
# ============================================================

def example_usage():
    """
    Demonstrate how to use a custom model.
    """
    from pyspark.sql import SparkSession
    import yaml

    print("=" * 70)
    print("CUSTOM MODEL EXAMPLE - PortfolioModel")
    print("=" * 70)

    # Initialize Spark
    spark = SparkSession.builder \
        .appName("CustomModelExample") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()

    # Parse example YAML config
    model_cfg = yaml.safe_load(EXAMPLE_PORTFOLIO_YAML)

    # Storage configuration
    storage_cfg = {
        "roots": {
            "bronze": "storage/bronze",
            "portfolio_silver": "storage/silver/portfolio"
        }
    }

    # Initialize model
    print("\n1. Initializing PortfolioModel...")
    portfolio_model = PortfolioModel(
        connection=spark,
        storage_cfg=storage_cfg,
        model_cfg=model_cfg,
        params={}
    )

    print("✓ Model initialized")
    print(f"  Model name: {portfolio_model.model_name}")
    print(f"  Backend: {portfolio_model.backend}")

    # Example 2: Build model from YAML config
    print("\n2. Building model from YAML config...")
    print("  (In production, this would load data from Bronze and build all tables)")
    print("  portfolio_model.build()")
    print("  ✓ Model built - creates all dimensions and facts in memory")

    # Example 3: Write to Silver layer
    print("\n3. Writing model to Silver layer...")
    print("  portfolio_model.write_tables(")
    print("      use_optimized_writer=True,")
    print("      partition_by={'fact_holdings': ['as_of_date']}")
    print("  )")
    print("  ✓ All tables written to storage/silver/portfolio/")

    # Example 4: Query data using convenience methods
    print("\n4. Querying data with convenience methods...")
    print("  # Get holdings for a portfolio")
    print("  holdings = portfolio_model.get_holdings(portfolio_id='PORT001')")
    print()
    print("  # Get portfolio value")
    print("  value = portfolio_model.get_portfolio_value(portfolio_id='PORT001')")
    print()
    print("  # Get allocation breakdown")
    print("  allocation = portfolio_model.get_allocation(")
    print("      portfolio_id='PORT001',")
    print("      by='security_type'")
    print("  )")
    print()
    print("  # Get performance")
    print("  performance = portfolio_model.get_performance(")
    print("      portfolio_id='PORT001',")
    print("      date_from='2024-01-01',")
    print("      date_to='2024-12-31'")
    print("  )")

    # Example 5: Calculate measures
    print("\n5. Calculating measures...")
    print("  # Total portfolio value")
    print("  value = portfolio_model.calculate_measure('total_value')")
    print()
    print("  # Average daily return")
    print("  avg_return = portfolio_model.calculate_measure('avg_daily_return')")
    print()
    print("  # Position count")
    print("  positions = portfolio_model.calculate_measure('position_count')")

    spark.stop()


# ============================================================
# KEY TAKEAWAYS
# ============================================================

"""
CREATING A CUSTOM MODEL - STEP BY STEP:

STEP 1: CREATE YAML CONFIGURATION (87% of the work)
======================================================

The YAML config is the source of truth. It defines:

1. Schema Section:
   - dimensions: Reference tables (securities, portfolios)
   - facts: Event/measurement tables (holdings, transactions)
   - Include: columns, types, primary keys, partitions

2. Graph Section:
   - nodes: How to build each table from Bronze
     - from: Source table in Bronze
     - transforms: SQL-like transformations
   - edges: Relationships between tables
     - Defines foreign keys and join paths
   - paths: Materialized views (pre-joined tables)
     - Define join sequences
     - Select columns to include

3. Measures Section (optional):
   - Pre-defined calculations
   - Aggregations: sum, avg, count, etc.
   - Can reference across tables

STEP 2: CREATE PYTHON CLASS (13% of the work)
==============================================

The Python class:
- Inherits from BaseModel (gets all functionality)
- Adds convenience methods for common queries
- No business logic needed - it's all in YAML!

Minimal example:
```python
class MyModel(BaseModel):
    pass  # That's it! All functionality inherited.
```

With convenience methods:
```python
class MyModel(BaseModel):
    def get_my_data(self, filter_value):
        df = self.get_table('my_table')
        return df.filter(df.column == filter_value)
```

STEP 3: USAGE
=============

```python
# Initialize
model = MyModel(connection=spark, storage_cfg=..., model_cfg=...)

# Build graph from YAML
model.build()

# Write to Silver
model.write_tables()

# Query data
df = model.get_table('my_table')
measure = model.calculate_measure('my_measure')
```

WHAT YOU GET FOR FREE FROM BaseModel:
======================================

Data Access:
- get_table(table_name) - Get any table (dim, fact, or path)
- get_dimension_df(dim_name) - Get dimension table
- get_fact_df(fact_name) - Get fact table
- list_tables() - List all available tables

Building:
- build() - Build entire model from YAML
- ensure_built() - Build if not already built
- write_tables() - Write all tables to storage

Measures:
- calculate_measure(measure_name) - Calculate metric
- calculate_measure_by_entity() - Group by dimension
- list_measures() - List available measures

Metadata:
- get_schema() - Get table schemas
- get_edges() - Get relationships
- get_graph_info() - Get graph structure

YAML CONFIGURATION TIPS:
=========================

1. Start Simple:
   - Begin with 1-2 dimensions and 1 fact
   - Add complexity incrementally
   - Test at each step

2. Use Descriptive Names:
   - dim_security (not dim_sec)
   - fact_holdings (not holdings)
   - Clear column names with units

3. Define Relationships:
   - All foreign keys in edges
   - Validates data integrity
   - Enables automatic joins

4. Leverage Paths:
   - Pre-join commonly used tables
   - Improves query performance
   - Simplifies user queries

5. Add Measures Early:
   - Common calculations in YAML
   - Users don't need to know SQL
   - Reusable across notebooks

TESTING YOUR MODEL:
===================

1. Validate YAML:
   ```python
from de_funk.models.registry import ModelRegistry
   registry = ModelRegistry(models_dir)
   config = registry.get_model_config('mymodel')  # Validates syntax
   ```

2. Test Building:
   ```python
   model.build()
   assert model._is_built
   assert 'dim_security' in model._dims
   ```

3. Test Tables:
   ```python
   df = model.get_table('dim_security')
   assert df.count() > 0
   df.printSchema()  # Verify schema
   ```

4. Test Measures:
   ```python
   value = model.calculate_measure('total_value')
   assert value > 0
   ```

5. Test Writes:
   ```python
   model.write_tables()
   # Verify files exist in storage/silver/mymodel/
   ```

FILES TO REFERENCE:
===================

YAML Config Examples:
- /home/user/de_Funk/configs/models/company.yaml
- /home/user/de_Funk/configs/models/macro.yaml
- /home/user/de_Funk/configs/models/city_finance.yaml

Python Model Examples:
- /home/user/de_Funk/models/implemented/company/model.py
- /home/user/de_Funk/models/implemented/macro/model.py

Base Classes:
- /home/user/de_Funk/models/base/model.py
- /home/user/de_Funk/models/registry.py

COMMON YAML PATTERNS:
=====================

Pattern 1: Simple Dimension
```yaml
nodes:
  - id: dim_product
    from: bronze.products
    transforms:
      - select: [product_id, product_name, category]
```

Pattern 2: Fact with Aggregation
```yaml
nodes:
  - id: fact_daily_sales
    from: bronze.transactions
    transforms:
      - group_by:
          columns: [date, product_id]
          aggregations:
            quantity: sum(quantity)
            revenue: sum(price * quantity)
```

Pattern 3: Calculated Columns
```yaml
nodes:
  - id: fact_metrics
    from: bronze.raw_data
    transforms:
      - select: [date, value1, value2]
      - add_column:
          name: ratio
          expr: value1 / value2
      - add_column:
          name: category
          expr: CASE WHEN ratio > 1 THEN 'high' ELSE 'low' END
```

Pattern 4: Multi-Table Join Path
```yaml
paths:
  - id: sales_with_product_and_customer
    hops:
      - fact_sales
      - dim_product
      - dim_customer
    select:
      - fact_sales.date
      - fact_sales.quantity
      - dim_product.product_name
      - dim_customer.customer_name
```
"""


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CUSTOM MODEL EXAMPLE")
    print("=" * 70)
    print("\nThis example demonstrates how to create a custom domain model")
    print("in de_Funk using YAML configuration and a minimal Python class.")
    print("\nComponents:")
    print("1. YAML Configuration (87% of work) - See EXAMPLE_PORTFOLIO_YAML")
    print("2. Python Class (13% of work) - See PortfolioModel")
    print("\n")

    # Show the YAML config
    print("=" * 70)
    print("EXAMPLE YAML CONFIGURATION")
    print("=" * 70)
    print(EXAMPLE_PORTFOLIO_YAML)

    print("\n" + "=" * 70)
    print("RUNNING EXAMPLES")
    print("=" * 70)
    example_usage()

    print("\n" + "=" * 70)
    print("Next steps:")
    print("1. Study the YAML configuration above")
    print("2. Study the PortfolioModel class")
    print("3. Create your own model YAML in configs/models/")
    print("4. Create your Python model class in models/implemented/")
    print("5. Test building and querying your model")
    print("6. Add to UniversalSession for cross-model queries")
    print("\nSee also:")
    print("- configs/models/company.yaml (real example)")
    print("- models/implemented/company/model.py (real example)")
    print("- models/base/model.py (base class)")
    print("=" * 70)
