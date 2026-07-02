"""
Session abstractions — scoped contexts for each pipeline path.

Sessions are short-lived (per task/request). They hold the configs
needed for their specific path and delegate operations to the Engine.

    BuildSession: reads Bronze+Silver, writes Silver
    QuerySession: reads Silver, writes nothing
    IngestSession: reads APIs, writes Raw+Bronze
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class Session(ABC):
    """Abstract base for all sessions."""

    def __init__(self, engine, storage_config=None, **kwargs):
        self.engine = engine
        self._storage_config = storage_config or {}

        from de_funk.core.storage import StorageRouter
        self.storage_router = StorageRouter(self._storage_config)

    def raw_path(self, provider: str, endpoint: str) -> str:
        """Resolve raw storage path."""
        return self.storage_router.raw_path(provider, endpoint)

    def bronze_path(self, provider: str, endpoint: str) -> str:
        """Resolve bronze storage path."""
        return self.storage_router.bronze_path(provider, endpoint)

    def silver_path(self, domain: str, table: str = "") -> str:
        """Resolve silver storage path."""
        return self.storage_router.silver_path(domain, table)

    def model_path(self, model_name: str, version: str = "") -> str:
        """Resolve ML model artifact path."""
        return self.storage_router.model_path(model_name, version)

    @abstractmethod
    def close(self):
        """Clean up session resources."""
        pass


class BuildSession(Session):
    """Session for building Silver tables from Bronze + Silver dependencies."""

    def __init__(self, engine, models: dict, graph=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.models = models
        self.graph = graph
        self._kwargs = kwargs

    def get_model(self, model_name: str) -> dict:
        """Get a domain model config by name."""
        if model_name not in self.models:
            raise KeyError(f"Model '{model_name}' not found. Available: {list(self.models.keys())}")
        return self.models[model_name]

    def get_dependencies(self, model_name: str) -> list[str]:
        """Get dependency list for a model."""
        model = self.get_model(model_name)
        return model.get("depends_on", []) if isinstance(model, dict) else getattr(model, 'depends_on', [])

    def build(self, model_name: str) -> Any:
        """Build a single model — passes this session directly to the builder."""
        import time
        t0 = time.perf_counter()
        logger.info(f"BuildSession.build({model_name})")

        try:
            from de_funk.models.base.domain_builder import DomainBuilderFactory
            from de_funk.models.base.builder import BuildResult

            builders = DomainBuilderFactory.create_builders(
                Path(self._kwargs.get("repo_root", ".")) / "domains"
            )
            if model_name not in builders:
                return BuildResult(
                    model_name=model_name, success=False,
                    error=f"No builder found for {model_name}",
                    duration_seconds=time.perf_counter() - t0,
                )

            builder_cls = builders[model_name]
            builder = builder_cls(self)  # Pass session directly
            result = builder.build()
            return result
        except Exception as e:
            from de_funk.models.base.builder import BuildResult
            logger.error(f"Build failed for {model_name}: {e}", exc_info=True)
            return BuildResult(
                model_name=model_name, success=False,
                error=str(e),
                duration_seconds=time.perf_counter() - t0,
            )

    def build_all(self) -> list:
        """Build all models in dependency order."""
        order = self._topological_sort()
        results = []
        for model_name in order:
            results.append(self.build(model_name))
        return results

    def _topological_sort(self) -> list[str]:
        """Sort models by dependencies (Kahn's algorithm)."""
        in_degree = {m: 0 for m in self.models}
        for model_name in self.models:
            deps = self.get_dependencies(model_name)
            for dep in deps:
                if dep in in_degree:
                    in_degree[model_name] = in_degree.get(model_name, 0) + 1

        from collections import deque
        queue = deque([m for m, d in in_degree.items() if d == 0])
        result = []

        dep_map = {}
        for model_name in self.models:
            for dep in self.get_dependencies(model_name):
                dep_map.setdefault(dep, []).append(model_name)

        while queue:
            m = queue.popleft()
            result.append(m)
            for dependent in dep_map.get(m, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Add any remaining (circular deps or missing)
        for m in self.models:
            if m not in result:
                result.append(m)

        return result

    def close(self):
        pass


class QuerySession(Session):
    """Session for querying Silver tables (read-only)."""

    def __init__(self, engine, models: dict, resolver=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.models = models
        self.resolver = resolver

    def resolve(self, ref_str: str):
        """Resolve a domain.field reference to a ResolvedField."""
        if self.resolver is None:
            raise RuntimeError("QuerySession has no resolver — was it created with one?")
        return self.resolver.resolve(ref_str)

    def find_join_path(self, src: str, dst: str) -> list:
        """Find join path between two tables."""
        if self.resolver is None:
            return []
        return self.resolver.find_join_path(src, dst)

    def distinct_values(self, resolved, extra_filters=None, resolver=None) -> list:
        """Return distinct values for a dimension field."""
        return self.engine.distinct_values(
            resolved, extra_filters=extra_filters,
            resolver=resolver or self.resolver,
        )

    def build_from(self, tables: dict[str, str], allowed_domains: set[str] | None = None) -> str:
        """Build FROM clause with automatic join resolution."""
        return self.engine.build_from(tables, resolver=self.resolver,
                                       allowed_domains=allowed_domains)

    def build_where(self, filters: list, from_tables: set[str] | None = None) -> list[str]:
        """Build WHERE clause fragments from filter specs."""
        return self.engine.build_where(filters, resolver=self.resolver,
                                        from_tables=from_tables)

    def close(self):
        pass


class IngestSession(Session):
    """Session for ingesting data from external APIs."""

    def __init__(self, engine, providers: dict, endpoints: dict, run_config=None, storage_config=None, **kwargs):
        super().__init__(engine, storage_config)
        self.providers = providers
        self.endpoints = endpoints
        self.run_config = run_config or {}

    def get_provider(self, provider_id: str) -> dict:
        """Get provider config by ID."""
        if provider_id not in self.providers:
            raise KeyError(f"Provider '{provider_id}' not found. Available: {list(self.providers.keys())}")
        return self.providers[provider_id]

    def get_endpoint(self, provider_id: str, endpoint_id: str) -> dict:
        """Get endpoint config by provider + endpoint ID."""
        key = f"{provider_id}.{endpoint_id}"
        if key not in self.endpoints:
            raise KeyError(f"Endpoint '{key}' not found.")
        return self.endpoints[key]

    def close(self):
        pass
