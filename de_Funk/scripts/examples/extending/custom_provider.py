"""
Custom Provider Example for de_Funk

This example demonstrates how to create a custom API provider for ingesting data
from a new external data source.

A provider consists of:
1. Registry - Defines API endpoints and configuration
2. Ingestor - Orchestrates API calls and data ingestion
3. Facets - Normalize data from API responses

Based on existing providers:
- datapipelines/providers/bls/
- datapipelines/providers/chicago/

Author: de_Funk Team
Date: 2024-11-08
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Iterator
from urllib.parse import urlencode

# Bootstrap: add repo to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from de_funk.utils.repo import get_repo_root
repo_root = get_repo_root()

from pyspark.sql import SparkSession, DataFrame
from de_funk.pipelines.base.registry import BaseRegistry
from de_funk.pipelines.base.http_client import HttpClient
from de_funk.pipelines.base.key_pool import ApiKeyPool
from de_funk.pipelines.ingestors.base_ingestor import Ingestor
from de_funk.pipelines.ingestors.bronze_sink import BronzeSink
from de_funk.pipelines.base.facet import Facet


# ============================================================
# STEP 1: CREATE A REGISTRY
# ============================================================

class CryptoRegistry(BaseRegistry):
    """
    Registry for CryptoCompare API.

    The registry defines:
    - Base URLs
    - API endpoints
    - Required parameters
    - Default query parameters
    - Response structure

    This is the configuration layer - no logic, just definitions.
    """
    pass  # BaseRegistry handles all logic; we just need to define config


# ============================================================
# STEP 2: CREATE FACETS FOR EACH DATA TYPE
# ============================================================

class CryptoPriceFacet(Facet):
    """
    Facet for cryptocurrency OHLCV (price) data.

    Normalizes daily price data from CryptoCompare API.
    """

    NUMERIC_COERCE = {
        "time": "long",
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volumefrom": "double",
        "volumeto": "double"
    }

    SPARK_CASTS = {
        "trade_date": "date",
        "symbol": "string",
        "open": "double",
        "high": "double",
        "low": "double",
        "close": "double",
        "volume": "double",
        "quote_volume": "double"
    }

    FINAL_COLUMNS = [
        ("trade_date", "date"),
        ("symbol", "string"),
        ("open", "double"),
        ("high", "double"),
        ("low", "double"),
        ("close", "double"),
        ("volume", "double"),
        ("quote_volume", "double")
    ]

    def __init__(self, spark, symbol: str = None):
        super().__init__(spark)
        self.symbol = symbol

    def postprocess(self, df: DataFrame):
        """Normalize crypto price data."""
        from pyspark.sql import functions as F

        # Rename columns
        df = df.withColumnRenamed("volumefrom", "volume") \
               .withColumnRenamed("volumeto", "quote_volume")

        # Convert timestamp to date
        if "time" in df.columns:
            df = df.withColumn(
                "trade_date",
                F.to_date(F.from_unixtime(F.col("time")))
            )

        # Add symbol if from context
        if self.symbol and "symbol" not in df.columns:
            df = df.withColumn("symbol", F.lit(self.symbol))

        # Remove invalid records
        df = df.filter(
            (F.col("open") > 0) &
            (F.col("high") >= F.col("low")) &
            (F.col("volume") >= 0)
        )

        return df


class CryptoMetadataFacet(Facet):
    """
    Facet for cryptocurrency metadata (coin info).

    Normalizes coin metadata from CryptoCompare API.
    """

    SPARK_CASTS = {
        "symbol": "string",
        "name": "string",
        "algorithm": "string",
        "proof_type": "string",
        "total_supply": "double",
        "max_supply": "double"
    }

    FINAL_COLUMNS = [
        ("symbol", "string"),
        ("name", "string"),
        ("algorithm", "string"),
        ("proof_type", "string"),
        ("total_supply", "double"),
        ("max_supply", "double")
    ]

    def postprocess(self, df: DataFrame):
        """Normalize metadata."""
        from pyspark.sql import functions as F

        # Rename common fields
        if "Symbol" in df.columns:
            df = df.withColumnRenamed("Symbol", "symbol")
        if "CoinName" in df.columns:
            df = df.withColumnRenamed("CoinName", "name")
        if "Algorithm" in df.columns:
            df = df.withColumnRenamed("Algorithm", "algorithm")
        if "ProofType" in df.columns:
            df = df.withColumnRenamed("ProofType", "proof_type")
        if "TotalCoinSupply" in df.columns:
            df = df.withColumnRenamed("TotalCoinSupply", "total_supply")
        if "MaxSupply" in df.columns:
            df = df.withColumnRenamed("MaxSupply", "max_supply")

        # Convert supply strings to numbers
        if "total_supply" in df.columns:
            df = df.withColumn(
                "total_supply",
                F.regexp_replace(F.col("total_supply"), "[^0-9.]", "").cast("double")
            )

        return df


# ============================================================
# STEP 3: CREATE AN INGESTOR
# ============================================================

class CryptoIngestor(Ingestor):
    """
    Ingestor for CryptoCompare API.

    Orchestrates:
    - API calls via HttpClient
    - Data normalization via Facets
    - Writing to Bronze layer via BronzeSink

    This is the orchestration layer that ties everything together.
    """

    def __init__(self, crypto_cfg: Dict, storage_cfg: Dict, spark: SparkSession):
        """
        Initialize crypto ingestor.

        Args:
            crypto_cfg: Provider configuration (from configs/providers/crypto.yaml)
            storage_cfg: Storage configuration
            spark: SparkSession instance
        """
        super().__init__(storage_cfg=storage_cfg)

        # Initialize registry (endpoint definitions)
        self.registry = CryptoRegistry(crypto_cfg)

        # Initialize HTTP client
        api_keys = crypto_cfg.get("credentials", {}).get("api_keys", [])
        self.http = HttpClient(
            base_urls=self.registry.base_urls,
            headers=self.registry.headers,
            rate_limit=self.registry.rate_limit,
            api_key_pool=ApiKeyPool(api_keys, rotation_minutes=90)
        )

        # Initialize Bronze sink (for writing data)
        self.sink = BronzeSink(storage_cfg)

        # Store Spark session
        self.spark = spark

    def _fetch_calls(self, calls: Iterator[Dict], response_key: str = None) -> List[List[Dict]]:
        """
        Execute API calls and return batches of data.

        Args:
            calls: Iterator of call specifications
            response_key: Key in response containing data array (None = use full response)

        Returns:
            List of batches (one batch per call)
        """
        batches = []
        for call in calls:
            # Render endpoint URL and query params
            ep, path, query = self.registry.render(call["ep_name"], **call["params"])

            # Make HTTP request
            payload = self.http.request(ep.base, path, query, ep.method)

            # Extract data from response
            if response_key:
                data = payload.get(response_key, [])
            else:
                # If response is array, use directly; else wrap in list
                data = payload if isinstance(payload, list) else [payload]

            batches.append(data)

        return batches

    # ============================================================
    # DATA INGESTION METHODS
    # ============================================================

    def ingest_daily_prices(self, symbol: str, date_from: str, date_to: str,
                           limit: int = None) -> None:
        """
        Ingest daily OHLCV price data for a cryptocurrency.

        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            limit: Optional limit on number of days
        """
        print(f"Ingesting daily prices for {symbol}: {date_from} to {date_to}")

        # Define API call
        calls = [{
            "ep_name": "daily_ohlcv",
            "params": {
                "fsym": symbol,
                "tsym": "USD",
                "toTs": self._date_to_timestamp(date_to),
                "limit": limit or 2000
            }
        }]

        # Fetch data from API
        batches = self._fetch_calls(calls, response_key="Data")

        # Normalize with facet
        facet = CryptoPriceFacet(self.spark, symbol=symbol)
        df = facet.normalize(batches)

        # Write to Bronze
        self.sink.write(
            provider="crypto",
            table="daily_prices",
            df=df,
            partition_cols=["trade_date"]
        )

        print(f"✓ Wrote {df.count()} records to Bronze: crypto.daily_prices")

    def ingest_coin_metadata(self, symbols: List[str] = None) -> None:
        """
        Ingest metadata for cryptocurrencies.

        Args:
            symbols: List of symbols to fetch (None = all)
        """
        print(f"Ingesting coin metadata for {len(symbols) if symbols else 'all'} coins")

        # Define API call
        calls = [{
            "ep_name": "coin_list",
            "params": {}
        }]

        # Fetch data
        batches = self._fetch_calls(calls, response_key="Data")

        # Normalize
        facet = CryptoMetadataFacet(self.spark)
        df = facet.normalize(batches)

        # Filter to specific symbols if requested
        if symbols:
            from pyspark.sql import functions as F
            df = df.filter(F.col("symbol").isin(symbols))

        # Write to Bronze
        self.sink.write(
            provider="crypto",
            table="coin_metadata",
            df=df
        )

        print(f"✓ Wrote {df.count()} records to Bronze: crypto.coin_metadata")

    def ingest_top_coins(self, limit: int = 100, date_from: str = None,
                        date_to: str = None) -> None:
        """
        Ingest data for top N cryptocurrencies by market cap.

        Args:
            limit: Number of top coins to fetch
            date_from: Start date for price data
            date_to: End date for price data
        """
        print(f"Ingesting top {limit} coins by market cap")

        # First, get list of top coins
        # (In real implementation, call API to get top coins)
        top_symbols = ["BTC", "ETH", "BNB", "SOL", "ADA"][:limit]

        # Ingest metadata
        self.ingest_coin_metadata(symbols=top_symbols)

        # Ingest price data for each coin
        if date_from and date_to:
            for symbol in top_symbols:
                self.ingest_daily_prices(symbol, date_from, date_to)

    # ============================================================
    # MAIN ENTRY POINT
    # ============================================================

    def run_all(self, symbols: List[str] = None, date_from: str = None,
                date_to: str = None, limit: int = 100) -> None:
        """
        Main entry point - ingest all data.

        Args:
            symbols: List of symbols (None = top coins)
            date_from: Start date for prices
            date_to: End date for prices
            limit: Number of coins to fetch if symbols=None
        """
        if symbols:
            # Specific symbols requested
            self.ingest_coin_metadata(symbols=symbols)
            if date_from and date_to:
                for symbol in symbols:
                    self.ingest_daily_prices(symbol, date_from, date_to)
        else:
            # Fetch top coins
            self.ingest_top_coins(limit=limit, date_from=date_from, date_to=date_to)

    # ============================================================
    # HELPER METHODS
    # ============================================================

    @staticmethod
    def _date_to_timestamp(date_str: str) -> int:
        """Convert YYYY-MM-DD to Unix timestamp."""
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp())


# ============================================================
# EXAMPLE CONFIGURATION
# ============================================================

def create_example_config() -> Dict:
    """
    Create example provider configuration.

    In production, this would be in configs/providers/crypto.yaml
    """
    return {
        "base_urls": ["https://min-api.cryptocompare.com"],
        "headers": {
            "Content-Type": "application/json"
        },
        "rate_limit_per_sec": 0.5,  # 2 requests per second

        "endpoints": {
            # Daily OHLCV prices
            "daily_ohlcv": {
                "path_template": "/data/v2/histoday",
                "method": "GET",
                "required_params": ["fsym", "tsym"],
                "default_query": {
                    "limit": 30,
                    "toTs": None  # Current time if not specified
                },
                "response_key": "Data"
            },

            # Coin metadata
            "coin_list": {
                "path_template": "/data/all/coinlist",
                "method": "GET",
                "required_params": [],
                "default_query": {},
                "response_key": "Data"
            },

            # Top coins by market cap
            "top_coins": {
                "path_template": "/data/top/mktcapfull",
                "method": "GET",
                "required_params": ["tsym"],
                "default_query": {
                    "limit": 10
                },
                "response_key": "Data"
            }
        },

        "credentials": {
            "api_keys": [
                # Add your API keys here
                # "your-api-key-1",
                # "your-api-key-2"
            ]
        }
    }


# ============================================================
# EXAMPLE USAGE
# ============================================================

def example_usage():
    """
    Demonstrate how to use the custom CryptoIngestor.
    """
    print("=" * 70)
    print("CUSTOM PROVIDER EXAMPLE - CryptoIngestor")
    print("=" * 70)

    # Initialize Spark
    spark = SparkSession.builder \
        .appName("CustomProviderExample") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()

    # Create configuration
    crypto_cfg = create_example_config()

    storage_cfg = {
        "roots": {
            "bronze": "storage/bronze"
        }
    }

    # Initialize ingestor
    ingestor = CryptoIngestor(
        crypto_cfg=crypto_cfg,
        storage_cfg=storage_cfg,
        spark=spark
    )

    print("\n" + "=" * 70)
    print("Example 1: Ingest metadata for specific coins")
    print("=" * 70)

    # Example 1: Ingest coin metadata
    # Note: This would call the real API - commented out to avoid actual API calls
    # ingestor.ingest_coin_metadata(symbols=["BTC", "ETH", "SOL"])

    print("\n" + "=" * 70)
    print("Example 2: Ingest price data for Bitcoin")
    print("=" * 70)

    # Example 2: Ingest daily prices for Bitcoin
    # ingestor.ingest_daily_prices(
    #     symbol="BTC",
    #     date_from="2024-01-01",
    #     date_to="2024-01-31"
    # )

    print("\n" + "=" * 70)
    print("Example 3: Ingest top coins")
    print("=" * 70)

    # Example 3: Ingest top 10 coins with price data
    # ingestor.run_all(
    #     limit=10,
    #     date_from="2024-01-01",
    #     date_to="2024-01-31"
    # )

    spark.stop()

    print("\nExamples complete!")
    print("\nNote: Actual API calls are commented out to avoid hitting real endpoints.")
    print("Uncomment the ingestor calls above to test with real API.")


# ============================================================
# KEY TAKEAWAYS
# ============================================================

"""
CREATING A CUSTOM PROVIDER - CHECKLIST:

