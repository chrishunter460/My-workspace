"""
DomainGraph — queryable graph model built from EdgeSpec.

Built from all EdgeSpec objects across all DomainModelConfig instances.
Provides BFS join path finding, domain scoping, proximity analysis,
and connected component detection.

Used by:
    - FieldResolver: join path resolution for queries
    - BuildSession: dependency resolution for builds
    - DeFunk: top-level graph for the entire data warehouse
"""
from __future__ import annotations
from collections import defaultdict, deque
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class DomainGraph:
    """Queryable graph of domain model relationships.

    Built from EdgeSpec objects in DomainModelConfig.graph.edges.
    Edges are bidirectional — if A→B exists, B→A is also navigable.
    """

    def __init__(self, models: dict[str, Any] | None = None):
        self._adjacency: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        self._domain_deps: dict[str, set[str]] = defaultdict(set)
        self._table_to_domain: dict[str, str] = {}

        if models:
            self._build_from_models(models)

    def _build_from_models(self, models: dict[str, Any]) -> None:
        """Build graph from all EdgeSpecs across models."""
        edge_count = 0
        for model_name, config in models.items():
            # Handle both dict and dataclass configs
            if isinstance(config, dict):
                graph_cfg = config.get("graph", {})
                edges = graph_cfg.get("edges", [])
                deps = config.get("depends_on", [])
            else:
                graph_cfg = getattr(config, 'graph', None)
                edges = getattr(graph_cfg, 'edges', []) if graph_cfg else []
                deps = getattr(config, 'depends_on', [])

            # Store domain dependencies
            self._domain_deps[model_name] = set(str(d) for d in deps)

            # Process edges
            for edge in edges:
                self._register_edge(edge, model_name)
                edge_count += 1

        logger.info(f"DomainGraph built: {len(self._adjacency)} tables, {edge_count} edges, {len(self._domain_deps)} domains")

    def _register_edge(self, edge, model_name: str) -> None:
        """Register one edge (list or EdgeSpec) bidirectionally."""
        if isinstance(edge, list) and len(edge) >= 4:
            # List format: [name, from_table, to_table, [join_keys], cardinality, domain]
            _name = edge[0]
            from_table = str(edge[1]).split(".")[-1]
            to_table = str(edge[2]).split(".")[-1]
            join_keys = edge[3] if isinstance(edge[3], list) else [edge[3]]

            if join_keys and "=" in str(join_keys[0]):
                parts = str(join_keys[0]).split("=")
                col_a, col_b = parts[0].strip(), parts[1].strip()
            else:
                col_a = col_b = str(join_keys[0]) if join_keys else ""

            # Bidirectional
            self._adjacency[from_table].append((to_table, col_a, col_b))
            self._adjacency[to_table].append((from_table, col_b, col_a))

            # Track table → domain
            self._table_to_domain[from_table] = model_name
            if len(edge) >= 6 and edge[5]:
                self._table_to_domain[to_table] = str(edge[5])
        elif hasattr(edge, 'from_table'):
            # EdgeSpec dataclass
            from_table = edge.from_table.split(".")[-1]
            to_table = edge.to_table.split(".")[-1]

            col_a = col_b = ""
            if edge.join_keys and "=" in str(edge.join_keys[0]):
                parts = str(edge.join_keys[0]).split("=")
                col_a, col_b = parts[0].strip(), parts[1].strip()

            self._adjacency[from_table].append((to_table, col_a, col_b))
            self._adjacency[to_table].append((from_table, col_b, col_a))

            self._table_to_domain[from_table] = model_name
            if edge.target_domain:
                self._table_to_domain[to_table] = edge.target_domain

    def find_join_path(
        self, src: str, dst: str, allowed_domains: set[str] | None = None
    ) -> list[tuple[str, str, str]] | None:
        """BFS shortest join path from src table to dst table.

        Returns list of (table, col_on_current, col_on_next) tuples,
        or None if no path exists.
        """
        if src == dst:
            return []
        if src not in self._adjacency or dst not in self._adjacency:
            return None

        visited = {src}
        queue = deque([(src, [])])

        while queue:
            current, path = queue.popleft()

            for neighbor, col_on_current, col_on_neighbor in self._adjacency.get(current, []):
                if neighbor in visited:
                    continue

                # Domain scoping
                if allowed_domains is not None:
                    neighbor_domain = self._table_to_domain.get(neighbor)
                    if neighbor_domain and neighbor_domain not in allowed_domains:
                        continue

                new_path = path + [(neighbor, col_on_current, col_on_neighbor)]

                if neighbor == dst:
                    return new_path

                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return None

    def reachable_domains(self, core_domains: set[str]) -> set[str]:
        """Get all domains reachable from the core set (transitive deps)."""
        result = set(core_domains)
        frontier = set(core_domains)

        while frontier:
            next_frontier = set()
            for domain in frontier:
                deps = self._domain_deps.get(domain, set())
                for dep in deps:
                    if dep not in result:
                        result.add(dep)
                        next_frontier.add(dep)
            frontier = next_frontier

        return result

    def neighbors(self, table_name: str) -> list[str]:
        """Get adjacent tables."""
        return [t for t, _, _ in self._adjacency.get(table_name, [])]

    def domains_for_table(self, table_name: str) -> str | None:
        """Get the domain that owns a table."""
        return self._table_to_domain.get(table_name)

    def all_tables(self) -> list[str]:
        """Get all tables in the graph."""
        return list(self._adjacency.keys())

    def all_edges(self) -> list[tuple[str, str, str, str]]:
        """Get all edges as (from, to, col_a, col_b) tuples."""
        edges = []
        seen = set()
        for from_table, neighbors in self._adjacency.items():
            for to_table, col_a, col_b in neighbors:
                key = tuple(sorted([from_table, to_table]))
                if key not in seen:
                    edges.append((from_table, to_table, col_a, col_b))
                    seen.add(key)
        return edges

    def distance(self, table_a: str, table_b: str) -> int:
        """Hop count between two tables (-1 if unreachable)."""
        path = self.find_join_path(table_a, table_b)
        return len(path) if path is not None else -1

    def connected_components(self) -> list[set[str]]:
        """Find connected components in the graph."""
        visited: set[str] = set()
        components: list[set[str]] = []

        for table in self._adjacency:
            if table in visited:
                continue
            component: set[str] = set()
            queue = deque([table])
            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor, _, _ in self._adjacency.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)
            components.append(component)

        return components

    def subgraph(self, domains: set[str]) -> DomainGraph:
        """Create a scoped subgraph containing only the specified domains."""
        filtered_models = {}
        # This is a simplified version — full implementation would filter edges
        return DomainGraph(filtered_models)
