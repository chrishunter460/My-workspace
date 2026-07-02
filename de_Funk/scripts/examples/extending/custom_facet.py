"""
Custom Facet Example for de_Funk

This example demonstrates how to create a custom facet for normalizing data from a new API source.
A facet is responsible for:
1. Converting raw API responses (lists of dicts) to PySpark DataFrames
2. Normalizing column names and types
3. Handling schema inconsistencies
4. Post-processing data

Based on: datapipelines/facets/base_facet.py

Author: de_Funk Team
Date: 2024-11-08
"""

from typing import List, Dict, Tuple, Optional
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import StringType, DoubleType, LongType, DateType

# Import base facet class
import sys
from pathlib import Path

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from de_funk.pipelines.base.facet import Facet


# ============================================================
# CUSTOM FACET EXAMPLE: Weather Data
# ============================================================

class WeatherFacet(Facet):
    """
    Example facet for weather API data.

    This facet demonstrates:
    - Numeric type coercion (temperature, precipitation)
    - Column renaming and standardization
    - Date parsing and formatting
    - Adding derived columns
    - Handling missing values
    """

    # Step 1: Define numeric coercion for raw JSON fields
    # This ensures consistent types before Spark schema inference
    NUMERIC_COERCE = {
        "temp": "double",          # Temperature in Celsius
        "feels_like": "double",    # Feels like temperature
        "humidity": "double",      # Humidity percentage
        "pressure": "double",      # Atmospheric pressure
        "wind_speed": "double",    # Wind speed
        "precipitation": "double", # Rainfall/snowfall
        "timestamp": "long"        # Unix timestamp
    }

    # Step 2: Define final Spark column types
    # Applied after postprocess() to ensure correct schema
    SPARK_CASTS = {
        "date": "date",
        "city": "string",
        "temperature_c": "double",
        "feels_like_c": "double",
        "humidity_pct": "double",
        "pressure_hpa": "double",
        "wind_speed_kmh": "double",
        "precipitation_mm": "double",
        "weather_condition": "string",
        "timestamp": "long"
    }

    # Step 3: Define final column order and types
    # Ensures consistent schema even with missing columns
    FINAL_COLUMNS: List[Tuple[str, str]] = [
        ("date", "date"),
        ("city", "string"),
        ("temperature_c", "double"),
        ("feels_like_c", "double"),
        ("humidity_pct", "double"),
        ("pressure_hpa", "double"),
        ("wind_speed_kmh", "double"),
        ("precipitation_mm", "double"),
        ("weather_condition", "string"),
        ("timestamp", "long")
    ]

    def __init__(self, spark, city: str = None, date_from: str = None, date_to: str = None):
        """
        Initialize weather facet.

        Args:
            spark: SparkSession instance
            city: City name to filter (optional)
            date_from: Start date for filtering (optional)
            date_to: End date for filtering (optional)
        """
        super().__init__(spark)
        self.city = city
        self.date_from = date_from
        self.date_to = date_to

    def postprocess(self, df: DataFrame) -> DataFrame:
        """
        Post-process the DataFrame after initial normalization.

        This is where you:
        - Rename columns to follow naming conventions
        - Add derived/calculated columns
        - Filter data
        - Handle missing values
        - Apply business logic

        Args:
            df: Raw DataFrame from API with coerced types

        Returns:
            Processed DataFrame ready for Bronze storage
        """

        # Step 1: Rename columns to follow naming conventions
        # Raw API: temp, feels_like, humidity
        # Standardized: temperature_c, feels_like_c, humidity_pct
        df = df.withColumnRenamed("temp", "temperature_c") \
               .withColumnRenamed("feels_like", "feels_like_c") \
               .withColumnRenamed("humidity", "humidity_pct") \
               .withColumnRenamed("pressure", "pressure_hpa") \
               .withColumnRenamed("wind_speed", "wind_speed_kmh") \
               .withColumnRenamed("precipitation", "precipitation_mm") \
               .withColumnRenamed("condition", "weather_condition")

        # Step 2: Convert timestamp to date
        # Assumes timestamp is Unix epoch in seconds
        if "timestamp" in df.columns:
            df = df.withColumn(
                "date",
                F.to_date(F.from_unixtime(F.col("timestamp")))
            )
        else:
            # If no timestamp, try parsing date field
            if "dt" in df.columns:
                df = df.withColumn("date", F.to_date(F.col("dt")))
            else:
                # Default to current date if no date info
                df = df.withColumn("date", F.current_date())

        # Step 3: Add derived columns
        # Convert temperature to Fahrenheit
        df = df.withColumn(
            "temperature_f",
            (F.col("temperature_c") * 9/5) + 32
        )

        # Classify temperature
        df = df.withColumn(
            "temp_category",
            F.when(F.col("temperature_c") < 0, "freezing")
             .when(F.col("temperature_c") < 10, "cold")
             .when(F.col("temperature_c") < 20, "mild")
             .when(F.col("temperature_c") < 30, "warm")
             .otherwise("hot")
        )

        # Step 4: Handle missing values
        # Fill missing precipitation with 0 (no rain)
        if "precipitation_mm" in df.columns:
            df = df.fillna({"precipitation_mm": 0.0})

        # Fill missing weather condition with "unknown"
        if "weather_condition" in df.columns:
            df = df.fillna({"weather_condition": "unknown"})

        # Step 5: Apply filters if specified
        if self.city:
            df = df.filter(F.col("city") == self.city)

        if self.date_from:
            df = df.filter(F.col("date") >= self.date_from)

        if self.date_to:
            df = df.filter(F.col("date") <= self.date_to)

        # Step 6: Remove invalid data
        # Remove records with impossible values
        df = df.filter(
            (F.col("temperature_c") > -100) &   # Reasonable min temp
            (F.col("temperature_c") < 60) &     # Reasonable max temp
            (F.col("humidity_pct") >= 0) &      # Valid humidity range
            (F.col("humidity_pct") <= 100)
        )

        return df


