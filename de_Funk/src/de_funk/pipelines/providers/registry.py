"""
Provider Registry - Dynamic provider discovery and management.

Purpose:
    Centralized registry that auto-discovers data providers and provides
    a unified interface for ingestion operations.

Key Features:
    - Auto-discover providers from directory structure
    - Dynamic import and instantiation
    - Provider metadata from {name}_provider.yaml files
    - Unified interface for orchestrator

Usage:
    from de_funk.pipelines.providers.registry import ProviderRegistry

    # List available providers
    providers = ProviderRegistry.list_available()
    # ['alpha_vantage', 'bls', 'chicago']

    # Get provider info
    info = ProviderRegistry.get_info('alpha_vantage')
    # {'name': 'alpha_vantage', 'models': ['stocks', 'company'], ...}

    # Get instantiated ingestor
    ingestor = ProviderRegistry.get_ingestor('chicago', spark=spark, config=cfg)
    ingestor.run()
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import yaml

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderInfo:
    """Metadata about a data provider."""

    name: str
    description: str = ""
    version: str = "1.0"

    # What models this provider feeds data to
    models: List[str] = field(default_factory=list)

    # Bronze tables this provider writes to
    bronze_tables: List[str] = field(default_factory=list)

    # API configuration key (in configs/pipelines/)
    # Rate limiting is configured in the JSON config file (rate_limit_per_sec)
    config_key: str = ""

    # Ingestor class info
    module_path: str = ""
    class_name: str = ""

    # Tags for filtering
    tags: List[str] = field(default_factory=list)

    # Whether provider is enabled
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'models': self.models,
            'bronze_tables': self.bronze_tables,
            'config_key': self.config_key,
            'tags': self.tags,
            'enabled': self.enabled,
        }


class ProviderRegistry:
    """
    Registry for data providers with auto-discovery.

    Discovers providers by scanning the providers directory for:
    1. {name}_provider.yaml files (preferred - explicit metadata)
    2. {name}_ingestor.py files (fallback - convention-based)

    Usage:
        # List all providers
        providers = ProviderRegistry.list_available()

        # Get provider details
        info = ProviderRegistry.get_info('chicago')

        # Get instantiated ingestor
        ingestor = ProviderRegistry.get_ingestor('chicago', spark=spark, config=config)
    """

    _providers: Dict[str, ProviderInfo] = {}
    _discovered: bool = False

    # Base directory for providers
    _providers_dir: Path = Path(__file__).parent

    @classmethod
    def discover(cls, force: bool = False) -> None:
        """
        Discover available providers.

        Scans providers directory and builds registry of available providers.

        Args:
            force: Re-discover even if already discovered
        """
        if cls._discovered and not force:
            return

        cls._providers = {}

        # Scan for provider directories
        for item in cls._providers_dir.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith('_') or item.name.startswith('.'):
                continue

            # Check for {name}_provider.yaml (preferred)
            provider_yaml = item / f'{item.name}_provider.yaml'
            if provider_yaml.exists():
                cls._load_provider_yaml(item.name, provider_yaml)
                continue

            # Fallback: Check for {name}_ingestor.py (convention)
            ingestor_file = item / f'{item.name}_ingestor.py'
            if ingestor_file.exists():
                cls._load_provider_convention(item.name)

        cls._discovered = True
        logger.debug(f"Discovered {len(cls._providers)} providers: {list(cls._providers.keys())}")

    @classmethod
    def _load_provider_yaml(cls, name: str, yaml_path: Path) -> None:
        """Load provider info from {name}_provider.yaml file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            info = ProviderInfo(
                name=name,
                description=data.get('description', ''),
                version=data.get('version', '1.0'),
                models=data.get('models', []),
                bronze_tables=data.get('bronze_tables', []),
                config_key=data.get('config_key', name),
                module_path=data.get('module_path', f'datapipelines.providers.{name}'),
                class_name=data.get('class_name', f'{cls._pascal_case(name)}Ingestor'),
                tags=data.get('tags', []),
                enabled=data.get('enabled', True),
            )

            cls._providers[name] = info
            logger.debug(f"Loaded provider from YAML: {name}")

        except Exception as e:
            logger.error(f"Error loading provider YAML {yaml_path}: {e}")

    @classmethod
    def _load_provider_convention(cls, name: str) -> None:
        """Load provider using naming conventions."""
        info = ProviderInfo(
            name=name,
            description=f'{cls._pascal_case(name)} data provider',
            module_path=f'datapipelines.providers.{name}',
            class_name=f'{cls._pascal_case(name)}Ingestor',
        )

        cls._providers[name] = info
        logger.debug(f"Loaded provider by convention: {name}")

    @classmethod
    def _pascal_case(cls, name: str) -> str:
        """Convert snake_case to PascalCase."""
        return ''.join(word.capitalize() for word in name.split('_'))

    @classmethod
    def list_available(cls) -> List[str]:
        """
        List all available provider names.

        Returns:
            List of provider names (e.g., ['alpha_vantage', 'bls', 'chicago'])
        """
        cls.discover()
        return sorted(p.name for p in cls._providers.values() if p.enabled)

    @classmethod
    def get_info(cls, provider_name: str) -> Optional[ProviderInfo]:
        """
        Get metadata for a specific provider.

        Args:
            provider_name: Provider name (e.g., 'chicago')

        Returns:
            ProviderInfo or None if not found
        """
        cls.discover()
        return cls._providers.get(provider_name)

    @classmethod
    def get_ingestor(
        cls,
        provider_name: str,
        spark: Any = None,
        storage_cfg: Dict = None,
        api_config: Dict = None,
        **kwargs
    ) -> Any:
        """
        Get an instantiated ingestor for a provider.

        Args:
            provider_name: Provider name (e.g., 'alpha_vantage')
            spark: Spark session (optional)
            storage_cfg: Storage configuration dict
            api_config: API configuration dict (optional - will lookup if not provided)
            **kwargs: Additional kwargs to pass to ingestor constructor

        Returns:
            Instantiated ingestor object

        Raises:
            ValueError: If provider not found
            ImportError: If ingestor class cannot be imported
        """
        cls.discover()

        info = cls._providers.get(provider_name)
        if not info:
            available = ', '.join(cls.list_available())
            raise ValueError(
                f"Provider '{provider_name}' not found. Available: {available}"
            )

        if not info.enabled:
            raise ValueError(f"Provider '{provider_name}' is disabled")

        # Import the ingestor class
        try:
            module = importlib.import_module(info.module_path)
            ingestor_class = getattr(module, info.class_name)
        except (ImportError, AttributeError) as e:
            raise ImportError(
                f"Cannot import {info.class_name} from {info.module_path}: {e}"
            )

        # Build constructor arguments based on provider
        constructor_kwargs = {**kwargs}

        if spark is not None:
            constructor_kwargs['spark'] = spark

        if storage_cfg is not None:
            constructor_kwargs['storage_cfg'] = storage_cfg

        if api_config is not None:
            # Use provided config
            constructor_kwargs[f'{provider_name}_cfg'] = api_config

        # Instantiate
        try:
            return ingestor_class(**constructor_kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Error instantiating {info.class_name}: {e}"
            )

    @classmethod
    def get_all_info(cls) -> Dict[str, ProviderInfo]:
        """
        Get metadata for all providers.

        Returns:
            Dict mapping provider name to ProviderInfo
        """
        cls.discover()
        return {name: info for name, info in cls._providers.items() if info.enabled}

    @classmethod
    def get_providers_for_model(cls, model_name: str) -> List[str]:
        """
        Get providers that feed data to a specific model.

        Args:
            model_name: Model name (e.g., 'stocks', 'city_finance')

        Returns:
            List of provider names that feed this model
        """
        cls.discover()
        return [
            name for name, info in cls._providers.items()
            if info.enabled and model_name in info.models
        ]

    @classmethod
    def get_providers_by_tag(cls, tag: str) -> List[str]:
        """
        Get providers with a specific tag.

        Args:
            tag: Tag to filter by (e.g., 'securities', 'municipal')

        Returns:
            List of provider names with this tag
        """
        cls.discover()
        return [
            name for name, info in cls._providers.items()
            if info.enabled and tag in info.tags
        ]

    @classmethod
    def register(cls, info: ProviderInfo) -> None:
        """
        Manually register a provider.

        Useful for testing or dynamically adding providers.

        Args:
            info: ProviderInfo to register
        """
        cls._providers[info.name] = info
        logger.debug(f"Registered provider: {info.name}")

    @classmethod
    def reset(cls) -> None:
        """Reset the registry (for testing)."""
        cls._providers = {}
        cls._discovered = False