1. CREATE CONFIGURATION (configs/providers/yourprovider.yaml):
   - base_urls: List of API base URLs
   - endpoints: Define each API endpoint
     - path_template: URL path with {placeholders}
     - method: GET, POST, etc.
     - required_params: Required parameters
     - default_query: Default query parameters
     - response_key: Key containing data array in response
   - credentials: API keys, tokens, etc.
   - rate_limit_per_sec: Rate limiting

2. CREATE REGISTRY (registry.py):
   ```python
   class YourProviderRegistry(BaseRegistry):
       pass  # BaseRegistry handles everything
   ```

3. CREATE FACETS (facets/):
   - One facet per data type (prices, metadata, etc.)
   - Define NUMERIC_COERCE for type consistency
   - Define SPARK_CASTS for final types
   - Define FINAL_COLUMNS for schema
   - Implement postprocess() for transformations

4. CREATE INGESTOR (ingestor.py):
   - Inherit from Ingestor
   - Initialize registry, HTTP client, sink
   - Implement data ingestion methods
   - Implement run_all() as main entry point

5. TESTING:
   - Test with small data first
   - Verify API pagination works
   - Check error handling
   - Validate output schema
   - Test rate limiting

6. INTEGRATION:
   - Add to configs/providers/
   - Add to run_full_pipeline.py
   - Document API requirements
   - Add example usage

