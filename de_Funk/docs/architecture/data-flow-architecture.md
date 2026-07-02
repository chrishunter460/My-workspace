# de_Funk Architecture Map

## Context

This document maps the complete data flow architecture of de_Funk — how data enters the system, how it's transformed and stored, how it's queried and served, and what codebase supports each layer.

**Last Updated**: 2026-03-15

---

## System Overview (30,000 ft)

```
                        ┌─────────────────────────────────────┐
                        │         OBSIDIAN PLUGIN              │
                        │   (TypeScript, ~815 lines)           │
                        │   obsidian-plugin/src/               │
                        │                                      │
                        │  Sidebar Filters ←→ Code Blocks      │
                        │  (filter-bus pub/sub)                │
                        └──────────────┬───────────────────────┘
                                       │ HTTP (POST /api/query)
                                       │ GET /api/dimensions
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         FASTAPI LAYER                │
                        │   src/de_funk/api/                   │
                        │                                      │
                        │  FieldResolver → QueryEngine (DuckDB)│
                        │  HandlerRegistry → Exhibit Handlers  │
                        └──────────────┬───────────────────────┘
                                       │ reads Delta/Parquet
                                       ▼
┌──────────────────┐    ┌─────────────────────────────────────┐
│  DATA SOURCES    │    │         SILVER LAYER                 │
│                  │    │   /shared/storage/silver/             │
│  Alpha Vantage   │    │                                      │
│  Chicago Portal  │    │   dims/ + facts/ per model           │
│  Cook County     │    │   Delta Lake format                  │
└────────┬─────────┘    └──────────────┬───────────────────────┘
         │                             ▲
         │ API calls                   │ model.build() + write_tables()
         ▼                             │
┌──────────────────┐    ┌─────────────────────────────────────┐
│  BRONZE LAYER    │───▶│     MODEL FRAMEWORK                  │
│  storage/bronze/ │    │   src/de_funk/models/base/           │
│  Delta Lake      │    │                                      │
│                  │    │   BaseModel → GraphBuilder →          │
│  Per provider/   │    │   DomainModel → ModelWriter           │
│  endpoint        │    │                                      │
└──────────────────┘    └─────────────────────────────────────┘
```

---

## Layer 1: Data Ingestion (Data In)

### Entry Points
| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/seed/seed_tickers.py` | Bootstrap ticker list from LISTING_STATUS | `python -m scripts.seed.seed_tickers` |
| `scripts/seed/seed_calendar.py` | Generate calendar dim (2000–2050) | `python -m scripts.seed.seed_calendar` |
| `scripts/seed/seed_market_cap.py` | Fetch market cap for ranking | `python -m scripts.seed.seed_market_cap` |
| `scripts/seed/seed_geography.py` | Geographic reference data | `python -m scripts.seed.seed_geography` |
| `scripts/ingest/run_bronze_ingestion.py` | **Main ingestion pipeline** | `python -m scripts.ingest.run_bronze_ingestion` |

### Pipeline Architecture (`src/de_funk/pipelines/`)

```
API Response → Provider.fetch() → raw batches
                    ↓
              Provider.normalize() → Spark DataFrame (via Facet)
                    ↓
              BronzeSink.smart_write() → Delta Lake table
                    ↓
              storage/bronze/{provider}/{table}/
