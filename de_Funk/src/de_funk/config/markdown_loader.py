"""
Markdown Config Loader - Parse YAML frontmatter from markdown files.

This module provides a unified approach to configuration where documentation
and machine-readable config live in the same markdown files. This enables:
- Single source of truth (docs + config in one file)
- Obsidian compatibility (readable in vault)
- Schema definitions embedded in endpoint files
- Bronze table config embedded (replaces storage.json entries)

Directory Structure Expected:
    Data Sources/
    ├── Providers/
    │   └── Alpha Vantage.md
    └── Endpoints/
        └── Alpha Vantage/           # Subfolder structure is for browsing only
            ├── Core/
            │   └── Company Overview.md
            └── Prices/
                └── Time Series Daily.md

Usage:
    from de_funk.config.markdown_loader import MarkdownConfigLoader

    loader = MarkdownConfigLoader(repo_root)
    providers = loader.load_providers()
    endpoints = loader.load_endpoints(provider="Alpha Vantage")

    # Get combined config for a provider (like JSON format)
    config = loader.get_provider_config("alpha_vantage")
"""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SchemaField:
    """
    Parsed schema field from array format.

    Enhanced format supports options dict as 6th element:
    [name, type, source, nullable, description, {transform: "...", coerce: "...", expr: "..."}]

    Options:
        transform: String transform to apply (e.g., "zfill(10)", "to_date(yyyy-MM-dd)")
        coerce: Type coercion for source value (e.g., "double", "long")
        expr: Expression for computed fields (e.g., "(high + low + close) / 3")
        default: Default value if source is null
    """
    name: str
    type: str
    source: str
    nullable: bool = True
    description: str = ""
    # Options from enhanced format
    transform: Optional[str] = None
    coerce: Optional[str] = None
    expr: Optional[str] = None
    default: Optional[Any] = None

    @property
    def is_computed(self) -> bool:
        """Check if this field is computed (source is _computed or expr is set)."""
        return self.source == '_computed' or self.expr is not None

    @property
    def is_generated(self) -> bool:
        """Check if this field is generated (source is _generated)."""
        return self.source == '_generated'


@dataclass
class BronzeConfig:
    """Bronze layer configuration for an endpoint."""
    table: str
    partitions: List[str] = field(default_factory=list)
    write_strategy: str = "upsert"
    key_columns: List[str] = field(default_factory=list)
    date_column: Optional[str] = None
    comment: str = ""


@dataclass
class EndpointConfig:
    """Parsed endpoint configuration from markdown."""
    endpoint_id: str
    provider: str
    method: str = "GET"
    endpoint_pattern: str = ""
    format: str = "json"
    auth: str = "inherit"
    response_key: Optional[str] = None
    default_query: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)
    pagination_type: str = "none"
    schema: List[SchemaField] = field(default_factory=list)
    bronze: Optional[BronzeConfig] = None
    # Metadata
    domain: str = ""
    data_tags: List[str] = field(default_factory=list)
    status: str = "active"
    enabled: bool = True  # Set to false to skip during ingestion
    # View ID mapping for multi-year datasets (year -> view_id)
    view_ids: Dict[str, str] = field(default_factory=dict)
    # Download method: "json" (default API pagination) or "csv" (bulk download)
    download_method: str = "json"
    # JSON structure type for Spark JSON reading:
    #   "nested_map" - Keys are dates/IDs → values are objects (e.g., prices)
    #   "object" - Single flat object (e.g., company_overview)
    #   "array_reports" - Contains annualReports/quarterlyReports arrays (e.g., financials)
    #   "array" - Simple array of objects
    json_structure: str = "object"
    # Raw JSON schema for explicit Spark schema (avoids inference)
    # Format: list of [field_name, type] or [field_name, type, nullable]
    # Example: [["1. open", "string"], ["2. high", "string"]]
    raw_schema: List[List[Any]] = field(default_factory=list)
    # Raw config dict for additional fields
    raw: Dict[str, Any] = field(default_factory=dict)

    def get_spark_raw_schema(self):
        """
        Convert raw_schema to a Spark StructType for explicit JSON reading.

        Returns:
            StructType if raw_schema is defined, None otherwise
        """
        if not self.raw_schema:
            return None

        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, LongType,
            DoubleType, FloatType, BooleanType, DateType, TimestampType
        )

        type_mapping = {
            'string': StringType(),
            'int': IntegerType(),
            'integer': IntegerType(),
            'long': LongType(),
            'double': DoubleType(),
            'float': FloatType(),
            'boolean': BooleanType(),
            'bool': BooleanType(),
            'date': DateType(),
            'timestamp': TimestampType(),
        }

        fields = []
        for field_def in self.raw_schema:
            if len(field_def) >= 2:
                name = field_def[0]
                type_str = field_def[1].lower()
                nullable = field_def[2] if len(field_def) > 2 else True
                spark_type = type_mapping.get(type_str, StringType())
                fields.append(StructField(name, spark_type, nullable))

        return StructType(fields) if fields else None