COMMON PATTERNS:

Pattern 1: Pagination
```python
def _fetch_with_pagination(self, ep_name, params, max_pages=None):
    offset = 0
    limit = 1000
    all_data = []

    while True:
        params["offset"] = offset
        params["limit"] = limit

        data = self._fetch_call(ep_name, params)
        if not data:
            break

        all_data.extend(data)
        offset += limit

        if max_pages and len(all_data) / limit >= max_pages:
            break

    return all_data
```

Pattern 2: Batch Processing
```python
def ingest_multiple(self, symbols: List[str]):
    for symbol in symbols:
        self.ingest_single(symbol)
        # Rate limiting handled by HttpClient
```

Pattern 3: Error Handling
```python
try:
    data = self.http.request(...)
except Exception as e:
    print(f"Error fetching {symbol}: {e}")
    continue  # Skip this symbol, continue with others
```

Pattern 4: Date Range Handling
```python
def split_date_range(date_from, date_to, chunk_days=30):
    # Split large date ranges into chunks
    # To avoid API limits and memory issues
    pass
```

FILES TO REFERENCE:
- /home/user/de_Funk/datapipelines/providers/chicago/chicago_ingestor.py
- /home/user/de_Funk/datapipelines/providers/bls/bls_registry.py
- /home/user/de_Funk/datapipelines/base/registry.py
- /home/user/de_Funk/datapipelines/base/http_client.py
- /home/user/de_Funk/datapipelines/ingestors/bronze_sink.py
"""


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CUSTOM PROVIDER EXAMPLE")
    print("=" * 70)
    print("\nThis example demonstrates how to create a custom provider for")
    print("ingesting data from external APIs in de_Funk.")
    print("\nComponents:")
    print("1. CryptoRegistry - Defines API endpoints")
    print("2. CryptoPriceFacet - Normalizes price data")
    print("3. CryptoMetadataFacet - Normalizes metadata")
    print("4. CryptoIngestor - Orchestrates ingestion")
    print("\n")

    example_usage()

    print("\n" + "=" * 70)
    print("Next steps:")
    print("1. Study the component implementations above")
    print("2. Create your provider configuration YAML")
    print("3. Implement your facets for data normalization")
    print("4. Implement your ingestor for orchestration")
    print("5. Test with sample API calls")
    print("6. Integrate with run_full_pipeline.py")
    print("\nSee also:")
    print("- examples/facets/custom_facet_example.py")
    print("- datapipelines/providers/chicago/")
    print("- datapipelines/providers/bls/")
    print("=" * 70)
