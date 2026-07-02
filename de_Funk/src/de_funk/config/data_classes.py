"""
Typed data classes mirroring domain YAML frontmatter structure.

These dataclasses provide IDE completion, validation at parse time,
and documentation of every field in the YAML configs. They replace
raw Dict[str, Any] passing throughout the codebase.

Domain configs (from markdown):
    DomainModelConfig, TableConfig, SourceConfig, SchemaField,
    EdgeSpec, MeasureDef, AliasSpec, EnrichSpec, GraphSpec,
    BuildSpec, MeasuresSpec, HookDef, PipelineStep, HooksConfig,
    ModelStorageSpec, PhaseSpec, BaseTemplate

Provider configs (from data source markdown):
    ProviderConfig, EndpointConfig, EndpointSchemaField
"""
from __future__ import annotations
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional


# ── Atomic types ─────────────────────────────────────────

@dataclass
class SchemaField:
    """One column in a table schema. Parsed from [name, type, nullable, desc, {opts}]."""
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    derived: Optional[str] = None
    fk: Optional[str] = None
    format: Optional[str] = None

    @staticmethod
    def from_list(arr: list) -> SchemaField:
        """Parse from YAML array: [name, type, nullable, desc, {opts}]."""
        opts = arr[4] if len(arr) > 4 and isinstance(arr[4], dict) else {}
        return SchemaField(
            name=arr[0], type=arr[1],
            nullable=arr[2] if len(arr) > 2 else True,
            description=arr[3] if len(arr) > 3 else "",
            derived=opts.get("derived"),
            fk=opts.get("fk"),
            format=opts.get("format"),
        )


@dataclass
class EdgeSpec:
    """One graph edge. Parsed from [name, from, to, [keys], cardinality, domain, ...]."""
    name: str
    from_table: str
    to_table: str
    join_keys: list[str] = dc_field(default_factory=list)
    cardinality: str = "many_to_one"
    target_domain: Optional[str] = None
    optional: bool = False

    @staticmethod
    def from_list(arr: list) -> EdgeSpec:
        """Parse from YAML array: [name, from, to, [keys], cardinality, domain, {opts}]."""
        opts = arr[6] if len(arr) > 6 and isinstance(arr[6], dict) else {}
        return EdgeSpec(
            name=arr[0], from_table=arr[1], to_table=arr[2],
            join_keys=arr[3] if len(arr) > 3 else [],
            cardinality=arr[4] if len(arr) > 4 else "many_to_one",
            target_domain=arr[5] if len(arr) > 5 and not isinstance(arr[5], dict) else None,
            optional=opts.get("optional", False),
        )


@dataclass
class MeasureDef:
    """One measure definition. Parsed from [name, agg, field, label, {opts}]."""
    name: str
    aggregation: str
    field: str | dict = ""
    label: str = ""
    format: Optional[str] = None
    options: dict = dc_field(default_factory=dict)

    @staticmethod
    def from_list(arr: list) -> MeasureDef:
        """Parse from YAML array: [name, agg, field, label, {opts}]."""
        opts = arr[4] if len(arr) > 4 and isinstance(arr[4], dict) else {}
        return MeasureDef(
            name=arr[0], aggregation=arr[1],
            field=arr[2] if len(arr) > 2 else "",
            label=arr[3] if len(arr) > 3 else "",
            format=opts.get("format"),
            options=opts,
        )


@dataclass
class AliasSpec:
    """One source alias. Parsed from [target_column, expression]."""
    target_column: str
    expression: str

    @staticmethod
    def from_list(arr: list) -> AliasSpec:
        return AliasSpec(target_column=arr[0], expression=arr[1] if len(arr) > 1 else arr[0])


@dataclass
class EnrichSpec:
    """Join-based enrichment on a table."""
    from_table: str
    join: list[str] = dc_field(default_factory=list)
    columns: list[str] = dc_field(default_factory=list)


@dataclass
class HookDef:
    """One hook definition — references a Python function by dotted path."""
    fn: str
    params: dict = dc_field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> HookDef:
        return HookDef(fn=data.get("fn", ""), params=data.get("params", {}))


