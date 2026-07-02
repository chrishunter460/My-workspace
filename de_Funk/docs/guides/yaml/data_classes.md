---
type: reference
description: "Complete reference for all typed data classes — maps 1:1 to YAML frontmatter"
---

# Data Classes Reference

> Every dataclass in `config/data_classes.py` mirrors a YAML frontmatter section. This is the typed Python representation of your markdown configs.

## Quick Reference

| Data Class | YAML Section | Used In |
|---|---|---|
| `SchemaField` | `schema: [...] entries` | Table files |
| `EdgeSpec` | `graph.edges: [...] entries` | model.md |
| `MeasureDef` | `measures: [...] entries` | model.md, table files |
| `AliasSpec` | `aliases: [...] entries` | Source files |
| `EnrichSpec` | `build.post_build.columns` | model.md |
| `HookDef` | `hooks.{phase}: [...] entries` | model.md |
| `PipelineStep` | `build.post_build: [...] entries` | model.md |
| `PhaseSpec` | `build.phases: {n: ...}` | model.md |
| `ModelStorageSpec` | `storage: {...}` | model.md |
| `BuildSpec` | `build: {...}` | model.md |
| `GraphSpec` | `graph: {...}` | model.md |
| `MeasuresSpec` | `measures: {...}` | model.md |
| `HooksConfig` | `hooks: {...}` | model.md |
| `TableConfig` | `Entire table file frontmatter` | tables/*.md |
| `SourceConfig` | `Entire source file frontmatter` | sources/*.md |
| `MLModelSpec` | `ml_models: {...} entries` | model.md |
| `DomainModelConfig` | `Entire model.md frontmatter` | model.md |
| `BaseTemplate` | `Entire _base/*.md frontmatter` | domains/_base/ |
| `EndpointSchemaField` | `schema: [...] entries` | Endpoint files |
| `EndpointConfig` | `Entire endpoint frontmatter` | Endpoints/*.md |
| `ProviderConfig` | `Entire provider frontmatter` | Providers/*.md |
| `RootsConfig` | `roots: {...}` | storage.json |
| `ApiLimits` | `api: {...}` | storage.json |
| `TablePath` | `tables: {...} entries` | storage.json |
| `ClusterConfig` | `cluster: {...}` | run_config.json |
| `RetryConfig` | `retry: {...}` | run_config.json |
| `RunConfig` | `Entire run_config.json` | run_config.json |

## Detailed Reference

### SchemaField

> One column in a table schema. Parsed from [name, type, nullable, desc, {opts}].

**YAML Section**: `schema: [...] entries`
**Used In**: Table files

| Field | Type | Default |
|---|---|---|
| `name` | `str` | — |
| `type` | `str` | — |
| `nullable` | `bool` | `True` |
| `description` | `str` | `''` |
| `derived` | `Optional[str]` | `None` |
| `fk` | `Optional[str]` | `None` |
| `format` | `Optional[str]` | `None` |

**YAML Example**:


### EdgeSpec

> One graph edge. Parsed from [name, from, to, [keys], cardinality, domain, ...].

**YAML Section**: `graph.edges: [...] entries`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `name` | `str` | — |
| `from_table` | `str` | — |
| `to_table` | `str` | — |
| `join_keys` | `list[str]` | `dc_field(default_factory=list)` |
| `cardinality` | `str` | `'many_to_one'` |
| `target_domain` | `Optional[str]` | `None` |
| `optional` | `bool` | `False` |

**YAML Example**:


### MeasureDef

> One measure definition. Parsed from [name, agg, field, label, {opts}].

**YAML Section**: `measures: [...] entries`
**Used In**: model.md, table files

| Field | Type | Default |
|---|---|---|
| `name` | `str` | — |
| `aggregation` | `str` | — |
| `field` | `str | dict` | `''` |
| `label` | `str` | `''` |
| `format` | `Optional[str]` | `None` |
| `options` | `dict` | `dc_field(default_factory=dict)` |

**YAML Example**:


### AliasSpec

> One source alias. Parsed from [target_column, expression].

**YAML Section**: `aliases: [...] entries`
**Used In**: Source files

| Field | Type | Default |
|---|---|---|
| `target_column` | `str` | — |
| `expression` | `str` | — |

**YAML Example**:


### EnrichSpec

> Join-based enrichment on a table.

**YAML Section**: `build.post_build.columns`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `from_table` | `str` | — |
| `join` | `list[str]` | `dc_field(default_factory=list)` |
| `columns` | `list[str]` | `dc_field(default_factory=list)` |

**YAML Example**:


### HookDef

> One hook definition — references a Python function by dotted path.

**YAML Section**: `hooks.{phase}: [...] entries`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `fn` | `str` | — |
| `params` | `dict` | `dc_field(default_factory=dict)` |

**YAML Example**:


### PipelineStep

> One step in a config-driven pipeline.

**YAML Section**: `build.post_build: [...] entries`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `op` | `str` | — |
| `fn` | `Optional[str]` | `None` |
| `params` | `dict` | `dc_field(default_factory=dict)` |

**YAML Example**:


### PhaseSpec

> One build phase — lists tables to build in this phase.

**YAML Section**: `build.phases: {n: ...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `tables` | `list[str]` | `dc_field(default_factory=list)` |

**YAML Example**:


### ModelStorageSpec

> Storage configuration for a domain model.

**YAML Section**: `storage: {...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `format` | `str` | `'delta'` |
| `silver_root` | `Optional[str]` | `None` |

**YAML Example**:


### BuildSpec

> Build configuration for a domain model.

**YAML Section**: `build: {...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `sort_by` | `list[str]` | `dc_field(default_factory=list)` |
| `optimize` | `bool` | `True` |
| `partitions` | `list[str]` | `dc_field(default_factory=list)` |
| `phases` | `dict[str, PhaseSpec]` | `dc_field(default_factory=dict)` |

**YAML Example**:


### GraphSpec

> Graph edges and paths for a domain model.

**YAML Section**: `graph: {...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `edges` | `list[EdgeSpec]` | `dc_field(default_factory=list)` |
| `paths` | `dict[str, Any]` | `dc_field(default_factory=dict)` |

**YAML Example**:


### MeasuresSpec

> Measure definitions for a domain model.

**YAML Section**: `measures: {...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `simple` | `list[MeasureDef]` | `dc_field(default_factory=list)` |
| `computed` | `list[MeasureDef]` | `dc_field(default_factory=list)` |

**YAML Example**:


### HooksConfig

> Build hooks declared in YAML frontmatter.

**YAML Section**: `hooks: {...}`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `pre_build` | `list[HookDef]` | `dc_field(default_factory=list)` |
| `before_build` | `list[HookDef]` | `dc_field(default_factory=list)` |
| `after_build` | `list[HookDef]` | `dc_field(default_factory=list)` |
| `post_build` | `list[HookDef]` | `dc_field(default_factory=list)` |

**YAML Example**:


### TableConfig

> Parsed from tables/*.md frontmatter.

**YAML Section**: `Entire table file frontmatter`
**Used In**: tables/*.md

| Field | Type | Default |
|---|---|---|
| `table` | `str` | `''` |
| `table_type` | `str` | `'dimension'` |
| `schema` | `list[SchemaField]` | `dc_field(default_factory=list)` |
| `primary_key` | `list[str]` | `dc_field(default_factory=list)` |
| `unique_key` | `list[str]` | `dc_field(default_factory=list)` |
| `partition_by` | `list[str]` | `dc_field(default_factory=list)` |
| `measures` | `list[MeasureDef]` | `dc_field(default_factory=list)` |
| `enrich` | `list[EnrichSpec]` | `dc_field(default_factory=list)` |
| `pipeline` | `list[PipelineStep]` | `dc_field(default_factory=list)` |
| `extends` | `Optional[str]` | `None` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### SourceConfig

> Parsed from sources/**/*.md frontmatter.

