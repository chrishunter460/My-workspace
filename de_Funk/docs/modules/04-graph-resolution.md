---
title: "Graph & Field Resolution"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/core/graph.py
  - src/de_funk/api/resolver.py
  - src/de_funk/api/bronze_resolver.py
---

# Graph & Field Resolution

> DomainGraph (BFS join paths), FieldResolver (domain.field -> table.column), and BronzeResolver.

## Purpose & Design Decisions

### What Problem This Solves

Users write queries using logical names like `securities.stocks.adjusted_close` or `corporate.finance.revenue`. The system must translate these to physical Silver table paths (`/shared/storage/silver/securities/stocks/facts/fact_daily_price`) and column names (`adjusted_close`), then automatically join tables when a query spans multiple tables (e.g., selecting `ticker` from `dim_stock` and `adjusted_close` from `fact_daily_price`).

This group solves three problems:

1. **Field resolution** (`FieldResolver`): Maps `domain.field` references to `(table_name, column, silver_path)` by scanning domain model markdown files and building a field index.
2. **Join path finding** (`DomainGraph` + `FieldResolver._join_graph`): Uses BFS over a bidirectional graph of EdgeSpec relationships to find the shortest join path between any two Silver tables, enabling automatic JOIN clause generation.
3. **Domain scoping**: Restricts BFS traversal to tables within allowed domains, preventing cross-domain joins that would produce incorrect results (e.g., municipal transit data accidentally joining to securities data via a shared `dim_calendar`).

`BronzeResolver` provides the same interface for Bronze (raw ingested) data, using `provider.endpoint.field` references instead of domain references.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| BFS (breadth-first search) for join paths | Guarantees shortest path (fewest JOINs), which produces the most efficient SQL. Graph is small enough (tens to low hundreds of tables) that BFS is instant. | Dijkstra with weighted edges; rejected because all edges have equal cost (one JOIN hop). |
| Longest-prefix domain matching in `FieldRef` | Dotted domain names like `corporate.finance` cannot be split on the first dot. `FieldRef._match_domain()` tries all known domain prefixes and picks the longest match, ensuring `corporate.finance.revenue` resolves to domain `corporate.finance`, field `revenue`. | First-dot split; kept as fallback before index is built, but fails for multi-segment domain names. |
| Lazy index building (`_built` flag) | The index scan reads every `*.md` file under `domains/models/`. Deferring this to first use avoids startup cost when the resolver is created but never called (e.g., build-only scripts). | Eager build in `__init__`; rejected because `DeFunk.from_app_config()` always creates a resolver even when only build sessions are used. |
| Bidirectional edges in the join graph | Queries may need to traverse from fact to dimension or dimension to fact. Storing both directions lets BFS find paths regardless of which table is the "source" and which is the "target". | Directed edges only; rejected because `fact_daily_price -> dim_stock` and `dim_stock -> fact_daily_price` are both valid join directions. |
| BronzeResolver returns `None` for `find_join_path()` | Bronze tables are single-table (no star schema), so there are no joins. Returning `None` signals to DuckDBSql that a CROSS JOIN or single-table scan is needed. | Raise an error; rejected because handlers check the return value and adapt their SQL generation. |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Join graph edges | `graph.edges` list in model.md frontmatter | `domains/models/*/model.md` |
| Domain dependencies (scoping) | `depends_on` list in model.md frontmatter | `domains/models/*/model.md` |
| Field-to-table mapping | `schema:` arrays in table markdown files | `domains/models/*/tables/*.md` |
| Table type -> subdirectory (`dims/`, `facts/`) | `table_type: dimension` or `table_type: fact` in table frontmatter | `domains/models/*/tables/*.md` |
| Per-domain silver path overrides | `domain_roots` dict passed to FieldResolver | `configs/storage.json` > `domain_roots` |
| Temporal field mapping | Hardcoded `_MAP` in `_resolve_temporal()` | `src/de_funk/api/resolver.py` (Python escape hatch) |
| Bronze endpoint discovery | `type: api-endpoint` + `schema:` + `bronze:` in endpoint frontmatter | `Data Sources/Endpoints/**/*.md` |

## Architecture

### Where This Fits

```
[domains/models/**/*.md]                    [Data Sources/Endpoints/**/*.md]
        |                                              |
        v                                              v
   FieldResolver._build_index()               BronzeResolver._build_index()
        |                                              |
        v                                              v
   FieldResolver.resolve("domain.field")      BronzeResolver.resolve("provider.endpoint.field")
        |                                              |
        +---> ResolvedField (table, column, path) <----+
                      |
                      v
              DuckDBSql.build_from()   <--- uses FieldResolver.find_join_path()
              DuckDBSql.build_where()  <--- uses FieldResolver.resolve()
                      |
                      v
                 Generated SQL
```

