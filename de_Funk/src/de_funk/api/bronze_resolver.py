"""
Bronze resolver — translates provider.endpoint.field references to Bronze table paths.

Scans ``data_sources/Endpoints/`` for ``type: api-endpoint`` files and builds an index
of {provider → {endpoint → {field → type}}} from their ``schema:`` frontmatter.

Implements the same interface as FieldResolver so existing handlers can query
Bronze data without modification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from de_funk.api.resolver import FieldRef, ResolvedField
from de_funk.config.logging import get_logger

logger = get_logger(__name__)

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


@dataclass
class BronzeEndpointInfo:
    """Metadata for one Bronze endpoint table."""
    provider_id: str
    endpoint_id: str
    bronze_path: Path
    fields: dict[str, str]  # {column_name: type_str}


class BronzeResolver:
    """
    Resolves provider.endpoint.field references to Bronze Delta Lake paths.

    Implements the resolver interface expected by handlers:
    - resolve(ref_str) → ResolvedField
    - reachable_domains(core_domains) → set (pass-through)
    - find_join_path(src, dst) → None (no joins)

    Usage::

        resolver = BronzeResolver(
            data_sources_root=Path("data_sources"),
            bronze_root=Path("/shared/storage/bronze"),
        )
        resolved = resolver.resolve("chicago.crimes.primary_type")
    """

    def __init__(self, data_sources_root: Path, bronze_root: Path) -> None:
        self.data_sources_root = data_sources_root
        self.bronze_root = bronze_root
        # {provider_id: {endpoint_id: BronzeEndpointInfo}}
        self._index: dict[str, dict[str, BronzeEndpointInfo]] = {}
        self._known_providers: set[str] = set()
        self._cache: dict[str, ResolvedField] = {}
        # Empty join graph — Bronze is single-table
        self._join_graph: dict[str, list] = {}
        self._table_to_domain: dict[str, str] = {}
        self._built = False

    def _build_index(self) -> None:
        """Scan data_sources/ and index all endpoint files with Bronze data on disk."""
        # Step 1: Build provider display_name → provider_id map
        provider_map: dict[str, str] = {}  # {"Chicago Data Portal": "chicago"}
        providers_dir = self.data_sources_root / "Providers"
        if providers_dir.exists():
            for md in providers_dir.glob("*.md"):
                fm = _parse_frontmatter(md)
                if fm.get("type") == "api-provider" and fm.get("provider_id"):
                    display = fm.get("provider", md.stem)
                    provider_map[display] = fm["provider_id"]

        logger.debug(f"Bronze providers: {provider_map}")

        # Step 2: Scan endpoint markdown files
        endpoints_dir = self.data_sources_root / "Endpoints"
        if not endpoints_dir.exists():
            logger.warning(f"data_sources/Endpoints/ not found at {endpoints_dir}")
            self._built = True
            return

        for md in endpoints_dir.rglob("*.md"):
            fm = _parse_frontmatter(md)
            if fm.get("type") != "api-endpoint":
                continue

            endpoint_id = fm.get("endpoint_id")
            schema = fm.get("schema")
            bronze_segment = fm.get("bronze")
            provider_display = fm.get("provider", "")

            if not endpoint_id or not schema or not bronze_segment:
                continue

            # Resolve provider_id from display name
            provider_id = provider_map.get(provider_display, bronze_segment)

            # Check Bronze path exists on disk
            bronze_path = self.bronze_root / provider_id / endpoint_id
            if not bronze_path.exists():
                logger.debug(
                    f"Bronze path missing for {provider_id}.{endpoint_id}: {bronze_path}"
                )
                continue

            # Parse schema columns: [[col_name, type, ...], ...]
            fields: dict[str, str] = {}
            for col in schema:
                if isinstance(col, list) and len(col) >= 2:
                    fields[col[0]] = col[1]

            info = BronzeEndpointInfo(
                provider_id=provider_id,
                endpoint_id=endpoint_id,
                bronze_path=bronze_path,
                fields=fields,
            )
            self._index.setdefault(provider_id, {})[endpoint_id] = info
            self._known_providers.add(provider_id)
            # Populate table_to_domain for compatibility
            self._table_to_domain[endpoint_id] = provider_id

        total_endpoints = sum(len(eps) for eps in self._index.values())
        total_fields = sum(
            len(ep.fields)
            for eps in self._index.values()
            for ep in eps.values()
        )
        logger.info(
            f"BronzeResolver index built: {len(self._index)} providers, "
            f"{total_endpoints} endpoints, {total_fields} fields"
        )
        self._built = True

    def resolve(self, ref_str: str) -> ResolvedField:
        """Resolve a provider.endpoint.field string to a ResolvedField.

        Bronze refs are always three-part: provider.endpoint.field.
        Provider IDs are single segments (chicago, alpha_vantage, cook_county).
        """
        if ref_str in self._cache:
            return self._cache[ref_str]

        if not self._built:
            self._build_index()

        provider_id, endpoint_id, field = self._parse_ref(ref_str)

        # Look up in index
        provider_eps = self._index.get(provider_id)
        if provider_eps is None:
            raise ValueError(
                f"Bronze provider '{provider_id}' not found. "
                f"Available: {sorted(self._known_providers)}"
            )

        ep_info = provider_eps.get(endpoint_id)
        if ep_info is None:
            raise ValueError(
                f"Bronze endpoint '{endpoint_id}' not found for provider '{provider_id}'. "
                f"Available: {sorted(provider_eps.keys())}"
            )

        if field not in ep_info.fields:
            raise ValueError(
                f"Field '{field}' not found in {provider_id}.{endpoint_id}. "
                f"Available: {sorted(ep_info.fields.keys())}"
            )

        # Build a FieldRef-compatible object for ResolvedField
        # Use provider_id as "domain" for handler compatibility
        ref = FieldRef.__new__(FieldRef)
        ref.raw = ref_str
        ref.domain = provider_id
        ref.field = f"{endpoint_id}.{field}"

        resolved = ResolvedField(
            ref=ref,
            table_name=endpoint_id,
            column=field,
            silver_path=ep_info.bronze_path,  # Reusing silver_path attr for bronze
            format_code=None,
        )
        self._cache[ref_str] = resolved
        return resolved

    def _parse_ref(self, ref_str: str) -> tuple[str, str, str]:
        """Parse a provider.endpoint.field reference into components.

        Uses known provider IDs for unambiguous splitting. Provider IDs
        may contain underscores (alpha_vantage, cook_county) but are
        always a single dot-separated segment.
        """
        if not self._built:
            self._build_index()

        # Try known providers first (handles underscore-containing IDs)
        for pid in self._known_providers:
            prefix = pid + "."
            if ref_str.startswith(prefix):
                remainder = ref_str[len(prefix):]
                parts = remainder.split(".", 1)
                if len(parts) == 2:
                    return pid, parts[0], parts[1]
                raise ValueError(
                    f"Invalid Bronze reference '{ref_str}' — expected "
                    f"'{pid}.endpoint.field' format"
                )

        # Fallback: split on first two dots
        parts = ref_str.split(".", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid Bronze reference '{ref_str}' — expected "
                "'provider.endpoint.field' format"
            )
        return parts[0], parts[1], parts[2]

    def reachable_domains(self, core_domains: set[str]) -> set[str]:
        """Pass-through — Bronze has no domain scoping."""
        return core_domains

    def find_join_path(
        self,
        src: str,
        dst: str,
        allowed_domains: set[str] | None = None,
    ) -> None:
        """Always returns None — Bronze has no join graph."""
        return None

    def get_endpoint_catalog(self) -> dict[str, dict]:
        """Return full Bronze endpoint catalog — used by GET /api/bronze/endpoints."""
        if not self._built:
            self._build_index()

        catalog: dict[str, dict] = {}
        for provider_id, endpoints in self._index.items():
            catalog[provider_id] = {
                "endpoints": {
                    ep_id: {
                        "ref": f"{provider_id}.{ep_id}",
                        "path": str(ep_info.bronze_path),
                        "fields": {
                            name: {"type": type_str}
                            for name, type_str in ep_info.fields.items()
                        },
                    }
                    for ep_id, ep_info in endpoints.items()
                }
            }
        return catalog
