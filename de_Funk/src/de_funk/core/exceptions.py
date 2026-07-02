"""
Custom Exception Hierarchy for de_Funk.

This module provides typed exceptions for different error categories with:
- Consistent error messages and formatting
- Structured details for debugging
- Recovery hints to guide users
- Proper exception chaining support

Exception Hierarchy:
    DeFunkError (base)
    ├── ConfigurationError
    │   ├── MissingConfigError
    │   └── InvalidConfigError
    ├── PipelineError
    │   ├── IngestionError
    │   ├── RateLimitError
    │   └── TransformationError
    ├── ModelError
    │   ├── ModelNotFoundError
    │   ├── TableNotFoundError
    │   ├── MeasureError
    │   └── DependencyError
    ├── QueryError
    │   ├── FilterError
    │   └── JoinError
    ├── StorageError
    │   ├── DataNotFoundError
    │   └── WriteError
    └── ForecastError
        ├── InsufficientDataError
        └── ModelTrainingError

Usage:
from de_funk.core.exceptions import ModelNotFoundError, IngestionError

    # Raise with structured details
    raise ModelNotFoundError("stocks")

    # Catch specific exceptions
    try:
        load_model(name)
    except ModelNotFoundError as e:
        logger.error(f"Model error: {e}")
        logger.debug(f"Details: {e.details}")

    # Chain exceptions
    try:
        fetch_data()
    except requests.RequestException as e:
        raise IngestionError("alpha_vantage", "prices", str(e)) from e
"""

from typing import Optional, Dict, Any, List


class DeFunkError(Exception):
    """
    Base exception for all de_Funk errors.

    Provides:
    - Structured error details
    - Recovery hints
    - Consistent string formatting
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None
    ):
        """
        Initialize DeFunkError.

        Args:
            message: Human-readable error message
            details: Structured details for debugging (logged but not shown to end users)
            recovery_hint: Suggestion for how to fix the error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.recovery_hint = recovery_hint

    def __str__(self) -> str:
        """Format error for display."""
        result = self.message
        if self.recovery_hint:
            result += f" | Hint: {self.recovery_hint}"
        return result

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"details={self.details!r}, "
            f"recovery_hint={self.recovery_hint!r})"
        )


# ============================================
# Configuration Errors
# ============================================

class ConfigurationError(DeFunkError):
    """Error in configuration loading or validation."""
    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    def __init__(self, config_key: str, config_file: Optional[str] = None):
        """
        Initialize MissingConfigError.

        Args:
            config_key: The missing configuration key
            config_file: Optional file where the key was expected
        """
        message = f"Missing required configuration: {config_key}"
        if config_file:
            message += f" (expected in {config_file})"

        super().__init__(
            message,
            details={'key': config_key, 'file': config_file},
            recovery_hint=f"Add '{config_key}' to your configuration file or environment"
        )
        self.config_key = config_key
        self.config_file = config_file


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""

    def __init__(self, config_key: str, value: Any, expected: str):
        """
        Initialize InvalidConfigError.

        Args:
            config_key: The configuration key with invalid value
            value: The invalid value
            expected: Description of what was expected
        """
        super().__init__(
            f"Invalid configuration value for '{config_key}': {value!r}",
            details={'key': config_key, 'value': value, 'expected': expected},
            recovery_hint=f"Expected: {expected}"
        )
        self.config_key = config_key
        self.value = value
        self.expected = expected


# ============================================
# Data Pipeline Errors
# ============================================

class PipelineError(DeFunkError):
    """Error in data pipeline execution."""
    pass


class IngestionError(PipelineError):
    """Error during data ingestion from API."""

    def __init__(self, provider: str, endpoint: str, error: str):
        """
        Initialize IngestionError.

        Args:
            provider: Data provider name (e.g., 'alpha_vantage')
            endpoint: API endpoint that failed
            error: Error message from the API or network layer
        """
        super().__init__(
            f"Ingestion failed for {provider}/{endpoint}: {error}",
            details={'provider': provider, 'endpoint': endpoint, 'error': error},
            recovery_hint="Check API credentials and rate limits"
        )
        self.provider = provider
        self.endpoint = endpoint
        self.error = error


