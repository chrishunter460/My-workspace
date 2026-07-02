"""
StorageRouter — resolves storage paths for all 4 data tiers.

Single source of truth for path resolution. Used by all Sessions.

Tiers:
    Raw    → /mnt/disk/storage/raw/{provider}/{endpoint}/
    Bronze → /shared/storage/bronze/{provider}/{endpoint}/
    Silver → /shared/storage/silver/{domain}/{model}/
    Models → /shared/storage/models/{model_name}/{version}/
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class StorageRouter:
    """Resolves storage paths from config."""

    def __init__(self, storage_config: dict | Any):
        if isinstance(storage_config, dict):
            roots = storage_config.get("roots", {})
            self._raw_root = roots.get("raw", "storage/raw")
            self._bronze_root = roots.get("bronze", "storage/bronze")
            self._silver_root = roots.get("silver", "storage/silver")
            self._models_root = roots.get("models", "storage/models")
            self._domain_roots = storage_config.get("domain_roots", {})
            self._tables = storage_config.get("tables", {})
        else:
            # Support typed RootsConfig
            roots = getattr(storage_config, 'roots', None)
            if roots:
                self._raw_root = getattr(roots, 'raw', 'storage/raw')
                self._bronze_root = getattr(roots, 'bronze', 'storage/bronze')
                self._silver_root = getattr(roots, 'silver', 'storage/silver')
                self._models_root = getattr(roots, 'models', 'storage/models')
            else:
                self._raw_root = "storage/raw"
                self._bronze_root = "storage/bronze"
                self._silver_root = "storage/silver"
                self._models_root = "storage/models"
            self._domain_roots = getattr(storage_config, 'domain_roots', {})
            self._tables = getattr(storage_config, 'tables', {})

    def raw_path(self, provider: str, endpoint: str) -> str:
        """Resolve raw storage path: raw_root/provider/endpoint."""
        return f"{self._raw_root}/{provider}/{endpoint}"

    def bronze_path(self, provider: str, endpoint: str) -> str:
        """Resolve bronze storage path: bronze_root/provider/endpoint."""
        return f"{self._bronze_root}/{provider}/{endpoint}"

    def silver_path(self, domain: str, table: str = "") -> str:
        """Resolve silver storage path with domain_roots overrides.

        Args:
            domain: Canonical domain name (e.g. "securities.stocks")
            table: Optional table subdirectory (e.g. "dims/dim_stock")
        """
        override = self._domain_roots.get(domain)
        if override:
            base = f"{self._silver_root}/{override}"
        else:
            base = f"{self._silver_root}/{domain.replace('.', '/')}"
        if table:
            return f"{base}/{table}"
        return base

    def model_path(self, model_name: str, version: str = "") -> str:
        """Resolve ML model artifact path."""
        base = f"{self._models_root}/{model_name}"
        if version:
            return f"{base}/{version}"
        return base

    def resolve(self, table_ref: str) -> str:
        """Resolve a config-style table reference to a path.

        Backward compatible with dal.py StorageRouter.resolve().

        Examples:
            "bronze.alpha_vantage.listing_status" → bronze_root/alpha_vantage/listing_status
            "silver.stocks/dims/dim_stock" → silver_root/stocks/dims/dim_stock
        """
        if table_ref.startswith("/"):
            return table_ref
        if table_ref.startswith("bronze."):
            rel = table_ref[7:].replace(".", "/")
            return f"{self._bronze_root}/{rel}"
        if table_ref.startswith("silver."):
            rel = table_ref[7:]
            return f"{self._silver_root}/{rel}"
        # Check tables dict for named tables
        if table_ref in self._tables:
            t = self._tables[table_ref]
            if isinstance(t, dict):
                root_name = t.get("root", "silver")
                root = self._silver_root if root_name == "silver" else self._bronze_root
                return f"{root}/{t.get('rel', table_ref)}"
        # Default to silver
        return f"{self._silver_root}/{table_ref}"

    @property
    def silver_root(self) -> str:
        return self._silver_root

    @property
    def bronze_root(self) -> str:
        return self._bronze_root

    @property
    def raw_root(self) -> str:
        return self._raw_root

    @property
    def models_root(self) -> str:
        return self._models_root