@dataclass
class PipelineStep:
    """One step in a config-driven pipeline."""
    op: str
    fn: Optional[str] = None
    params: dict = dc_field(default_factory=dict)


# ── Nested specs ─────────────────────────────────────────

@dataclass
class PhaseSpec:
    """One build phase — lists tables to build in this phase."""
    tables: list[str] = dc_field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> PhaseSpec:
        return PhaseSpec(tables=data.get("tables", []))


@dataclass
class ModelStorageSpec:
    """Storage configuration for a domain model."""
    format: str = "delta"
    silver_root: Optional[str] = None

    @staticmethod
    def from_dict(data: dict) -> ModelStorageSpec:
        silver = data.get("silver", {})
        return ModelStorageSpec(
            format=data.get("format", "delta"),
            silver_root=silver.get("root") if isinstance(silver, dict) else None,
        )


@dataclass
class BuildSpec:
    """Build configuration for a domain model."""
    sort_by: list[str] = dc_field(default_factory=list)
    optimize: bool = True
    partitions: list[str] = dc_field(default_factory=list)
    phases: dict[str, PhaseSpec] = dc_field(default_factory=dict)
    post_build: list[dict] = dc_field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> BuildSpec:
        phases = {}
        for k, v in data.get("phases", {}).items():
            phases[str(k)] = PhaseSpec.from_dict(v) if isinstance(v, dict) else PhaseSpec(tables=[])
        return BuildSpec(
            sort_by=data.get("sort_by", []),
            optimize=data.get("optimize", True),
            partitions=data.get("partitions", []),
            phases=phases,
            post_build=data.get("post_build", []),
        )


@dataclass
class GraphSpec:
    """Graph edges and paths for a domain model."""
    edges: list[EdgeSpec] = dc_field(default_factory=list)
    paths: dict[str, Any] = dc_field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> GraphSpec:
        edges = [EdgeSpec.from_list(e) if isinstance(e, list) else e for e in data.get("edges", [])]
        return GraphSpec(edges=edges, paths=data.get("paths", {}))


@dataclass
class MeasuresSpec:
    """Measure definitions for a domain model."""
    simple: list[MeasureDef] = dc_field(default_factory=list)
    computed: list[MeasureDef] = dc_field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> MeasuresSpec:
        simple = [MeasureDef.from_list(m) if isinstance(m, list) else m for m in data.get("simple", [])]
        computed = [MeasureDef.from_list(m) if isinstance(m, list) else m for m in data.get("computed", [])]
        return MeasuresSpec(simple=simple, computed=computed)


@dataclass
class HooksConfig:
    """Build hooks declared in YAML frontmatter."""
    pre_build: list[HookDef] = dc_field(default_factory=list)
    before_build: list[HookDef] = dc_field(default_factory=list)
    after_build: list[HookDef] = dc_field(default_factory=list)
    post_build: list[HookDef] = dc_field(default_factory=list)

    @staticmethod
    def from_dict(data: dict) -> HooksConfig:
        def _parse_hooks(arr: list) -> list[HookDef]:
            return [HookDef.from_dict(h) if isinstance(h, dict) else h for h in arr]
        return HooksConfig(
            pre_build=_parse_hooks(data.get("pre_build", [])),
            before_build=_parse_hooks(data.get("before_build", [])),
            after_build=_parse_hooks(data.get("after_build", [])),
            post_build=_parse_hooks(data.get("post_build", [])),
        )


# ── Config containers ────────────────────────────────────