**YAML Section**: `Entire source file frontmatter`
**Used In**: sources/*.md

| Field | Type | Default |
|---|---|---|
| `source` | `str` | `''` |
| `maps_to` | `str` | `''` |
| `from_ref` | `str` | `''` |
| `aliases` | `list[AliasSpec]` | `dc_field(default_factory=list)` |
| `domain_source` | `Optional[str]` | `None` |
| `filter` | `list[str]` | `dc_field(default_factory=list)` |
| `discriminator` | `Optional[str]` | `None` |
| `extends` | `Optional[str]` | `None` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### MLModelSpec

> ML model definition from YAML. Parsed from model.md ml_models: section.

**YAML Section**: `ml_models: {...} entries`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `name` | `str` | `''` |
| `type` | `str` | `''` |
| `target` | `list[str]` | `dc_field(default_factory=list)` |
| `features` | `list[str]` | `dc_field(default_factory=list)` |
| `lookback_days` | `int` | `90` |
| `forecast_horizon` | `int` | `7` |
| `parameters` | `dict` | `dc_field(default_factory=dict)` |
| `retrain_if_stale_days` | `int` | `7` |
| `enabled` | `bool` | `True` |

**YAML Example**:


### DomainModelConfig

> Parsed from model.md frontmatter + auto-discovered tables/sources/views.

**YAML Section**: `Entire model.md frontmatter`
**Used In**: model.md

| Field | Type | Default |
|---|---|---|
| `model` | `str` | `''` |
| `version` | `str` | `'1.0'` |
| `description` | `str` | `''` |
| `extends` | `list[str]` | `dc_field(default_factory=list)` |
| `depends_on` | `list[str]` | `dc_field(default_factory=list)` |
| `status` | `str` | `'active'` |
| `sources_from` | `Optional[str]` | `None` |
| `storage` | `ModelStorageSpec` | `dc_field(default_factory=ModelStorageSpec)` |
| `graph` | `GraphSpec` | `dc_field(default_factory=GraphSpec)` |
| `build` | `BuildSpec` | `dc_field(default_factory=BuildSpec)` |
| `measures` | `MeasuresSpec` | `dc_field(default_factory=MeasuresSpec)` |
| `hooks` | `HooksConfig` | `dc_field(default_factory=HooksConfig)` |
| `ml_models` | `dict[str, MLModelSpec]` | `dc_field(default_factory=dict)` |
| `metadata` | `dict` | `dc_field(default_factory=dict)` |
| `tables` | `dict[str, TableConfig]` | `dc_field(default_factory=dict)` |
| `sources` | `dict[str, SourceConfig]` | `dc_field(default_factory=dict)` |
| `views` | `dict[str, Any]` | `dc_field(default_factory=dict)` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### BaseTemplate

> Reusable base template from domains/_base/.

**YAML Section**: `Entire _base/*.md frontmatter`
**Used In**: domains/_base/

| Field | Type | Default |
|---|---|---|
| `type` | `str` | `'domain-base'` |
| `model` | `str` | `''` |
| `version` | `str` | `'1.0'` |
| `description` | `str` | `''` |
| `extends` | `Optional[str]` | `None` |
| `canonical_fields` | `list[SchemaField]` | `dc_field(default_factory=list)` |
| `tables` | `dict[str, TableConfig]` | `dc_field(default_factory=dict)` |
| `depends_on` | `list[str]` | `dc_field(default_factory=list)` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### EndpointSchemaField

> One field in an endpoint schema — different from domain SchemaField.

**YAML Section**: `schema: [...] entries`
**Used In**: Endpoint files

| Field | Type | Default |
|---|---|---|
| `name` | `str` | `''` |
| `type` | `str` | `'string'` |
| `source_field` | `str` | `''` |
| `nullable` | `bool` | `True` |
| `description` | `str` | `''` |
| `transform` | `Optional[str]` | `None` |
| `coerce` | `Optional[str]` | `None` |
| `default` | `Optional[Any]` | `None` |

**YAML Example**:


### EndpointConfig

> Parsed from Endpoints/**/*.md frontmatter.