@dataclass
class ProviderConfig:
    """Parsed provider configuration from markdown."""
    provider_id: str
    provider: str
    api_type: str = "rest"
    base_url: str = ""
    auth_model: str = "api-key"
    env_api_key: str = ""
    rate_limit_per_sec: float = 1.0
    default_headers: Dict[str, str] = field(default_factory=dict)
    models: List[str] = field(default_factory=list)
    # Metadata
    category: str = "public"
    data_domains: List[str] = field(default_factory=list)
    data_tags: List[str] = field(default_factory=list)
    status: str = "active"
    # Raw config dict for additional fields
    raw: Dict[str, Any] = field(default_factory=dict)


class MarkdownConfigLoader:
    """
    Load configuration from markdown files with YAML frontmatter.

    Provides recursive discovery of endpoints (folder structure is for
    human organization in Obsidian, not code logic).
    """

    def __init__(self, docs_path: Path):
        """
        Initialize the markdown config loader.

        Args:
            docs_path: Path to repo root directory (contains data_sources/)
        """
        self.docs_path = Path(docs_path)
        # Support both directory names
        ds = self.docs_path / "data_sources"
        if not ds.exists():
            ds = self.docs_path / "Data Sources"
        self.data_sources_path = ds
        self.providers_path = self.data_sources_path / "Providers"
        self.endpoints_path = self.data_sources_path / "Endpoints"
        self.models_path = self.docs_path / "Models"

        # Cache for loaded configs
        self._providers_cache: Optional[Dict[str, ProviderConfig]] = None
        self._endpoints_cache: Optional[Dict[str, EndpointConfig]] = None

    def parse_frontmatter(self, md_path: Path) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from a markdown file.

        Args:
            md_path: Path to markdown file

        Returns:
            Tuple of (frontmatter dict, body content)

        Raises:
            ValueError: If no valid frontmatter found
        """
        content = md_path.read_text(encoding='utf-8')

        # Match YAML frontmatter between --- markers
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', content, re.DOTALL)
        if not match:
            raise ValueError(f"No YAML frontmatter found in {md_path}")

        frontmatter_yaml = match.group(1)
        body = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_yaml) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in frontmatter of {md_path}: {e}")

        return frontmatter, body

    def parse_schema_block(self, body: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract schema from ```yaml code block in markdown body.

        Looks for a schema: key in any yaml code block.

        Args:
            body: Markdown body content

        Returns:
            List of schema field dicts, or None if not found
        """
        # Find yaml code blocks
        yaml_blocks = re.findall(r'```yaml\s*\n(.*?)```', body, re.DOTALL)

        for block in yaml_blocks:
            try:
                parsed = yaml.safe_load(block)
                if parsed and 'schema' in parsed:
                    return parsed['schema']
            except yaml.YAMLError:
                continue

        return None

    def parse_view_ids_table(self, body: str) -> Dict[str, str]:
        """
        Extract view_id mappings from markdown table.

        Parses tables with Year and view_id columns:
        | Year | view_id | Format | Notes |
        |------|---------|--------|-------|
        | 2026 | 6694-f78c | JSON | provisional |
        | 2025 | t59y-fr3k | JSON | provisional |

        Args:
            body: Markdown body content

        Returns:
            Dict mapping year (str) to view_id (str)
        """
        view_ids = {}

        # Find markdown table rows (| col1 | col2 | ...)
        # Skip header separator row (|---|---|)
        table_rows = re.findall(r'^\|\s*(\d{4})\s*\|\s*([a-z0-9-]+)\s*\|', body, re.MULTILINE)

        for year, view_id in table_rows:
            # Validate it looks like a Socrata 4x4 ID (xxxx-xxxx)
            if re.match(r'^[a-z0-9]{4}-[a-z0-9]{4}$', view_id):
                view_ids[year] = view_id
                logger.debug(f"Found view_id: {year} -> {view_id}")

        if view_ids:
            logger.info(f"Parsed {len(view_ids)} view_ids from markdown table")

        return view_ids

    def parse_schema_array(self, schema_list: List) -> List[SchemaField]:
        """
        Convert compact array schema to structured SchemaField objects.

        Basic format: [field_name, type, source_field, nullable, description]
        Enhanced format: [field_name, type, source_field, nullable, description, options_dict]

        Options dict can contain:
            - transform: String transform (e.g., "zfill(10)")
            - coerce: Type coercion (e.g., "double")
            - expr: Computed field expression
            - default: Default value

        Minimum: [field_name, type, source_field]

        Args:
            schema_list: List of schema field arrays

        Returns:
            List of SchemaField objects
        """
        fields = []
        for row in schema_list:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                logger.warning(f"Invalid schema row (need at least 3 elements): {row}")
                continue

            # Extract basic fields
            name = str(row[0])
            field_type = str(row[1])
            source = str(row[2])
            nullable = bool(row[3]) if len(row) > 3 else True
            description = str(row[4]) if len(row) > 4 else ""

            # Extract options dict if present (6th element)
            options = {}
            if len(row) > 5 and isinstance(row[5], dict):
                options = row[5]

            field = SchemaField(
                name=name,
                type=field_type,
                source=source,
                nullable=nullable,
                description=description,
                transform=options.get('transform'),
                coerce=options.get('coerce'),
                expr=options.get('expr'),
                default=options.get('default'),
            )
            fields.append(field)

        return fields

    def parse_bronze_config(self, frontmatter: Dict[str, Any]) -> Optional[BronzeConfig]:
        """
        Parse bronze layer configuration from frontmatter.

        Supports two formats:
        1. Flattened (v2.6+): bronze is table name, other props at top level
           bronze: income_statements
           partitions: [report_type]
           write_strategy: upsert
           key_columns: [...]

        2. Nested (legacy): bronze is dict with all properties
           bronze:
             table: income_statements
             partitions: [report_type]

        Args:
            frontmatter: Full frontmatter dict

        Returns:
            BronzeConfig object or None if not configured
        """
        bronze_value = frontmatter.get('bronze')
        if not bronze_value:
            return None

        # New flattened format: bronze is just the table name (string)
        if isinstance(bronze_value, str):
            return BronzeConfig(
                table=bronze_value,
                partitions=frontmatter.get('partitions', []) or [],
                write_strategy=frontmatter.get('write_strategy', 'upsert'),
                key_columns=frontmatter.get('key_columns', []) or [],
                date_column=frontmatter.get('date_column'),
                comment=frontmatter.get('comment', '')
            )

        # Legacy nested format: bronze is a dict
        if isinstance(bronze_value, dict):
            return BronzeConfig(
                table=bronze_value.get('table', ''),
                partitions=bronze_value.get('partitions', []) or [],
                write_strategy=bronze_value.get('write_strategy', 'upsert'),
                key_columns=bronze_value.get('key_columns', []) or [],
                date_column=bronze_value.get('date_column'),
                comment=bronze_value.get('comment', '')
            )

        return None

    def load_provider(self, md_path: Path) -> Optional[ProviderConfig]:
        """
        Load a single provider configuration from markdown.

        Args:
            md_path: Path to provider markdown file

        Returns:
            ProviderConfig or None if not a valid provider file
        """
        try:
            frontmatter, _ = self.parse_frontmatter(md_path)
        except ValueError as e:
            logger.warning(f"Could not parse {md_path}: {e}")
            return None

        if frontmatter.get('type') != 'api-provider':
            return None

        # Generate provider_id from filename if not specified
        provider_id = frontmatter.get(
            'provider_id',
            md_path.stem.lower().replace(' ', '_').replace('-', '_')
        )

        return ProviderConfig(
            provider_id=provider_id,
            provider=frontmatter.get('provider', md_path.stem),
            api_type=frontmatter.get('api_type', 'rest'),
            base_url=frontmatter.get('base_url', ''),
            auth_model=frontmatter.get('auth_model', 'api-key'),
            env_api_key=frontmatter.get('env_api_key', ''),
            rate_limit_per_sec=float(frontmatter.get('rate_limit_per_sec', 1.0)),
            default_headers=frontmatter.get('default_headers', {}) or {},
            models=frontmatter.get('models', []) or [],
            category=frontmatter.get('category', 'public'),
            data_domains=frontmatter.get('data_domains', []) or [],
            data_tags=frontmatter.get('data_tags', []) or [],
            status=frontmatter.get('status', 'active'),
            raw=frontmatter
        )

    def load_endpoint(self, md_path: Path) -> Optional[EndpointConfig]:
        """
        Load a single endpoint configuration from markdown.

        Args:
            md_path: Path to endpoint markdown file

        Returns:
            EndpointConfig or None if not a valid endpoint file
        """
        try:
            frontmatter, body = self.parse_frontmatter(md_path)
        except ValueError as e:
            logger.warning(f"Could not parse {md_path}: {e}")
            return None

        if frontmatter.get('type') != 'api-endpoint':
            return None

        # Generate endpoint_id from filename if not specified
        endpoint_id = frontmatter.get(
            'endpoint_id',
            md_path.stem.lower().replace(' ', '_').replace('-', '_')
        )

        # Parse schema - check frontmatter first (v2.6+), then body code block (legacy)
        schema_fields = []
        if 'schema' in frontmatter and frontmatter['schema']:
            # Schema in frontmatter (flattened format)
            schema_fields = self.parse_schema_array(frontmatter['schema'])
        else:
            # Fallback to schema in markdown code block (legacy)
            schema_list = self.parse_schema_block(body)
            if schema_list:
                schema_fields = self.parse_schema_array(schema_list)

        # Parse bronze config (supports both flattened and nested formats)
        bronze_config = self.parse_bronze_config(frontmatter)

        # Parse view_ids table if this endpoint requires view_id parameter
        required_params = frontmatter.get('required_params', []) or []
        view_ids = {}
        if 'view_id' in required_params:
            view_ids = self.parse_view_ids_table(body)

        return EndpointConfig(
            endpoint_id=endpoint_id,
            provider=frontmatter.get('provider', ''),
            method=frontmatter.get('method', 'GET'),
            endpoint_pattern=frontmatter.get('endpoint_pattern', ''),
            format=frontmatter.get('format', 'json'),
            auth=frontmatter.get('auth', 'inherit'),
            response_key=frontmatter.get('response_key'),
            default_query=frontmatter.get('default_query', {}) or {},
            required_params=required_params,
            pagination_type=frontmatter.get('pagination_type', 'none'),
            schema=schema_fields,
            bronze=bronze_config,
            domain=frontmatter.get('domain', ''),
            data_tags=frontmatter.get('data_tags', []) or [],
            status=frontmatter.get('status', 'active'),
            enabled=frontmatter.get('enabled', True),
            view_ids=view_ids,
            download_method=frontmatter.get('download_method', 'json'),
            json_structure=frontmatter.get('json_structure', 'object'),
            raw_schema=frontmatter.get('raw_schema', []) or [],
            raw=frontmatter
        )

    def load_providers(self, force_reload: bool = False) -> Dict[str, ProviderConfig]:
        """
        Load all provider configurations from markdown files.

        Args:
            force_reload: If True, bypass cache

        Returns:
            Dict mapping provider_id to ProviderConfig
        """
        if self._providers_cache is not None and not force_reload:
            return self._providers_cache

        providers = {}

        if not self.providers_path.exists():
            logger.debug(f"Providers path does not exist: {self.providers_path}")
            return providers

        for md_file in self.providers_path.glob("*.md"):
            if md_file.name.startswith('_'):
                continue  # Skip templates

            provider = self.load_provider(md_file)
            if provider:
                providers[provider.provider_id] = provider
                logger.debug(f"Loaded provider: {provider.provider_id} from {md_file.name}")

        self._providers_cache = providers
        return providers

    def load_endpoints(
        self,
        provider: Optional[str] = None,
        force_reload: bool = False
    ) -> Dict[str, EndpointConfig]:
        """
        Load all endpoint configurations recursively.

        Folder structure under Endpoints/ is for human organization only.
        Code searches recursively regardless of subfolder structure.

        Args:
            provider: Optional provider name to filter by
            force_reload: If True, bypass cache

        Returns:
            Dict mapping endpoint_id to EndpointConfig
        """
        if self._endpoints_cache is not None and not force_reload:
            endpoints = self._endpoints_cache
        else:
            endpoints = {}

            if not self.endpoints_path.exists():
                logger.debug(f"Endpoints path does not exist: {self.endpoints_path}")
                return endpoints

            # Recursive glob - folder structure doesn't matter
            for md_file in self.endpoints_path.rglob("*.md"):
                if md_file.name.startswith('_'):
                    continue  # Skip templates

                endpoint = self.load_endpoint(md_file)
                if endpoint:
                    if not endpoint.enabled:
                        logger.debug(f"Skipping disabled endpoint: {endpoint.endpoint_id}")
                        continue
                    endpoints[endpoint.endpoint_id] = endpoint
                    logger.debug(
                        f"Loaded endpoint: {endpoint.endpoint_id} "
                        f"(provider: {endpoint.provider}) from {md_file.name}"
                    )

            self._endpoints_cache = endpoints

        # Filter by provider if specified (match display name, slug, or bronze field)
        if provider:
            prov_lower = provider.lower()
            return {
                eid: ep for eid, ep in endpoints.items()
                if ep.provider == provider
                or ep.provider.lower().replace(' ', '_') == prov_lower
                or getattr(ep, 'bronze', '') == prov_lower
                or ep.provider.lower().replace(' ', '_').startswith(prov_lower)
            }

        return endpoints

    def get_provider_config(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Get combined provider config in format compatible with existing code.

        Combines provider settings with all its endpoints into a dict
        matching the structure of *_endpoints.json files.

        Args:
            provider_id: Provider identifier (e.g., 'alpha_vantage')

        Returns:
            Dict with base_urls, headers, rate_limit_per_sec, endpoints
        """
        providers = self.load_providers()

        # Try exact match first, then fuzzy match
        provider = providers.get(provider_id)
        if not provider:
            # Try matching by display name
            for pid, prov in providers.items():
                if prov.provider.lower().replace(' ', '_') == provider_id.lower():
                    provider = prov
                    break

        if not provider:
            return None

        # Load endpoints for this provider
        endpoints = self.load_endpoints(provider=provider.provider)

        # Build endpoints dict in JSON-compatible format
        endpoints_dict = {}
        for eid, ep in endpoints.items():
            endpoints_dict[eid] = {
                'base': 'core',
                'method': ep.method,
                'path_template': ep.endpoint_pattern,
                'required_params': ep.required_params,
                'default_query': ep.default_query,
                'response_key': ep.response_key,
                'default_path_params': {},
            }

        return {
            'base_urls': {'core': provider.base_url},
            'headers': provider.default_headers,
            'rate_limit_per_sec': provider.rate_limit_per_sec,
            'endpoints': endpoints_dict,
            # Additional fields from markdown
            'env_api_key': provider.env_api_key,
            'models': provider.models,
            'api_type': provider.api_type,
        }

    def get_bronze_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract all bronze table configurations from endpoints.

        Returns:
            Dict mapping table name to storage config (replaces storage.json entries)
        """
        bronze_configs = {}
        endpoints = self.load_endpoints()

        for eid, endpoint in endpoints.items():
            if endpoint.bronze and endpoint.bronze.table:
                bronze_configs[endpoint.bronze.table] = {
                    'root': 'bronze',
                    'rel': endpoint.bronze.table,
                    'partitions': endpoint.bronze.partitions,
                    'write_strategy': endpoint.bronze.write_strategy,
                    'key_columns': endpoint.bronze.key_columns,
                    'date_column': endpoint.bronze.date_column,
                    'comment': endpoint.bronze.comment or f"From endpoint: {eid}",
                    '_source_endpoint': eid,
                    '_source_provider': endpoint.provider,
                }

        return bronze_configs

    def get_endpoint_schema(self, endpoint_id: str) -> List[Dict[str, Any]]:
        """
        Get schema for an endpoint as list of dicts.

        Args:
            endpoint_id: Endpoint identifier

        Returns:
            List of field dicts with name, type, source, nullable, description,
            and optional transform, coerce, expr, default
        """
        endpoints = self.load_endpoints()
        endpoint = endpoints.get(endpoint_id)

        if not endpoint or not endpoint.schema:
            return []

        result = []
        for f in endpoint.schema:
            field_dict = {
                'name': f.name,
                'type': f.type,
                'source': f.source,
                'nullable': f.nullable,
                'description': f.description,
            }
            # Add optional fields if present
            if f.transform:
                field_dict['transform'] = f.transform
            if f.coerce:
                field_dict['coerce'] = f.coerce
            if f.expr:
                field_dict['expr'] = f.expr
            if f.default is not None:
                field_dict['default'] = f.default

            result.append(field_dict)

        return result

    def get_coercion_rules(self, endpoint_id: str) -> Dict[str, str]:
        """
        Get source field to type coercion rules for an endpoint.

        Returns a dict mapping source field names to their coercion type.
        This is derived from schema fields with coerce option set.

        Args:
            endpoint_id: Endpoint identifier

        Returns:
            Dict mapping source field name to coercion type (e.g., {'MarketCap': 'long'})
        """
        endpoints = self.load_endpoints()
        endpoint = endpoints.get(endpoint_id)

        if not endpoint or not endpoint.schema:
            return {}

        rules = {}
        for f in endpoint.schema:
            if f.coerce and f.source != '_computed' and f.source != '_generated':
                rules[f.source] = f.coerce

        return rules

    def get_field_mappings(self, endpoint_id: str) -> Dict[str, str]:
        """
        Get source field to output field name mappings for an endpoint.

        Returns a dict mapping source field names to output field names.

        Args:
            endpoint_id: Endpoint identifier

        Returns:
            Dict mapping source field name to output field name
        """
        endpoints = self.load_endpoints()
        endpoint = endpoints.get(endpoint_id)

        if not endpoint or not endpoint.schema:
            return {}

        mappings = {}
        for f in endpoint.schema:
            if f.source and f.source not in ('_computed', '_generated'):
                mappings[f.source] = f.name

        return mappings

    def get_computed_fields(self, endpoint_id: str) -> List[Dict[str, Any]]:
        """
        Get computed field definitions for an endpoint.

        Returns list of computed fields with their expressions.

        Args:
            endpoint_id: Endpoint identifier

        Returns:
            List of dicts with name, type, expr, and optional default
        """
        endpoints = self.load_endpoints()
        endpoint = endpoints.get(endpoint_id)

        if not endpoint or not endpoint.schema:
            return []

        computed = []
        for f in endpoint.schema:
            if f.is_computed and f.expr:
                computed.append({
                    'name': f.name,
                    'type': f.type,
                    'expr': f.expr,
                    'default': f.default,
                })

        return computed

    def clear_cache(self) -> None:
        """Clear all cached configurations."""
        self._providers_cache = None
        self._endpoints_cache = None


def get_markdown_loader(repo_root: Path) -> MarkdownConfigLoader:
    """
    Factory function to get a MarkdownConfigLoader for a repository.

    Args:
        repo_root: Repository root path

    Returns:
        MarkdownConfigLoader instance
    """
    return MarkdownConfigLoader(repo_root)
