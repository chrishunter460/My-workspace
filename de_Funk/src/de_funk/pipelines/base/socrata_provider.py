"""
Socrata Base Provider.

Base class for Socrata-based data providers (Chicago, Cook County, etc.).
Contains shared functionality for date parsing and DataFrame creation.

Usage:
    from de_funk.pipelines.base.socrata_provider import SocrataBaseProvider

    class ChicagoProvider(SocrataBaseProvider):
        PROVIDER_NAME = "Chicago Data Portal"
        ...

Author: de_Funk Team
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Generator
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

from de_funk.pipelines.base.provider import BaseProvider
from de_funk.pipelines.base.socrata_client import SocrataClient
from de_funk.config.logging import get_logger
from de_funk.config.markdown_loader import EndpointConfig

logger = get_logger(__name__)


def _normalize_year_amount(record: dict, year: str) -> None:
    """Normalize year-specific amount columns into a single 'amount' field.

    Socrata budget datasets use wide-format columns like '2016_ordinance_amount'
    or '2013_appropriation_ordinance' instead of a consistent 'amount' column.
    This coalesces the year-matching column into 'amount' at the row level so
    bronze tables have a clean year + amount schema.
    """
    if record.get('amount') is not None:
        return

    # Try year-specific column names (Chicago budget API conventions)
    candidates = [
        f"{year}_ordinance_amount",
        f"{year}_appropriation_ordinance",
    ]
    for col in candidates:
        val = record.get(col)
        if val is not None:
            record['amount'] = val
            return

    # Fallback to generic columns
    for col in ('ordinance_amount', 'estimated_revenue', 'total_budgeted_amount'):
        val = record.get(col)
        if val is not None:
            record['amount'] = val
            return


class SocrataBaseProvider(BaseProvider):
    """
    Base class for Socrata API providers.

    Provides common functionality:
    - Socrata client initialization
    - Date/timestamp parsing for various formats
    - DataFrame creation from endpoint schema
    - Resource ID extraction from endpoint patterns
    - Raw layer support for large CSV downloads
    """

    def __init__(
        self,
        provider_id: str,
        spark=None,
        docs_path: Optional[Path] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize Socrata provider.

        Args:
            provider_id: Provider identifier (e.g., 'chicago', 'cook_county')
            spark: SparkSession
            docs_path: Path to repo root
            storage_path: Path to storage root (for raw layer)
        """
        self._storage_path = Path(storage_path) if storage_path else None
        # Initialize base (loads markdown config)
        super().__init__(provider_id, spark, docs_path)

    # =========================================================================
    # RAW DATA DUMP
    # =========================================================================

    def enable_raw_save(self, storage_path: Path = None, enabled: bool = True) -> None:
        """
        Enable/disable saving raw API responses (CSV files) before transformation.

        Raw CSVs are saved to: {storage_path}/raw/{provider_id}/{endpoint}_{resource_id}.csv

        Args:
            storage_path: Base storage path (optional - updates storage_path if provided)
            enabled: Whether to enable raw saving (sets storage_path to None if False)
        """
        if storage_path:
            self._storage_path = Path(storage_path) if enabled else None
        elif not enabled:
            self._storage_path = None

        if self._storage_path:
            raw_dir = self._storage_path / 'raw' / self.provider_id
            raw_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Raw data dump enabled: {raw_dir}")
        else:
            logger.info(f"Raw data dump disabled for {self.provider_id}")

    def _setup(self) -> None:
        """Setup Socrata client using config from markdown."""
        # Get app token from environment
        import os
        app_token = None
        if self.env_api_key:
            env_value = os.environ.get(self.env_api_key, "")
            if env_value:
                # Handle comma-separated keys
                app_token = env_value.split(",")[0].strip()

        # Get settings from markdown
        default_limit = self.get_provider_setting('default_limit', 50000)
        timeout = self.get_provider_setting('timeout', 120)

        # Create Socrata client
        self.client = SocrataClient(
            base_url=self.base_url,
            app_token=app_token,
            rate_limit_per_sec=self.rate_limit,
            timeout=timeout
        )

        self._default_limit = default_limit

        logger.info(
            f"{self.__class__.__name__} initialized: {len(self._endpoints)} endpoints, "
            f"rate_limit={self.rate_limit}"
        )

    # =========================================================================
    # UNIFIED INTERFACE IMPLEMENTATION
    # =========================================================================

    def list_work_items(self, status: str = 'active', **kwargs) -> List[str]:
        """List available endpoint IDs for ingestion."""
        if status == 'active':
            return [
                eid for eid, ep in self._endpoints.items()
                if ep.status == 'active'
            ]
        return list(self._endpoints.keys())

    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch data for an endpoint, yielding batches of records."""
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            logger.warning(f"Unknown endpoint: {work_item}")
            return

        # Check if this is a multi-year endpoint with view_ids
        if endpoint.view_ids:
            yield from self._fetch_multi_year(work_item, endpoint, max_records, **kwargs)
        else:
            yield from self._fetch_single_resource(work_item, endpoint, max_records, **kwargs)

    def _fetch_single_resource(
        self,
        endpoint_id: str,
        endpoint: EndpointConfig,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch from a single Socrata resource."""
        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            logger.warning(f"Could not extract resource_id for: {endpoint_id}")
            return

        # Use CSV only for full downloads (no max_records limit)
        # When max_records is set, use JSON API for efficiency
        if endpoint.download_method == 'csv' and max_records is None:
            raw_path = self._get_raw_path(endpoint_id, resource_id)

            if raw_path:
                # Raw layer approach: download to file, then read
                if raw_path.exists():
                    logger.info(f"Using existing CSV for {endpoint_id}: {raw_path}")
                else:
                    logger.info(f"Downloading CSV for {endpoint_id}")
                    self.client.download_csv_to_file(
                        resource_id=resource_id,
                        output_path=str(raw_path),
                        label=endpoint_id
                    )
                for batch in self.client.fetch_csv_from_file(
                    file_path=str(raw_path),
                    batch_size=self._default_limit,
                    max_records=max_records,
                    label=endpoint_id
                ):
                    yield batch
                # Preserve raw CSV for verification
                # self._cleanup_raw_file(raw_path, endpoint_id)
            else:
                # Streaming approach (no storage path configured)
                logger.info(f"Using CSV streaming for {endpoint_id}")
                for batch in self.client.fetch_csv(
                    resource_id=resource_id,
                    batch_size=self._default_limit,
                    max_records=max_records,
                    label=endpoint_id
                ):
                    yield batch
            return

        # Default: JSON API with pagination
        params = dict(endpoint.default_query or {})

        for batch in self.client.fetch_all(
            resource_id=resource_id,
            query_params=params,
            limit=self._default_limit,
            max_records=max_records,
            label=endpoint_id
        ):
            yield batch

    def _fetch_multi_year(
        self,
        endpoint_id: str,
        endpoint: EndpointConfig,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """Fetch from multiple year-based view_ids."""
        # Only use CSV for full downloads (no max_records limit)
        use_csv = endpoint.download_method == 'csv' and max_records is None
        params = dict(endpoint.default_query or {})

        if use_csv:
            logger.info(f"Using CSV for multi-year {endpoint_id}")

        # view_ids is Dict[str, str] mapping year -> view_id
        for year, resource_id in endpoint.view_ids.items():
            if not resource_id:
                continue

            year_label = f"{endpoint_id}/{year}"

            if use_csv:
                raw_path = self._get_raw_path(endpoint_id, resource_id, year=year)

                if raw_path:
                    # Raw layer approach: download to file, then read
                    if raw_path.exists():
                        logger.info(f"Using existing CSV for {year_label}: {raw_path}")
                    else:
                        logger.info(f"Downloading CSV for {year_label}")
                        self.client.download_csv_to_file(
                            resource_id=resource_id,
                            output_path=str(raw_path),
                            label=year_label
                        )
                    for batch in self.client.fetch_csv_from_file(
                        file_path=str(raw_path),
                        batch_size=self._default_limit,
                        max_records=max_records,
                        label=year_label
                    ):
                        for record in batch:
                            record['year'] = year
                            _normalize_year_amount(record, year)
                        yield batch
                    # Preserve raw CSV for verification
                    # self._cleanup_raw_file(raw_path, year_label)
                else:
                    # Streaming approach (no storage path configured)
                    for batch in self.client.fetch_csv(
                        resource_id=resource_id,
                        batch_size=self._default_limit,
                        max_records=max_records,
                        label=year_label
                    ):
                        for record in batch:
                            record['year'] = year
                            _normalize_year_amount(record, year)
                        yield batch
            else:
                # Use JSON API with pagination
                for batch in self.client.fetch_all(
                    resource_id=resource_id,
                    query_params=params,
                    limit=self._default_limit,
                    max_records=max_records,
                    label=year_label
                ):
                    for record in batch:
                        record['year'] = year
                        _normalize_year_amount(record, year)
                    yield batch

    def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
        """Normalize raw records to a Spark DataFrame."""
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        return self._create_dataframe(records, endpoint)

    def get_table_name(self, work_item: str) -> str:
        """Get Bronze table name for an endpoint.

        If bronze.table is just the provider name (no slash), appends the work_item.
        e.g., bronze: chicago + work_item: crimes -> chicago/crimes
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            table = endpoint.bronze.table
            # If table is just provider name (no slash), append endpoint name
            if '/' not in table:
                return f"{table}/{work_item}"
            return table
        return f"{self.provider_id}_{work_item}"

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_raw_path(self, endpoint_id: str, resource_id: str, year: Optional[str] = None) -> Optional[Path]:
        """
        Get the raw layer file path for a CSV download.

        Raw layer structure:
            storage/raw/{provider}/{endpoint}_{resource_id}.csv
            storage/raw/{provider}/{endpoint}_{year}_{resource_id}.csv (for multi-year)

        Args:
            endpoint_id: Endpoint identifier
            resource_id: Socrata resource/view ID
            year: Optional year for multi-year endpoints

        Returns:
            Path to raw CSV file, or None if storage_path not configured
        """
        if not self._storage_path:
            return None

        raw_dir = self._storage_path / 'raw' / self.provider_id

        if year:
            filename = f"{endpoint_id}_{year}_{resource_id}.csv"
        else:
            filename = f"{endpoint_id}_{resource_id}.csv"

        return raw_dir / filename

    def _cleanup_raw_file(self, raw_path: Path, label: str) -> None:
        """
        Delete raw CSV file after successful Bronze write.

        Args:
            raw_path: Path to the raw CSV file
            label: Label for logging (endpoint_id or endpoint_id/year)
        """
        try:
            if raw_path.exists():
                file_size = raw_path.stat().st_size
                raw_path.unlink()
                logger.info(f"Cleaned up raw CSV: {label} ({file_size:,} bytes freed)")
        except OSError as e:
            logger.warning(f"Failed to cleanup raw CSV {label}: {e}")

    def _get_resource_id(self, endpoint: EndpointConfig) -> Optional[str]:
        """Extract Socrata 4x4 resource ID from endpoint pattern."""
        pattern = endpoint.endpoint_pattern
        if "/resource/" in pattern and ".json" in pattern:
            start = pattern.find("/resource/") + len("/resource/")
            end = pattern.find(".json")
            return pattern[start:end]
        return None

    def get_resource_id(self, endpoint_id: str) -> Optional[str]:
        """Get Socrata resource ID for an endpoint (public method)."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None
        return self._get_resource_id(endpoint)

    def list_endpoints(self) -> List[str]:
        """List all available endpoint IDs (alias for list_work_items)."""
        return self.list_work_items(status='all')

    # =========================================================================
    # DATE/TIMESTAMP PARSING (Shared by all Socrata providers)
    # =========================================================================

    def _safe_parse_date(self, col_val):
        """
        Normalize date strings to yyyy-MM-dd format for ANSI-safe parsing.

        Uses try_to_timestamp (then cast to date) to gracefully handle malformed
        data by returning NULL instead of throwing an error.

        Handles Socrata date formats:
        - ISO timestamp: 2025-02-26T00:00:00.000 -> 2025-02-26
        - ISO date: 2025-02-26 (no change)
        - US date: 01/16/2025 or 1/6/2025 -> 2025-01-16
        - Month name: October 01 2019 -> 2019-10-01
        - Year only: 2020 -> 2020-01-01
        - NULL/empty: NULL
        """
        trimmed = F.trim(col_val)

        # US date format: MM/DD/YYYY
        parts = F.split(trimmed, "/")
        us_date_formatted = F.concat(
            parts[2],
            F.lit("-"),
            F.lpad(parts[0], 2, "0"),
            F.lit("-"),
            F.lpad(parts[1], 2, "0")
        )

        # Month name format: "October 01 2019" -> "2019-10-01"
        # Split by space: ["October", "01", "2019"]
        space_parts = F.split(trimmed, " ")
        month_name = F.lower(space_parts[0])
        month_num = (
            F.when(month_name == "january", "01")
            .when(month_name == "february", "02")
            .when(month_name == "march", "03")
            .when(month_name == "april", "04")
            .when(month_name == "may", "05")
            .when(month_name == "june", "06")
            .when(month_name == "july", "07")
            .when(month_name == "august", "08")
            .when(month_name == "september", "09")
            .when(month_name == "october", "10")
            .when(month_name == "november", "11")
            .when(month_name == "december", "12")
            .otherwise(None)
        )
        month_name_formatted = F.concat(
            space_parts[2], F.lit("-"),  # year
            month_num, F.lit("-"),       # month
            F.lpad(space_parts[1], 2, "0")  # day
        )

        normalized = (
            F.when(
                col_val.isNull() | (F.length(trimmed) == 0),
                F.lit(None).cast("string")
            ).when(
                trimmed.contains("T"),
                F.substring(trimmed, 1, 10)
            ).when(
                trimmed.contains("/"),
                us_date_formatted
            ).when(
                # Month name format: starts with letter, has 2 spaces
                (F.size(space_parts) == 3) & month_num.isNotNull(),
                month_name_formatted
            ).when(
                F.length(trimmed) == 4,
                F.concat(trimmed, F.lit("-01-01"))
            ).otherwise(
                trimmed
            )
        )

        # Use try_to_timestamp and cast to date (try_to_date not available in PySpark)
        # This returns NULL for malformed dates instead of throwing errors
        return F.try_to_timestamp(normalized, F.lit("yyyy-MM-dd")).cast("date")

    def _safe_parse_timestamp(self, col_val):
        """
        Normalize timestamp strings for ANSI-safe parsing.

        Uses try_to_timestamp to gracefully handle malformed data by returning NULL
        instead of throwing an error (e.g., '2022 03:39:00 AM-07-29 00:00:00').

        Handles formats:
        - ISO: 2025-02-26T14:30:00.000 -> 2025-02-26 14:30:00
        - US: 01/16/2025 -> 2025-01-16 00:00:00
        - Date only: 2025-02-26 -> 2025-02-26 00:00:00
        - Year only: 2020 -> 2020-01-01 00:00:00
        """
        trimmed = F.trim(col_val)

        iso_normalized = F.regexp_replace(
            F.substring(trimmed, 1, 19),
            "T", " "
        )

        parts = F.split(trimmed, "/")
        us_timestamp = F.concat(
            parts[2], F.lit("-"),
            F.lpad(parts[0], 2, "0"), F.lit("-"),
            F.lpad(parts[1], 2, "0"),
            F.lit(" 00:00:00")
        )

        normalized = (
            F.when(
                col_val.isNull() | (F.length(trimmed) == 0),
                F.lit(None).cast("string")
            ).when(
                trimmed.contains("T"),
                iso_normalized
            ).when(
                trimmed.contains("/"),
                us_timestamp
            ).when(
                F.length(trimmed) == 10,
                F.concat(trimmed, F.lit(" 00:00:00"))
            ).when(
                F.length(trimmed) == 4,
                F.concat(trimmed, F.lit("-01-01 00:00:00"))
            ).otherwise(
                trimmed
            )
        )

        # Use try_to_timestamp to return NULL for malformed dates instead of throwing errors
        return F.try_to_timestamp(normalized, F.lit("yyyy-MM-dd HH:mm:ss"))

    def _create_dataframe(
        self,
        records: List[Dict],
        endpoint: EndpointConfig
    ) -> DataFrame:
        """
        Create Spark DataFrame from records using endpoint schema.

        Uses SparkNormalizer for core operations (field mapping, type coercion)
        with Socrata-specific date parsing.

        Record keys are normalized (e.g., "Case Number" -> "case_number") to match
        schema conventions.

        Args:
            records: List of record dicts from API
            endpoint: Endpoint configuration with schema

        Returns:
            Spark DataFrame
        """
        import json as json_module
        from de_funk.pipelines.base.normalizer import SparkNormalizer

        # Normalize record keys: "Case Number" -> "case_number"
        # This ensures CSV column names match schema source definitions
        # Also handle the_geom fields - convert complex types to JSON strings
        # (Socrata geom fields can be string/WKT, array/coords, or dict/GeoJSON)
        if records:
            normalized_records = []
            for record in records:
                normalized_record = {}
                for k, v in record.items():
                    norm_key = self._normalize_column_name(k)
                    # Convert geom/location fields to JSON string if they're complex types
                    # Socrata geom fields can be string (WKT), array (coords), or dict (GeoJSON)
                    # Common names: the_geom, location, shape, geometry
                    is_geom_field = norm_key in ('the_geom', 'location', 'shape', 'geometry') or norm_key.endswith('_geom')
                    if is_geom_field and isinstance(v, (dict, list)):
                        normalized_record[norm_key] = json_module.dumps(v)
                    else:
                        normalized_record[norm_key] = v
                normalized_records.append(normalized_record)
            records = normalized_records

        if not endpoint.schema:
            return self.spark.createDataFrame(records, samplingRatio=1.0)

        # Extract field mappings and type coercions from endpoint schema
        field_mappings = {}
        type_coercions = {}
        date_columns = []
        timestamp_columns = []

        for field_def in endpoint.schema:
            # Field mapping (source -> target)
            if field_def.source:
                field_mappings[field_def.source] = field_def.name

            # Type coercion (for non-string, non-date types)
            target_type = field_def.type.lower()
            if target_type in ('int', 'long', 'double', 'float'):
                type_coercions[field_def.name] = target_type
            elif target_type == 'date':
                date_columns.append(field_def.name)
            elif target_type == 'timestamp':
                timestamp_columns.append(field_def.name)

        # Use SparkNormalizer for core operations
        normalizer = SparkNormalizer(self.spark)
        df = normalizer.normalize(
            records,
            field_mappings=field_mappings,
            type_coercions=type_coercions,
            add_metadata=False  # Socrata data doesn't need ingestion metadata
        )

        # Apply Socrata-specific date parsing (handles US, ISO, month name formats)
        for col_name in date_columns:
            if col_name in df.columns:
                df = df.withColumn(col_name, self._safe_parse_date(F.col(col_name)))

        for col_name in timestamp_columns:
            if col_name in df.columns:
                df = df.withColumn(col_name, self._safe_parse_timestamp(F.col(col_name)))

        # Derive year partition from date_column if year is NULL/missing
        # This fixes the __HIVE_DEFAULT_PARTITION__ issue for year partitions
        if endpoint.bronze and endpoint.bronze.partitions and 'year' in endpoint.bronze.partitions:
            date_col = endpoint.bronze.date_column
            if date_col and date_col in df.columns:
                if 'year' in df.columns:
                    # Year column exists but may be NULL - coalesce with derived value
                    df = df.withColumn(
                        'year',
                        F.coalesce(
                            F.col('year'),
                            F.year(F.col(date_col))
                        )
                    )
                else:
                    # No year column - derive from date
                    df = df.withColumn('year', F.year(F.col(date_col)))

        return df

    def _apply_schema_types(self, df: DataFrame, endpoint: EndpointConfig) -> DataFrame:
        """
        Apply Socrata-specific type casting and date parsing to a DataFrame.

        This handles:
        - Numeric type casting via try_cast
        - Socrata date format parsing (US, ISO, month names)
        - Year partition derivation from date columns

        Args:
            df: DataFrame with string columns
            endpoint: Endpoint configuration with schema

        Returns:
            DataFrame with proper types
        """
        if not endpoint.schema:
            return df

        # Cast columns to target types with Socrata-specific date handling
        for field_def in endpoint.schema:
            if field_def.name not in df.columns:
                continue

            target_type = field_def.type.lower()
            if target_type == 'string':
                continue
            elif target_type in ('int', 'long'):
                df = df.withColumn(field_def.name,
                    F.col(field_def.name).try_cast('double').cast(target_type))
            elif target_type in ('double', 'float'):
                df = df.withColumn(field_def.name, F.col(field_def.name).try_cast('double'))
            elif target_type == 'date':
                df = df.withColumn(field_def.name,
                    self._safe_parse_date(F.col(field_def.name)))
            elif target_type == 'timestamp':
                df = df.withColumn(field_def.name,
                    self._safe_parse_timestamp(F.col(field_def.name)))
            elif target_type == 'boolean':
                df = df.withColumn(field_def.name, F.col(field_def.name).cast('boolean'))

        # Derive year partition from date_column if needed
        if endpoint.bronze and endpoint.bronze.partitions and 'year' in endpoint.bronze.partitions:
            date_col = endpoint.bronze.date_column
            if date_col and date_col in df.columns:
                if 'year' in df.columns:
                    df = df.withColumn(
                        'year',
                        F.coalesce(F.col('year'), F.year(F.col(date_col)))
                    )
                else:
                    df = df.withColumn('year', F.year(F.col(date_col)))

        return df

    def _normalize_column_name(self, col_name: str) -> str:
        """
        Normalize column name to match schema conventions.

        Converts CSV column names to lowercase with underscores.
        Example: "Case Number" -> "case_number"
                 "FBI Code" -> "fbi_code"
                 "X Coordinate" -> "x_coordinate"

        Args:
            col_name: Original column name from CSV

        Returns:
            Normalized column name
        """
        import re
        # Replace spaces and special chars with underscores, convert to lowercase
        normalized = re.sub(r'[^a-zA-Z0-9_]', '_', col_name.lower())
        # Remove consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized

    def read_csv_with_spark(
        self,
        csv_path: Path,
        endpoint: EndpointConfig
    ) -> DataFrame:
        """
        Read CSV file directly with Spark (distributed across executors).

        This is much faster than Python csv.DictReader for large files because:
        - CSV parsing is distributed across all executors
        - No data flows through the driver
        - Memory pressure is distributed

        Column names are normalized to lowercase with underscores (e.g., "Case Number" -> "case_number")
        to match schema conventions and Delta Lake requirements.

        Args:
            csv_path: Path to CSV file (must be on shared storage)
            endpoint: Endpoint configuration with schema

        Returns:
            Spark DataFrame with schema applied
        """
        logger.info(f"Reading CSV with Spark: {csv_path}")

        # Read CSV with Spark - all columns as strings initially
        df = self.spark.read.csv(
            str(csv_path),
            header=True,
            inferSchema=False,  # Keep as strings, we'll cast
            multiLine=True,     # Handle quoted newlines
            escape='"',
            quote='"'
        )

        # Normalize column names: "Case Number" -> "case_number", "FBI Code" -> "fbi_code"
        # This is required for Delta Lake (doesn't accept spaces) and schema matching
        original_cols = df.columns
        normalized_cols = [self._normalize_column_name(c) for c in original_cols]
        df = df.toDF(*normalized_cols)
        logger.info(f"Normalized {len(original_cols)} column names (e.g., '{original_cols[0]}' -> '{normalized_cols[0]}')")

        logger.info(f"Spark CSV read complete: {df.count():,} rows, {len(df.columns)} columns")

        if not endpoint.schema:
            return df

        # Select and rename columns based on schema
        select_exprs = []
        for field_def in endpoint.schema:
            source_col = field_def.source or field_def.name
            if source_col in df.columns:
                select_exprs.append(F.col(source_col).alias(field_def.name))
            else:
                # Column doesn't exist in CSV - create null column
                select_exprs.append(F.lit(None).cast(StringType()).alias(field_def.name))

        df = df.select(select_exprs)

        # Apply Socrata-specific type casting and date parsing
        return self._apply_schema_types(df, endpoint)

    def get_raw_path(self, work_item: str) -> Optional[str]:
        """
        Get path to raw CSV file for bulk reading.

        Returns path if:
        - Endpoint uses CSV download method
        - Storage path is configured
        - Not a multi-year endpoint

        Args:
            work_item: Work item identifier

        Returns:
            Path to raw CSV file, or None if INCREMENTAL path should be used
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return None

        # Only use BULK for CSV downloads with storage path
        if endpoint.download_method != 'csv' or not self._storage_path:
            return None

        # Multi-year endpoints: return comma-separated paths
        if endpoint.view_ids:
            paths = []
            for year, resource_id in endpoint.view_ids.items():
                if not resource_id:
                    continue
                p = self._get_raw_path(work_item, resource_id, year=year)
                if p:
                    paths.append(str(p))
            return ','.join(paths) if paths else None

        resource_id = self._get_resource_id(endpoint)
        if not resource_id:
            return None

        raw_path = self._get_raw_path(work_item, resource_id)
        return str(raw_path) if raw_path else None

    def read_raw_as_df(self, work_item: str, raw_path: str) -> Optional[DataFrame]:
        """
        Read raw CSV file(s) with Spark and return normalized DataFrame.

        Downloads any missing CSVs first. Handles multi-year endpoints
        (comma-separated paths) by reading each and unioning.

        Args:
            work_item: Work item identifier
            raw_path: Path to raw CSV file, or comma-separated paths for multi-year

        Returns:
            Spark DataFrame with normalized data
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint:
            return None

        paths = raw_path.split(',')
        dfs = []

        for p in paths:
            raw_path_obj = Path(p.strip())

            # Download if not exists
            if not raw_path_obj.exists():
                # Extract resource_id from filename (format: endpoint_resourceid.csv)
                stem = raw_path_obj.stem
                parts = stem.rsplit('_', 1)
                resource_id = parts[-1] if len(parts) > 1 else self._get_resource_id(endpoint)
                if resource_id:
                    logger.info(f"Downloading CSV: {work_item} → {raw_path_obj.name}")
                    raw_path_obj.parent.mkdir(parents=True, exist_ok=True)
                    self.client.download_csv_to_file(
                        resource_id=resource_id,
                        output_path=str(raw_path_obj),
                        label=work_item
                    )

            if not raw_path_obj.exists():
                logger.warning(f"CSV not found: {raw_path_obj}")
                continue

            df = self.read_csv_with_spark(raw_path_obj, endpoint)
            if df is not None:
                dfs.append(df)

        if not dfs:
            return None
        if len(dfs) == 1:
            return dfs[0]

        # Union all year DataFrames (align columns)
        result = dfs[0]
        for df in dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)
        logger.info(f"Unioned {len(dfs)} CSVs for {work_item}")
        return result


    def download_all_csv(self, work_items: Optional[List[str]] = None, force: bool = False) -> dict:
        """
        Download raw CSV files for all endpoints. No Spark, no Bronze — just HTTP.

        This is Operation 1 of the two-step pipeline:
          1. download_all_csv() → raw CSVs on disk
          2. IngestorEngine.run() → Spark reads raw → Bronze → Silver

        Args:
            work_items: Specific endpoints to download (None = all)
            force: If True, re-download even if file exists

        Returns:
            Dict of {endpoint_id: {path, bytes, status}}
        """
        if not self._storage_path:
            raise ValueError("storage_path required for CSV download. Pass storage_path to create_socrata_provider().")

        items = work_items or self.list_work_items()
        results = {}

        for endpoint_id in items:
            endpoint = self._endpoints.get(endpoint_id)
            if not endpoint:
                results[endpoint_id] = {'status': 'skipped', 'reason': 'unknown endpoint'}
                continue

            # Handle multi-year endpoints
            if endpoint.view_ids:
                for year, resource_id in endpoint.view_ids.items():
                    if not resource_id:
                        continue
                    raw_path = self._get_raw_path(endpoint_id, resource_id, year=year)
                    if not raw_path:
                        continue
                    key = f"{endpoint_id}/{year}"
                    if raw_path.exists() and not force:
                        results[key] = {'path': str(raw_path), 'bytes': raw_path.stat().st_size, 'status': 'exists'}
                        logger.info(f"  {key}: exists ({raw_path.stat().st_size:,} bytes)")
                    else:
                        try:
                            logger.info(f"  Downloading {key}...")
                            nbytes = self.client.download_csv_to_file(
                                resource_id=resource_id,
                                output_path=str(raw_path),
                                label=f"{endpoint_id}/{year}",
                            )
                            results[key] = {'path': str(raw_path), 'bytes': nbytes, 'status': 'downloaded'}
                        except Exception as e:
                            results[key] = {'status': 'error', 'reason': str(e)}
                            logger.error(f"  {key}: {e}")
            else:
                resource_id = self._get_resource_id(endpoint)
                if not resource_id:
                    results[endpoint_id] = {'status': 'skipped', 'reason': 'no resource_id'}
                    continue

                raw_path = self._get_raw_path(endpoint_id, resource_id)
                if not raw_path:
                    results[endpoint_id] = {'status': 'skipped', 'reason': 'no raw path'}
                    continue

                if raw_path.exists() and not force:
                    results[endpoint_id] = {'path': str(raw_path), 'bytes': raw_path.stat().st_size, 'status': 'exists'}
                    logger.info(f"  {endpoint_id}: exists ({raw_path.stat().st_size:,} bytes)")
                else:
                    try:
                        logger.info(f"  Downloading {endpoint_id}...")
                        nbytes = self.client.download_csv_to_file(
                            resource_id=resource_id,
                            output_path=str(raw_path),
                            label=endpoint_id,
                        )
                        results[endpoint_id] = {'path': str(raw_path), 'bytes': nbytes, 'status': 'downloaded'}
                    except Exception as e:
                        results[endpoint_id] = {'status': 'error', 'reason': str(e)}
                        logger.error(f"  {endpoint_id}: {e}")

        downloaded = sum(1 for r in results.values() if r['status'] == 'downloaded')
        existed = sum(1 for r in results.values() if r['status'] == 'exists')
        errors = sum(1 for r in results.values() if r['status'] == 'error')
        logger.info(f"Download complete: {downloaded} downloaded, {existed} existed, {errors} errors")
        return results


def create_socrata_provider(
    provider_id: str,
    spark=None,
    docs_path: Optional[Path] = None,
    storage_path: Optional[Path] = None,
    preserve_raw: bool = True,
) -> SocrataBaseProvider:
    """
    Config-driven factory for Socrata providers.

    No subclass needed — provider_id determines which markdown configs
    to load. All behavior comes from SocrataBaseProvider + config.

    Args:
        provider_id: Provider identifier ('chicago', 'cook_county', etc.)
        spark: SparkSession
        docs_path: Path to repo root (contains Data Sources/)
        storage_path: Path to storage root (for raw layer)
        preserve_raw: If True, save raw CSV files before Bronze write

    Returns:
        Configured SocrataBaseProvider instance
    """
    provider = SocrataBaseProvider(
        provider_id=provider_id,
        spark=spark,
        docs_path=docs_path,
        storage_path=storage_path,
    )
    if preserve_raw and storage_path:
        provider.enable_raw_save(storage_path)
    return provider