`DomainGraph` is built separately by `DeFunk` from all model configs and held at the app level. `FieldResolver` builds its own parallel join graph (`_join_graph`) by scanning model.md files directly. Both use BFS over bidirectional adjacency lists. The `DomainGraph` is used by `BuildSession` for dependency resolution; `FieldResolver._join_graph` is used by `DuckDBSql.build_from()` for query-time JOIN generation.

### Dependencies

| Depends On | What For |
|------------|----------|
| `yaml` (PyYAML) | Parsing YAML frontmatter from domain model markdown |
| `de_funk.config.logging` | Logger for index build and resolution events |
| Domain model markdown files (`domains/models/`) | Schema fields, graph edges, and model metadata |
| Data source markdown files (`Data Sources/Endpoints/`) | Bronze endpoint schemas and provider mappings |
| Storage paths (silver_root, bronze_root) | Physical path construction in ResolvedField |

| Depended On By | What For |
|----------------|----------|
| `DuckDBSql.build_from()` (`core/sql.py`) | BFS join path resolution via `resolver.find_join_path()` |
| `DuckDBSql.build_where()` (`core/sql.py`) | Field resolution via `resolver.resolve()` for WHERE clause columns |
| `QuerySession` (`core/sessions.py`) | Wraps FieldResolver for query-time field resolution |
| API handlers (`api/handlers/`) | Resolve exhibit field references, build FROM/WHERE clauses |
| `DeFunk` (`app.py`) | Creates FieldResolver inside `query_session()` |
| FastAPI domain catalog endpoint | `resolver.get_field_catalog()` for `GET /api/domains` |

## Key Classes

### DomainGraph

**File**: `src/de_funk/core/graph.py:22`

**Purpose**: Queryable graph of domain model relationships.

| Method | Description |
|--------|-------------|
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> list[tuple[str, str, str]] | None` | BFS shortest join path from src table to dst table. |
| `reachable_domains(core_domains: set[str]) -> set[str]` | Get all domains reachable from the core set (transitive deps). |
| `neighbors(table_name: str) -> list[str]` | Get adjacent tables. |
| `domains_for_table(table_name: str) -> str | None` | Get the domain that owns a table. |
| `all_tables() -> list[str]` | Get all tables in the graph. |
| `all_edges() -> list[tuple[str, str, str, str]]` | Get all edges as (from, to, col_a, col_b) tuples. |
| `distance(table_a: str, table_b: str) -> int` | Hop count between two tables (-1 if unreachable). |
| `connected_components() -> list[set[str]]` | Find connected components in the graph. |
| `subgraph(domains: set[str]) -> DomainGraph` | Create a scoped subgraph containing only the specified domains. |

### FieldRef

**File**: `src/de_funk/api/resolver.py:37`

**Purpose**: Parsed domain.field reference (e.g. 'corporate.finance.amount').

| Attribute | Type |
|-----------|------|
| `_known_domains` | `set[str]` |

### ResolvedField

**File**: `src/de_funk/api/resolver.py:81`

**Purpose**: Resolution result — storage path + column for a domain.field ref.

| Method | Description |
|--------|-------------|
| `domain() -> str` | Canonical domain name (e.g. 'corporate.finance'). |

### FieldResolver

**File**: `src/de_funk/api/resolver.py:107`

**Purpose**: Resolves domain.field references to Silver table paths.

| Method | Description |
|--------|-------------|
| `reachable_domains(core_domains: set[str]) -> set[str]` | Compute allowed domains: core domains + their depends_on. |
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> list[tuple[str, str, str]] | None` | Find a join path between two Silver tables using BFS over graph.edges. |
| `resolve(ref_str: str) -> ResolvedField` | Resolve a domain.field string to a ResolvedField. |
| `resolve_many(refs: list[str]) -> dict[str, ResolvedField]` | Resolve multiple domain.field references in one call. Returns `{ref_str: ResolvedField}`. |
| `get_field_catalog() -> dict[str, dict]` | Return full field catalog — used by GET /api/domains. |

### BronzeEndpointInfo

**File**: `src/de_funk/api/bronze_resolver.py:40`

**Purpose**: Metadata for one Bronze endpoint table.