@dataclass
class TableConfig:
    """Parsed from tables/*.md frontmatter."""
    table: str = ""
    table_type: str = "dimension"
    schema: list[SchemaField] = dc_field(default_factory=list)
    primary_key: list[str] = dc_field(default_factory=list)
    unique_key: list[str] = dc_field(default_factory=list)
    partition_by: list[str] = dc_field(default_factory=list)
    measures: list[MeasureDef] = dc_field(default_factory=list)
    enrich: list[EnrichSpec] = dc_field(default_factory=list)
    pipeline: list[PipelineStep] = dc_field(default_factory=list)
    extends: Optional[str] = None
    source_file: Optional[str] = None

    @staticmethod
    def from_dict(name: str, data: dict) -> TableConfig:
        schema = [SchemaField.from_list(s) if isinstance(s, list) else s for s in data.get("schema", [])]
        measures = [MeasureDef.from_list(m) if isinstance(m, list) else m for m in data.get("measures", [])]
        return TableConfig(
            table=name,
            table_type=data.get("table_type", data.get("type", "dimension")),
            schema=schema,
            primary_key=data.get("primary_key", []),
            unique_key=data.get("unique_key", []),
            partition_by=data.get("partition_by", data.get("partitions", [])),
            measures=measures,
            extends=data.get("extends"),
            source_file=data.get("_source_file"),
        )


@dataclass
class SourceConfig:
    """Parsed from sources/**/*.md frontmatter."""
    source: str = ""
    maps_to: str = ""
    from_ref: str = ""
    aliases: list[AliasSpec] = dc_field(default_factory=list)
    domain_source: Optional[str] = None
    filter: list[str] = dc_field(default_factory=list)
    discriminator: Optional[str] = None
    extends: Optional[str] = None
    source_file: Optional[str] = None

    @staticmethod
    def from_dict(name: str, data: dict) -> SourceConfig:
        aliases = [AliasSpec.from_list(a) if isinstance(a, list) else a for a in data.get("aliases", [])]
        return SourceConfig(
            source=name,
            maps_to=data.get("maps_to", ""),
            from_ref=data.get("from", ""),
            aliases=aliases,
            domain_source=data.get("domain_source"),
            filter=data.get("filter", []),
            discriminator=data.get("discriminator"),
            extends=data.get("extends"),
            source_file=data.get("_source_file"),
        )


@dataclass
class MLModelSpec:
    """ML model definition from YAML. Parsed from model.md ml_models: section."""
    name: str = ""
    type: str = ""              # arima, prophet, random_forest
    target: list[str] = dc_field(default_factory=list)
    features: list[str] = dc_field(default_factory=list)
    lookback_days: int = 90
    forecast_horizon: int = 7
    parameters: dict = dc_field(default_factory=dict)
    retrain_if_stale_days: int = 7
    enabled: bool = True

    @staticmethod
    def from_dict(name: str, data: dict) -> MLModelSpec:
        return MLModelSpec(
            name=name,
            type=data.get("type", ""),
            target=data.get("target", []),
            features=data.get("features", []),
            lookback_days=data.get("lookback_days", 90),
            forecast_horizon=data.get("forecast_horizon", 7),
            parameters=data.get("parameters", {}),
            retrain_if_stale_days=data.get("retrain_if_stale_days", 7),
            enabled=data.get("enabled", True),
        )