```

**Core components:**

| Class | File | Lines | Role |
|-------|------|-------|------|
| `IngestorEngine` | `src/de_funk/pipelines/base/ingestor_engine.py` | 929 | Orchestrator — async writes via ThreadPoolExecutor, backpressure, batching |
| `BaseProvider` | `src/de_funk/pipelines/base/provider.py` | 401 | Abstract interface: `list_work_items()`, `fetch()`, `normalize()`, `get_table_name()` |
| `Facet` | `src/de_funk/pipelines/base/facet.py` | 496 | Schema-aware normalization: type coercion, computed fields, column ordering |
| `BronzeSink` | `src/de_funk/pipelines/ingestors/bronze_sink.py` | 716 | Delta Lake writer: 3 strategies (append_immutable, upsert, smart_write) |
| `HttpClient` | `src/de_funk/pipelines/base/http_client.py` | 248 | Rate-limited HTTP with API key rotation |
| `SocrataClient` | `src/de_funk/pipelines/base/socrata_client.py` | 861 | Socrata/OpenData API client (SoQL, pagination, CSV download) |
| `SocrataBaseProvider` | `src/de_funk/pipelines/base/socrata_provider.py` | 830 | Base for Chicago + Cook County providers |

**Resilience infrastructure:**

| Class | File | Lines | Role |
|-------|------|-------|------|
| `RateLimiter` | `pipelines/base/` | 306 | Enforces per-provider API rate limits |
| `CircuitBreaker` | `pipelines/base/` | 398 | Prevents cascading failures on API outages |
| `ApiKeyPool` | `pipelines/base/` | 23 | Multi-key rotation with cooldown |
| `ProgressTracker` | `pipelines/base/` | 899 | Ingestion progress logging |
| `Normalizer` | `pipelines/base/` | 371 | Schema-aware normalization pipeline |

### Providers (Data Sources)

| Provider | Location | Data | Work Items |
|----------|----------|------|------------|
| **Alpha Vantage** | `src/de_funk/pipelines/providers/alpha_vantage/` | Securities | prices, reference, income, balance, cashflow, earnings, dividends, splits |
| **Chicago** | `src/de_funk/pipelines/providers/chicago/` | Municipal | 60+ endpoints (crimes, permits, inspections, ridership, etc.) |
| **Cook County** | `src/de_funk/pipelines/providers/cook_county/` | County | Property records, assessments, neighborhoods |

**Provider Registry:** `src/de_funk/pipelines/providers/registry.py` (344 lines) — auto-discovers providers from directory structure.

### Configuration (Markdown-Driven)

All ingestion config lives in markdown with YAML frontmatter (single source of truth):

- **Provider configs:** `data_sources/Providers/{Provider Name}.md` — base_url, rate limits, API key env var
- **Endpoint configs:** `data_sources/Endpoints/{Provider}/{Category}/{Endpoint}.md` — response_key, query params, schema, write strategy, key columns, partitions

### Raw Layer (Optional Cache)

```
storage/raw/alpha_vantage/{endpoint}/{ticker}.json   ← API JSON cached
storage/raw/chicago/{endpoint}_{resource_id}.csv     ← CSV downloads cached
```
Skips API call on re-run if file exists (unless `--force-api`).

### Bronze Layer Output

```
storage/bronze/
├── securities_reference/          # Unified tickers (partitioned: asset_type)
├── securities_prices_daily/       # Unified OHLCV (partitioned: year)
├── income_statement/              # Financial statements
├── balance_sheet/
├── cash_flow/
├── chicago_crimes/                # Municipal data (partitioned: year)
├── chicago_building_permits/
└── ... (one directory per endpoint)
```

All Delta Lake format with `_delta_log/` transaction logs.

**Write Strategies:**
- `append_immutable` — Time-series (prices, events): INSERT-only with date-range dedup
- `upsert` — Reference data (company info): read-merge-overwrite
- `smart_write` — Auto-selects based on `storage.json` table config

---

## Layer 2: Model Framework (Bronze → Silver)

### Entry Points
| Script | Purpose | Command |
|--------|---------|---------|
| `scripts/build/build_models.py` | Build all Silver models | `python -m scripts.build.build_models` |
| `scripts/build/rebuild_model.py` | Rebuild specific model | `python -m scripts.build.build_models --models stocks` |

### Build Pipeline

```
DomainBuilderFactory.create_builders()
    ↓ scans domains/models/
DomainConfigLoaderV4.load_model_config(name)
    ↓ assembles from model.md + tables/*.md + sources/**/*.md
ConfigTranslator.translate_domain_config()
    ↓ synthesizes graph.nodes from sources + tables