class RateLimitError(PipelineError):
    """API rate limit exceeded."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        """
        Initialize RateLimitError.

        Args:
            provider: Data provider that rate limited the request
            retry_after: Optional seconds to wait before retrying
        """
        wait_time = retry_after or 60
        super().__init__(
            f"Rate limit exceeded for {provider}",
            details={'provider': provider, 'retry_after': retry_after},
            recovery_hint=f"Wait {wait_time} seconds before retrying"
        )
        self.provider = provider
        self.retry_after = retry_after


class TransformationError(PipelineError):
    """Error during data transformation."""

    def __init__(self, stage: str, error: str, record_count: Optional[int] = None):
        """
        Initialize TransformationError.

        Args:
            stage: Transformation stage that failed
            error: Error description
            record_count: Optional number of records being processed
        """
        message = f"Transformation failed at stage '{stage}': {error}"
        if record_count is not None:
            message += f" (processing {record_count} records)"

        super().__init__(
            message,
            details={'stage': stage, 'error': error, 'records': record_count}
        )
        self.stage = stage
        self.error = error
        self.record_count = record_count


# ============================================
# Model Errors
# ============================================

class ModelError(DeFunkError):
    """Error in model operations."""
    pass


class ModelNotFoundError(ModelError):
    """Requested model does not exist."""

    def __init__(self, model_name: str, available_models: Optional[List[str]] = None):
        """
        Initialize ModelNotFoundError.

        Args:
            model_name: Name of the model that wasn't found
            available_models: Optional list of available model names
        """
        message = f"Model not found: '{model_name}'"
        hint = "Check available models with ModelRegistry.list_models()"
        if available_models:
            hint = f"Available models: {', '.join(available_models)}"

        super().__init__(
            message,
            details={'model': model_name, 'available': available_models},
            recovery_hint=hint
        )
        self.model_name = model_name
        self.available_models = available_models


class TableNotFoundError(ModelError):
    """Requested table does not exist in model."""

    def __init__(self, model_name: str, table_name: str, available_tables: Optional[List[str]] = None):
        """
        Initialize TableNotFoundError.

        Args:
            model_name: Model name
            table_name: Table that wasn't found
            available_tables: Optional list of available tables
        """
        message = f"Table '{table_name}' not found in model '{model_name}'"
        hint = None
        if available_tables:
            hint = f"Available tables: {', '.join(available_tables)}"

        super().__init__(
            message,
            details={'model': model_name, 'table': table_name, 'available': available_tables},
            recovery_hint=hint
        )
        self.model_name = model_name
        self.table_name = table_name
        self.available_tables = available_tables


class MeasureError(ModelError):
    """Error calculating a measure."""

    def __init__(self, measure_name: str, error: str, model_name: Optional[str] = None):
        """
        Initialize MeasureError.

        Args:
            measure_name: Name of the measure that failed
            error: Error description
            model_name: Optional model name for context
        """
        message = f"Failed to calculate measure '{measure_name}'"
        if model_name:
            message = f"Failed to calculate measure '{measure_name}' in model '{model_name}'"
        message += f": {error}"

        super().__init__(
            message,
            details={'measure': measure_name, 'error': error, 'model': model_name}
        )
        self.measure_name = measure_name
        self.error = error
        self.model_name = model_name


class DependencyError(ModelError):
    """Model dependency not satisfied."""

    def __init__(self, model_name: str, missing_deps: List[str]):
        """
        Initialize DependencyError.

        Args:
            model_name: Model with missing dependencies
            missing_deps: List of missing dependency model names
        """
        super().__init__(
            f"Model '{model_name}' has unmet dependencies: {', '.join(missing_deps)}",
            details={'model': model_name, 'missing': missing_deps},
            recovery_hint="Build dependent models first: " + " -> ".join(missing_deps + [model_name])
        )
        self.model_name = model_name
        self.missing_deps = missing_deps


# ============================================
# Query Errors
# ============================================

class QueryError(DeFunkError):
    """Error executing a query."""
    pass


class FilterError(QueryError):
    """Error applying filters."""

    def __init__(self, filter_spec: Dict[str, Any], error: str):
        """
        Initialize FilterError.

        Args:
            filter_spec: The filter specification that failed
            error: Error description
        """
        super().__init__(
            f"Invalid filter specification: {error}",
            details={'filter': filter_spec, 'error': error}
        )
        self.filter_spec = filter_spec
        self.error = error


class JoinError(QueryError):
    """Error joining tables."""

    def __init__(self, left_table: str, right_table: str, error: str):
        """
        Initialize JoinError.

        Args:
            left_table: Left side of the join
            right_table: Right side of the join
            error: Error description
        """
        super().__init__(
            f"Failed to join '{left_table}' with '{right_table}': {error}",
            details={'left': left_table, 'right': right_table, 'error': error}
        )
        self.left_table = left_table
        self.right_table = right_table
        self.error = error


# ============================================
# Storage Errors
# ============================================

class StorageError(DeFunkError):
    """Error in storage operations."""
    pass


class DataNotFoundError(StorageError):
    """Requested data does not exist."""

    def __init__(self, path: str, table: Optional[str] = None):
        """
        Initialize DataNotFoundError.

        Args:
            path: Path where data was expected
            table: Optional table name
        """
        message = f"Data not found at: {path}"
        if table:
            message = f"Data for table '{table}' not found at: {path}"

        super().__init__(
            message,
            details={'path': path, 'table': table},
            recovery_hint="Run ingestion pipeline to populate data"
        )
        self.path = path
        self.table = table


class WriteError(StorageError):
    """Error writing data to storage."""

    def __init__(self, path: str, error: str):
        """
        Initialize WriteError.

        Args:
            path: Path where write was attempted
            error: Error description
        """
        super().__init__(
            f"Failed to write to '{path}': {error}",
            details={'path': path, 'error': error},
            recovery_hint="Check disk space and write permissions"
        )
        self.path = path
        self.error = error


# ============================================
# Forecast Errors
# ============================================

class ForecastError(DeFunkError):
    """Error in forecasting operations."""
    pass


class InsufficientDataError(ForecastError):
    """Not enough data for forecasting."""

    def __init__(self, required: int, available: int, ticker: Optional[str] = None):
        """
        Initialize InsufficientDataError.

        Args:
            required: Minimum required data points
            available: Actually available data points
            ticker: Optional ticker symbol for context
        """
        message = f"Insufficient data for forecast: need {required}, have {available}"
        if ticker:
            message = f"Insufficient data for forecast of {ticker}: need {required}, have {available}"

        super().__init__(
            message,
            details={'required': required, 'available': available, 'ticker': ticker}
        )
        self.required = required
        self.available = available
        self.ticker = ticker


class ModelTrainingError(ForecastError):
    """Error training forecast model."""

    def __init__(self, model_type: str, error: str, ticker: Optional[str] = None):
        """
        Initialize ModelTrainingError.

        Args:
            model_type: Type of forecast model (e.g., 'ARIMA', 'Prophet')
            error: Error description
            ticker: Optional ticker symbol for context
        """
        message = f"Failed to train {model_type} model: {error}"
        if ticker:
            message = f"Failed to train {model_type} model for {ticker}: {error}"

        super().__init__(
            message,
            details={'model_type': model_type, 'error': error, 'ticker': ticker}
        )
        self.model_type = model_type
        self.error = error
        self.ticker = ticker


# ============================================
# Connection Errors
# ============================================

class ConnectionError(DeFunkError):
    """Error in database connection."""

    def __init__(self, backend: str, error: str):
        """
        Initialize ConnectionError.

        Args:
            backend: Database backend (e.g., 'duckdb', 'spark')
            error: Error description
        """
        super().__init__(
            f"Failed to connect to {backend}: {error}",
            details={'backend': backend, 'error': error},
            recovery_hint=f"Check {backend} installation and configuration"
        )
        self.backend = backend
        self.error = error