@dataclass
class DomainModelConfig:
    """Parsed from model.md frontmatter + auto-discovered tables/sources/views."""
    model: str = ""
    version: str = "1.0"
    description: str = ""
    extends: list[str] = dc_field(default_factory=list)
    depends_on: list[str] = dc_field(default_factory=list)
    status: str = "active"
    sources_from: Optional[str] = None

    storage: ModelStorageSpec = dc_field(default_factory=ModelStorageSpec)
    graph: GraphSpec = dc_field(default_factory=GraphSpec)
    build: BuildSpec = dc_field(default_factory=BuildSpec)
    measures: MeasuresSpec = dc_field(default_factory=MeasuresSpec)
    hooks: HooksConfig = dc_field(default_factory=HooksConfig)
    ml_models: dict[str, MLModelSpec] = dc_field(default_factory=dict)
    metadata: dict = dc_field(default_factory=dict)

    tables: dict[str, TableConfig] = dc_field(default_factory=dict)
    sources: dict[str, SourceConfig] = dc_field(default_factory=dict)
    views: dict[str, Any] = dc_field(default_factory=dict)

    # Raw dict preserved for backward compat during migration
    _raw: dict = dc_field(default_factory=dict, repr=False)
    source_file: Optional[str] = None

    @staticmethod
    def from_dict(data: dict) -> DomainModelConfig:
        """Convert raw YAML dict to typed DomainModelConfig.

        Parses all nested structures (tables, sources, edges, measures, hooks)
        into their typed dataclass equivalents. Preserves the raw dict in _raw
        for backward compatibility during the migration period.
        """
        # Parse extends (can be string or list)
        extends = data.get("extends", [])
        if isinstance(extends, str):
            extends = [extends] if extends else []

        # Parse tables
        tables = {}
        for name, tdata in data.get("tables", {}).items():
            if isinstance(tdata, dict):
                tables[name] = TableConfig.from_dict(name, tdata)

        # Parse sources
        sources = {}
        for name, sdata in data.get("sources", {}).items():
            if isinstance(sdata, dict):
                sources[name] = SourceConfig.from_dict(name, sdata)

        # Parse ml_models
        ml_models = {}
        for name, mdata in data.get("ml_models", {}).items():
            if isinstance(mdata, dict):
                ml_models[name] = MLModelSpec.from_dict(name, mdata)

        return DomainModelConfig(
            model=data.get("model", ""),
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            extends=extends,
            depends_on=data.get("depends_on", []),
            status=data.get("status", "active"),
            sources_from=data.get("sources_from"),
            storage=ModelStorageSpec.from_dict(data.get("storage", {})),
            graph=GraphSpec.from_dict(data.get("graph", {})),
            build=BuildSpec.from_dict(data.get("build", {})),
            measures=MeasuresSpec.from_dict(data.get("measures", {})),
            hooks=HooksConfig.from_dict(data.get("hooks", {})),
            ml_models=ml_models,
            metadata=data.get("metadata", {}),
            tables=tables,
            sources=sources,
            views=data.get("views", {}),
            _raw=data,
            source_file=data.get("_source_file"),
        )


@dataclass
class BaseTemplate:
    """Reusable base template from domains/_base/."""
    type: str = "domain-base"
    model: str = ""
    version: str = "1.0"
    description: str = ""
    extends: Optional[str] = None
    canonical_fields: list[SchemaField] = dc_field(default_factory=list)
    tables: dict[str, TableConfig] = dc_field(default_factory=dict)
    depends_on: list[str] = dc_field(default_factory=list)
    source_file: Optional[str] = None


# ── Provider / Endpoint configs ──────────────────────────

@dataclass
class EndpointSchemaField:
    """One field in an endpoint schema — different from domain SchemaField."""
    name: str = ""
    type: str = "string"
    source_field: str = ""
    nullable: bool = True
    description: str = ""
    transform: Optional[str] = None
    coerce: Optional[str] = None
    default: Optional[Any] = None


@dataclass
class EndpointConfig:
    """Parsed from Endpoints/**/*.md frontmatter."""
    endpoint_id: str = ""
    provider: str = ""
    method: str = "GET"
    endpoint_pattern: str = ""
    format: str = "json"
    auth: str = "inherit"
    response_key: Optional[str] = None
    default_query: dict = dc_field(default_factory=dict)
    required_params: list[str] = dc_field(default_factory=list)
    pagination_type: str = "none"
    bulk_download: bool = False
    download_method: str = "json"
    json_structure: str = "object"
    raw_schema: list[list] = dc_field(default_factory=list)
    schema: list[EndpointSchemaField] = dc_field(default_factory=list)
    bronze: Optional[str] = None
    partitions: list[str] = dc_field(default_factory=list)
    write_strategy: str = "upsert"
    key_columns: list[str] = dc_field(default_factory=list)
    date_column: Optional[str] = None
    domain: str = ""
    data_tags: list[str] = dc_field(default_factory=list)
    status: str = "active"
    update_cadence: str = ""
    source_file: Optional[str] = None