BuilderRegistry.get_build_order()
    ↓ topological sort (respects depends_on)
For each model in order:
    model = DomainModel(config, spark, storage)
    model.build()  →  GraphBuilder loads nodes from Bronze
                       applies filters, joins, derives, dedup
                       separates dims vs facts
    model.write_tables()  →  ModelWriter persists to Silver (Delta)
```

### BaseModel Framework (`src/de_funk/models/base/`)

| Class | File | Lines | Role |
|-------|------|-------|------|
| `BaseModel` | `model.py` | 939 | Thin orchestrator: loads config, lazy-loads composition helpers, delegates to builders |
| `GraphBuilder` | `graph_builder.py` | 661 | Builds nodes from Bronze: load → filter → join → select → derive → dedup → drop |
| `DomainModel` | `domain_model.py` | 814 | Extends BaseModel: seed, union, distinct, generated, unpivot node types |
| `DomainBuilder` | `domain_builder.py` | 217 | Factory: creates dynamic builder classes via `type()`, registers with BuilderRegistry |
| `ModelWriter` | `model_writer.py` | 331 | Persists dims/ and facts/ to Silver as Delta Lake, optional auto-vacuum |
| `TableAccessor` | `table_accessor.py` | 395 | Table access, schema inspection, FK relationships, denormalization |
| `MeasureCalculator` | `measure_calculator.py` | 277 | Calculate simple, computed, weighted measures |
| `BuilderRegistry` | `builder.py` | 564 | Discovers builders, topological sort, executes in dependency order |

### Custom Model Classes

```
BaseModel
├── DomainModel (default for all domain models)
│   ├── TemporalModel    → src/de_funk/models/domains/foundation/temporal/model.py
│   ├── CompanyModel     → src/de_funk/models/domains/corporate/company/model.py
│   └── StocksModel      → src/de_funk/models/domains/securities/stocks/model.py
└── ForecastModel (legacy)
```

Mapping in `DomainBuilder.CUSTOM_MODEL_CLASSES`.

### Domain Configs (`domains/`)

```
domains/
├── _model_guides_/              # Reference docs (not loaded)
├── _base/                       # Base templates for inheritance
└── models/
    ├── corporate/
    │   ├── entity/              # Company model
    │   │   ├── model.md         # type: domain-model (extends, depends_on, build phases)
    │   │   ├── tables/          # type: domain-model-table (schema, filters, derives)
    │   │   │   └── dim_company.md
    │   │   └── sources/         # type: domain-model-source (from, aliases, transforms)
    │   │       └── entity/company_overview.md
    │   └── finance/             # Corporate finance model
    ├── securities/
    │   ├── master/              # Base securities (dim_security, fact_security_prices)
    │   └── stocks/              # Stocks (extends master, adds stock-specific)
    ├── county/
    │   ├── geospatial/          # Cook County boundaries
    │   └── property/            # Assessed values, parcel sales
    └── municipal/
        ├── entity/              # City entity dimension
        ├── finance/             # Budgets, property tax, contracts, vendors
        ├── geospatial/          # Wards, community areas, patrol areas
        ├── housing/             # Building permits
        ├── operations/          # Service requests (311)
        ├── public_safety/       # Crimes
        ├── regulatory/          # Violations, licenses, food inspections
        └── transportation/      # Bus/rail ridership, traffic
