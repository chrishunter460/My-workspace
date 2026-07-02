"""
Unified configuration management for de_Funk.

This module provides a centralized, type-safe configuration system that:
- Loads all configuration from a single entry point
- Validates configuration values
- Supports clear precedence: env vars > explicit params > config files > defaults
- Eliminates hardcoded values scattered throughout the codebase
- Provides centralized logging configuration
"""

from .loader import ConfigLoader
from .models import (
    AppConfig,
    ConnectionConfig,
    StorageConfig,
    APIConfig,
    SparkConfig,
    DuckDBConfig,
)
from .logging import (
    setup_logging,
    get_logger,
    LogConfig,
    LogTimer,
    log_function_call,
)

__all__ = [
    # Configuration
    "ConfigLoader",
    "AppConfig",
    "ConnectionConfig",
    "StorageConfig",
    "APIConfig",
    "SparkConfig",
    "DuckDBConfig",
    # Logging
    "setup_logging",
    "get_logger",
    "LogConfig",
    "LogTimer",
    "log_function_call",
]
