from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional
from de_funk.config import ConfigLoader, AppConfig
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RepoContext:
    """
    Repository context with database connection and configuration.

    Now powered by the unified ConfigLoader system for consistent configuration management.
    """
    repo: Path
    spark: Any  # Kept for backward compatibility
    storage: Dict[str, Any]
    connection: Optional[Any] = None  # DataConnection (DuckDB or Spark)
    connection_type: str = "spark"  # Default to spark for backward compatibility
    _config: Optional[AppConfig] = None  # Internal: full typed config

    def get_api_config(self, provider: str) -> Dict[str, Any]:
        """
        Get API configuration for any provider.

        Args:
            provider: Provider name (e.g., 'alpha_vantage', 'bls', 'chicago')

        Returns:
            API configuration dict (empty if not found)
        """
        return self._config.apis.get(provider, {}) if self._config else {}

    @classmethod
    def from_repo_root(cls, connection_type: Optional[str] = None) -> "RepoContext":
        """
        Create RepoContext from repository root.

        Now uses ConfigLoader for centralized, validated configuration loading.

        Args:
            connection_type: Override connection type ('spark' or 'duckdb').
                           If None, uses precedence: env var > storage.json > default

        Returns:
            RepoContext with appropriate connection
        """
        # Use ConfigLoader for centralized config management
        loader = ConfigLoader()
        config = loader.load(connection_type=connection_type)
        logger.debug(f"Loaded configuration from {config.repo_root}")

        # Create connection based on type
        spark = None
        connection = None

        if config.connection.type == "duckdb":
            from de_funk.core.connection import ConnectionFactory
            # Get DuckDB path from config
            duckdb_path = config.connection.duckdb.database_path
            duckdb_path.parent.mkdir(parents=True, exist_ok=True)
            connection = ConnectionFactory.create("duckdb", db_path=str(duckdb_path))
            logger.info(f"Created DuckDB connection: {duckdb_path}")
            # DuckDB-only mode: No Spark needed for UI/analytics
            spark = None
        else:
            # Spark mode
            from de_funk.orchestration.common.spark_session import get_spark
            # Pass SparkConfig to get_spark for proper configuration
            spark = get_spark("CompanyPipeline", spark_config=config.connection.spark)
            from de_funk.core.connection import ConnectionFactory
            connection = ConnectionFactory.create("spark", spark_session=spark)
            logger.info("Created Spark connection")

        # Storage config with all paths resolved to absolute by ConfigLoader
        # This is the single source of truth for storage paths
        storage_dict = config.storage

        return cls(
            repo=config.repo_root,
            spark=spark,
            storage=storage_dict,
            connection=connection,
            connection_type=config.connection.type,
            _config=config,
        )

    @property
    def config(self) -> Optional[AppConfig]:
        """Get the full typed configuration object."""
        return self._config
