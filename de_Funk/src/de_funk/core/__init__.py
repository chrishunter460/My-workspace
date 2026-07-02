"""
Core infrastructure for de_Funk.

Provides foundational abstractions for:
- Data connections (Spark, DuckDB, future: GraphDB)
- Repository context
- Validation
- Custom exceptions
- Error handling utilities
"""

# =============================================================================
# Lightweight imports first (no heavy dependencies like pandas/duckdb)
# =============================================================================

# Custom exceptions (no dependencies)
from .exceptions import (
    DeFunkError,
    ConfigurationError,
    MissingConfigError,
    InvalidConfigError,
    PipelineError,
    IngestionError,
    RateLimitError,
    TransformationError,
    ModelError,
    ModelNotFoundError,
    TableNotFoundError,
    MeasureError,
    DependencyError,
    QueryError,
    FilterError,
    JoinError,
    StorageError,
    DataNotFoundError,
    WriteError,
    ForecastError,
    InsufficientDataError,
    ModelTrainingError,
)

# Error handling utilities (depends only on config.logging)
from .error_handling import (
    handle_exceptions,
    retry_on_exception,
    ErrorContext,
    safe_call,
    ensure_not_none,
)

# =============================================================================
# Heavy imports (require pandas, duckdb, etc.) - conditional/lazy
# =============================================================================

# These may fail if dependencies aren't installed - that's OK for lightweight usage
DataConnection = None
DuckDBConnection = None
NotebookValidator = None
ValidationError = None
RepoContext = None

_heavy_imports_loaded = False


def _load_heavy_imports():
    """Lazy load heavy imports that require pandas/duckdb."""
    global DataConnection, DuckDBConnection, NotebookValidator, ValidationError, RepoContext
    global _heavy_imports_loaded

    if _heavy_imports_loaded:
        return

    try:
        from .connection import DataConnection as _DataConnection
        DataConnection = _DataConnection
    except ImportError:
        pass

    try:
        from .duckdb_connection import DuckDBConnection as _DuckDBConnection
        DuckDBConnection = _DuckDBConnection
    except ImportError:
        pass

    try:
        from .validation import NotebookValidator as _NotebookValidator
        from .validation import ValidationError as _ValidationError
        NotebookValidator = _NotebookValidator
        ValidationError = _ValidationError
    except ImportError:
        pass

    try:
        from .context import RepoContext as _RepoContext
        RepoContext = _RepoContext
    except ImportError:
        pass

    _heavy_imports_loaded = True


def __getattr__(name):
    """
    Lazy attribute loading for heavy imports.

    This allows `from core import DataConnection` to work even if pandas
    isn't installed when the module is first imported.
    """
    heavy_attrs = {'DataConnection', 'DuckDBConnection', 'NotebookValidator',
                   'ValidationError', 'RepoContext'}

    if name in heavy_attrs:
        _load_heavy_imports()
        return globals().get(name)

    raise AttributeError(f"module 'core' has no attribute {name!r}")

__all__ = [
    # Connections
    'DataConnection',
    'DuckDBConnection',
    # Validation
    'NotebookValidator',
    'ValidationError',
    # Context
    'RepoContext',
    # Base exception
    'DeFunkError',
    # Configuration exceptions
    'ConfigurationError',
    'MissingConfigError',
    'InvalidConfigError',
    # Pipeline exceptions
    'PipelineError',
    'IngestionError',
    'RateLimitError',
    'TransformationError',
    # Model exceptions
    'ModelError',
    'ModelNotFoundError',
    'TableNotFoundError',
    'MeasureError',
    'DependencyError',
    # Query exceptions
    'QueryError',
    'FilterError',
    'JoinError',
    # Storage exceptions
    'StorageError',
    'DataNotFoundError',
    'WriteError',
    # Forecast exceptions
    'ForecastError',
    'InsufficientDataError',
    'ModelTrainingError',
    # Error handling utilities
    'handle_exceptions',
    'retry_on_exception',
    'ErrorContext',
    'safe_call',
    'ensure_not_none',
]
