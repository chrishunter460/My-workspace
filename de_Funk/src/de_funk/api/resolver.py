"""
Field resolver — translates domain.field references to Silver table paths and columns.

Scans ``domains/models/`` for ``type: domain-model-table`` files and builds an index
of {domain → {field → (table_name, format_code)}} from their ``schema:`` frontmatter.

No dependency on ModelConfigLoader — works directly with the markdown files.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from de_funk.config.logging import get_logger

logger = get_logger(__name__)

_TEMPORAL_DOMAIN = "temporal"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    try:
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return {}
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


class FieldRef:
    """Parsed domain.field reference (e.g. 'corporate.finance.amount').

    Uses longest-prefix match against known canonical domain names so that
    dotted domains like ``corporate.finance`` are parsed correctly.
    """

    # Populated by FieldResolver._build_index once domain discovery completes.
    _known_domains: set[str] = set()

    def __init__(self, raw: str) -> None:
        if self._known_domains:
            self.domain, self.field = self._match_domain(raw)
        else:
            # Fallback before index is built: first-dot split
            parts = raw.split(".", 1)
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid field reference '{raw}' — expected 'domain.field' format"
                )
            self.domain, self.field = parts
        self.raw = raw

    @classmethod
    def _match_domain(cls, raw: str) -> tuple[str, str]:
        """Match longest known domain prefix from a raw reference string."""
        best = ""
        for d in cls._known_domains:
            if raw.startswith(d + ".") and len(d) > len(best):
                best = d
        if best:
            return best, raw[len(best) + 1:]
        # No known domain matched — fall back to first-dot split
        parts = raw.split(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid field reference '{raw}' — expected 'domain.field' format"
            )
        return parts[0], parts[1]

    def __repr__(self) -> str:
        return f"FieldRef({self.raw!r})"


class ResolvedField:
    """Resolution result — storage path + column for a domain.field ref."""

    def __init__(
        self,
        ref: FieldRef,
        table_name: str,
        column: str,
        silver_path: Path,
        format_code: Optional[str] = None,
    ) -> None:
        self.ref = ref
        self.table_name = table_name
        self.column = column
        self.silver_path = silver_path
        self.format_code = format_code

    @property
    def domain(self) -> str:
        """Canonical domain name (e.g. 'corporate.finance')."""
        return self.ref.domain

    def __repr__(self) -> str:
        return f"ResolvedField({self.ref.raw!r} → {self.table_name}.{self.column})"


class FieldResolver:
    """
    Resolves domain.field references to Silver table paths.

    Scans ``domains/models/`` on first use and builds an index:
      {domain_name: {field_name: (table_name, format_code)}}

    The domain name is derived from the top-level folder under ``domains/models/``
    (e.g. ``domains/models/securities/`` → domain ``securities``, or more specifically
    from the table file's path segment directly above ``tables/``).

    Usage::

        resolver = FieldResolver(domains_root=Path("domains"), storage_root=Path("storage/silver"))
        resolved = resolver.resolve("stocks.adjusted_close")
    """

    def __init__(
        self,
        domains_root: Path,
        storage_root: Path,
        domain_overrides: Optional[dict[str, Path]] = None,
    ) -> None:
        self.domains_root = domains_root
        self.storage_root = storage_root
        # Per-domain storage path overrides from configs/storage.json
        # e.g. {"securities.stocks": Path("/shared/storage/silver/stocks")}
        self._domain_overrides: dict[str, Path] = domain_overrides or {}
        self._cache: dict[str, ResolvedField] = {}
        # {domain: {field: (table_name, format_code, subdir)}}
        self._index: dict[str, dict[str, tuple[str, Optional[str], str]]] = {}
        # {table_name: set(column_names)} — reverse index from schema
        self._table_columns: dict[str, set[str]] = {}
        # Adjacency list built from graph.edges in model.md files.
        # {table: [(neighbor_table, col_on_table, col_on_neighbor)]}
        # Stored bidirectionally so BFS can traverse in either direction.
        self._join_graph: dict[str, list[tuple[str, str, str]]] = {}
        # Domain scoping: {canonical_domain: set(dependency_domains)}
        self._domain_deps: dict[str, set[str]] = {}
        # Reverse lookup: {table_name: canonical_domain}
        self._table_to_domain: dict[str, str] = {}
        self._built = False

    def _build_dir_to_model_map(self, models_root: Path) -> dict[Path, str]:
        """
        Scan model.md files to build a {directory → model_name} map and
        populate ``self._join_graph`` and ``self._domain_deps`` from model frontmatter.

        Each subdomain directory contains a model.md with a ``model:`` field
        (e.g. ``model: corporate.finance``). Table files in that directory use
        this as their domain name.

        The ``graph.edges`` list declares join relationships between Silver tables;
        these are parsed into a bidirectional adjacency graph for query-time JOIN
        resolution so the executor can join any two tables without cross-joining.

        The ``depends_on`` list declares which other domains a model can reach,
        used for domain-scoped filter and join resolution.
        """
        dir_map: dict[Path, str] = {}
        for model_file in models_root.rglob("model.md"):
            fm = _parse_frontmatter(model_file)
            if fm.get("type") == "domain-model" and fm.get("model"):
                canonical = fm["model"]
                dir_map[model_file.parent] = canonical
                # Store depends_on for domain scoping
                deps = fm.get("depends_on") or []
                self._domain_deps[canonical] = {str(d) for d in deps}
                # Load graph edges into the join graph
                graph_cfg = fm.get("graph") or {}
                for edge in (graph_cfg.get("edges") or []):
                    self._register_edge(edge)
        logger.debug(f"Join graph: {len(self._join_graph)} tables with known edges")
        logger.debug(f"Domain deps: {self._domain_deps}")
        return dir_map

    @staticmethod
    def _table_name_from_ref(ref: str) -> str:
        """Strip domain prefix from a table reference: 'domain.table' → 'table'."""
        return ref.split(".")[-1] if "." in ref else ref

    def _register_edge(self, edge: list) -> None:
        """
        Parse one graph edge tuple and add bidirectional entries to _join_graph.

        Edge format (positional list from model.md YAML):
          [edge_name, from_table, to_table_ref, [col_a=col_b, ...], cardinality, domain?, ...]

        Only the first key pair is used (compound FK edges are rare and unsupported here).
        """
        if not isinstance(edge, list) or len(edge) < 4:
            return
        from_table = str(edge[1])
        to_ref = str(edge[2])
        keys_list = edge[3]
        to_table = self._table_name_from_ref(to_ref)

        if not isinstance(keys_list, list) or not keys_list:
            return

        # Parse "col_a=col_b" from first key pair
        first_key = str(keys_list[0])
        if "=" in first_key:
            col_a, col_b = first_key.split("=", 1)
        else:
            return  # Malformed — skip

        # Register A→B
        self._join_graph.setdefault(from_table, []).append((to_table, col_a, col_b))
        # Register B→A (bidirectional for JOIN purposes)
        self._join_graph.setdefault(to_table, []).append((from_table, col_b, col_a))

    def _domain_for_table(self, md_file: Path, dir_map: dict[Path, str]) -> str:
        """
        Find the domain name for a table file by walking up to find the nearest
        model.md ancestor. Falls back to the folder name above ``tables/``.
        """
        # Walk up from the tables/ parent to find a directory with a known model
        search = md_file.parent.parent  # tables/ → model dir
        while search.name:
            if search in dir_map:
                return dir_map[search]
            search = search.parent

        # Fallback: segment just above "tables/"
        parts = md_file.parts
        try:
            tables_idx = list(parts).index("tables")
            return parts[tables_idx - 1]
        except ValueError:
            return md_file.parent.name

    def _build_index(self) -> None:
        """Scan domains/models/ and index all domain-model-table files."""
        models_root = self.domains_root / "models"
        if not models_root.exists():
            logger.warning(f"domains/models/ not found at {models_root}")
            self._built = True
            return

        # First pass: build directory → model_name map from model.md files
        dir_map = self._build_dir_to_model_map(models_root)
        # Populate FieldRef with known domains so dotted names parse correctly
        FieldRef._known_domains = set(dir_map.values()) | {_TEMPORAL_DOMAIN}
        logger.debug(f"Found {len(dir_map)} domain models: {sorted(dir_map.values())}")

        for md_file in models_root.rglob("*.md"):
            fm = _parse_frontmatter(md_file)
            if fm.get("type") != "domain-model-table":
                continue

            table_name = fm.get("table", md_file.stem)
            schema = fm.get("schema", [])
            additional = fm.get("additional_schema", [])
            if not schema and not additional:
                continue
            # Merge base schema + additional_schema (fact tables that extend
            # base templates put extra columns in additional_schema)
            schema = list(schema) + list(additional)

            # Derive subdirectory from table_type: "dimension" → "dims", "fact" → "facts"
            table_type = fm.get("table_type", "")
            if table_type == "dimension":
                subdir = "dims"
            elif table_type == "fact":
                subdir = "facts"
            else:
                subdir = ""

            domain = self._domain_for_table(md_file, dir_map)
            self._table_to_domain[table_name] = domain

            if domain not in self._index:
                self._index[domain] = {}

            for col in schema:
                if not isinstance(col, list) or len(col) < 2:
                    continue
                col_name = col[0]
                format_code = None
                if len(col) >= 5 and isinstance(col[4], dict):
                    format_code = col[4].get("format")
                # Don't overwrite — first table wins for a given field name
                if col_name not in self._index[domain]:
                    self._index[domain][col_name] = (table_name, format_code, subdir)
                # Always populate table_columns reverse index
                self._table_columns.setdefault(table_name, set()).add(col_name)

        logger.info(f"FieldResolver index built: {len(self._index)} domains, "
                    f"{sum(len(v) for v in self._index.values())} fields")
        self._built = True

    def reachable_domains(self, core_domains: set[str]) -> set[str]:
        """Compute allowed domains: core domains + their depends_on.

        Used by handlers to scope filter and join resolution so that
        cross-domain page filters don't contaminate unrelated exhibits.
        """
        if not self._built:
            self._build_index()
        result = set(core_domains)
        for d in core_domains:
            result |= self._domain_deps.get(d, set())
        return result

    def find_join_path(
        self,
        src: str,
        dst: str,
        allowed_domains: set[str] | None = None,
    ) -> list[tuple[str, str, str]] | None:
        """
        Find a join path between two Silver tables using BFS over graph.edges.

        When *allowed_domains* is provided, the BFS will not traverse into
        tables belonging to domains outside the allowed set.  This prevents
        cross-domain joins (e.g. municipal → corporate via dim_calendar).

        Returns a list of (next_table, col_on_current, col_on_next) steps, or
        None if no path exists in the join graph.
        """
        if not self._built:
            self._build_index()
        if src == dst:
            return []

        from collections import deque
        queue: deque[tuple[str, list[tuple[str, str, str]]]] = deque()
        queue.append((src, []))
        visited = {src}

        while queue:
            current, path = queue.popleft()
            for neighbor, col_on_current, col_on_neighbor in self._join_graph.get(current, []):
                if neighbor in visited:
                    continue
                # Domain-scoped BFS: skip neighbors outside allowed domains
                if allowed_domains is not None:
                    neighbor_domain = self._table_to_domain.get(neighbor)
                    if neighbor_domain and neighbor_domain not in allowed_domains:
                        continue
                step = (neighbor, col_on_current, col_on_neighbor)
                new_path = path + [step]
                if neighbor == dst:
                    return new_path
                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return None  # no path found

    def resolve(self, ref_str: str) -> ResolvedField:
        """Resolve a domain.field string to a ResolvedField."""
        if ref_str in self._cache:
            return self._cache[ref_str]

        if not self._built:
            self._build_index()

        ref = FieldRef(ref_str)
        resolved = (
            self._resolve_temporal(ref)
            if ref.domain == _TEMPORAL_DOMAIN
            else self._resolve_domain_field(ref)
        )
        self._cache[ref_str] = resolved
        return resolved

    def resolve_many(self, refs: list[str]) -> dict[str, ResolvedField]:
        return {ref: self.resolve(ref) for ref in refs}

    def get_field_catalog(self) -> dict[str, dict]:
        """Return full field catalog — used by GET /api/domains."""
        if not self._built:
            self._build_index()
        catalog: dict[str, dict] = {}
        for domain, fields in self._index.items():
            catalog[domain] = {
                "fields": {
                    field: {"table": table_name, "column": field, "format": fmt}
                    for field, (table_name, fmt, _subdir) in fields.items()
                },
            }
        return catalog

    def _resolve_temporal(self, ref: FieldRef) -> ResolvedField:
        _MAP = {
            "date":        ("dim_calendar", "date"),
            "date_id":     ("dim_calendar", "date_id"),
            "year":        ("dim_calendar", "year"),
            "month":       ("dim_calendar", "month"),
            "quarter":     ("dim_calendar", "quarter"),
            "day_of_week": ("dim_calendar", "day_of_week"),
            "week":        ("dim_calendar", "week_of_year"),
        }
        if ref.field not in _MAP:
            raise ValueError(
                f"Unknown temporal field '{ref.field}'. Available: {list(_MAP)}"
            )
        table_name, column = _MAP[ref.field]
        temporal_root = self._domain_overrides.get("temporal", self.storage_root / "temporal")
        # dim_calendar lives in dims/ subdirectory
        return ResolvedField(ref, table_name, column, temporal_root / "dims" / table_name)

    def _resolve_domain_field(self, ref: FieldRef) -> ResolvedField:
        domain = ref.domain
        field = ref.field
        domain_fields = self._index.get(domain)
        if domain_fields is None:
            available = sorted(self._index)
            raise ValueError(
                f"Domain '{domain}' not found. Available domains: {available}"
            )

        entry = domain_fields.get(field)
        if entry is None:
            available = sorted(domain_fields)[:20]
            raise ValueError(
                f"Field '{field}' not found in domain '{domain}'. "
                f"Available fields (first 20): {available}"
            )
        table_name, format_code, subdir = entry
        # Use domain-specific override if present, otherwise fall back to default root
        # Convert dots to path separators: corporate.entity → corporate/entity
        domain_path = domain.replace(".", "/")
        domain_root = self._domain_overrides.get(domain, self.storage_root / domain_path)
        # Silver tables are stored in dims/ or facts/ subdirectories when table_type is set
        if subdir:
            silver_path = domain_root / subdir / table_name
        else:
            silver_path = domain_root / table_name
        logger.debug(f"Resolved {ref.raw} → {table_name}.{ref.field} @ {silver_path}")
        return ResolvedField(ref, table_name, ref.field, silver_path, format_code)
