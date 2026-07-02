"""
Alpha Vantage Provider Implementation.

Implements data ingestion from Alpha Vantage API.
Configuration loaded from markdown documentation (single source of truth).

Features:
- Rate limiting: Pro tier 75 calls/min (1.25 calls/sec)
- Bulk ticker discovery via LISTING_STATUS endpoint
- All financial statement endpoints (income, balance, cash flow, earnings)
- Integration with IngestorEngine for distributed cluster execution

Usage:
    from de_funk.pipelines.providers.alpha_vantage import create_alpha_vantage_provider
    from de_funk.pipelines.base.ingestor_engine import IngestorEngine

    provider = create_alpha_vantage_provider(spark, docs_path)
    engine = IngestorEngine(provider, storage_cfg)

    # Set tickers to process
    provider.set_tickers(["AAPL", "MSFT", "GOOGL"])

    # Ingest specific data types
    results = engine.run(work_items=["prices", "reference"])

Author: de_Funk Team
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import List, Optional, Any, Dict, Generator
from pathlib import Path

from pyspark.sql import DataFrame

from de_funk.pipelines.base.provider import BaseProvider, DataType, FetchResult
from de_funk.pipelines.base.http_client import HttpClient
from de_funk.pipelines.base.key_pool import ApiKeyPool
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# Mapping from DataType enum to endpoint_id in markdown
DATATYPE_TO_ENDPOINT = {
    DataType.REFERENCE: "company_overview",
    DataType.PRICES: "time_series_daily_adjusted",
    DataType.INCOME_STATEMENT: "income_statement",
    DataType.BALANCE_SHEET: "balance_sheet",
    DataType.CASH_FLOW: "cash_flow",
    DataType.EARNINGS: "earnings",
    DataType.OPTIONS: "historical_options",
    DataType.DIVIDENDS: "dividends",
    DataType.SPLITS: "splits",
}


class AlphaVantageProvider(BaseProvider):
    """
    Alpha Vantage implementation of BaseProvider.

    Configuration loaded from:
    - Data Sources/Providers/Alpha Vantage.md
    - Data Sources/Endpoints/Alpha Vantage/**/*.md

    Features:
    - Raw layer caching: When storage_path is set, raw API responses are saved
      as JSON files to storage/raw/alpha_vantage/{endpoint}/{ticker}.json
    - On subsequent runs, cached raw files are used instead of making API calls
    - This mirrors the Socrata CSV caching pattern used by Chicago/Cook County providers
    - Use force_api=True to bypass cache and always hit the API
    """

    PROVIDER_NAME = "Alpha Vantage"

    def __init__(
        self,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize Alpha Vantage provider.

        Args:
            spark: SparkSession
            docs_path: Path to repo root
            storage_path: Path to storage root. When set, enables raw layer caching:
                - Raw API responses saved to: {storage_path}/raw/alpha_vantage/{endpoint}/{ticker}.json
                - On re-runs, cached raw files are used instead of API calls
                - This avoids hitting rate limits when re-processing raw → bronze
        """
        # Tickers to process (set via set_tickers() before running)
        self._tickers: List[str] = []

        # Raw layer storage (automatic when storage_path is set, like Socrata)
        self._storage_path = Path(storage_path) if storage_path else None

        # Initialize base (loads markdown config)
        super().__init__(
            provider_id="alpha_vantage",
            spark=spark,
            docs_path=docs_path
        )

    def _setup(self) -> None:
        """Setup HTTP client and API key pool."""
        # Get API keys from environment
        api_keys = []
        if self.env_api_key:
            env_value = os.environ.get(self.env_api_key, "")
            if env_value:
                api_keys = [k.strip() for k in env_value.split(",") if k.strip()]

        self.key_pool = ApiKeyPool(api_keys, cooldown_seconds=60.0)

        # Build base URLs dict for HttpClient
        base_urls = {"core": self.base_url} if self.base_url else {}

        # Get headers from config (usually empty for Alpha Vantage)
        headers = {}
        if self._provider_config:
            headers = self._provider_config.default_headers or {}

        # Create HTTP client
        self.http = HttpClient(
            base_urls,
            headers,
            self.rate_limit,
            self.key_pool
        )

        # Thread lock for HTTP requests
        self._http_lock = threading.Lock()

        # Get US exchanges from provider settings
        self._us_exchanges = self.get_provider_setting(
            'us_exchanges',
            ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
        )

        logger.info(
            f"AlphaVantageProvider initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={self.rate_limit}"
        )
        if self._storage_path:
            logger.info(f"Raw layer enabled: {self._storage_path}/raw/alpha_vantage/")

    # =========================================================================
    # RAW DATA DUMP (automatic when storage_path is set, like Socrata)
    # =========================================================================

    def enable_raw_save(self, storage_path: Path = None, enabled: bool = True) -> None:
        """
        Enable/disable saving raw API responses (JSON files) before transformation.

        Raw responses are saved to: {storage_path}/raw/alpha_vantage/{endpoint_id}/{ticker}.json

        Args:
            storage_path: Base storage path (optional - updates storage_path if provided)
            enabled: Whether to enable raw saving
        """
        if storage_path:
            self._storage_path = Path(storage_path) if enabled else None
        elif not enabled:
            self._storage_path = None

        if self._storage_path:
            raw_dir = self._storage_path / 'raw' / 'alpha_vantage'
            raw_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Raw data dump enabled: {raw_dir}")
        else:
            logger.info("Raw data dump disabled")

    def _get_raw_path(self, endpoint_id: str, ticker: str) -> Optional[Path]:
        """
        Get the raw layer file path for a JSON response.

        Raw layer structure (consistent with Socrata):
            storage/raw/alpha_vantage/{endpoint_id}/{ticker}.json

        Args:
            endpoint_id: API endpoint identifier
            ticker: Ticker symbol

        Returns:
            Path to raw JSON file, or None if storage_path not configured
        """
        if not self._storage_path:
            return None

        raw_dir = self._storage_path / 'raw' / 'alpha_vantage' / endpoint_id
        return raw_dir / f"{ticker}.json"

    def _save_raw_response(
        self,
        ticker: str,
        endpoint_id: str,
        payload: Any,
        timestamp: datetime = None
    ) -> Optional[Path]:
        """
        Save raw API response to JSON file.

        Args:
            ticker: Ticker symbol
            endpoint_id: API endpoint identifier
            payload: Raw API response (dict or list)
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Path to saved file, or None if storage_path not configured
        """
        file_path = self._get_raw_path(endpoint_id, ticker)
        if not file_path:
            return None

        try:
            # Create endpoint directory
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Add metadata wrapper
            ts = timestamp or datetime.now()
            raw_data = {
                "_meta": {
                    "ticker": ticker,
                    "endpoint_id": endpoint_id,
                    "fetched_at": ts.isoformat(),
                    "provider": "alpha_vantage"
                },
                "response": payload
            }

            with open(file_path, 'w') as f:
                json.dump(raw_data, f, indent=2, default=str)

            logger.debug(f"Saved raw response: {file_path}")
            return file_path

        except Exception as e:
            logger.warning(f"Failed to save raw response for {ticker}/{endpoint_id}: {e}")
            return None

    def _load_raw_response(
        self,
        ticker: str,
        endpoint_id: str
    ) -> Optional[Any]:
        """
        Load raw API response from JSON file if it exists.

        This enables re-processing from raw → bronze without hitting the API again.
        Pattern mirrors Socrata CSV caching.

        Args:
            ticker: Ticker symbol
            endpoint_id: API endpoint identifier

        Returns:
            Raw API response payload, or None if file doesn't exist
        """
        file_path = self._get_raw_path(endpoint_id, ticker)
        if not file_path or not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                raw_data = json.load(f)

            # Extract the response payload (unwrap metadata wrapper)
            payload = raw_data.get("response", raw_data)

            logger.debug(f"Loaded raw response: {file_path}")
            return payload

        except Exception as e:
            logger.warning(f"Failed to load raw response for {ticker}/{endpoint_id}: {e}")
            return None

    def has_raw_data(self, ticker: str, endpoint_id: str) -> bool:
        """
        Check if raw data exists for a ticker/endpoint combination.

        Args:
            ticker: Ticker symbol
            endpoint_id: API endpoint identifier

        Returns:
            True if raw JSON file exists
        """
        file_path = self._get_raw_path(endpoint_id, ticker)
        return file_path is not None and file_path.exists()

    # =========================================================================
    # TICKER MANAGEMENT
    # =========================================================================

    def set_tickers(self, tickers: List[str]) -> None:
        """
        Set tickers to process for ingestion.

        Must be called before using fetch() or running with IngestorEngine.

        Args:
            tickers: List of ticker symbols
        """
        self._tickers = tickers
        logger.info(f"AlphaVantageProvider: set {len(tickers)} tickers")

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION
    # =========================================================================

    def list_work_items(self, **kwargs) -> List[str]:
        """List available data types for ingestion."""
        # Return DataType values that have corresponding endpoints configured
        work_items = []
        for dt, endpoint_id in DATATYPE_TO_ENDPOINT.items():
            if endpoint_id in self._endpoints:
                work_items.append(dt.value)
        return work_items

    def populate_raw_cache(
        self,
        work_item: str,
        force_api: bool = False,
        **kwargs
    ) -> Dict[str, int]:
        """
        Populate raw JSON cache by fetching from API (no transformation).

        This is Phase 1 of the Spark-native pipeline:
        1. populate_raw_cache() - API → Raw JSON files (this method)
        2. fetch_as_dataframe() - Spark reads raw JSON → DataFrame

        Only fetches data for tickers missing from cache (unless force_api=True).

        Args:
            work_item: Data type to fetch (e.g., 'prices', 'reference')
            force_api: If True, refetch all tickers even if cached

        Returns:
            Dict with stats: {'cached': N, 'fetched': N, 'failed': N, 'total': N}
        """
        data_type = self._get_data_type(work_item)
        if not data_type:
            logger.warning(f"Unknown work item: {work_item}")
            return {'cached': 0, 'fetched': 0, 'failed': 0, 'total': 0}

        if not self._tickers:
            logger.warning("No tickers set. Call set_tickers() before populate_raw_cache().")
            return {'cached': 0, 'fetched': 0, 'failed': 0, 'total': 0}

        if not self._storage_path:
            raise ValueError("storage_path must be set to use populate_raw_cache()")

        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id or endpoint_id not in self._endpoints:
            logger.warning(f"No endpoint configured for: {work_item}")
            return {'cached': 0, 'fetched': 0, 'failed': 0, 'total': 0}

        stats = {'cached': 0, 'fetched': 0, 'failed': 0, 'total': len(self._tickers)}

        # Check which tickers need fetching
        tickers_to_fetch = []
        for ticker in self._tickers:
            if force_api or not self.has_raw_data(ticker, endpoint_id):
                tickers_to_fetch.append(ticker)
            else:
                stats['cached'] += 1

        logger.info(
            f"populate_raw_cache({work_item}): {stats['cached']} cached, "
            f"{len(tickers_to_fetch)} to fetch"
        )

        # Fetch missing tickers
        for i, ticker in enumerate(tickers_to_fetch):
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(tickers_to_fetch)} tickers fetched")

            result = self._fetch_single(ticker, data_type, force_api=True, **kwargs)

            if result.success and result.data:
                stats['fetched'] += 1
            else:
                stats['failed'] += 1
                logger.debug(f"Failed to fetch {ticker}: {result.error}")

        logger.info(
            f"populate_raw_cache({work_item}) complete: "
            f"{stats['fetched']} fetched, {stats['failed']} failed, {stats['cached']} cached"
        )

        return stats

    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        force_api: bool = False,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch data for a data type, yielding batches of records.

        Iterates through tickers and fetches the specified data type for each.
        If raw layer is enabled, will use cached raw JSON files when available
        (similar to Socrata CSV caching pattern).

        Args:
            work_item: Data type to fetch (e.g., 'prices', 'reference')
            max_records: Maximum records to return
            force_api: If True, always hit API even if raw cache exists
            **kwargs: Additional parameters passed to _fetch_single
        """
        data_type = self._get_data_type(work_item)
        if not data_type:
            logger.warning(f"Unknown work item: {work_item}")
            return

        if not self._tickers:
            logger.warning("No tickers set. Call set_tickers() before fetch().")
            return

        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id or endpoint_id not in self._endpoints:
            logger.warning(f"No endpoint configured for: {work_item}")
            return

        # Log cache status
        if self._storage_path and not force_api:
            cached_count = sum(1 for t in self._tickers if self.has_raw_data(t, endpoint_id))
            logger.info(
                f"Fetching {work_item} for {len(self._tickers)} tickers "
                f"({cached_count} cached, {len(self._tickers) - cached_count} need API)"
            )
        else:
            logger.info(f"Fetching {work_item} for {len(self._tickers)} tickers (API mode)")

        total_records = 0
        from_cache = 0
        from_api = 0

        for ticker in self._tickers:
            if max_records and total_records >= max_records:
                logger.info(f"Reached max_records limit ({max_records})")
                break

            # Track whether this came from cache
            had_cache = self._storage_path and self.has_raw_data(ticker, endpoint_id) and not force_api

            result = self._fetch_single(ticker, data_type, force_api=force_api, **kwargs)

            if not result.success:
                logger.warning(f"Failed to fetch {work_item} for {ticker}: {result.error}")
                continue

            if result.data:
                records = self._convert_to_records(ticker, data_type, result.data)
                if records:
                    total_records += len(records)
                    if had_cache:
                        from_cache += 1
                    else:
                        from_api += 1
                    yield records

        logger.info(
            f"Fetched {total_records} records for {work_item} "
            f"(from cache: {from_cache}, from API: {from_api})"
        )

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """
        Normalize raw records to a Spark DataFrame.

        Uses SparkNormalizer for standard operations (field mapping, type coercion,
        date parsing, metadata). This is the same pattern used by Chicago, Cook County,
        and other providers.
        """
        from de_funk.pipelines.base.normalizer import SparkNormalizer

        if not records:
            return self.spark.createDataFrame([], samplingRatio=1.0)

        data_type = self._get_data_type(work_item)
        if not data_type:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        # Get endpoint config for field mappings and type coercions
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        field_mappings = self.get_field_mappings(endpoint_id) if endpoint_id else {}
        type_coercions = self.get_type_coercions(endpoint_id) if endpoint_id else {}

        logger.info(f"[{endpoint_id}] field_mappings: {len(field_mappings)}, type_coercions: {len(type_coercions)}")

        # Use standard normalizer
        normalizer = SparkNormalizer(self.spark)

        try:
            if data_type == DataType.PRICES:
                return self._normalize_prices(normalizer, records, field_mappings, type_coercions)
            elif data_type == DataType.REFERENCE:
                return self._normalize_reference(normalizer, records, field_mappings, type_coercions)
            elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                              DataType.CASH_FLOW, DataType.EARNINGS):
                return self._normalize_financials(normalizer, records, field_mappings, type_coercions)
            elif data_type in (DataType.DIVIDENDS, DataType.SPLITS):
                return self._normalize_corporate_actions(normalizer, records, field_mappings, type_coercions)
        except Exception as e:
            logger.warning(f"Failed to normalize {work_item}: {e}", exc_info=True)

        return self.spark.createDataFrame(records, samplingRatio=1.0)

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name from endpoint config.

        If bronze.table is just the provider name (no slash), appends the endpoint_id.
        e.g., bronze: alpha_vantage + endpoint_id: prices_daily -> alpha_vantage/prices_daily
        """
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                endpoint = self._endpoints.get(endpoint_id)
                if endpoint and endpoint.bronze:
                    table = endpoint.bronze.table
                    # If table is just provider name (no slash), append endpoint name
                    if '/' not in table:
                        return f"{table}/{endpoint_id}"
                    return table
        return f"alpha_vantage_{work_item}"

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """Get partition columns from endpoint config."""
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                return super().get_partitions(endpoint_id)
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """Get key columns from endpoint config."""
        data_type = self._get_data_type(work_item)
        if data_type:
            endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
            if endpoint_id:
                return super().get_key_columns(endpoint_id)
        return ["ticker"]

    # =========================================================================
    # SPARK JSON READING (Distributed)
    # =========================================================================

    def get_raw_path(self, work_item: str) -> Optional[str]:
        """
        Get path to raw JSON files for bulk reading.

        Returns glob pattern if raw files exist, None otherwise.
        Used by IngestorEngine to determine if BULK path should be used.

        Args:
            work_item: Work item identifier (e.g., 'prices', 'reference')

        Returns:
            Glob pattern (e.g., 'storage/raw/alpha_vantage/prices/*.json') or None
        """
        if not self._storage_path:
            return None

        data_type = self._get_data_type(work_item)
        if not data_type:
            return None

        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id:
            return None

        raw_dir = self._storage_path / "raw" / "alpha_vantage" / endpoint_id
        if not raw_dir.exists():
            return None

        json_files = list(raw_dir.glob("*.json"))
        if not json_files:
            return None

        logger.debug(f"{work_item}: Found {len(json_files)} raw JSON files")
        return str(raw_dir / "*.json")

    def read_raw_as_df(self, work_item: str, raw_path: str) -> Optional[DataFrame]:
        """
        Read raw JSON files with Spark and return normalized DataFrame.

        Handles format-specific details:
        - nested_map: Date-keyed JSON (prices) - Struct→Map conversion
        - object: Flat JSON (company overview)
        - array_reports: Nested arrays (financials)

        If endpoint has raw_schema defined, uses explicit schema instead of inference.
        This significantly improves performance for large file sets.

        Args:
            work_item: Work item identifier
            raw_path: Glob pattern to raw JSON files

        Returns:
            Spark DataFrame with normalized data
        """
        data_type = self._get_data_type(work_item)
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        endpoint = self._endpoints.get(endpoint_id)

        json_structure = endpoint.json_structure if endpoint else "object"
        response_key = endpoint.response_key if endpoint else None

        # Check for explicit raw_schema
        has_raw_schema = endpoint and endpoint.raw_schema
        if has_raw_schema:
            logger.info(f"{work_item}: Reading raw JSON with explicit schema (structure={json_structure})")
        else:
            logger.info(f"{work_item}: Reading raw JSON with schema inference (structure={json_structure})")

        try:
            if json_structure == "nested_map":
                df = self._read_nested_map_json(raw_path, response_key, data_type, endpoint)
            elif json_structure == "array_reports":
                df = self._read_array_reports_json(raw_path, data_type, endpoint)
            elif json_structure == "array":
                df = self._read_array_json(raw_path, data_type, endpoint)
            elif json_structure == "object":
                df = self._read_object_json(raw_path, data_type, endpoint)
            else:
                logger.warning(f"Unknown json_structure: {json_structure}, falling back to object")
                df = self._read_object_json(raw_path, data_type, endpoint)

            if df is not None:
                count = df.count()
                logger.info(f"{work_item}: Spark JSON read {count:,} records")

            return df

        except Exception as e:
            logger.error(f"Spark JSON reading failed for {work_item}: {e}", exc_info=True)
            return None

    def _read_nested_map_json(
        self,
        json_pattern: str,
        response_key: str,
        data_type: DataType,
        endpoint=None
    ) -> Optional[DataFrame]:
        """
        Read JSON files with nested map structure (date keys → value objects).

        Used for: time_series_daily (prices)

        Structure:
            {"Time Series (Daily)": {"2024-01-15": {"1. open": "123", ...}, ...}}

        Strategy:
            1. Read all JSON files with Spark (with explicit schema if available)
            2. Extract response_key field
            3. Explode map to (date, struct) rows
            4. Flatten struct fields

        Args:
            json_pattern: Glob pattern for JSON files
            response_key: Key containing the nested map (e.g., "Time Series (Daily)")
            data_type: DataType for normalization
            endpoint: Optional EndpointConfig with raw_schema for explicit schema

        Returns:
            DataFrame with flattened records
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import MapType, StringType, StructType, StructField

        # Build file schema if raw_schema is defined
        # For nested_map, raw_schema defines the VALUE schema (OHLCV fields)
        file_schema = None
        if endpoint and endpoint.raw_schema:
            value_schema = endpoint.get_spark_raw_schema()
            if value_schema:
                # Build full file schema with wrapper:
                # {"_meta": {...}, "response": {"Meta Data": {...}, "Time Series (Daily)": {<date>: <value_schema>}}}
                meta_schema = StructType([
                    StructField("ticker", StringType(), True),
                    StructField("endpoint_id", StringType(), True),
                    StructField("fetched_at", StringType(), True),
                    StructField("provider", StringType(), True)
                ])
                # The nested map becomes MapType(StringType, value_schema)
                map_type = MapType(StringType(), value_schema)
                # Response has Meta Data + the time series map
                response_fields = [StructField("Meta Data", StructType([
                    StructField("1. Information", StringType(), True),
                    StructField("2. Symbol", StringType(), True),
                    StructField("3. Last Refreshed", StringType(), True),
                    StructField("4. Output Size", StringType(), True),
                    StructField("5. Time Zone", StringType(), True),
                ]), True)]
                if response_key:
                    response_fields.append(StructField(response_key, map_type, True))
                response_schema = StructType(response_fields)
                file_schema = StructType([
                    StructField("_meta", meta_schema, True),
                    StructField("response", response_schema, True)
                ])
                logger.debug(f"Using explicit schema with {len(value_schema.fields)} value fields")

        # Read all JSON files - use explicit schema if available, otherwise sampling
        if file_schema:
            df = (self.spark.read
                  .option("multiline", True)
                  .schema(file_schema)
                  .json(json_pattern))
        else:
            # samplingRatio=0.01 samples ~1% of files for schema inference (faster for many small files)
            df = (self.spark.read
                  .option("multiline", True)
                  .option("samplingRatio", "0.01")
                  .json(json_pattern))

        if df.isEmpty():
            return None

        # Extract ticker from input file path
        df = df.withColumn("_file", F.input_file_name())
        df = df.withColumn(
            "ticker",
            F.regexp_extract(F.col("_file"), r"/([A-Z0-9\-\.]+)\.json$", 1)
        )

        # Handle wrapped structure: {"response": {...}, "metadata": {...}}
        if "response" in df.columns:
            df = df.withColumn("_payload", F.col("response"))
        else:
            df = df.withColumn("_payload", F.struct(*[c for c in df.columns if c not in ["_file", "ticker"]]))

        # Extract the nested map using response_key
        # The response_key may have special chars like "Time Series (Daily)"
        if response_key:
            safe_key = f"`{response_key}`"
            df = df.withColumn("_data_map", F.col(f"_payload.{safe_key}"))
        else:
            # If no response_key, assume the payload IS the map
            df = df.withColumn("_data_map", F.col("_payload"))

        # Filter out rows where the map is null
        df = df.filter(F.col("_data_map").isNotNull())

        # Spark infers date-keyed JSON as a Struct (not a Map).
        # explode() only works on Maps, so we need to convert Struct -> Map first.
        data_map_schema = df.schema["_data_map"].dataType
        if isinstance(data_map_schema, StructType):
            # Get the value type (OHLCV struct) from the first field
            if not data_map_schema.fields:
                logger.warning("_data_map struct has no fields")
                return None
            value_type = data_map_schema.fields[0].dataType
            map_type = MapType(StringType(), value_type)

            # Convert: Struct -> JSON string -> Map type
            df = df.withColumn("_data_json", F.to_json(F.col("_data_map")))
            df = df.withColumn("_data_map", F.from_json(F.col("_data_json"), map_type))
            df = df.drop("_data_json")

        # Explode the map: each (date_key, value_struct) becomes a row
        # explode() on a Map creates columns named 'key' and 'value'
        df = df.select(
            "ticker",
            F.explode(F.col("_data_map"))
        )
        # Rename the generated columns to meaningful names
        df = df.withColumnRenamed("key", "trade_date").withColumnRenamed("value", "_ohlcv")

        # Repartition to distribute work across workers (one partition per file is inefficient)
        # Use 200 partitions to match spark.sql.shuffle.partitions default
        num_partitions = int(self.spark.conf.get("spark.sql.shuffle.partitions", "200"))
        df = df.repartition(num_partitions, "ticker")

        # Flatten the OHLCV struct - get all field names dynamically
        ohlcv_schema = df.schema["_ohlcv"].dataType
        if isinstance(ohlcv_schema, StructType):
            for field in ohlcv_schema.fields:
                df = df.withColumn(field.name, F.col(f"_ohlcv.`{field.name}`"))
        df = df.drop("_ohlcv")

        # Now normalize using SparkNormalizer
        return self._normalize_spark_df(df, data_type)

    def _read_object_json(
        self,
        json_pattern: str,
        data_type: DataType,
        endpoint=None
    ) -> Optional[DataFrame]:
        """
        Read JSON files with flat object structure.

        Used for: company_overview (reference)

        Structure:
            {"Symbol": "AAPL", "Name": "Apple Inc", "MarketCap": "3000000000000", ...}

        Strategy:
            1. Read all JSON files with Spark (with explicit schema if available)
            2. Each file becomes one row
            3. Extract ticker from filename

        Args:
            json_pattern: Glob pattern for JSON files
            data_type: DataType for normalization
            endpoint: Optional EndpointConfig with raw_schema for explicit schema

        Returns:
            DataFrame with one row per file
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StructType, StructField, StringType

        # Build file schema if raw_schema is defined
        # For object type, raw_schema defines the response object fields
        file_schema = None
        if endpoint and endpoint.raw_schema:
            response_schema = endpoint.get_spark_raw_schema()
            if response_schema:
                # Build full file schema with wrapper:
                # {"_meta": {...}, "response": {<response_schema>}}
                meta_schema = StructType([
                    StructField("ticker", StringType(), True),
                    StructField("endpoint_id", StringType(), True),
                    StructField("fetched_at", StringType(), True),
                    StructField("provider", StringType(), True)
                ])
                file_schema = StructType([
                    StructField("_meta", meta_schema, True),
                    StructField("response", response_schema, True)
                ])
                logger.debug(f"Using explicit schema with {len(response_schema.fields)} response fields")

        # Read all JSON files - use explicit schema if available, otherwise sampling
        if file_schema:
            df = (self.spark.read
                  .option("multiline", True)
                  .schema(file_schema)
                  .json(json_pattern))
        else:
            # Use sampling to reduce schema inference overhead
            df = (self.spark.read
                  .option("multiline", True)
                  .option("samplingRatio", "0.01")
                  .json(json_pattern))

        if df.isEmpty():
            return None

        # Handle wrapped structure: {"response": {...}, "metadata": {...}}
        if "response" in df.columns:
            # Extract fields from response struct
            response_schema = df.schema["response"].dataType
            if hasattr(response_schema, 'fields'):
                for field in response_schema.fields:
                    df = df.withColumn(field.name, F.col(f"response.`{field.name}`"))
            df = df.drop("response", "metadata")

        # Add ticker from filename if not in data
        df = df.withColumn("_file", F.input_file_name())
        if "Symbol" not in df.columns and "ticker" not in df.columns:
            df = df.withColumn(
                "ticker",
                F.regexp_extract(F.col("_file"), r"/([A-Z0-9\-\.]+)\.json$", 1)
            )
        df = df.drop("_file")

        # Normalize
        return self._normalize_spark_df(df, data_type)

    def _read_array_json(
        self,
        json_pattern: str,
        data_type: DataType,
        endpoint=None
    ) -> Optional[DataFrame]:
        """
        Read JSON files with simple array response.

        Used for: dividends, splits

        Structure:
            {"_meta": {"ticker": "AAPL", ...}, "response": [
                {"ex_dividend_date": "2024-01-15", "amount": "0.25", ...},
                ...
            ]}

        Strategy:
            1. Read all JSON files with Spark
            2. Extract ticker from _meta
            3. Explode the response array
            4. Flatten array elements into columns

        Args:
            json_pattern: Glob pattern for JSON files
            data_type: DataType for normalization
            endpoint: Optional EndpointConfig with raw_schema for explicit schema

        Returns:
            DataFrame with one row per array element
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StructType, StructField, StringType, ArrayType

        # Build file schema if raw_schema is defined
        file_schema = None
        if endpoint and endpoint.raw_schema:
            record_schema = endpoint.get_spark_raw_schema()
            if record_schema:
                meta_schema = StructType([
                    StructField("ticker", StringType(), True),
                    StructField("endpoint_id", StringType(), True),
                    StructField("fetched_at", StringType(), True),
                    StructField("provider", StringType(), True)
                ])
                file_schema = StructType([
                    StructField("_meta", meta_schema, True),
                    StructField("response", ArrayType(record_schema), True)
                ])
                logger.debug(f"Using explicit schema for array JSON")

        # Read all JSON files
        if file_schema:
            df = (self.spark.read
                  .option("multiLine", True)
                  .option("mode", "PERMISSIVE")
                  .schema(file_schema)
                  .json(json_pattern))
        else:
            df = (self.spark.read
                  .option("multiLine", True)
                  .option("mode", "PERMISSIVE")
                  .option("samplingRatio", 0.1)
                  .json(json_pattern))

        if df.isEmpty():
            logger.warning(f"No data read from {json_pattern}")
            return None

        # Extract ticker from _meta
        if "_meta" in df.columns:
            df = df.withColumn("ticker", F.col("_meta.ticker"))
            df = df.drop("_meta")

        # Handle response - could be struct with 'data' array or direct array
        if "response" in df.columns:
            # Filter out null responses
            df = df.filter(F.col("response").isNotNull())

            # Check the response schema to determine structure
            response_schema = df.schema["response"].dataType

            if isinstance(response_schema, StructType):
                # Response is a struct (e.g., {"symbol": "...", "data": [...]})
                # Check if it has a 'data' field containing the array
                field_names = [f.name for f in response_schema.fields]

                if "data" in field_names:
                    # Use response.data as the array
                    array_col = F.col("response.data")
                    logger.debug("Using response.data as array source")
                else:
                    # Unexpected struct without 'data' field
                    logger.warning(f"Response struct has no 'data' field. Fields: {field_names}")
                    return None
            else:
                # Response is directly an array
                array_col = F.col("response")
                logger.debug("Using response directly as array source")

            # Filter out null/empty arrays
            df = df.filter(array_col.isNotNull())
            df = df.filter(F.size(array_col) > 0)

            # Explode the array
            df = df.select(
                "ticker",
                F.explode(array_col).alias("_record")
            )

            # Flatten the struct - get all field names dynamically
            # Skip 'ticker' field if it exists in record to avoid duplicate
            record_schema = df.schema["_record"].dataType
            if isinstance(record_schema, StructType):
                for field in record_schema.fields:
                    # Skip ticker - already extracted from _meta
                    if field.name.lower() == "ticker":
                        continue
                    df = df.withColumn(field.name, F.col(f"_record.`{field.name}`"))
            df = df.drop("_record")

        # Normalize using SparkNormalizer
        return self._normalize_spark_df(df, data_type)

    def _read_array_reports_json(
        self,
        json_pattern: str,
        data_type: DataType,
        endpoint=None
    ) -> Optional[DataFrame]:
        """
        Read JSON files with annual/quarterly report arrays.

        Used for: income_statement, balance_sheet, cash_flow, earnings

        Structure:
            {"annualReports": [...], "quarterlyReports": [...]}
            or {"annualEarnings": [...], "quarterlyEarnings": [...]}

        Strategy:
            1. Read all JSON files with Spark (with explicit schema if available)
            2. Explode annualReports and quarterlyReports arrays
            3. Union with report_type column

        Args:
            json_pattern: Glob pattern for JSON files
            data_type: DataType for normalization
            endpoint: Optional EndpointConfig with raw_schema for explicit schema

        Returns:
            DataFrame with all reports
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StructType, StructField, StringType, ArrayType

        # Build file schema if raw_schema is defined
        # For array_reports, raw_schema defines the report record fields
        file_schema = None
        if endpoint and endpoint.raw_schema:
            report_schema = endpoint.get_spark_raw_schema()
            if report_schema:
                # Build full file schema with wrapper:
                # {"_meta": {...}, "response": {"symbol": "...", "annualReports": [...], "quarterlyReports": [...]}}
                meta_schema = StructType([
                    StructField("ticker", StringType(), True),
                    StructField("endpoint_id", StringType(), True),
                    StructField("fetched_at", StringType(), True),
                    StructField("provider", StringType(), True)
                ])
                # Determine array column names based on data type
                if data_type == DataType.EARNINGS:
                    annual_col = "annualEarnings"
                    quarterly_col = "quarterlyEarnings"
                else:
                    annual_col = "annualReports"
                    quarterly_col = "quarterlyReports"
                response_schema = StructType([
                    StructField("symbol", StringType(), True),
                    StructField(annual_col, ArrayType(report_schema), True),
                    StructField(quarterly_col, ArrayType(report_schema), True)
                ])
                file_schema = StructType([
                    StructField("_meta", meta_schema, True),
                    StructField("response", response_schema, True)
                ])
                logger.debug(f"Using explicit schema with {len(report_schema.fields)} report fields")

        # Read all JSON files - use explicit schema if available, otherwise sampling
        if file_schema:
            df = (self.spark.read
                  .option("multiline", True)
                  .schema(file_schema)
                  .json(json_pattern))
        else:
            # Use sampling to reduce schema inference overhead
            df = (self.spark.read
                  .option("multiline", True)
                  .option("samplingRatio", "0.01")
                  .json(json_pattern))

        if df.isEmpty():
            return None

        # Handle wrapped structure
        if "response" in df.columns:
            response_schema = df.schema["response"].dataType
            if hasattr(response_schema, 'fields'):
                for field in response_schema.fields:
                    df = df.withColumn(field.name, F.col(f"response.`{field.name}`"))
            df = df.drop("response", "metadata")

        # Add ticker from filename
        df = df.withColumn("_file", F.input_file_name())
        df = df.withColumn(
            "ticker",
            F.regexp_extract(F.col("_file"), r"/([A-Z0-9\-\.]+)\.json$", 1)
        )

        # Determine array column names based on data type
        if data_type == DataType.EARNINGS:
            annual_col = "annualEarnings"
            quarterly_col = "quarterlyEarnings"
        else:
            annual_col = "annualReports"
            quarterly_col = "quarterlyReports"

        dfs = []

        # Explode annual reports
        if annual_col in df.columns:
            df_annual = df.filter(F.col(annual_col).isNotNull())
            if not df_annual.isEmpty():
                df_annual = df_annual.select(
                    "ticker",
                    F.explode(F.col(annual_col)).alias("_report")
                )
                df_annual = df_annual.withColumn("report_type", F.lit("annual"))
                # Flatten report struct
                report_schema = df_annual.schema["_report"].dataType
                if hasattr(report_schema, 'fields'):
                    for field in report_schema.fields:
                        df_annual = df_annual.withColumn(field.name, F.col(f"_report.`{field.name}`"))
                df_annual = df_annual.drop("_report")
                dfs.append(df_annual)

        # Explode quarterly reports
        if quarterly_col in df.columns:
            df_quarterly = df.filter(F.col(quarterly_col).isNotNull())
            if not df_quarterly.isEmpty():
                df_quarterly = df_quarterly.select(
                    "ticker",
                    F.explode(F.col(quarterly_col)).alias("_report")
                )
                df_quarterly = df_quarterly.withColumn("report_type", F.lit("quarterly"))
                # Flatten report struct
                report_schema = df_quarterly.schema["_report"].dataType
                if hasattr(report_schema, 'fields'):
                    for field in report_schema.fields:
                        df_quarterly = df_quarterly.withColumn(field.name, F.col(f"_report.`{field.name}`"))
                df_quarterly = df_quarterly.drop("_report")
                dfs.append(df_quarterly)

        if not dfs:
            return None

        # Union all reports
        result = dfs[0]
        for df_part in dfs[1:]:
            result = result.unionByName(df_part, allowMissingColumns=True)

        # Normalize
        return self._normalize_spark_df(result, data_type)

    def _normalize_spark_df(self, df: DataFrame, data_type: DataType) -> DataFrame:
        """
        Apply normalization to a Spark DataFrame using SparkNormalizer.

        Uses the same field mappings and type coercions as the Python path.

        Args:
            df: Raw Spark DataFrame
            data_type: DataType for getting endpoint config

        Returns:
            Normalized DataFrame
        """
        from de_funk.pipelines.base.normalizer import SparkNormalizer

        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        endpoint = self._endpoints.get(endpoint_id) if endpoint_id else None

        if not endpoint:
            return df

        # Get field mappings and type coercions from markdown config
        field_mappings = self._get_field_mappings_for_endpoint(endpoint_id)
        type_coercions = self._get_type_coercions_for_endpoint(endpoint_id)

        normalizer = SparkNormalizer(self.spark)

        # Apply field renaming
        for source_col, target_col in field_mappings.items():
            if source_col in df.columns and source_col != target_col:
                df = df.withColumnRenamed(source_col, target_col)

        # Apply type coercions using SparkNormalizer's safe casting
        df = normalizer._apply_type_coercions(df, type_coercions)

        # Apply date parsing for date columns
        date_columns = self._get_date_columns_for_endpoint(endpoint_id)
        if date_columns:
            df = normalizer._parse_dates(df, date_columns)

        return df

    def _get_field_mappings_for_endpoint(self, endpoint_id: str) -> Dict[str, str]:
        """Get source → target field mappings from endpoint schema."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint or not endpoint.schema:
            return {}

        mappings = {}
        for field in endpoint.schema:
            if field.source and field.source not in ('_computed', '_generated', '_key', '_param', '_na'):
                mappings[field.source] = field.name
        return mappings

    def _get_type_coercions_for_endpoint(self, endpoint_id: str) -> Dict[str, str]:
        """Get field → type coercions from endpoint schema."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint or not endpoint.schema:
            return {}

        coercions = {}
        for field in endpoint.schema:
            if field.coerce:
                # Use target field name for coercion
                coercions[field.name] = field.coerce
        return coercions

    def _get_date_columns_for_endpoint(self, endpoint_id: str) -> List[str]:
        """Get date column names from endpoint schema."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint or not endpoint.schema:
            return []

        date_cols = []
        for field in endpoint.schema:
            if field.type == 'date' or (field.transform and 'to_date' in field.transform):
                date_cols.append(field.name)
        return date_cols

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_data_type(self, work_item: str) -> Optional[DataType]:
        """Convert work_item string to DataType enum."""
        for dt in DataType:
            if dt.value == work_item:
                return dt
        return None

    def _get_response_key(self, data_type: DataType) -> Optional[str]:
        """Get response key from endpoint config."""
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if endpoint_id:
            endpoint = self._endpoints.get(endpoint_id)
            if endpoint:
                return endpoint.response_key
        return None

    def _convert_to_records(
        self,
        ticker: str,
        data_type: DataType,
        data: Any
    ) -> List[Dict]:
        """Convert raw API data to list of record dicts."""
        records = []

        if data_type == DataType.REFERENCE:
            if isinstance(data, dict):
                record = dict(data)
                # Only add ticker if Symbol not in response (Symbol gets renamed to ticker)
                if 'Symbol' not in record:
                    record['ticker'] = ticker
                records.append(record)

        elif data_type == DataType.PRICES:
            if isinstance(data, dict):
                for date_str, ohlcv in data.items():
                    try:
                        # ohlcv should be a dict with OHLCV values
                        if not isinstance(ohlcv, dict):
                            logger.debug(f"Skipping malformed OHLCV for {ticker}/{date_str}: not a dict")
                            continue
                        record = dict(ohlcv)
                        record['ticker'] = ticker
                        record['trade_date'] = date_str
                        records.append(record)
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Skipping malformed OHLCV for {ticker}/{date_str}: {e}")

        elif data_type in (DataType.INCOME_STATEMENT, DataType.BALANCE_SHEET,
                          DataType.CASH_FLOW):
            if isinstance(data, dict):
                for report_type in ['annualReports', 'quarterlyReports']:
                    for report in data.get(report_type, []):
                        record = dict(report)
                        record['ticker'] = ticker
                        record['report_type'] = 'annual' if 'annual' in report_type.lower() else 'quarterly'
                        records.append(record)

        elif data_type == DataType.EARNINGS:
            # EARNINGS API uses different keys: annualEarnings, quarterlyEarnings
            if isinstance(data, dict):
                for report_type in ['annualEarnings', 'quarterlyEarnings']:
                    for report in data.get(report_type, []):
                        record = dict(report)
                        record['ticker'] = ticker
                        record['report_type'] = 'annual' if 'annual' in report_type.lower() else 'quarterly'
                        records.append(record)

        elif data_type == DataType.DIVIDENDS:
            # DIVIDENDS API returns array in 'data' key
            if isinstance(data, list):
                for div in data:
                    record = dict(div)
                    record['ticker'] = ticker
                    records.append(record)

        elif data_type == DataType.SPLITS:
            # SPLITS API returns array in 'data' key
            if isinstance(data, list):
                for split in data:
                    record = dict(split)
                    record['ticker'] = ticker
                    records.append(record)

        return records

    # =========================================================================
    # NORMALIZATION METHODS
    # =========================================================================

    def _normalize_prices(
        self,
        normalizer,
        records: List[Dict],
        field_mappings: Dict[str, str],
        type_coercions: Dict[str, str]
    ) -> DataFrame:
        """Normalize price records using SparkNormalizer."""
        from pyspark.sql import functions as F
        from pyspark.sql.types import LongType, DoubleType

        # Standard numeric fields for prices
        price_coercions = {
            'open': 'double', 'high': 'double', 'low': 'double', 'close': 'double',
            'adjusted_close': 'double', 'volume': 'double',
            'dividend_amount': 'double', 'split_coefficient': 'double'
        }
        # Merge with endpoint-defined coercions
        all_coercions = {**price_coercions, **type_coercions}

        # Computed columns for prices
        computed = {
            'year': 'year(trade_date)',
            'month': 'month(trade_date)',
            'volume_weighted': '(high + low + close) / 3.0'
        }

        # Normalize with standard utility
        df = normalizer.normalize(
            records,
            field_mappings=field_mappings,
            type_coercions=all_coercions,
            date_columns=['trade_date'],
            computed_columns=computed,
            add_metadata=False,  # Prices don't need ingestion metadata
            metadata_columns={'asset_type': 'stocks'}
        )

        # Add missing fields specific to prices schema
        df = df.withColumn('transactions', F.lit(None).cast(LongType()))
        df = df.withColumn('otc', F.lit(False))

        # Final column selection
        final_cols = ['trade_date', 'ticker', 'asset_type', 'year', 'month',
                      'open', 'high', 'low', 'close', 'volume', 'volume_weighted',
                      'transactions', 'otc', 'adjusted_close', 'dividend_amount',
                      'split_coefficient']

        for c in final_cols:
            if c not in df.columns:
                df = df.withColumn(c, F.lit(None))

        return df.select(*final_cols)

    def _normalize_reference(
        self,
        normalizer,
        records: List[Dict],
        field_mappings: Dict[str, str],
        type_coercions: Dict[str, str]
    ) -> DataFrame:
        """Normalize reference/overview records using SparkNormalizer."""
        # Use standard normalizer with endpoint-defined mappings
        return normalizer.normalize(
            records,
            field_mappings=field_mappings,
            type_coercions=type_coercions,
            add_metadata=True,
            metadata_columns={'asset_type': 'stocks'}
        )

    def _normalize_financials(
        self,
        normalizer,
        records: List[Dict],
        field_mappings: Dict[str, str],
        type_coercions: Dict[str, str]
    ) -> DataFrame:
        """Normalize financial statement records using SparkNormalizer."""
        # Use standard normalizer with endpoint-defined mappings
        return normalizer.normalize(
            records,
            field_mappings=field_mappings,
            type_coercions=type_coercions,
            date_columns=['fiscal_date_ending'],
            add_metadata=True
        )

    def _normalize_corporate_actions(
        self,
        normalizer,
        records: List[Dict],
        field_mappings: Dict[str, str],
        type_coercions: Dict[str, str]
    ) -> DataFrame:
        """
        Normalize corporate action records (dividends, splits) using SparkNormalizer.

        Dividends schema:
            - ticker, ex_dividend_date, dividend_amount, record_date, payment_date, declaration_date

        Splits schema:
            - ticker, effective_date, split_from, split_to, split_ratio (computed)
        """
        from pyspark.sql import functions as F

        # Detect type from records to determine date columns
        is_dividends = any('ex_dividend_date' in r or 'amount' in r for r in records[:5]) if records else False
        is_splits = any('split_from' in r or 'split_to' in r for r in records[:5]) if records else False

        if is_dividends:
            # Dividend-specific date columns
            date_columns = ['ex_dividend_date', 'record_date', 'payment_date', 'declaration_date']

            # Normalize with standard utility
            df = normalizer.normalize(
                records,
                field_mappings=field_mappings,
                type_coercions=type_coercions,
                date_columns=date_columns,
                add_metadata=True
            )
            return df

        elif is_splits:
            # Split-specific normalization
            date_columns = ['effective_date']

            # Normalize with standard utility
            df = normalizer.normalize(
                records,
                field_mappings=field_mappings,
                type_coercions=type_coercions,
                date_columns=date_columns,
                add_metadata=True
            )

            # Compute split_ratio if split_from and split_to exist
            if 'split_from' in df.columns and 'split_to' in df.columns:
                df = df.withColumn(
                    'split_ratio',
                    F.when(
                        (F.col('split_from').isNotNull()) & (F.col('split_from') != 0),
                        F.col('split_to').cast('double') / F.col('split_from').cast('double')
                    ).otherwise(F.lit(None))
                )
            return df

        else:
            # Fallback - just normalize with provided mappings
            return normalizer.normalize(
                records,
                field_mappings=field_mappings,
                type_coercions=type_coercions,
                add_metadata=True
            )

    # =========================================================================
    # API REQUEST HELPERS
    # =========================================================================

    def _fetch_single(
        self,
        ticker: str,
        data_type: DataType,
        force_api: bool = False,
        **kwargs
    ) -> FetchResult:
        """
        Fetch a single data type for a ticker.

        If raw layer is enabled (storage_path set), will check for existing
        raw JSON files before making API calls. This mirrors the Socrata
        CSV caching pattern.

        Args:
            ticker: Ticker symbol
            data_type: Type of data to fetch
            force_api: If True, always hit API even if raw exists
            **kwargs: Additional parameters (outputsize, etc.)

        Returns:
            FetchResult with data or error
        """
        endpoint_id = DATATYPE_TO_ENDPOINT.get(data_type)
        if not endpoint_id:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=f"Unsupported data type: {data_type}"
            )

        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=f"Endpoint not configured: {endpoint_id}"
            )

        try:
            # Check if raw data already exists (like Socrata CSV caching)
            # This avoids hitting the API when re-processing raw → bronze
            if self._storage_path and not force_api:
                cached_payload = self._load_raw_response(ticker, endpoint_id)
                if cached_payload is not None:
                    logger.debug(f"Using cached raw for {ticker}/{endpoint_id}")
                    # Extract data using response key from config
                    response_key = endpoint.response_key
                    if response_key:
                        data = cached_payload.get(response_key, cached_payload)
                    else:
                        data = cached_payload
                    return FetchResult(
                        ticker=ticker,
                        data_type=data_type,
                        success=True,
                        data=data
                    )

            # No cached data - make API request
            # Build query params from endpoint config
            params = dict(endpoint.default_query or {})
            params["symbol"] = ticker
            if data_type == DataType.PRICES:
                params["outputsize"] = kwargs.get("outputsize", "full")

            # Add API key
            params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

            # Make request
            with self._http_lock:
                payload = self.http.request("core", "", params, "GET")

            # Save raw response before any transformation (automatic when storage_path set)
            if self._storage_path:
                self._save_raw_response(ticker, endpoint_id, payload)

            # Check for API errors
            if isinstance(payload, dict):
                if "Error Message" in payload:
                    return FetchResult(
                        ticker=ticker,
                        data_type=data_type,
                        success=False,
                        error=payload["Error Message"][:60]
                    )
                if "Information" in payload and len(payload) == 1:
                    return FetchResult(
                        ticker=ticker,
                        data_type=data_type,
                        success=False,
                        error="API limit reached"
                    )

            # Extract data using response key from config
            response_key = endpoint.response_key
            if response_key:
                data = payload.get(response_key, payload)
            else:
                data = payload

            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=True,
                data=data
            )

        except Exception as e:
            return FetchResult(
                ticker=ticker,
                data_type=data_type,
                success=False,
                error=str(e)[:50]
            )

    # =========================================================================
    # TICKER DISCOVERY AND SEEDING
    # =========================================================================

    def discover_tickers(self, state: str = "active", **kwargs) -> tuple:
        """Discover tickers using LISTING_STATUS endpoint."""
        import csv
        import io

        endpoint = self._endpoints.get("listing_status")
        if not endpoint:
            logger.warning("listing_status endpoint not configured")
            return [], {}

        params = dict(endpoint.default_query or {})
        params["state"] = state
        params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

        with self._http_lock:
            response_text = self.http.request_text("core", "", params, "GET")

        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        tickers = [row['symbol'] for row in rows if row.get('symbol')]
        ticker_exchanges = {
            row['symbol']: row.get('exchange', 'UNKNOWN')
            for row in rows if row.get('symbol')
        }

        us_tickers = [t for t in tickers if ticker_exchanges.get(t) in self._us_exchanges]

        return us_tickers, ticker_exchanges

    def get_tickers_by_market_cap(
        self,
        max_tickers: int = None,
        min_market_cap: float = None,
        storage_cfg: Dict = None
    ) -> List[str]:
        """Get tickers sorted by market cap from existing reference data."""
        from pyspark.sql.functions import col, desc, isnan, upper

        if not storage_cfg:
            logger.warning("No storage config provided for market cap ranking")
            return []

        # Market cap is in company_reference (from COMPANY_OVERVIEW), not securities_reference
        bronze_path = Path(storage_cfg["roots"]["bronze"]) / "company_reference"

        if not bronze_path.exists():
            logger.debug(f"company_reference not found at {bronze_path}")
            return []

        try:
            if (bronze_path / "_delta_log").exists():
                df = self.spark.read.format("delta").load(str(bronze_path))
            else:
                df = self.spark.read.parquet(str(bronze_path))

            df_filtered = df.filter(
                (col("market_cap").isNotNull()) &
                (~isnan(col("market_cap"))) &
                (col("market_cap") > 0)
            )

            if "asset_type" in df.columns:
                df_filtered = df_filtered.filter(col("asset_type") == "stocks")

            if min_market_cap:
                df_filtered = df_filtered.filter(col("market_cap") >= min_market_cap)

            df_filtered = df_filtered.filter(
                (~upper(col("ticker")).rlike(r".*[-]?W[S]?$")) &
                (~upper(col("ticker")).rlike(r".*-P-.*|.*-P[A-Z]$"))
            )

            df_ranked = (df_filtered
                        .select("ticker", "market_cap")
                        .dropDuplicates(["ticker"])
                        .orderBy(desc("market_cap")))

            if max_tickers:
                df_ranked = df_ranked.limit(max_tickers)

            rows = df_ranked.collect()
            return [row.ticker for row in rows]

        except Exception as e:
            logger.warning(f"Failed to get market cap rankings: {e}")
            return []

    def seed_tickers(
        self,
        state: str = "active",
        filter_us_exchanges: bool = True
    ) -> Any:
        """Seed tickers from LISTING_STATUS endpoint to Bronze layer."""
        import csv
        import io
        from datetime import datetime
        from pyspark.sql.types import (
            StructType, StructField, StringType, DateType, TimestampType
        )

        logger.info(f"Seeding tickers (state={state})")

        endpoint = self._endpoints.get("listing_status")
        if not endpoint:
            logger.warning("listing_status endpoint not configured")
            return self.spark.createDataFrame([], samplingRatio=1.0)

        params = dict(endpoint.default_query or {})
        params["state"] = state
        params["apikey"] = self.key_pool.next_key() if self.key_pool else ""

        with self._http_lock:
            response_text = self.http.request_text("core", "", params, "GET")

        csv_reader = csv.DictReader(io.StringIO(response_text))
        rows = list(csv_reader)

        logger.info(f"Fetched {len(rows)} tickers from LISTING_STATUS")

        if filter_us_exchanges:
            rows = [r for r in rows if r.get('exchange') in self._us_exchanges]
            logger.info(f"Filtered to {len(rows)} US exchange tickers")

        now = datetime.now()
        transformed = []
        for row in rows:
            ipo_date = None
            if row.get('ipoDate'):
                try:
                    ipo_date = datetime.strptime(row['ipoDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            delisting_date = None
            if row.get('delistingDate'):
                try:
                    delisting_date = datetime.strptime(row['delistingDate'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            asset_type_raw = row.get('assetType', 'Stock')
            if asset_type_raw == 'Stock':
                asset_type = 'stocks'
            elif asset_type_raw == 'ETF':
                asset_type = 'etfs'
            else:
                asset_type = 'stocks'

            transformed.append({
                'ticker': row.get('symbol'),
                'security_name': row.get('name'),
                'asset_type': asset_type,
                'exchange_code': row.get('exchange'),
                'ipo_date': ipo_date,
                'delisting_date': delisting_date,
                'status': row.get('status', 'Active'),
                'ingestion_timestamp': now,
                'snapshot_date': now.date(),
            })

        schema = StructType([
            StructField('ticker', StringType(), False),
            StructField('security_name', StringType(), True),
            StructField('asset_type', StringType(), True),
            StructField('exchange_code', StringType(), True),
            StructField('ipo_date', DateType(), True),
            StructField('delisting_date', DateType(), True),
            StructField('status', StringType(), True),
            StructField('ingestion_timestamp', TimestampType(), True),
            StructField('snapshot_date', DateType(), True),
        ])

        df = self.spark.createDataFrame(transformed, schema=schema)
        logger.info(f"Created DataFrame with {df.count()} tickers")

        return df


def create_alpha_vantage_provider(
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None
) -> AlphaVantageProvider:
    """
    Factory function to create an AlphaVantageProvider.

    Args:
        spark: SparkSession
        docs_path: Path to repo root
        storage_path: Path to storage root. When set, enables raw layer caching:
            - First run: Fetches from API, saves raw JSON to storage/raw/alpha_vantage/
            - Subsequent runs: Reads from cached raw JSON (no API calls)
            - Use force_api=True on fetch() to bypass cache

    Returns:
        Configured AlphaVantageProvider

    Example:
        # With raw caching enabled
        provider = create_alpha_vantage_provider(
            spark=spark,
            docs_path=repo_root,
            storage_path=Path("/shared/storage")
        )
        provider.set_tickers(["AAPL", "MSFT"])

        # First run: hits API, saves raw JSON
        for batch in provider.fetch("prices"):
            process(batch)

        # Second run: reads from cached raw JSON (no API calls)
        for batch in provider.fetch("prices"):
            process(batch)

        # Force API call even with cache
        for batch in provider.fetch("prices", force_api=True):
            process(batch)
    """
    return AlphaVantageProvider(spark=spark, docs_path=docs_path, storage_path=storage_path)
