"""
Centralized configuration loader.

This module provides the main ConfigLoader class that handles all configuration loading
with proper precedence, validation, and error handling.

Configuration Source Priority (for API configs):
1. Markdown files in Data Sources/ (preferred - unified config + docs)
2. JSON files in configs/pipelines/ (fallback - legacy format)

When JSON fallback is used, a warning is logged to encourage migration.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from .logging import get_logger
from .markdown_loader import MarkdownConfigLoader
from .models import (
    AppConfig,
    ConnectionConfig,
    StorageConfig,
    APIConfig,
    SparkConfig,
    DuckDBConfig,
    DebugConfig,
)
from .constants import (
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_SPARK_DRIVER_MEMORY,
    DEFAULT_SPARK_EXECUTOR_MEMORY,
    DEFAULT_SPARK_SHUFFLE_PARTITIONS,
    DEFAULT_SPARK_TIMEZONE,
    DEFAULT_SPARK_LEGACY_TIME_PARSER,
    DEFAULT_DUCKDB_PATH,
    DEFAULT_DUCKDB_MEMORY_LIMIT,
    DEFAULT_DUCKDB_THREADS,
)

logger = get_logger(__name__)

# Import centralized repo root discovery
try:
    from de_funk.utils.repo import get_repo_root
    _HAS_UTILS_REPO = True
except ImportError:
    # Fallback if utils.repo doesn't exist yet (during migration)
    _HAS_UTILS_REPO = False
    from .constants import REPO_MARKERS


class ConfigLoader:
    """
    Centralized configuration loader.

    Handles loading configuration from multiple sources with clear precedence:
    1. Explicit parameters (highest priority)
    2. Environment variables
    3. Configuration files
    4. Default values (lowest priority)

    Usage:
        loader = ConfigLoader()
        config = loader.load()  # Auto-discover repo root

        # Or with explicit repo root
        loader = ConfigLoader(repo_root="/path/to/repo")
        config = loader.load(connection_type="spark")
    """

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize ConfigLoader.

        Args:
            repo_root: Optional explicit repo root. If not provided, will auto-discover.
        """
        self._repo_root = Path(repo_root) if repo_root else self._discover_repo_root()
        self._env_loaded = False

    @staticmethod
    def _discover_repo_root(start_path: Optional[Path] = None) -> Path:
        """
        Discover repository root by walking up from start_path.

        Now delegates to the centralized utils.repo.get_repo_root() function.

        Args:
            start_path: Starting path for search. Defaults to current working directory.

        Returns:
            Path to repository root.

        Raises:
            ValueError: If repo root cannot be found.
        """
        # Use centralized repo root discovery
        if _HAS_UTILS_REPO:
            return get_repo_root(start_path)

        # Fallback to original implementation (for backward compatibility)
        current = Path(start_path) if start_path else Path.cwd()

        for parent in [current] + list(current.parents):
            if all((parent / marker).exists() for marker in REPO_MARKERS):
                return parent

        raise ValueError(
            f"Could not find repository root from {current}. "
            f"Looking for directories containing: {', '.join(REPO_MARKERS)}"
        )

    def load_env(self, env_file: Optional[Path] = None) -> None:
        """
        Load environment variables from .env file.

        Args:
            env_file: Optional explicit path to .env file. If not provided,
                     looks for .env in repo root.
        """
        if self._env_loaded:
            return

        # Find .env file
        if env_file is None:
            env_file = self._repo_root / ".env"

        if not env_file.exists():
            logger.debug(f"No .env file found at {env_file}. Using environment variables only.")
            self._env_loaded = True
            return

        # Parse and load .env file
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value

            self._env_loaded = True
            logger.debug(f"Loaded environment from {env_file}")

        except (IOError, OSError) as e:
            logger.warning(f"Failed to load .env file: {e}")
            self._env_loaded = True

    def _get_api_keys(self, provider: str) -> List[str]:
        """
        Get API keys for a provider from environment.

        Args:
            provider: Provider name (e.g., 'alpha_vantage', 'bls', 'chicago')

        Returns:
            List of API keys (empty if not found)
        """
        env_var = f"{provider.upper()}_API_KEYS"
        keys_str = os.getenv(env_var, "").strip()

        if not keys_str:
            return []

        # Split by comma and clean
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        return keys

    def _load_json_config(self, filename: str) -> Dict[str, Any]:
        """
        Load JSON configuration file.

        Args:
            filename: Path to JSON file relative to configs/ directory
                     (e.g., "storage.json" or "pipelines/alpha_vantage_endpoints.json")

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If file not found or invalid JSON
        """
        config_path = self._repo_root / "configs" / filename

        if not config_path.exists():
            raise ValueError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {config_path}: {e}")

    def _build_connection_config(
        self,
        connection_type: Optional[str] = None,
        storage_json: Optional[Dict[str, Any]] = None,
    ) -> ConnectionConfig:
        """
        Build connection configuration with proper precedence.

        Precedence: explicit param > env var > storage.json > default

        Args:
            connection_type: Explicit connection type
            storage_json: Loaded storage.json data

        Returns:
            ConnectionConfig instance
        """
        # Determine connection type with precedence
        conn_type = (
            connection_type
            or os.getenv("CONNECTION_TYPE")
            or (storage_json or {}).get("connection", {}).get("type")
            or DEFAULT_CONNECTION_TYPE
        )

        # Build type-specific config
        if conn_type == "spark":
            spark_config = SparkConfig(
                driver_memory=os.getenv("SPARK_DRIVER_MEMORY", DEFAULT_SPARK_DRIVER_MEMORY),
                executor_memory=os.getenv("SPARK_EXECUTOR_MEMORY", DEFAULT_SPARK_EXECUTOR_MEMORY),
                shuffle_partitions=int(os.getenv("SPARK_SHUFFLE_PARTITIONS", DEFAULT_SPARK_SHUFFLE_PARTITIONS)),
                timezone=os.getenv("SPARK_TIMEZONE", DEFAULT_SPARK_TIMEZONE),
                legacy_time_parser=os.getenv("SPARK_LEGACY_TIME_PARSER", str(DEFAULT_SPARK_LEGACY_TIME_PARSER)).lower() == "true",
            )
            return ConnectionConfig(type="spark", spark=spark_config)

        elif conn_type == "duckdb":
            db_path = Path(os.getenv("DUCKDB_PATH", DEFAULT_DUCKDB_PATH))
            if not db_path.is_absolute():
                db_path = self._repo_root / db_path

            # Defensive validation: Detect and prevent nested duckdb paths
            # e.g., /path/storage/duckdb/storage/duckdb/analytics.db
            path_str = str(db_path)
            if "duckdb/storage/duckdb" in path_str or "duckdb\\storage\\duckdb" in path_str:
                logger.warning(f"Detected nested duckdb path: {db_path}")
                # Fix by extracting the correct path
                parts = path_str.split("duckdb")
                if len(parts) >= 2:
                    # Take the repo root up to first 'duckdb' + 'duckdb/analytics.db'
                    fixed_path = parts[0] + "duckdb" + parts[-1]
                    db_path = Path(fixed_path)
                    logger.info(f"Corrected duckdb path: {db_path}")

            duckdb_config = DuckDBConfig(
                database_path=db_path,
                memory_limit=os.getenv("DUCKDB_MEMORY_LIMIT", DEFAULT_DUCKDB_MEMORY_LIMIT),
                threads=int(os.getenv("DUCKDB_THREADS", DEFAULT_DUCKDB_THREADS)),
            )
            return ConnectionConfig(type="duckdb", duckdb=duckdb_config)

        else:
            raise ValueError(f"Unknown connection type: {conn_type}")

    def _build_storage_config(self, storage_json: Dict[str, Any]) -> StorageConfig:
        """
        Build storage configuration from storage.json.

        Args:
            storage_json: Loaded storage.json data

        Returns:
            StorageConfig instance
        """
        return StorageConfig.from_dict(storage_json, self._repo_root)

    def _get_run_config_storage_path(self) -> Optional[str]:
        """
        Get storage_path from run_config.json (single source of truth).

        Returns:
            Storage path string or None if not set
        """
        config_path = self._repo_root / "configs" / "run_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    run_config = json.load(f)
                return run_config.get("defaults", {}).get("storage_path")
            except Exception as e:
                logger.debug(f"Could not read run_config.json: {e}")
        return None

    def _resolve_storage_paths(self, storage_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve all storage paths to absolute paths.

        SINGLE SOURCE OF TRUTH: run_config.json storage_path
        No fallbacks - if not configured, raise error.

        Args:
            storage_json: Raw storage.json data with table definitions

        Returns:
            Storage config with all paths resolved to absolute

        Raises:
            ValueError: If storage_path not configured in run_config.json
        """
        resolved = dict(storage_json)  # Shallow copy

        # Get storage_path from run_config.json (REQUIRED - no fallback)
        run_config_storage = self._get_run_config_storage_path()

        if not run_config_storage:
            raise ValueError(
                "Storage path not configured.\n"
                "Set 'storage_path' in configs/run_config.json:\n"
                '  "defaults": {\n'
                '    "storage_path": "/shared/storage"\n'
                '  }\n'
                "This is the single source of truth for Bronze/Silver data location."
            )

        # Resolve all root paths using run_config.json storage_path
        if "roots" in resolved:
            resolved["roots"] = {}
            for key, rel_path in storage_json.get("roots", {}).items():
                # Skip comment keys
                if key.startswith("_"):
                    resolved["roots"][key] = rel_path
                    continue

                # Use run_config.json storage_path for bronze/silver
                if key in ("bronze", "silver"):
                    abs_path = Path(run_config_storage) / key
                    resolved["roots"][key] = str(abs_path)
                # Other paths (e.g., stocks_silver, company_silver) resolve relative to storage_path
                # Strip the leading "storage/" prefix if present and join with run_config_storage
                elif rel_path and not Path(rel_path).is_absolute():
                    rel_path_obj = Path(rel_path)
                    # If path starts with "storage/", strip it and use the rest
                    # e.g., "storage/silver/stocks" -> "silver/stocks"
                    if rel_path_obj.parts and rel_path_obj.parts[0] == "storage":
                        # Join all parts after "storage/"
                        sub_path = Path(*rel_path_obj.parts[1:])
                        abs_path = Path(run_config_storage) / sub_path
                    else:
                        # Path doesn't start with storage/, use as-is relative to storage root
                        abs_path = Path(run_config_storage) / rel_path_obj
                    resolved["roots"][key] = str(abs_path)
                else:
                    resolved["roots"][key] = rel_path

        logger.debug(f"Resolved storage roots: {resolved.get('roots', {})}")
        return resolved

    def load_storage(self) -> Dict[str, Any]:
        """
        Load only storage configuration (no API/provider configs).

        Use this for silver-only builds or any operation that doesn't need
        ingestion configuration. Much faster than load() since it skips
        parsing provider markdown files.

        Returns:
            Storage configuration dict with resolved paths

        Raises:
            ValueError: If storage.json missing or storage_path not configured
        """
        try:
            storage_json = self._load_json_config("storage.json")
        except ValueError as e:
            raise ValueError(f"Failed to load storage configuration: {e}")

        return self._resolve_storage_paths(storage_json)

    def _inject_api_keys(self, provider: str, endpoint_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject API keys into raw endpoint config.

        Args:
            provider: Provider name (e.g., 'alpha_vantage', 'bls')
            endpoint_json: Loaded endpoint JSON data

        Returns:
            Config dict with API keys injected
        """
        # Get API keys from environment
        api_keys = self._get_api_keys(provider)

        if not api_keys:
            logger.debug(
                f"No API keys found for {provider}. "
                f"Set {provider.upper()}_API_KEYS in .env file or environment."
            )

        # Inject API keys into credentials section
        config = endpoint_json.copy()
        if "credentials" not in config:
            config["credentials"] = {}
        config["credentials"]["api_keys"] = api_keys

        return config

    def _load_api_configs_from_markdown(self) -> Dict[str, Dict[str, Any]]:
        """
        Load API configurations from markdown files in Data Sources/.

        Returns:
            Dict mapping provider_id to config dict (JSON-compatible format)
        """
        if not (self._repo_root / "Data Sources" / "Providers").exists():
            logger.debug("No markdown provider configs found (Data Sources/Providers/ missing)")
            return {}

        try:
            md_loader = MarkdownConfigLoader(self._repo_root)
            providers = md_loader.load_providers()

            apis = {}
            for provider_id, provider in providers.items():
                # Get JSON-compatible config
                config = md_loader.get_provider_config(provider_id)
                if config:
                    # Inject API keys
                    config = self._inject_api_keys(provider_id, config)
                    apis[provider_id] = config
                    logger.debug(f"Loaded API config from markdown: {provider_id}")

            return apis

        except Exception as e:
            logger.warning(f"Error loading markdown configs: {e}")
            return {}

    def load(
        self,
        connection_type: Optional[str] = None,
        load_env: bool = True,
    ) -> AppConfig:
        """
        Load complete application configuration including API configs.

        For silver-only builds that don't need API configs, use load_storage() instead.

        Args:
            connection_type: Optional explicit connection type ('spark' or 'duckdb')
            load_env: Whether to load .env file. Default True.

        Returns:
            Complete AppConfig instance

        Raises:
            ValueError: If configuration is invalid or required files missing
        """
        # Load environment if requested
        if load_env:
            self.load_env()

        # Load JSON configs
        try:
            storage_json = self._load_json_config("storage.json")
        except ValueError as e:
            raise ValueError(f"Failed to load storage configuration: {e}")

        # Build connection config
        connection = self._build_connection_config(connection_type, storage_json)

        # Resolve all storage paths to absolute paths
        # This ensures ALL code uses consistent absolute paths
        storage = self._resolve_storage_paths(storage_json)

        # Load API configs: Markdown first (preferred), JSON fallback (legacy)
        # Priority: Markdown > JSON
        apis = {}

        # 1. Try loading from markdown (Data Sources/)
        markdown_apis = self._load_api_configs_from_markdown()
        apis.update(markdown_apis)

        if markdown_apis:
            logger.info(f"Loaded {len(markdown_apis)} provider(s) from markdown: {list(markdown_apis.keys())}")

        # 2. Fallback to JSON for providers not in markdown
        pipelines_dir = self._repo_root / "configs" / "pipelines"

        if pipelines_dir.exists():
            for endpoint_file in pipelines_dir.glob("*_endpoints.json"):
                provider_name = endpoint_file.stem.replace("_endpoints", "")

                # Skip if already loaded from markdown
                if provider_name in apis:
                    logger.debug(f"Provider '{provider_name}' loaded from markdown, skipping JSON")
                    continue

                try:
                    endpoint_json = self._load_json_config(f"pipelines/{endpoint_file.name}")
                    # Just inject API keys, don't transform structure
                    apis[provider_name] = self._inject_api_keys(provider_name, endpoint_json)

                    # Warn about JSON fallback - encourage migration to markdown
                    logger.warning(
                        f"⚠️ FALLBACK: Using JSON config for '{provider_name}'. "
                        f"Migrate to: Data Sources/Providers/{provider_name.replace('_', ' ').title()}.md"
                    )
                except ValueError as e:
                    logger.warning(f"Could not load {provider_name} API config: {e}")

        # Get log level
        log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

        # Load debug flags from environment
        debug = DebugConfig.from_env()

        # Build final config
        return AppConfig(
            repo_root=self._repo_root,
            connection=connection,
            storage=storage,
            apis=apis,
            log_level=log_level,
            debug=debug,
            env_loaded=self._env_loaded,
        )

    @property
    def repo_root(self) -> Path:
        """Get repository root path."""
        return self._repo_root
