"""
Domain Config Loader V4 — multi-file domain model configuration.

Loads model configurations from the domains/ (v4) directory structure
where models are split across multiple files:

    domains/
    ├── _model_guides_/     # Reference docs (type: reference) — not loaded
    ├── _base/              # Base templates (type: domain-base)
    └── models/             # Concrete models
        └── {model}/
            ├── model.md        # type: domain-model
            ├── tables/*.md     # type: domain-model-table
            ├── sources/**/*.md # type: domain-model-source
            └── views/*.md      # type: domain-model-view

Usage:
    from de_funk.config.domain import DomainConfigLoader, get_domain_loader

    loader = DomainConfigLoader(Path("domains"))
    config = loader.load_model_config("county.property")
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .extends import (
    parse_front_matter,
    deep_merge,
    resolve_extends_reference,
    resolve_nested_extends,
)
from .schema import process_table_schema
from .subsets import absorb_subsets

logger = logging.getLogger(__name__)

# File types recognized by the v4 loader
FILE_TYPES = {
    "domain-base",
    "domain-model",
    "domain-model-table",
    "domain-model-source",
    "domain-model-view",
    "reference",
}


class DomainConfigLoader:
    """
    Multi-file domain configuration loader (v4 format).

    Discovers and assembles model configs from directory structures where
    each model is a directory with model.md + tables/*.md + sources/**/*.md
    + views/*.md.
    """

    def __init__(self, domains_dir: Path):
        self.domains_dir = Path(domains_dir)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._parse_cache: Dict[str, Dict[str, Any]] = {}

        # Index: maps type → list of (name, path) tuples
        self._type_index: Dict[str, List[tuple]] = {t: [] for t in FILE_TYPES}
        # Maps model name → model.md path (relative)
        self._model_to_path: Dict[str, Path] = {}

        self._build_index()

    def _build_index(self):
        """Scan all .md files and categorize by type."""
        if not self.domains_dir.exists():
            logger.warning(f"Domains directory not found: {self.domains_dir}")
            return

        for md_file in sorted(self.domains_dir.rglob("*.md")):
            if md_file.name.lower() in ("readme.md",):
                continue

            config = parse_front_matter(md_file)
            if not config:
                continue

            file_type = config.get("type", "")
            if file_type not in FILE_TYPES:
                continue

            rel_path = md_file.relative_to(self.domains_dir)
            name = config.get("model") or config.get("table") or config.get(
                "view") or config.get("source") or md_file.stem

            self._type_index[file_type].append((name, rel_path))
            self._parse_cache[str(md_file)] = config

            # Index domain-model files for quick lookup
            if file_type == "domain-model":
                model_name = config.get("model", md_file.stem)
                self._model_to_path[model_name] = rel_path

    def load_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Load complete model configuration by name.

        Discovers model.md, then auto-discovers tables/, sources/, views/
        in the same directory and assembles everything into one config dict.

        Args:
            model_name: Model identifier (e.g., "county_property")

        Returns:
            Assembled configuration dictionary
        """
        if model_name in self._cache:
            return self._cache[model_name]

        if model_name not in self._model_to_path:
            raise FileNotFoundError(
                f"Domain model '{model_name}' not found in {self.domains_dir}"
            )

        rel_path = self._model_to_path[model_name]
        model_file = self.domains_dir / rel_path
        model_dir = model_file.parent

        # Parse model.md
        model_config = parse_front_matter(model_file)
        model_config["_source_file"] = str(rel_path)

        # Resolve top-level extends (single string or list)
        extends = model_config.get("extends")
        if extends:
            if isinstance(extends, str):
                extends = [extends]
            for ext_ref in extends:
                parent = resolve_extends_reference(
                    ext_ref, self.domains_dir, self._parse_cache
                )
                model_config = deep_merge(parent, model_config)

        # Auto-discover tables/, sources/, views/
        tables = self._discover_tables(model_dir)
        sources = self._discover_sources(model_dir)
        views = self._discover_views(model_dir)

        # Assemble into unified config
        config = self._assemble_model(model_config, tables, sources, views)

        # Resolve nested extends (tables, views, graph sections)
        config = resolve_nested_extends(config, self.domains_dir, self._parse_cache)

        # Process table schemas (additional_schema + derivations)
        for table_name, table_config in config.get("tables", {}).items():
            if isinstance(table_config, dict) and table_config.get("schema"):
                process_table_schema(table_config)

        self._cache[model_name] = config
        return config

    def _discover_tables(self, model_dir: Path) -> Dict[str, Dict]:
        """Find all tables/*.md in the model directory."""
        tables = {}
        tables_dir = model_dir / "tables"
        if not tables_dir.exists():
            return tables

        for md_file in sorted(tables_dir.glob("*.md")):
            config = self._get_parsed(md_file)
            if config.get("type") == "domain-model-table":
                table_name = config.get("table", md_file.stem)
                config["_source_file"] = str(
                    md_file.relative_to(self.domains_dir)
                )
                tables[table_name] = config
        return tables

    def _discover_sources(self, model_dir: Path) -> Dict[str, Dict]:
        """Find all sources/**/*.md in the model directory."""
        sources = {}
        sources_dir = model_dir / "sources"
        if not sources_dir.exists():
            # Try parent's sources/ (sources often live one level up)
            sources_dir = model_dir.parent / "sources"
            if not sources_dir.exists():
                return sources

        for md_file in sorted(sources_dir.rglob("*.md")):
            config = self._get_parsed(md_file)
            if config.get("type") == "domain-model-source":
                source_name = config.get("source", md_file.stem)
                config["_source_file"] = str(
                    md_file.relative_to(self.domains_dir)
                )
                sources[source_name] = config
        return sources

    def _discover_views(self, model_dir: Path) -> Dict[str, Dict]:
        """Find all views/*.md in the model directory."""
        views = {}
        views_dir = model_dir / "views"
        if not views_dir.exists():
            return views

        for md_file in sorted(views_dir.glob("*.md")):
            config = self._get_parsed(md_file)
            if config.get("type") == "domain-model-view":
                view_name = config.get("view", md_file.stem)
                config["_source_file"] = str(
                    md_file.relative_to(self.domains_dir)
                )
                views[view_name] = config
        return views

    def _get_parsed(self, file_path: Path) -> Dict[str, Any]:
        """Get parsed front matter, using cache."""
        cache_key = str(file_path)
        if cache_key not in self._parse_cache:
            self._parse_cache[cache_key] = parse_front_matter(file_path)
        return self._parse_cache[cache_key]

    def _assemble_model(
        self,
        model_config: Dict,
        tables: Dict[str, Dict],
        sources: Dict[str, Dict],
        views: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """
        Merge discovered files into the model config.

        Tables from separate files are merged into config["tables"],
        preserving any inline table definitions from model.md.
        Same for sources and views.
        """
        # Merge tables — separate files override inline definitions
        existing_tables = model_config.get("tables", {})
        if isinstance(existing_tables, dict):
            merged_tables = deep_merge(existing_tables, tables)
        else:
            merged_tables = tables
        if merged_tables:
            model_config["tables"] = merged_tables

        # Merge sources
        existing_sources = model_config.get("sources", {})
        if isinstance(existing_sources, dict):
            merged_sources = deep_merge(existing_sources, sources)
        else:
            merged_sources = sources
        if merged_sources:
            model_config["sources"] = merged_sources

        # Merge views — separate files override inline definitions
        existing_views = model_config.get("views", {})
        if isinstance(existing_views, dict):
            merged_views = deep_merge(existing_views, views)
        else:
            merged_views = views
        if merged_views:
            model_config["views"] = merged_views

        return model_config

    def list_models(self) -> List[str]:
        """List all domain-model names."""
        return sorted(self._model_to_path.keys())

    def get_dependencies(self, model_name: str) -> List[str]:
        """Get depends_on for a model."""
        config = self.load_model_config(model_name)
        return config.get("depends_on", [])

    def get_build_order(self, models: Optional[List[str]] = None) -> List[str]:
        """Topologically sorted build order (Kahn's algorithm)."""
        if models is None:
            models = self.list_models()

        graph: Dict[str, List[str]] = {}
        for model in models:
            try:
                deps = self.get_dependencies(model)
                graph[model] = [d for d in deps if d in models]
            except Exception as e:
                logger.warning(f"Could not get deps for {model}: {e}")
                graph[model] = []

        in_degree = {m: 0 for m in models}
        for model, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[model] += 1

        queue = sorted(m for m in models if in_degree[m] == 0)
        result = []

        while queue:
            model = queue.pop(0)
            result.append(model)
            for other, deps in graph.items():
                if model in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0 and other not in result:
                        queue.append(other)

        if len(result) != len(models):
            missing = set(models) - set(result)
            logger.warning(f"Circular dependencies detected: {missing}")
            result.extend(sorted(missing))

        return result

    def load_base(self, base_ref: str, with_subsets: bool = False) -> Dict[str, Any]:
        """
        Load a base template by dotted reference.

        Args:
            base_ref: Dotted reference (e.g., "_base.simple.base_template")
            with_subsets: If True, run subset auto-absorption on the result

        Returns:
            Base config dict, optionally with absorbed subset columns
        """
        config = resolve_extends_reference(
            base_ref, self.domains_dir, self._parse_cache
        )
        if with_subsets and config.get("subsets"):
            config = absorb_subsets(
                config, self.domains_dir, self._parse_cache, parent_ref=base_ref
            )
        return config

    def clear_cache(self):
        """Clear all caches."""
        self._cache.clear()
        self._parse_cache.clear()


def get_domain_loader(domains_dir: Path) -> DomainConfigLoader:
    """
    Factory: return V4 domain config loader.

    Args:
        domains_dir: Path to the domains/ directory

    Returns:
        DomainConfigLoader instance

    Raises:
        FileNotFoundError: If domains_dir doesn't exist or has no v4 structure
    """
    domains_dir = Path(domains_dir)

    if not domains_dir.exists():
        raise FileNotFoundError(f"Domains directory not found: {domains_dir}")

    return DomainConfigLoader(domains_dir)