| Attribute | Type |
|-----------|------|
| `provider_id` | `str` |
| `endpoint_id` | `str` |
| `bronze_path` | `Path` |
| `fields` | `dict[str, str]` |

### BronzeResolver

**File**: `src/de_funk/api/bronze_resolver.py:48`

**Purpose**: Resolves provider.endpoint.field references to Bronze Delta Lake paths.

| Method | Description |
|--------|-------------|
| `resolve(ref_str: str) -> ResolvedField` | Resolve a provider.endpoint.field string to a ResolvedField. |
| `reachable_domains(core_domains: set[str]) -> set[str]` | Pass-through — Bronze has no domain scoping. |
| `find_join_path(src: str, dst: str, allowed_domains: set[str] | None) -> None` | Always returns None — Bronze has no join graph. |
| `get_endpoint_catalog() -> dict[str, dict]` | Return full Bronze endpoint catalog — used by GET /api/bronze/endpoints. |

## How to Use

### Common Operations

```python
from pathlib import Path
from de_funk.api.resolver import FieldResolver, FieldRef, ResolvedField

# Create a resolver
resolver = FieldResolver(
    domains_root=Path("domains"),
    storage_root=Path("/shared/storage/silver"),
    domain_overrides={"securities.stocks": Path("/shared/storage/silver/stocks")},
)

# Resolve a single field
resolved = resolver.resolve("securities.stocks.adjusted_close")
# resolved.table_name   -> "fact_daily_price"
# resolved.column        -> "adjusted_close"
# resolved.silver_path   -> Path("/shared/storage/silver/stocks/facts/fact_daily_price")
# resolved.format_code   -> "currency" (or None)
# resolved.domain        -> "securities.stocks"

# Resolve temporal fields (built-in dim_calendar mapping)
cal = resolver.resolve("temporal.year")
# cal.table_name  -> "dim_calendar"
# cal.column      -> "year"

# Resolve multiple fields at once
resolved_map = resolver.resolve_many([
    "securities.stocks.ticker",
    "securities.stocks.adjusted_close",
    "temporal.date",
])
# resolved_map["securities.stocks.ticker"].table_name -> "dim_stock"

# Find a join path between tables
path = resolver.find_join_path("fact_daily_price", "dim_stock")
# path -> [("dim_stock", "ticker", "ticker")]
# Meaning: JOIN dim_stock ON fact_daily_price.ticker = dim_stock.ticker

# Get the full field catalog (for API discovery)
catalog = resolver.get_field_catalog()
# catalog["securities.stocks"]["fields"]["ticker"] -> {"table": "dim_stock", "column": "ticker", "format": None}
```

```python
from de_funk.core.graph import DomainGraph

# Build graph from loaded models
graph = DomainGraph(models)  # models: dict[str, DomainModelConfig or dict]

# Find join path with domain scoping
path = graph.find_join_path(
    "fact_daily_price", "dim_calendar",
    allowed_domains={"securities.stocks", "temporal"},
)

# Check graph connectivity
components = graph.connected_components()
# [{"fact_daily_price", "dim_stock", "dim_calendar"}, {"fact_crime", "dim_crime_type"}]

# Get all domains reachable from a set (follows depends_on transitively)
reachable = graph.reachable_domains({"securities.stocks"})
# {"securities.stocks", "temporal", "corporate.entity"}
```

```python
from de_funk.api.bronze_resolver import BronzeResolver

# Create a Bronze resolver
bronze = BronzeResolver(
    data_sources_root=Path("Data Sources"),
    bronze_root=Path("/shared/storage/bronze"),
)

# Resolve a Bronze field
resolved = bronze.resolve("chicago.crimes.primary_type")
# resolved.table_name  -> "crimes"
# resolved.column      -> "primary_type"
# resolved.silver_path -> Path("/shared/storage/bronze/chicago/crimes")  (reuses silver_path attr)

# Get the endpoint catalog
catalog = bronze.get_endpoint_catalog()
# catalog["chicago"]["endpoints"]["crimes"]["fields"]["primary_type"] -> {"type": "string"}
```

### Integration Examples

```python
# FieldResolver + DuckDBSql: automatic FROM clause with joins
from de_funk.core.engine import Engine

engine = Engine.for_duckdb()
resolver = FieldResolver(domains_root=Path("domains"), storage_root=Path("/shared/storage/silver"))

# Resolve fields from different tables
ticker = resolver.resolve("securities.stocks.ticker")       # -> dim_stock
close = resolver.resolve("securities.stocks.adjusted_close") # -> fact_daily_price

# Build FROM with automatic join
tables = {
    ticker.table_name: str(ticker.silver_path),
    close.table_name: str(close.silver_path),
}
from_sql = engine.build_from(tables, resolver=resolver)
# -> 'delta_scan(...) AS "dim_stock" JOIN delta_scan(...) AS "fact_daily_price" ON "dim_stock"."ticker" = "fact_daily_price"."ticker"'

# Domain-scoped queries (prevent cross-domain contamination)
allowed = resolver.reachable_domains({"securities.stocks"})
from_sql = engine.build_from(tables, resolver=resolver, allowed_domains=allowed)
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValueError: Domain 'stocks' not found. Available domains: [...]` | Using short name instead of canonical name | Use `securities.stocks` not `stocks` |
| `ValueError: Field 'price' not found in domain 'securities.stocks'` | Field name does not match schema column name | Check `domains/models/securities/stocks/tables/*.md` for the exact column names in `schema:` |
| `ValueError: Invalid field reference 'foo' -- expected 'domain.field' format` | Reference missing the dot separator | Use `domain.field` format, e.g. `securities.stocks.ticker` |
| `find_join_path()` returns `None` | No edge connects the two tables, or domain scoping excludes the path | Add an edge in `model.md` `graph.edges`, or widen `allowed_domains` |
| CROSS JOIN in generated SQL | `find_join_path()` returned `None` so DuckDBSql fell back to CROSS JOIN | Declare the missing edge in domain model config |
| Wrong table resolved for a field | Multiple tables have the same column name; first-discovered table wins | Rename the column or use a more specific domain reference |
| `Bronze provider 'alpha_vantage' not found` | Bronze data directory does not exist on disk | Run the ingestion pipeline first, or check `bronze_root` path |
| Temporal field resolution fails | Unknown temporal field name | Use one of: `date`, `date_id`, `year`, `month`, `quarter`, `day_of_week`, `week` |

### Debug Checklist

- [ ] Check `resolver._index` after first resolution to verify domains and fields were indexed
- [ ] Check `resolver._join_graph` to see what edges were discovered
- [ ] Test `FieldRef("securities.stocks.ticker")` to verify domain parsing: `.domain` should be `securities.stocks`, `.field` should be `ticker`
- [ ] Verify table markdown files have `type: domain-model-table` in frontmatter (files without this are skipped)
- [ ] For join issues, test `resolver.find_join_path("table_a", "table_b")` in isolation
- [ ] For domain scoping issues, check `resolver._domain_deps` to see declared dependencies
- [ ] For Bronze issues, check that the Bronze path exists on disk: `bronze_root/provider_id/endpoint_id/`
- [ ] Enable DEBUG logging to see "Resolved X -> table.column @ path" messages

### Common Pitfalls

1. **`FieldRef._known_domains` is a class variable**: It is populated once when `FieldResolver._build_index()` runs. If you create a `FieldRef` before any resolver has been built, it falls back to first-dot splitting, which fails for multi-segment domain names like `corporate.finance`.
2. **First table wins for duplicate field names**: If `dim_stock` and `fact_daily_price` both have a `ticker` column, the first table discovered during `rglob("*.md")` wins for `securities.stocks.ticker`. This is by design (dimensions are typically discovered first) but can surprise if file ordering changes.
3. **`DomainGraph` and `FieldResolver._join_graph` are separate**: `DomainGraph` is built by `DeFunk` from model dicts. `FieldResolver` builds its own `_join_graph` by re-scanning model.md files. They should be identical, but if model loading and markdown files diverge, the graphs may differ.
4. **BronzeResolver reuses `silver_path` attribute for Bronze paths**: `ResolvedField.silver_path` actually points to the Bronze path when resolved through `BronzeResolver`. The attribute name is a misnomer inherited from the shared interface.
5. **`subgraph()` on DomainGraph is a stub**: The current implementation returns an empty graph. Domain scoping is implemented via `allowed_domains` parameter on `find_join_path()` instead.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/core/graph.py` | DomainGraph — queryable graph model built from EdgeSpec. | `DomainGraph` |
| `src/de_funk/api/resolver.py` | Field resolver — translates domain.field references to Silver table paths and columns. | `FieldRef`, `ResolvedField`, `FieldResolver` |
| `src/de_funk/api/bronze_resolver.py` | Bronze resolver — translates provider.endpoint.field references to Bronze table paths. | `BronzeEndpointInfo`, `BronzeResolver` |
