"""
Base Provider Interface.

Defines the abstract interface that all data providers must implement.
Configuration is loaded from markdown documentation files (single source of truth).

Usage:
    from de_funk.pipelines.base.provider import BaseProvider

    class MyProvider(BaseProvider):
        def list_work_items(self, **kwargs) -> List[str]:
            return ["endpoint1", "endpoint2"]

        def fetch(self, work_item: str, **kwargs) -> Generator[List[Dict], None, None]:
            for batch in paginate_api(work_item):
                yield batch

        def normalize(self, records: List[Dict], work_item: str) -> DataFrame:
            return spark.createDataFrame(records)

        def get_table_name(self, work_item: str) -> str:
            return f"bronze_{work_item}"

Author: de_Funk Team
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Generator
from enum import Enum
from pathlib import Path

from de_funk.config.logging import get_logger
from de_funk.config.markdown_loader import (
    MarkdownConfigLoader,
    ProviderConfig as MarkdownProviderConfig,
    EndpointConfig,
)

logger = get_logger(__name__)


class DataType(Enum):
    """Standard data types supported by providers."""
    REFERENCE = "reference"
    PRICES = "prices"
    INCOME_STATEMENT = "income"
    BALANCE_SHEET = "balance"
    CASH_FLOW = "cashflow"
    EARNINGS = "earnings"
    OPTIONS = "options"
    ETF_PROFILE = "etf_profile"
    DIVIDENDS = "dividends"
    SPLITS = "splits"


@dataclass
class FetchResult:
    """Result from a single data fetch operation."""
    ticker: str
    data_type: DataType
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    api_calls: int = 1

    def __bool__(self) -> bool:
        return self.success and self.data is not None


@dataclass
class WorkItemResult:
    """Result from ingesting a single work item."""
    work_item: str
    success: bool
    record_count: int = 0
    error: Optional[str] = None
    table_path: Optional[str] = None


class BaseProvider(ABC):
    """
    Abstract base class for data providers.

    Configuration is loaded from markdown documentation files via MarkdownConfigLoader.
    This ensures documentation and configuration stay in sync (single source of truth).

    The key abstraction is "work_item":
    - For Alpha Vantage: work_item = DataType (prices, reference, etc.)
    - For Socrata: work_item = endpoint_id (crimes, building_permits, etc.)

    Example:
        class MyProvider(BaseProvider):
            def list_work_items(self, **kwargs) -> List[str]:
                return list(self._endpoints.keys())

            def fetch(self, work_item: str, **kwargs):
                endpoint = self._endpoints[work_item]
                for batch in self.paginate(endpoint):
                    yield batch
    """

    # Override in subclass to match markdown provider name
    PROVIDER_NAME: str = ""

    def __init__(
        self,
        provider_id: str,
        spark=None,
        docs_path: Optional[Path] = None,
        session=None,
    ):
        """
        Initialize the provider with configuration from markdown.

        Args:
            provider_id: Provider identifier (e.g., 'alpha_vantage', 'chicago')
            spark: SparkSession for DataFrame operations
            docs_path: Path to repo root containing markdown configs
            session: Optional IngestSession from Engine/Session pattern
        """
        self.provider_id = provider_id
        self.spark = spark
        self._docs_path = docs_path
        self.ingest_session = session

        # Load configuration from markdown
        self._provider_config: Optional[MarkdownProviderConfig] = None
        self._endpoints: Dict[str, EndpointConfig] = {}

        if docs_path:
            self._load_config_from_markdown(docs_path)

        # Call provider-specific setup
        self._setup()

    def _load_config_from_markdown(self, docs_path: Path) -> None:
        """
        Load provider and endpoint configs from markdown files.

        Args:
            docs_path: Path to repo root
        """
        try:
            loader = MarkdownConfigLoader(docs_path)

            # Load provider config (base_url, rate_limit, etc.)
            providers = loader.load_providers()
            self._provider_config = providers.get(self.provider_id)

            if not self._provider_config:
                logger.warning(f"Provider config not found for: {self.provider_id}")

            # Load endpoint configs using provider name
            provider_name = self.PROVIDER_NAME or (
                self._provider_config.provider if self._provider_config else None
            )
            if provider_name:
                self._endpoints = loader.load_endpoints(provider=provider_name)
                logger.debug(
                    f"Loaded {len(self._endpoints)} endpoints for {provider_name}"
                )

        except Exception as e:
            logger.warning(f"Failed to load markdown config for {self.provider_id}: {e}")

    @property
    def base_url(self) -> str:
        """Get base URL from markdown config."""
        if self._provider_config:
            return self._provider_config.base_url
        return ""

    @property
    def rate_limit(self) -> float:
        """Get rate limit from markdown config."""
        if self._provider_config:
            return self._provider_config.rate_limit_per_sec
        return 1.0

    @property
    def env_api_key(self) -> str:
        """Get environment variable name for API key."""
        if self._provider_config:
            return self._provider_config.env_api_key
        return ""

    def get_provider_setting(self, key: str, default: Any = None) -> Any:
        """
        Get provider-specific setting from markdown config.

        Args:
            key: Setting key (e.g., 'us_exchanges', 'default_limit')
            default: Default value if not found

        Returns:
            Setting value or default
        """
        if self._provider_config and self._provider_config.raw:
            settings = self._provider_config.raw.get('provider_settings', {})
            return settings.get(key, default)
        return default

    def get_endpoint_config(self, endpoint_id: str) -> Optional[EndpointConfig]:
        """Get endpoint configuration by ID."""
        return self._endpoints.get(endpoint_id)

    @abstractmethod
    def _setup(self) -> None:
        """
        Setup provider-specific resources (HTTP client, key pool, etc).
        Called during __init__ after markdown config is loaded.
        """
        pass

    # =========================================================================
    # UNIFIED INTERFACE - All providers must implement these
    # =========================================================================

    @abstractmethod
    def list_work_items(self, **kwargs) -> List[str]:
        """
        List available work items for ingestion.

        For ticker-based providers: returns list of DataType values
        For endpoint-based providers: returns list of endpoint IDs

        Args:
            **kwargs: Provider-specific filters (e.g., status='active')

        Returns:
            List of work item identifiers
        """
        pass

    @abstractmethod
    def fetch(
        self,
        work_item: str,
        max_records: Optional[int] = None,
        **kwargs
    ) -> Generator[List[Dict], None, None]:
        """
        Fetch data for a single work item, yielding batches of raw records.

        This is a generator that yields batches of records. The IngestorEngine
        will pass these to StreamingBronzeWriter for memory-safe writes.

        Args:
            work_item: Work item identifier (DataType or endpoint_id)
            max_records: Maximum records to fetch (None = no limit)
            **kwargs: Provider-specific options

        Yields:
            List[Dict] - Batches of raw record dictionaries
        """
        pass

    @abstractmethod
    def normalize(self, records: List[Dict], work_item: str) -> Any:
        """
        Normalize raw records to a Spark DataFrame.

        Args:
            records: List of raw record dictionaries from fetch()
            work_item: The work item these records came from

        Returns:
            Spark DataFrame with proper schema
        """
        pass

    @abstractmethod
    def get_table_name(self, work_item: str) -> str:
        """
        Get the Bronze table name for a work item.

        Args:
            work_item: Work item identifier

        Returns:
            Table name (e.g., "securities_prices_daily", "chicago_crimes")
        """
        pass

    def get_partitions(self, work_item: str) -> Optional[List[str]]:
        """
        Get partition columns for a work item from endpoint config.

        Args:
            work_item: Work item identifier

        Returns:
            List of partition column names, or None
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.partitions or None
        return None

    def get_key_columns(self, work_item: str) -> List[str]:
        """
        Get key columns for upsert operations from endpoint config.

        Args:
            work_item: Work item identifier

        Returns:
            List of column names that form the unique key
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.key_columns or []
        return []

    def get_write_strategy(self, work_item: str) -> str:
        """
        Get write strategy from endpoint config.

        Args:
            work_item: Work item identifier

        Returns:
            Write strategy: "append" or "upsert" (default: "append")
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.write_strategy or "append"
        return "append"  # Default to append to preserve existing data

    def get_date_column(self, work_item: str) -> Optional[str]:
        """
        Get date column for append_immutable strategy.

        Args:
            work_item: Work item identifier

        Returns:
            Date column name or None
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint and endpoint.bronze:
            return endpoint.bronze.date_column
        return None

    def get_response_key(self, work_item: str) -> Optional[str]:
        """
        Get response key for extracting data from API response.

        Args:
            work_item: Work item identifier

        Returns:
            Response key string or None
        """
        endpoint = self._endpoints.get(work_item)
        if endpoint:
            return endpoint.response_key
        return None

    def get_field_mappings(self, work_item: str) -> Dict[str, str]:
        """
        Get source to target field name mappings from endpoint schema.

        Args:
            work_item: Work item identifier

        Returns:
            Dict mapping source field names to target field names
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint or not endpoint.schema:
            return {}

        mappings = {}
        for field in endpoint.schema:
            if field.source and field.source not in ('_computed', '_generated'):
                mappings[field.source] = field.name
        return mappings

    def get_type_coercions(self, work_item: str) -> Dict[str, str]:
        """
        Get type coercion rules from endpoint schema.

        Returns mapping of target field name to coercion type (e.g., 'long', 'double').
        Only includes fields with explicit {coerce: type} in schema.

        Args:
            work_item: Work item identifier

        Returns:
            Dict mapping field names to coercion types
        """
        endpoint = self._endpoints.get(work_item)
        if not endpoint or not endpoint.schema:
            return {}

        coercions = {}
        for field in endpoint.schema:
            if field.coerce:
                coercions[field.name] = field.coerce
        return coercions
