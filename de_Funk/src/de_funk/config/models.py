"""
Typed configuration models using dataclasses.

These models provide type safety and validation for all configuration values.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List


@dataclass
class SparkConfig:
    """Spark connection configuration."""
    driver_memory: str = "8g"  # Increased for long-running batch jobs
    executor_memory: str = "8g"  # Increased for long-running batch jobs
    shuffle_partitions: int = 200
    timezone: str = "UTC"
    legacy_time_parser: bool = True
    additional_config: Dict[str, Any] = field(default_factory=dict)

    def to_spark_conf_dict(self) -> Dict[str, str]:
        """Convert to Spark configuration dictionary."""
        config = {
            "spark.driver.memory": self.driver_memory,
            "spark.executor.memory": self.executor_memory,
            "spark.sql.shuffle.partitions": str(self.shuffle_partitions),
            "spark.sql.session.timeZone": self.timezone,
            "spark.sql.legacy.timeParserPolicy": "LEGACY" if self.legacy_time_parser else "CORRECTED",
        }
        config.update(self.additional_config)
        return config


@dataclass
class DuckDBConfig:
    """DuckDB connection configuration."""
    database_path: Path
    memory_limit: str = "4GB"
    threads: int = 4
    read_only: bool = False
    additional_config: Dict[str, Any] = field(default_factory=dict)

    def to_connection_params(self) -> Dict[str, Any]:
        """Convert to DuckDB connection parameters."""
        return {
            "database": str(self.database_path),
            "read_only": self.read_only,
            "config": {
                "memory_limit": self.memory_limit,
                "threads": self.threads,
                **self.additional_config,
            }
        }


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    type: str  # "spark" or "duckdb"
    spark: Optional[SparkConfig] = None
    duckdb: Optional[DuckDBConfig] = None

    def __post_init__(self):
        """Validate connection type."""
        if self.type not in ("spark", "duckdb"):
            raise ValueError(f"Invalid connection type: {self.type}. Must be 'spark' or 'duckdb'.")

        if self.type == "spark" and self.spark is None:
            raise ValueError("Spark configuration required when connection type is 'spark'.")

        if self.type == "duckdb" and self.duckdb is None:
            raise ValueError("DuckDB configuration required when connection type is 'duckdb'.")


@dataclass
class StorageConfig:
    """Storage layer configuration."""
    bronze_root: Path
    silver_root: Path
    tables: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], repo_root: Path) -> "StorageConfig":
        """Create from storage.json dictionary."""
        return cls(
            bronze_root=repo_root / data.get("bronze_root", "storage/bronze"),
            silver_root=repo_root / data.get("silver_root", "storage/silver"),
            tables=data.get("tables", {}),
        )


@dataclass
class APIConfig:
    """API provider configuration."""
    name: str
    base_url: str
    endpoints: Dict[str, Any]
    api_keys: List[str] = field(default_factory=list)
    rate_limit_calls: int = 5
    rate_limit_period: int = 60
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any], api_keys: Optional[List[str]] = None) -> "APIConfig":
        """Create from endpoint JSON dictionary."""
        # Handle both base_url (string) and base_urls (dict) formats
        base_url = data.get("base_url", "")
        if not base_url and "base_urls" in data:
            # If base_urls dict exists, use the 'core' entry
            base_url = data["base_urls"].get("core", "")

        # Handle both rate_limit dict and rate_limit_per_sec number formats
        if "rate_limit_per_sec" in data:
            # Convert from calls per second to calls/period
            rate_limit_per_sec = data["rate_limit_per_sec"]
            rate_limit_calls = int(rate_limit_per_sec * 60)  # Scale to calls per minute
            rate_limit_period = 60
        else:
            # Use nested rate_limit object
            rate_limit_calls = data.get("rate_limit", {}).get("calls", 5)
            rate_limit_period = data.get("rate_limit", {}).get("period", 60)

        return cls(
            name=name,
            base_url=base_url,
            endpoints=data.get("endpoints", {}),
            api_keys=api_keys or [],
            rate_limit_calls=rate_limit_calls,
            rate_limit_period=rate_limit_period,
            headers=data.get("headers", {}),
            timeout=data.get("timeout", 30),
        )


@dataclass
class DebugConfig:
    """Debug logging configuration."""
    filters: bool = False  # Enable detailed filter logging
    exhibits: bool = False  # Enable exhibit data logging
    sql: bool = False  # Enable SQL query logging

    @classmethod
    def from_env(cls) -> "DebugConfig":
        """Load debug flags from environment variables."""
        import os
        return cls(
            filters=os.getenv("DEBUG_FILTERS", "false").lower() == "true",
            exhibits=os.getenv("DEBUG_EXHIBITS", "false").lower() == "true",
            sql=os.getenv("DEBUG_SQL", "false").lower() == "true",
        )


@dataclass
class AppConfig:
    """
    Main application configuration.

    This is the top-level config object that contains all configuration for the application.
    """
    repo_root: Path
    connection: ConnectionConfig
    storage: Dict[str, Any]  # Raw storage config (JSON dict from storage.json)
    apis: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Raw API configs (JSON dicts)
    log_level: str = "INFO"
    debug: DebugConfig = field(default_factory=DebugConfig)
    env_loaded: bool = False

    def __post_init__(self):
        """Validate configuration."""
        if not self.repo_root.exists():
            raise ValueError(f"Repository root does not exist: {self.repo_root}")

        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {self.log_level}")

    @property
    def models_dir(self) -> Path:
        """Get models configuration directory (v3.0 domains/)."""
        return self.repo_root / "domains"

    @property
    def legacy_models_dir(self) -> Path:
        """Get legacy models configuration directory (v1.x/v2.x configs/models/)."""
        return self.repo_root / "configs" / "models"

    @property
    def configs_dir(self) -> Path:
        """Get configs directory."""
        return self.repo_root / "configs"