```

### Config Loading (`src/de_funk/config/domain/`)

| File | Role |
|------|------|
| `__init__.py` (357 lines) | `DomainConfigLoaderV4` — scans markdown, assembles multi-file configs, resolves extends |
| `config_translator.py` | Translates domain config → build-compatible config (synthesizes graph.nodes) |
| `extends.py` | Inheritance resolution |
| `schema.py` | Table schema processing |
| `sources.py` | Source config processing |
| `graph.py` | Edge parsing from tabular format |
| `build.py` | Build phase parsing |
| `federation.py` | Cross-model federation |
| `views.py` | View definitions |

### Node Transformation Pipeline (inside GraphBuilder)

For each node defined in graph config:
1. **Load** from Bronze/Silver or custom source (seed, union, distinct)
2. **Filter** — backend-agnostic filter expressions
3. **Join** — with other nodes/tables, auto-dedup columns
4. **Select** — column aliasing/projection
5. **Derive** — computed columns (SHA1, SQL expressions, column refs)
6. **Unique Key** — deduplication
7. **Drop** — remove helper columns

### Silver Layer Output

```
/shared/storage/silver/
├── temporal/
│   └── dims/dim_calendar/
├── corporate/
│   ├── entity/dims/dim_company/
│   └── finance/dims/ + facts/
├── stocks/
│   ├── dims/dim_stock/
│   └── facts/fact_stock_prices/
├── county/
│   ├── geospatial/dims/
│   └── property/facts/
└── municipal/
    ├── finance/dims/ + facts/
    ├── geospatial/dims/
    ├── public_safety/facts/
    └── ... (one subdir per model)
```

All Delta Lake format, partitioned as configured.

---

## Layer 3: Query & Serving (Data Out)

### Two Query Paths

**Path A: FastAPI → Obsidian Plugin** (primary, active development)
**Path B: UniversalSession → Notebooks/Scripts** (legacy Streamlit path, still functional)

---

### Path A: FastAPI + Obsidian Plugin

#### FastAPI Backend (`src/de_funk/api/`)

| File | Role |
|------|------|
| `main.py` | App factory: loads storage config, creates QueryEngine + FieldResolver, mounts routers, CORS for Obsidian |
| `executor.py` | `QueryEngine` — DuckDB connection, SQL generation, Delta/Parquet reading, response truncation |
| `resolver.py` | `FieldResolver` — scans `domains/models/` tables, builds index `{domain.field → (table, column, path, format)}`, BFS join graph |
| `routers/query.py` | `POST /api/query` — dispatches to exhibit handler by block type |
| `routers/dimensions.py` | `GET /api/dimensions/{domain}/{field}` — distinct values with context filters |
| `routers/health.py` | Health check |
| `routers/domains.py` | Domain metadata |

**Exhibit Handlers** (`src/de_funk/api/handlers/`):

| Handler | Types | Output |
|---------|-------|--------|
| `GraphicalHandler` | plotly.line, bar, scatter, area, pie, heatmap | `{series: [{name, x[], y[]}]}` |
| `BoxHandler` | plotly.box, ohlcv, candlestick | OHLCV series |
| `TableDataHandler` | table.data | `{columns, rows}` |
| `PivotHandler` | table.pivot, great_table | `{html, expandable?}` |
| `MetricsHandler` | cards.metric | `{metrics: [{key, label, value, format}]}` |

**Query execution flow:**
```
POST /api/query {type: "plotly.line", data: {x: "date", y: "adjusted_close"}, filters: [...]}
    ↓
HandlerRegistry.get("plotly.line") → GraphicalHandler
    ↓
handler.execute(payload, resolver):
  1. Resolve field refs: "stocks.adjusted_close" → (fact_stock_prices, adjusted_close, silver_path)
  2. Collect all tables needed
  3. Find join paths via BFS on join graph (from graph.edges in model configs)
  4. Build SQL: SELECT ... FROM table1 JOIN table2 ON ... WHERE ... GROUP BY ... ORDER BY ...
  5. Execute via DuckDB
  6. Shape response (series for charts, rows for tables, html for pivots)
  7. Truncate if > max_response_mb (default 4MB)
    ↓
JSON response → Plugin
```

#### Obsidian Plugin (`obsidian-plugin/src/`)

| File | Lines | Role |
|------|-------|------|
| `main.ts` | 159 | Plugin lifecycle: register code block processor, sidebar, event listeners |
| `contract.ts` | 182 | TypeScript interfaces mirroring Python API models |
| `api-client.ts` | 118 | HTTP client with response caching (TTL-based) |
| `frontmatter.ts` | 123 | YAML frontmatter parsing (extracts filters, controls, models) |
| `filter-bus.ts` | 24 | Global pub/sub for filter change events |
| `filter-sidebar.ts` | 300+ | Sidebar panel: filter dropdowns, date pickers, search, tag strips, controls |
| `settings.ts` | 89 | Plugin settings (serverUrl, apiKey, cacheTtl) |
| `resolver.ts` | 163 | YAML block parsing, API payload construction, filter merging |
| `processors/de-funk.ts` | 153 | Code block processor: parse → buildRequest → query → dispatch to renderer |
| `processors/config-panel.ts` | 58 | Pub/sub state store for control panels |
| `render/graphical.ts` | 140 | Plotly chart rendering (dark/light theme, responsive) |
| `render/tabular.ts` | 79 | HTML table rendering with pagination + CSV download |
| `render/pivot.ts` | 144 | GT HTML injection + expandable row drill-down |
| `render/metric-cards.ts` | 31 | CSS grid KPI cards |
| `render/format.ts` | 59 | Value formatting ($, $K, $M, %, date, number) |

**End-to-end user flow:**

```
1. User opens Obsidian note
   ↓
   parseFrontmatter() extracts filters + controls from YAML header
   ↓
   Sidebar renders filter UI (fetches dimension values via GET /api/dimensions)

2. User selects filter value (e.g., ticker = "AAPL")
   ↓
   filter-bus broadcasts change → all exhibit blocks re-render

3. Each ```de_funk code block:
   ↓
   parseBlock(YAML) → DeFunkBlock
   ↓
   buildRequest(block, noteFilters, controlState) → merged payload
   ↓
   client.query(payload) → POST /api/query
   ↓
   Response dispatched by type:
     plotly.*  → renderGraphical() → Plotly.newPlot()
     table.*   → renderTabular()   → HTML table
     pivot.*   → renderPivot()     → GT HTML + expandable rows
     cards.*   → renderMetricCards() → CSS grid

4. User changes sidebar control (e.g., "Group by" dropdown)
   ↓
   config-panel pub/sub fires → subscribed exhibits re-render with new state
```

**Sidebar Architecture:**

The sidebar renders three types of filter controls:
- **`select`** — Multi-select dropdown with search bar + tag strip (removable chips). Fetches dimension values from API. Supports `context_filters` for dependent filtering (e.g., only show tickers from selected sector).
- **`date_range`** — Date picker (from/to)
- **`range`** — Numeric range (from/to)

Plus interactive **controls** defined in frontmatter:
- `dimensions` — dropdown to change group_by field
- `measures` — dropdown to change y-axis field
- `sort_order` — toggle asc/desc
- `show_legend`, `show_totals` — checkboxes
- `color_palette` — dropdown

State flows through `config-panel.ts` pub/sub store → subscribed exhibits re-render.

---

### Path B: UniversalSession (Script/Notebook Path)

| File | Role |
|------|------|
| `src/de_funk/models/api/session.py` (39.5 KB) | `UniversalSession` — cross-model query interface, dynamic model loading, auto-joins |
| `src/de_funk/models/api/auto_join.py` (92.9 KB) | `AutoJoinHandler` — graph traversal for cross-model joins, materialized view discovery |
| `src/de_funk/models/api/query_planner.py` (25.8 KB) | `GraphQueryPlanner` — per-model join planning using NetworkX |
| `src/de_funk/models/api/aggregation.py` | `AggregationHandler` — data aggregation |
| `src/de_funk/models/api/dal.py` | `StorageRouter` — resolves "bronze.alpha_vantage.prices" to filesystem paths; `Table` — auto-detects Delta vs Parquet |

**Notebook system** (legacy Streamlit, being replaced by Obsidian):
- `src/de_funk/notebook/managers/notebook_manager.py` (46.6 KB)
- `src/de_funk/notebook/parsers/markdown_parser.py` (66.4 KB)
- `src/de_funk/core/session/filters.py` (17.3 KB) — canonical FilterEngine

---

## Layer 4: Supporting Infrastructure

### Configuration System (`src/de_funk/config/`)

| File | Role |
|------|------|
| `loader.py` (545 lines) | `ConfigLoader` — single entry point, precedence: env > params > files > defaults |
| `models.py` (192 lines) | Typed dataclasses: `AppConfig`, `ConnectionConfig`, `SparkConfig`, `DuckDBConfig`, `StorageConfig` |
| `constants.py` (43 lines) | Default values (DuckDB default backend, memory limits, paths) |
| `logging.py` | `setup_logging()`, `get_logger()`, `LogTimer` — centralized logging |
| `markdown_loader.py` | `MarkdownConfigLoader` — loads provider + endpoint configs from markdown |

**Key config files:**
- `configs/storage.json` — storage roots, table mappings, API limits, connection defaults
- `.env` — API keys, connection overrides
- `data_sources/Providers/*.md` — provider metadata
- `data_sources/Endpoints/**/*.md` — endpoint schemas + write strategies

### Core Infrastructure (`src/de_funk/core/`)

| File | Role |
|------|------|
| `context.py` | `RepoContext` — repo-wide context, uses ConfigLoader internally |
| `connection.py` | `DataConnection` abstract + `SparkConnection` |
| `duckdb_connection.py` | `DuckDBConnection` — Delta extension, auto-init views |
| `exceptions.py` | Exception hierarchy: `DeFunkError` → `ConfigurationError`, `ModelError`, `PipelineError`, etc. |
| `error_handling.py` | `@handle_exceptions`, `@retry_on_exception`, `safe_call()` |

### Orchestration (`src/de_funk/orchestration/`)

| File | Role |
|------|------|
| `orchestration/common/spark_session.py` | `get_spark()` — factory with Delta Lake config, retry logic |

### Exhibit Type Catalog (`exhibits/`)

| File | Role |
|------|------|
| `exhibits/_index.md` | Master registry of all exhibit types + aliases |
| `exhibits/types/` | Per-type documentation |
| `exhibits/_base/` | Base exhibit definitions + computations guide |

---

## Data Flow Summary

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ External     │     │   Raw Cache  │     │    Bronze    │     │    Silver    │     │   Obsidian   │
│ APIs         │────▶│  (optional)  │────▶│  Delta Lake  │────▶│  Delta Lake  │────▶│   Plugin     │
│              │     │  JSON/CSV    │     │              │     │  dims+facts  │     │              │
│ Alpha Vantage│     │              │     │ Per endpoint │     │  Per model   │     │ Charts,      │
│ Chicago      │     │ storage/raw/ │     │ storage/     │     │ /shared/     │     │ Tables,      │
│ Cook County  │     │              │     │ bronze/      │     │ storage/     │     │ Pivots,      │
└─────────────┘     └──────────────┘     └──────────────┘     │ silver/      │     │ Metrics      │
                                                               └──────────────┘     └──────────────┘

   Provider.fetch()   raw layer cache     IngestorEngine +     model.build() +      FastAPI +
   + normalize()                          BronzeSink            ModelWriter          QueryEngine
                                                                                    (DuckDB)
```

### Key Design Decisions

1. **Markdown-driven config** — schemas, endpoints, models all defined in markdown with YAML frontmatter (single source of truth, self-documenting)
2. **Delta Lake everywhere** — ACID, time travel, schema evolution for both Bronze and Silver
3. **Backend abstraction** — Spark for batch ETL (build), DuckDB for interactive queries (serve)
4. **Composition over inheritance** — BaseModel delegates to GraphBuilder, TableAccessor, MeasureCalculator, ModelWriter
5. **Reactive UI** — Obsidian plugin uses filter-bus + config-panel pub/sub for live re-rendering
6. **Two query paths** — FastAPI/DuckDB for Obsidian (fast), UniversalSession for scripts/notebooks (flexible)
7. **Provider-agnostic ingestion** — BaseProvider interface + auto-discovery registry
8. **Raw layer caching** — API responses cached to disk, avoids re-hitting APIs on schema changes
