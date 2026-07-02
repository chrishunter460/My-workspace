"""
Default configuration constants.

These values are used when no explicit configuration is provided.
"""

from pathlib import Path

# Connection defaults
DEFAULT_CONNECTION_TYPE = "duckdb"
DEFAULT_LOG_LEVEL = "INFO"

# Debug logging switches (controlled by environment variables or profile)
# Set DEBUG_FILTERS=true to enable detailed filter logging
# Set DEBUG_EXHIBITS=true to enable exhibit data logging
DEFAULT_DEBUG_FILTERS = False
DEFAULT_DEBUG_EXHIBITS = False
DEFAULT_DEBUG_SQL = False

# Spark defaults (increased for long-running batch jobs)
DEFAULT_SPARK_DRIVER_MEMORY = "8g"
DEFAULT_SPARK_EXECUTOR_MEMORY = "8g"
DEFAULT_SPARK_SHUFFLE_PARTITIONS = 200
DEFAULT_SPARK_TIMEZONE = "UTC"
DEFAULT_SPARK_LEGACY_TIME_PARSER = True

# DuckDB defaults
DEFAULT_DUCKDB_PATH = "storage/duckdb/analytics.db"
DEFAULT_DUCKDB_MEMORY_LIMIT = "4GB"
DEFAULT_DUCKDB_THREADS = 4

# Storage defaults
DEFAULT_BRONZE_ROOT = "storage/bronze"
DEFAULT_SILVER_ROOT = "storage/silver"

# API defaults
DEFAULT_RATE_LIMIT_CALLS = 5
DEFAULT_RATE_LIMIT_PERIOD = 60  # seconds
DEFAULT_REQUEST_TIMEOUT = 30  # seconds

# Repo structure markers - used to find repo root
REPO_MARKERS = ["src", "configs", ".git"]