**YAML Section**: `Entire endpoint frontmatter`
**Used In**: Endpoints/*.md

| Field | Type | Default |
|---|---|---|
| `endpoint_id` | `str` | `''` |
| `provider` | `str` | `''` |
| `method` | `str` | `'GET'` |
| `endpoint_pattern` | `str` | `''` |
| `format` | `str` | `'json'` |
| `auth` | `str` | `'inherit'` |
| `response_key` | `Optional[str]` | `None` |
| `default_query` | `dict` | `dc_field(default_factory=dict)` |
| `required_params` | `list[str]` | `dc_field(default_factory=list)` |
| `pagination_type` | `str` | `'none'` |
| `bulk_download` | `bool` | `False` |
| `download_method` | `str` | `'json'` |
| `json_structure` | `str` | `'object'` |
| `raw_schema` | `list[list]` | `dc_field(default_factory=list)` |
| `schema` | `list[EndpointSchemaField]` | `dc_field(default_factory=list)` |
| `bronze` | `Optional[str]` | `None` |
| `partitions` | `list[str]` | `dc_field(default_factory=list)` |
| `write_strategy` | `str` | `'upsert'` |
| `key_columns` | `list[str]` | `dc_field(default_factory=list)` |
| `date_column` | `Optional[str]` | `None` |
| `domain` | `str` | `''` |
| `data_tags` | `list[str]` | `dc_field(default_factory=list)` |
| `status` | `str` | `'active'` |
| `update_cadence` | `str` | `''` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### ProviderConfig

> Parsed from Providers/*.md frontmatter.

**YAML Section**: `Entire provider frontmatter`
**Used In**: Providers/*.md

| Field | Type | Default |
|---|---|---|
| `provider_id` | `str` | `''` |
| `provider` | `str` | `''` |
| `api_type` | `str` | `'rest'` |
| `base_url` | `str` | `''` |
| `auth_model` | `str` | `'api-key'` |
| `env_api_key` | `str` | `''` |
| `rate_limit_per_sec` | `float` | `1.0` |
| `default_headers` | `dict` | `dc_field(default_factory=dict)` |
| `provider_settings` | `dict` | `dc_field(default_factory=dict)` |
| `endpoints` | `list[str]` | `dc_field(default_factory=list)` |
| `models` | `list[str]` | `dc_field(default_factory=list)` |
| `category` | `str` | `'public'` |
| `data_domains` | `list[str]` | `dc_field(default_factory=list)` |
| `data_tags` | `list[str]` | `dc_field(default_factory=list)` |
| `status` | `str` | `'active'` |
| `source_file` | `Optional[str]` | `None` |

**YAML Example**:


### RootsConfig

> Storage mount points for each data tier.

**YAML Section**: `roots: {...}`
**Used In**: storage.json

| Field | Type | Default |
|---|---|---|
| `raw` | `str` | `'storage/raw'` |
| `bronze` | `str` | `'storage/bronze'` |
| `silver` | `str` | `'storage/silver'` |
| `models` | `str` | `'storage/models'` |

**YAML Example**:


### ApiLimits

> Query limits for the API layer.

**YAML Section**: `api: {...}`
**Used In**: storage.json

| Field | Type | Default |
|---|---|---|
| `duckdb_memory_limit` | `str` | `'3GB'` |
| `max_sql_rows` | `int` | `30000` |
| `max_dimension_values` | `int` | `10000` |
| `max_response_mb` | `float` | `4.0` |

**YAML Example**:


### TablePath

> Storage path for one table (root tier + relative path).

**YAML Section**: `tables: {...} entries`
**Used In**: storage.json

| Field | Type | Default |
|---|---|---|
| `root` | `str` | `'silver'` |
| `rel` | `str` | `''` |
| `partitions` | `list[str]` | `dc_field(default_factory=list)` |

**YAML Example**:


### ClusterConfig

> Spark cluster settings from run_config.json.

**YAML Section**: `cluster: {...}`
**Used In**: run_config.json

| Field | Type | Default |
|---|---|---|
| `spark_master` | `str` | `'auto'` |
| `fallback_to_local` | `bool` | `True` |
| `task_batch_size` | `int` | `50` |

**YAML Example**:


### RetryConfig

> Retry policy from run_config.json.

**YAML Section**: `retry: {...}`
**Used In**: run_config.json

| Field | Type | Default |
|---|---|---|
| `max_retries` | `int` | `3` |
| `retry_delay_seconds` | `float` | `2.0` |
| `exponential_backoff` | `bool` | `True` |

**YAML Example**:


### RunConfig

> Pipeline run configuration from run_config.json.

**YAML Section**: `Entire run_config.json`
**Used In**: run_config.json

| Field | Type | Default |
|---|---|---|
| `defaults` | `dict` | `dc_field(default_factory=dict)` |
| `providers` | `dict[str, dict]` | `dc_field(default_factory=dict)` |
| `silver_models` | `list[str]` | `dc_field(default_factory=list)` |
| `cluster` | `ClusterConfig` | `dc_field(default_factory=ClusterConfig)` |
| `retry` | `RetryConfig` | `dc_field(default_factory=RetryConfig)` |
| `profiles` | `dict[str, dict]` | `dc_field(default_factory=dict)` |

**YAML Example**:


