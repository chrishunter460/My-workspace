"""
Dependency Graph - Model build ordering via topological sort.

Purpose:
    Analyzes model dependencies from YAML configs and provides
    correct build order using topological sort.

Key Features:
    - Auto-discover model dependencies from model.yaml files
    - Topological sort for correct build order
    - Automatic dependency resolution for partial builds
    - Circular dependency detection
    - Visualization of dependency graph

Usage:
    from de_funk.orchestration.dependency_graph import DependencyGraph
    from pathlib import Path

    # Initialize with configs path
    dep_graph = DependencyGraph(Path("configs/models"))
    dep_graph.build()

    # Get full build order
    order = dep_graph.topological_sort()
    # ['core', 'company', 'macro', 'stocks', 'city_finance', ...]

    # Get build order for specific models (with auto-deps)
    order = dep_graph.filter_buildable(['stocks', 'city_finance'])
    # ['core', 'company', 'macro', 'stocks', 'city_finance']

    # Visualize dependencies
    print(dep_graph.visualize())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelInfo:
    """Metadata about a model for dependency resolution."""
    name: str
    version: str = "1.0"
    depends_on: List[str] = field(default_factory=list)
    inherits_from: Optional[str] = None
    storage_root: str = ""
    enabled: bool = True


class DependencyGraph:
    """
    Model dependency graph with topological sorting.

    Uses NetworkX for graph operations when available,
    falls back to simple implementation otherwise.

    Discovers model dependencies by reading model.yaml files
    from the configs/models directory.
    """

    def __init__(self, configs_path: Path):
        """
        Initialize dependency graph.

        Args:
            configs_path: Path to configs/models directory
        """
        self.configs_path = configs_path
        self.models: Dict[str, ModelInfo] = {}
        self._graph: Optional[nx.DiGraph] = None if not HAS_NETWORKX else nx.DiGraph()
        self._built = False

    def build(self, force: bool = False) -> None:
        """
        Build dependency graph by discovering model configs.

        Args:
            force: Rebuild even if already built
        """
        if self._built and not force:
            return

        self.models = {}
        if HAS_NETWORKX:
            self._graph = nx.DiGraph()

        # Discover models
        self._discover_models()

        # Build graph edges
        self._build_edges()

        self._built = True
        logger.debug(f"Built dependency graph with {len(self.models)} models")

    def _discover_models(self) -> None:
        """Discover models from model.yaml files."""
        if not self.configs_path.exists():
            logger.warning(f"Configs path not found: {self.configs_path}")
            return

        # Check for v2.0 modular pattern (model.yaml in subdirs)
        for model_dir in self.configs_path.iterdir():
            if not model_dir.is_dir():
                continue
            if model_dir.name.startswith('_'):
                # Skip base templates
                continue

            model_yaml = model_dir / 'model.yaml'
            if model_yaml.exists():
                self._load_model_yaml(model_yaml, model_dir.name)
                continue

            # Also check for v1.x single-file pattern
            # (model.yaml named after directory)

        # Check for v1.x single YAML files in root
        for yaml_file in self.configs_path.glob('*.yaml'):
            if yaml_file.stem not in self.models:
                self._load_model_yaml(yaml_file, yaml_file.stem)

    def _load_model_yaml(self, yaml_path: Path, model_name: str) -> None:
        """Load model info from YAML file."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if data is None:
                return

            # Handle depends_on as string or list
            depends_on = data.get('depends_on', [])
            if isinstance(depends_on, str):
                depends_on = [d.strip() for d in depends_on.split(',')]

            # Get storage root
            storage = data.get('storage', {})
            storage_root = storage.get('root', f'storage/silver/{model_name}')

            info = ModelInfo(
                name=model_name,
                version=str(data.get('version', '1.0')),
                depends_on=depends_on,
                inherits_from=data.get('inherits_from'),
                storage_root=storage_root,
                enabled=data.get('enabled', True),
            )

            self.models[model_name] = info
            logger.debug(f"Loaded model: {model_name} (deps: {depends_on})")

        except Exception as e:
            logger.error(f"Error loading model YAML {yaml_path}: {e}")

    def _build_edges(self) -> None:
        """Build graph edges from dependencies."""
        if HAS_NETWORKX:
            # Add all models as nodes
            for name in self.models:
                self._graph.add_node(name)

            # Add dependency edges (dependency -> model)
            for name, info in self.models.items():
                for dep in info.depends_on:
                    if dep in self.models:
                        self._graph.add_edge(dep, name)
                    else:
                        logger.warning(f"Model '{name}' depends on unknown model '{dep}'")

    def get_dependencies(
        self,
        model_name: str,
        recursive: bool = True
    ) -> List[str]:
        """
        Get dependencies for a model.

        Args:
            model_name: Model to get dependencies for
            recursive: If True, include transitive dependencies

        Returns:
            List of dependency model names
        """
        self.build()

        if model_name not in self.models:
            return []

        if not recursive:
            return list(self.models[model_name].depends_on)

        if HAS_NETWORKX:
            # Get all ancestors (transitive dependencies)
            try:
                return list(nx.ancestors(self._graph, model_name))
            except nx.NetworkXError:
                return []
        else:
            # Simple recursive implementation
            return self._get_deps_recursive(model_name, set())

    def _get_deps_recursive(
        self,
        model_name: str,
        visited: Set[str]
    ) -> List[str]:
        """Recursively get dependencies (fallback when no NetworkX)."""
        if model_name in visited or model_name not in self.models:
            return []

        visited.add(model_name)
        deps = []

        for dep in self.models[model_name].depends_on:
            if dep not in visited:
                deps.append(dep)
                deps.extend(self._get_deps_recursive(dep, visited))

        return deps

    def topological_sort(self) -> List[str]:
        """
        Get all models in correct build order.

        Returns:
            List of model names in topological order

        Raises:
            ValueError: If circular dependency detected
        """
        self.build()

        if HAS_NETWORKX:
            try:
                return list(nx.topological_sort(self._graph))
            except nx.NetworkXUnfeasible as e:
                # Find the cycle for better error message
                cycles = list(nx.simple_cycles(self._graph))
                raise ValueError(
                    f"Circular dependency detected: {cycles[0] if cycles else 'unknown'}"
                ) from e
        else:
            return self._topo_sort_simple()

    def _topo_sort_simple(self) -> List[str]:
        """Simple topological sort (fallback when no NetworkX)."""
        # Kahn's algorithm
        in_degree: Dict[str, int] = {name: 0 for name in self.models}

        for name, info in self.models.items():
            for dep in info.depends_on:
                if dep in self.models:
                    in_degree[name] += 1

        # Start with nodes that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort for deterministic order
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for dependents
            for name, info in self.models.items():
                if node in info.depends_on:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        if len(result) != len(self.models):
            raise ValueError("Circular dependency detected")

        return result

    def filter_buildable(self, requested: List[str]) -> List[str]:
        """
        Get build order for specific models with their dependencies.

        Auto-includes all required dependencies.

        Args:
            requested: List of model names to build

        Returns:
            List of models in correct build order (deps + requested)

        Example:
            >>> dep_graph.filter_buildable(['stocks'])
            ['core', 'company', 'stocks']  # core and company are auto-included
        """
        self.build()

        # Collect all required models (requested + dependencies)
        required: Set[str] = set(requested)
        for model in requested:
            required.update(self.get_dependencies(model, recursive=True))

        # Get full build order and filter to required
        full_order = self.topological_sort()
        return [m for m in full_order if m in required]

    def get_dependents(self, model_name: str) -> List[str]:
        """
        Get models that depend on this model.

        Args:
            model_name: Model to find dependents of

        Returns:
            List of model names that depend on this model
        """
        self.build()

        if HAS_NETWORKX:
            try:
                return list(nx.descendants(self._graph, model_name))
            except nx.NetworkXError:
                return []
        else:
            # Simple implementation
            dependents = []
            for name, info in self.models.items():
                if model_name in info.depends_on:
                    dependents.append(name)
                    dependents.extend(self.get_dependents(name))
            return list(set(dependents))

    def visualize(self) -> str:
        """
        Generate text visualization of dependency graph.

        Returns:
            Multi-line string showing dependencies
        """
        self.build()

        lines = ["Model Dependency Graph:", "=" * 40]

        for model in self.topological_sort():
            deps = self.get_dependencies(model, recursive=False)
            if deps:
                lines.append(f"  {model} ← {', '.join(deps)}")
            else:
                lines.append(f"  {model} (no dependencies)")

        return "\n".join(lines)

    def get_tiers(self) -> Dict[int, List[str]]:
        """
        Get models organized by dependency tier.

        Tier 0: No dependencies
        Tier 1: Depends only on Tier 0
        Tier 2: Depends on Tier 0 or 1
        etc.

        Returns:
            Dict mapping tier number to list of model names
        """
        self.build()

        tiers: Dict[int, List[str]] = {}
        assigned: Dict[str, int] = {}

        # Assign tier based on max dependency tier + 1
        for model in self.topological_sort():
            deps = self.get_dependencies(model, recursive=False)

            if not deps:
                tier = 0
            else:
                tier = max(assigned.get(d, 0) for d in deps if d in assigned) + 1

            assigned[model] = tier

            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(model)

        return tiers

    def list_models(self) -> List[str]:
        """Get list of all discovered models."""
        self.build()
        return sorted(self.models.keys())

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get info for a specific model."""
        self.build()
        return self.models.get(model_name)

    def validate(self) -> List[str]:
        """
        Validate the dependency graph.

        Returns:
            List of validation errors (empty if valid)
        """
        self.build()
        errors = []

        # Check for missing dependencies
        for name, info in self.models.items():
            for dep in info.depends_on:
                if dep not in self.models:
                    errors.append(f"Model '{name}' depends on unknown model '{dep}'")

        # Check for cycles
        try:
            self.topological_sort()
        except ValueError as e:
            errors.append(str(e))

        return errors