# ============================================================
# EXAMPLE USAGE
# ============================================================

def example_usage():
    """
    Demonstrate how to use the custom WeatherFacet.
    """
    from pyspark.sql import SparkSession

    # Initialize Spark
    spark = SparkSession.builder \
        .appName("CustomFacetExample") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()

    # Example 1: Sample API response data
    # In a real scenario, this would come from an API call
    sample_data = [
        {
            "city": "New York",
            "temp": 15.5,
            "feels_like": 14.0,
            "humidity": 65,
            "pressure": 1013,
            "wind_speed": 12.5,
            "precipitation": 0.0,
            "condition": "partly cloudy",
            "timestamp": 1699401600  # 2023-11-08 00:00:00
        },
        {
            "city": "Los Angeles",
            "temp": 22.0,
            "feels_like": 21.5,
            "humidity": 45,
            "pressure": 1015,
            "wind_speed": 8.0,
            "precipitation": None,  # Missing data
            "condition": "clear",
            "timestamp": 1699401600
        },
        {
            "city": "Chicago",
            "temp": 8.0,
            "feels_like": 5.0,
            "humidity": 78,
            "pressure": 1010,
            "wind_speed": 18.0,
            "precipitation": 2.5,
            "condition": "rainy",
            "timestamp": 1699401600
        }
    ]

    # Example 2: Use the facet to normalize data
    print("=" * 70)
    print("Example 1: Normalize weather data with WeatherFacet")
    print("=" * 70)

    facet = WeatherFacet(
        spark=spark,
        city=None,  # No city filter
        date_from="2023-01-01",
        date_to="2024-12-31"
    )

    # Normalize the data (simulates multiple batches from API)
    batches = [sample_data]  # In reality, multiple API responses
    df = facet.normalize(batches)

    print("\nNormalized Schema:")
    df.printSchema()

    print("\nNormalized Data:")
    df.show(truncate=False)

    # Example 3: Filter by city
    print("\n" + "=" * 70)
    print("Example 2: Filter weather data for specific city")
    print("=" * 70)

    facet_filtered = WeatherFacet(
        spark=spark,
        city="Chicago",
        date_from="2023-01-01"
    )

    df_filtered = facet_filtered.normalize(batches)

    print("\nFiltered Data (Chicago only):")
    df_filtered.show(truncate=False)

    # Example 4: Demonstrate error handling
    print("\n" + "=" * 70)
    print("Example 3: Handle missing/invalid data")
    print("=" * 70)

    invalid_data = [
        {
            "city": "Boston",
            "temp": -150,  # Invalid temperature
            "humidity": 150,  # Invalid humidity
            "timestamp": 1699401600
        },
        {
            "city": "Seattle",
            "temp": 12.0,
            "humidity": 88,
            # Missing other fields - will be filled with NULL
            "timestamp": 1699401600
        }
    ]

    facet_invalid = WeatherFacet(spark=spark)
    df_invalid = facet_invalid.normalize([invalid_data])

    print("\nData with invalid records (filtered out):")
    df_invalid.show(truncate=False)
    print(f"Records after filtering: {df_invalid.count()} (invalid temp/humidity removed)")

    # Example 5: Show final column order is enforced
    print("\n" + "=" * 70)
    print("Example 4: Demonstrate consistent schema with missing columns")
    print("=" * 70)

    minimal_data = [
        {
            "city": "Miami",
            "temp": 28.0,
            "timestamp": 1699401600
            # Many fields missing - will be filled with NULL
        }
    ]

    facet_minimal = WeatherFacet(spark=spark)
    df_minimal = facet_minimal.normalize([minimal_data])

    print("\nMinimal data (missing fields filled with NULL):")
    df_minimal.show(truncate=False)
    print("\nSchema (all columns present even if NULL):")
    df_minimal.printSchema()

    spark.stop()


# ============================================================
# ADVANCED EXAMPLE: Time Series Facet
# ============================================================