@dataclass
class ProviderConfig:
    """Parsed from Providers/*.md frontmatter."""
    provider_id: str = ""
    provider: str = ""
    api_type: str = "rest"
    base_url: str = ""
    auth_model: str = "api-key"
    env_api_key: str = ""
    rate_limit_per_sec: float = 1.0
    default_headers: dict = dc_field(default_factory=dict)
    provider_settings: dict = dc_field(default_factory=dict)
    endpoints: list[str] = dc_field(default_factory=list)
    models: list[str] = dc_field(default_factory=list)
    category: str = "public"
    data_domains: list[str] = dc_field(default_factory=list)
    data_tags: list[str] = dc_field(default_factory=list)
    status: str = "active"
    source_file: Optional[str] = None


# ── Infrastructure data classes ──────────────────────────
# Typed replacements for raw dicts from storage.json / run_config.json.

@dataclass
class RootsConfig:
    """Storage mount points for each data tier."""
    raw: str = "storage/raw"
    bronze: str = "storage/bronze"
    silver: str = "storage/silver"
    models: str = "storage/models"

    @staticmethod
    def from_dict(data: dict) -> RootsConfig:
        return RootsConfig(
            raw=data.get("raw", "storage/raw"),
            bronze=data.get("bronze", "storage/bronze"),
            silver=data.get("silver", "storage/silver"),
            models=data.get("models", "storage/models"),
        )


@dataclass
class ApiLimits:
    """Query limits for the API layer."""
    duckdb_memory_limit: str = "3GB"
    max_sql_rows: int = 30000
    max_dimension_values: int = 10000
    max_response_mb: float = 4.0

    @staticmethod
    def from_dict(data: dict) -> ApiLimits:
        return ApiLimits(
            duckdb_memory_limit=data.get("duckdb_memory_limit", "3GB"),
            max_sql_rows=data.get("max_sql_rows", 30000),
            max_dimension_values=data.get("max_dimension_values", 10000),
            max_response_mb=data.get("max_response_mb", 4.0),
        )


@dataclass
class TablePath:
    """Storage path for one table (root tier + relative path)."""
    root: str = "silver"
    rel: str = ""
    partitions: list[str] = dc_field(default_factory=list)

    @property
    def full_path(self) -> str:
        return f"{self.root}/{self.rel}" if self.rel else self.root

    @staticmethod
    def from_dict(data: dict) -> TablePath:
        return TablePath(
            root=data.get("root", "silver"),
            rel=data.get("rel", ""),
            partitions=data.get("partitions", []),
        )


@dataclass
class ClusterConfig:
    """Spark cluster settings from run_config.json."""
    spark_master: str = "auto"
    fallback_to_local: bool = True
    task_batch_size: int = 50

    @staticmethod
    def from_dict(data: dict) -> ClusterConfig:
        return ClusterConfig(
            spark_master=data.get("spark_master", "auto"),
            fallback_to_local=data.get("fallback_to_local", True),
            task_batch_size=data.get("task_batch_size", 50),
        )


@dataclass
class RetryConfig:
    """Retry policy from run_config.json."""
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    exponential_backoff: bool = True

    @staticmethod
    def from_dict(data: dict) -> RetryConfig:
        return RetryConfig(
            max_retries=data.get("max_retries", 3),
            retry_delay_seconds=data.get("retry_delay_seconds", 2.0),
            exponential_backoff=data.get("exponential_backoff", True),
        )


@dataclass
class RunConfig:
    """Pipeline run configuration from run_config.json."""
    defaults: dict = dc_field(default_factory=dict)
    providers: dict[str, dict] = dc_field(default_factory=dict)
    silver_models: list[str] = dc_field(default_factory=list)
    cluster: ClusterConfig = dc_field(default_factory=ClusterConfig)
    retry: RetryConfig = dc_field(default_factory=RetryConfig)
    profiles: dict[str, dict] = dc_field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict) -> RunConfig:
        silver = data.get("silver_models", {})
        return RunConfig(
            defaults=data.get("defaults", {}),
            providers=data.get("providers", {}),
            silver_models=silver.get("models", []) if isinstance(silver, dict) else silver,
            cluster=ClusterConfig.from_dict(data.get("cluster", {})),
            retry=RetryConfig.from_dict(data.get("retry", {})),
            profiles=data.get("profiles", {}),
        )