class StockPriceFacet(Facet):
    """
    Advanced example: Stock price time series data.

    Demonstrates:
    - Multiple numeric coercions
    - Complex postprocessing
    - Technical indicator calculations
    - Data quality checks
    """

    NUMERIC_COERCE = {
        "o": "double",    # Open
        "h": "double",    # High
        "l": "double",    # Low
        "c": "double",    # Close
        "v": "long",      # Volume
        "vw": "double",   # Volume weighted
        "t": "long"       # Timestamp
    }

    SPARK_CASTS = {
        "trade_date": "date",
        "ticker": "string",
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "long",
        "volume_weighted": "double"
    }

    FINAL_COLUMNS = [
        ("trade_date", "date"),
        ("ticker", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "long"),
        ("volume_weighted", "double")
    ]

    def __init__(self, spark, ticker: str = None):
        super().__init__(spark)
        self.ticker = ticker

    def postprocess(self, df: DataFrame) -> DataFrame:
        """
        Advanced postprocessing for stock price data.
        """
        # Rename short column names
        column_mapping = {
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "volume_weighted",
            "t": "timestamp",
            "T": "ticker"
        }

        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.withColumnRenamed(old_name, new_name)

        # Convert timestamp to date
        if "timestamp" in df.columns:
            df = df.withColumn(
                "trade_date",
                F.to_date(F.from_unixtime(F.col("timestamp") / 1000))  # ms to s
            )

        # Add calculated columns
        # Daily range
        df = df.withColumn("daily_range", F.col("high") - F.col("low"))

        # Daily change
        df = df.withColumn("daily_change", F.col("close") - F.col("open"))

        # Daily change percentage
        df = df.withColumn(
            "daily_change_pct",
            (F.col("daily_change") / F.col("open")) * 100
        )

        # Data quality: Remove invalid records
        df = df.filter(
            (F.col("open") > 0) &
            (F.col("high") >= F.col("low")) &  # High >= Low
            (F.col("high") >= F.col("open")) &  # High >= Open
            (F.col("low") <= F.col("close")) &  # Low <= Close
            (F.col("volume") >= 0)
        )

        # Filter by ticker if specified
        if self.ticker:
            df = df.filter(F.col("ticker") == self.ticker)

        return df


# ============================================================
# KEY TAKEAWAYS
# ============================================================

"""
KEY CONCEPTS FOR CREATING CUSTOM FACETS:

1. NUMERIC_COERCE:
   - Pre-coerces Python types before Spark schema inference
   - Prevents schema mismatch errors
   - Use for numeric fields that might be int, float, or string

2. SPARK_CASTS:
   - Final type enforcement after postprocess()
   - Ensures consistent schema
   - Applied to all columns (creates NULL if missing)

3. FINAL_COLUMNS:
   - Defines exact column order and types
   - Missing columns are filled with NULL
   - Ensures consistent schema across batches

4. postprocess():
   - Main transformation logic
   - Rename columns to follow conventions
   - Add derived/calculated columns
   - Filter and clean data
   - Handle missing values

5. Error Handling:
   - Filter invalid data in postprocess()
   - Use fillna() for missing values
   - Validate business rules (e.g., high >= low)

6. Best Practices:
   - Use clear, descriptive column names
   - Follow naming conventions (snake_case)
   - Include units in column names (temperature_c, wind_speed_kmh)
   - Document assumptions and transformations
   - Test with edge cases (missing data, invalid values)

COMMON PATTERNS:

Pattern 1: Date Conversion
    df = df.withColumn("date", F.to_date(F.from_unixtime(F.col("timestamp"))))

Pattern 2: Derived Columns
    df = df.withColumn("new_col", F.col("col_a") + F.col("col_b"))

Pattern 3: Categorization
    df = df.withColumn("category",
        F.when(F.col("value") < 10, "low")
         .when(F.col("value") < 20, "medium")
         .otherwise("high"))

Pattern 4: Missing Value Handling
    df = df.fillna({"column": default_value})

Pattern 5: Data Validation
    df = df.filter((F.col("value") >= min) & (F.col("value") <= max))

TESTING YOUR FACET:

1. Test with sample data:
   - Create mock API responses
   - Include edge cases (nulls, invalid data)
   - Verify schema is correct

2. Test with real API:
   - Small date range first
   - Verify all columns present
   - Check for unexpected values

3. Verify postprocess():
   - Check column renames work
   - Verify calculated columns correct
   - Ensure filtering works
   - Validate final schema matches FINAL_COLUMNS

FILES TO REFERENCE:
- datapipelines/facets/base_facet.py - Base class
- datapipelines/providers/chicago/facets/*.py - Real examples
- datapipelines/providers/alpha_vantage/facets/*.py - Current examples
"""


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CUSTOM FACET EXAMPLE - WeatherFacet")
    print("=" * 70)
    print("\nThis example demonstrates how to create a custom facet for")
    print("normalizing API data in de_Funk.")
    print("\nRunning examples...\n")

    example_usage()

    print("\n" + "=" * 70)
    print("Example complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Study the WeatherFacet implementation above")
    print("2. Review the StockPriceFacet for advanced patterns")
    print("3. Create your own facet for your API")
    print("4. Test with sample data first")
    print("5. Integrate with your provider/ingestor")
    print("\nSee also:")
    print("- examples/providers/custom_provider_example.py")
    print("- datapipelines/facets/base_facet.py")
    print("=" * 70)
