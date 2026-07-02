---
title: "API Layer"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - src/de_funk/api/handlers/base.py
  - src/de_funk/api/handlers/box.py
  - src/de_funk/api/handlers/formatting.py
  - src/de_funk/api/handlers/graphical.py
  - src/de_funk/api/handlers/gt_formatter.py
  - src/de_funk/api/handlers/metrics.py
  - src/de_funk/api/handlers/pivot.py
  - src/de_funk/api/handlers/reshape.py
  - src/de_funk/api/handlers/table_data.py
  - src/de_funk/api/models/requests.py
  - src/de_funk/api/routers/bronze.py
  - src/de_funk/api/routers/dimensions.py
  - src/de_funk/api/routers/domains.py
  - src/de_funk/api/routers/health.py
  - src/de_funk/api/routers/models.py
  - src/de_funk/api/routers/predict.py
  - src/de_funk/api/routers/query.py
  - src/de_funk/api/main.py
---

# API Layer

> FastAPI routers, exhibit handlers, and pydantic request/response models — the Obsidian connection point.

## Purpose & Design Decisions

### What Problem This Solves

The Obsidian plugin renders data exhibits (charts, tables, pivots, metric cards) inside markdown notes. Each exhibit block specifies a `type` and field references using canonical domain names (e.g. `securities.stocks.close`). The API layer translates these exhibit block payloads into SQL queries against DuckDB-scanned Silver Delta tables, executes them, and returns structured JSON responses that the plugin renders as Plotly charts or Great Tables HTML.

Without this layer, the plugin would need to understand storage paths, join logic, and SQL dialects directly. The API provides a single `/api/query` POST endpoint that accepts the same YAML block structure the user writes in Obsidian, making the plugin a thin rendering client.

### Key Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| Registry-based handler dispatch (`type` string -> handler class) | Each exhibit family (graphical, pivot, table, metric, box) has different SQL generation and response shaping logic. The registry pattern decouples routing from execution and allows new exhibit types without modifying the router. | Single monolithic query handler with switch/case |
| Handlers access Engine directly (no QueryEngine bridge) | Removes an unnecessary abstraction layer. Handlers call `_engine.execute_sql()`, `_engine.build_from()`, etc. directly, reducing indirection and making debugging easier. | Intermediate QueryEngine class wrapping Engine |
| Pydantic request models mirror YAML block syntax 1:1 | The Obsidian plugin serializes the YAML block as JSON and sends it verbatim. Pydantic models validate and normalize the payload without requiring a separate DTO mapping layer. | Manual dict parsing in handlers |
| Response size capping via `max_response_mb` | Prevents a single unfiltered pivot from consuming all browser memory. `truncate_to_mb()` and series point capping are applied before serialization. | Client-side pagination (adds latency for every page) |

### Config-Driven Aspects

| Behavior | Controlled By | Location |
|----------|--------------|----------|
| Maximum response payload size | `storage.json` > `api.max_response_mb` (default 4.0) | `configs/storage.json` |
| CORS allowed origins | Hardcoded list in `create_app()` including `app://obsidian.md` | `src/de_funk/api/main.py` |
| Silver storage root path | `storage.json` > `roots.silver` | `configs/storage.json` |
| Domain-specific storage overrides | `storage.json` > `domain_roots` | `configs/storage.json` |
| Max SQL result rows | `ExhibitHandler._max_sql_rows` (default 30,000) | `src/de_funk/api/handlers/base.py` |
| Max pivot column combinations | `PivotHandler.MAX_PIVOT_COLUMNS` (200) | `src/de_funk/api/handlers/pivot.py` |
| Max HTML rows before expandable mode | `PivotHandler.MAX_HTML_ROWS` (400) | `src/de_funk/api/handlers/pivot.py` |

## Architecture

### Where This Fits

```
[Obsidian Plugin] --POST /api/query--> [FastAPI Routers] --> [Handler Registry]
                                                                    |
                                                              [ExhibitHandler]
                                                                    |
                                                [FieldResolver] + [Engine (DuckDB)]
                                                                    |
                                                          [Silver Delta Tables]
```

The API layer sits between the Obsidian plugin (HTTP client) and the Engine (DuckDB query execution). On startup, `DeFunk.from_config()` initializes the Engine, which provides a `HandlerRegistry` containing instances of each handler subclass with shared DuckDB connection and FieldResolver. The FieldResolver maps canonical domain field references (e.g. `securities.stocks.close`) to physical Silver table paths and column names.

### Dependencies

| Depends On | What For |
|------------|----------|
| `de_funk.app.DeFunk` | Application initialization, config loading, engine creation |
| `de_funk.api.resolver.FieldResolver` | Resolving `domain.field` references to Silver table paths and columns |
| `de_funk.api.measures.build_measure_sql` | Translating measure tuples (including computed measures) into SQL expressions |
| `de_funk.api.executor.truncate_to_mb` | Response size capping |
| `de_funk.api.handlers.gt_formatter.build_gt` | Rendering pivot data as Great Tables HTML |
| `de_funk.config.logging` | Structured logging |

| Depended On By | What For |
|----------------|----------|
| Obsidian plugin (`obsidian-plugin/`) | All exhibit rendering: charts, tables, pivots, metric cards |
| `src/de_funk/api/routers/bronze.py` | Bronze-layer query endpoints share the same handler pattern |

## Key Classes

### ExhibitHandler

**File**: `src/de_funk/api/handlers/base.py:22`

**Purpose**: Base class for exhibit handlers.

| Attribute | Type |
|-----------|------|
| `handles` | `set[str]` |
| `_engine` | `Any` |
| `max_response_mb` | `float` |
| `storage_root` | `Any` |
| `_max_sql_rows` | `int` |
| `_max_dimension_values` | `int` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: Any) -> Any` | Execute the exhibit query and return a response model. |
| `distinct_values(resolved, extra_filters, resolver) -> list` | Return distinct values for a dimension field. |
| `distinct_values_by_measure(resolved, order_by, order_dir, extra_filters, resolver) -> list` | Return distinct values ordered by aggregated measure. |

### BoxHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/box.py:11`

**Purpose**: Handles `plotly.box`, `box`, `ohlcv`, and `candlestick` exhibit types. Supports two modes: OHLCV candlestick charts (when open/high/low/close fields are all provided) and generic box plots (single y field). Optional `group_by` splits data into separate traces.

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> dict` | Resolves OHLCV or y fields, builds SQL with domain-scoped joins and filters, executes the query, and returns a dict with `series`, `mode` ("ohlcv" or "box"), and `grouped` flag. |

### GraphicalHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/graphical.py:20`

**Purpose**: Handles all Plotly chart types: `plotly.line`, `plotly.bar`, `plotly.scatter`, `plotly.area`, `plotly.pie`, and `plotly.heatmap`. Unifies pie chart `labels`/`values` fields to the standard `x`/`y` pattern. Supports multi-y series, `group_by` for grouped charts, and configurable aggregation. Response is capped at `max_response_mb` by truncating series points.

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> GraphicalResponse` | Resolves x/y/group_by fields, builds aggregated SQL with GROUP BY, executes, and shapes results into `SeriesData` objects grouped by the group_by dimension. Applies response size capping. |

### MetricsHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/metrics.py:20`

**Purpose**: Handles `cards.metric`, `kpi`, and `metric_cards` exhibit types. Computes scalar aggregate values (one row) for display as KPI cards in Obsidian. Supports computed measures that reference prior measure keys (e.g. divide revenue by shares).

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> MetricResponse` | Builds a single-row aggregate SQL from measure tuples, resolves format codes from field metadata and formatting overrides, returns `MetricResponse` with labeled, formatted metric values. |

### PivotHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/pivot.py:48`

**Purpose**: Handles `table.pivot`, `pivot`, `great_table`, and `gt` exhibit types. Always renders output as Great Tables HTML. Supports 1D pivots (rows only), 2D pivots via SQL conditional aggregation (`FILTER (WHERE ...)`), three layout modes (`by_measure`, `by_column`, `by_dimension`), GROUPING SETS for totals, DuckDB LAG() window calculations, and expandable hierarchical pivots for large result sets.

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> GreatTablesResponse` | Resolves row/col/measure/sort fields, dispatches to `_query_1d` or `_query_2d_wide`, applies expandable pivot splitting when rows exceed MAX_HTML_ROWS, renders via `build_gt()`, and returns HTML with optional expandable JSON data. |

### TableDataHandler (ExhibitHandler)

**File**: `src/de_funk/api/handlers/table_data.py:20`

**Purpose**: Handles `table.data` and `data_table` exhibit types. Produces flat tabular data with optional per-column aggregation and sorting. The response includes column metadata (labels, format codes) so the plugin can render a styled HTML table.

| Attribute | Type |
|-----------|------|
| `handles` | `—` |

| Method | Description |
|--------|-------------|
| `execute(payload: dict[str, Any], resolver: FieldResolver) -> TableResponse` | Resolves column fields, applies optional aggregation per column (SUM, AVG, COUNT_DISTINCT, etc.), builds SQL with sort, executes, applies `truncate_to_mb`, and returns `TableResponse` with column metadata and row data. |

### FilterSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:17`

**Purpose**: A single filter applied to a field.

| Attribute | Type |
|-----------|------|
| `model_config` | `—` |
| `field` | `str` |
| `operator` | `str` |
| `value` | `Union[list, str, int, float, dict]` |

### PageFilters (BaseModel)

**File**: `src/de_funk/api/models/requests.py:25`

**Purpose**: Page-level filter inheritance control.

| Attribute | Type |
|-----------|------|
| `ignore` | `list[str]` |

### SortSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:31`

**Purpose**: Sort directive — applied at query level.

| Attribute | Type |
|-----------|------|
| `by` | `Optional[str]` |
| `order` | `str` |
| `values` | `Optional[list[str]]` |

### BucketSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:38`

**Purpose**: Binning config for a dimension.

| Attribute | Type |
|-----------|------|
| `size` | `Optional[float]` |
| `edges` | `Optional[list[float]]` |
| `count` | `Optional[int]` |

### WindowSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:45`

**Purpose**: Row-over-row window calculation.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `source` | `str` |
| `type` | `str` |
| `label` | `Optional[str]` |

### TotalsSpec (BaseModel)

**File**: `src/de_funk/api/models/requests.py:53`

**Purpose**: Backend-computed summary rows/cols.

| Attribute | Type |
|-----------|------|
| `rows` | `bool` |
| `cols` | `bool` |

### SortConfig (BaseModel)

**File**: `src/de_funk/api/models/requests.py:59`

**Purpose**: Sort config for pivot rows and cols.

| Attribute | Type |
|-----------|------|
| `rows` | `Optional[SortSpec]` |
| `cols` | `Optional[SortSpec]` |

### MeasureTuple (BaseModel)

**File**: `src/de_funk/api/models/requests.py:65`

**Purpose**: Measure definition as a tuple.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `field` | `Union[str, dict]` |
| `aggregation` | `Optional[str]` |
| `format` | `Optional[str]` |
| `label` | `Optional[str]` |

### ColumnTuple (BaseModel)

**File**: `src/de_funk/api/models/requests.py:78`

**Purpose**: Column definition for table.data.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `field` | `str` |
| `aggregation` | `Optional[str]` |
| `format` | `Optional[str]` |
| `label` | `Optional[str]` |

### GraphicalQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:91`

**Purpose**: Request for plotly.line, plotly.bar, plotly.scatter, plotly.area, plotly.pie, plotly.heatmap.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `x` | `Optional[str]` |
| `y` | `Optional[Union[str, list[str]]]` |
| `group_by` | `Optional[str]` |
| `size` | `Optional[str]` |
| `color` | `Optional[str]` |
| `labels` | `Optional[str]` |
| `values` | `Optional[str]` |
| `z` | `Optional[str]` |
| `aggregation` | `Optional[str]` |
| `sort` | `Optional[SortSpec]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### BoxQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:109`

**Purpose**: Request for plotly.box (OHLCV or generic).

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `category` | `str` |
| `open` | `Optional[str]` |
| `high` | `Optional[str]` |
| `low` | `Optional[str]` |
| `close` | `Optional[str]` |
| `y` | `Optional[str]` |
| `group_by` | `Optional[str]` |
| `sort` | `Optional[SortSpec]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### TableDataQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:125`

**Purpose**: Request for table.data.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `columns` | `list[ColumnTuple]` |
| `sort_by` | `Optional[str]` |
| `sort_order` | `str` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### PivotQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:136`

**Purpose**: Request for table.pivot — always renders via Great Tables.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `rows` | `Union[str, list[str]]` |
| `cols` | `Optional[Union[str, list[str]]]` |
| `layout` | `str` |
| `measures` | `list[MeasureTuple]` |
| `buckets` | `Optional[dict[str, BucketSpec]]` |
| `windows` | `Optional[list[WindowSpec]]` |
| `totals` | `Optional[TotalsSpec]` |
| `sort` | `Optional[SortConfig]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

| Method | Description |
|--------|-------------|
| `row_fields() -> list[str]` | Normalize rows to a list. |
| `col_fields() -> list[str]` | Normalize cols to a list (empty if None). |

### MetricQueryRequest (BaseModel)

**File**: `src/de_funk/api/models/requests.py:164`

**Purpose**: Request for cards.metric.

| Attribute | Type |
|-----------|------|
| `type` | `str` |
| `metrics` | `list[MeasureTuple]` |
| `filters` | `list[FilterSpec]` |
| `page_filters` | `Optional[PageFilters]` |
| `models` | `list[str]` |

### SeriesData (BaseModel)

**File**: `src/de_funk/api/models/requests.py:187`

**Purpose**: One series in a graphical response.

| Attribute | Type |
|-----------|------|
| `name` | `str` |
| `x` | `list` |
| `y` | `list` |
| `size` | `Optional[list]` |

### GraphicalResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:195`

**Purpose**: Response envelope for all Plotly chart types. Contains one or more `SeriesData` objects, a `truncated` flag indicating if the response was capped at `max_response_mb`, and an optional `formatting` pass-through dict for the frontend renderer.

| Attribute | Type |
|-----------|------|
| `series` | `list[SeriesData]` |
| `truncated` | `bool` |
| `formatting` | `Optional[dict[str, Any]]` |

### TableColumn (BaseModel)

**File**: `src/de_funk/api/models/requests.py:201`

**Purpose**: Column metadata for flat table responses. Carries the column key (matching SQL alias), display label, optional format code, and optional spanner group label for Great Tables rendering.

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `label` | `str` |
| `format` | `Optional[str]` |
| `group` | `Optional[str]` |

### TableResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:208`

**Purpose**: Response for `table.data` exhibits. Contains column metadata, row data as a list of lists, a `truncated` flag, and optional formatting pass-through.

| Attribute | Type |
|-----------|------|
| `columns` | `list[TableColumn]` |
| `rows` | `list[list[Any]]` |
| `truncated` | `bool` |
| `formatting` | `Optional[dict[str, Any]]` |

### ExpandableData (BaseModel)

**File**: `src/de_funk/api/models/requests.py:215`

**Purpose**: Overflow detail rows for hierarchical expand/collapse pivots.

| Attribute | Type |
|-----------|------|
| `columns` | `list[dict[str, Any]]` |
| `children` | `dict[str, list[list[Any]]]` |
| `total_rows` | `int` |

### GreatTablesResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:228`

**Purpose**: Response for all pivot exhibit types. Contains the rendered Great Tables HTML string and optional `ExpandableData` for hierarchical pivots that exceed the HTML row cap. The plugin injects the HTML directly into the DOM.

| Attribute | Type |
|-----------|------|
| `html` | `str` |
| `expandable` | `Optional[ExpandableData]` |

### MetricValue (BaseModel)

**File**: `src/de_funk/api/models/requests.py:233`

**Purpose**: A single KPI metric value with its display key, label, computed value, and optional format code (e.g. `$`, `%`, `,.0f`).

| Attribute | Type |
|-----------|------|
| `key` | `str` |
| `label` | `str` |
| `value` | `Any` |
| `format` | `Optional[str]` |

### MetricResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:240`

**Purpose**: Response for `cards.metric` exhibits. Contains a list of `MetricValue` objects, one per requested metric.

| Attribute | Type |
|-----------|------|
| `metrics` | `list[MetricValue]` |

### DimensionValuesResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:244`

**Purpose**: Response for the `/api/dimensions/{ref}` endpoint. Returns the canonical field name and a list of distinct values, used to populate sidebar filter dropdowns in the Obsidian plugin.

| Attribute | Type |
|-----------|------|
| `field` | `str` |
| `values` | `list[Any]` |

### HealthResponse (BaseModel)

**File**: `src/de_funk/api/models/requests.py:249`

**Purpose**: Response for the `/api/health` liveness endpoint. Returns a status string and API version.

| Attribute | Type |
|-----------|------|
| `status` | `str` |
| `version` | `str` |

## How to Use

### Common Operations

**Starting the API server:**

```bash
# Via the serve script (recommended)
python -m scripts.serve.run_api

# Or directly via uvicorn
uvicorn de_funk.api.main:app --host 0.0.0.0 --port 8765
```

**Querying a pivot table (POST /api/query):**

```python
import requests

payload = {
    "type": "table.pivot",
    "rows": "corporate.entity.sector",
    "measures": [
        {"key": "avg_cap", "field": "securities.stocks.market_cap", "aggregation": "AVG", "format": "$,.0f"}
    ],
    "filters": [
        {"field": "securities.stocks.exchange", "op": "in", "value": ["NYSE"]}
    ]
}
resp = requests.post("http://localhost:8765/api/query", json=payload)
# Returns: {"html": "<table>...</table>", "expandable": null}
```

**Fetching dimension values for a sidebar dropdown (GET /api/dimensions):**

```python
resp = requests.get(
    "http://localhost:8765/api/dimensions/corporate.entity.sector",
    params={"order_by": "securities.stocks.market_cap", "order_dir": "desc"}
)
# Returns: {"field": "corporate.entity.sector", "values": ["TECHNOLOGY", "HEALTHCARE", ...]}
```

**Fetching the field catalog (GET /api/domains):**

```python
resp = requests.get("http://localhost:8765/api/domains")
# Returns: {"securities.stocks": {"close": {"table": "fact_daily_prices", "column": "close", ...}}, ...}
```

### Integration Examples

**Obsidian plugin exhibit block (YAML in markdown) -> API call:**

The plugin parses the YAML block, serializes it as JSON, and POSTs to `/api/query`:

```yaml
# In Obsidian markdown:
```de_funk
type: plotly.line
x: securities.stocks.trade_date
y: securities.stocks.close
group_by: securities.stocks.ticker
filters:
  - field: securities.stocks.ticker
    op: in
    value: [AAPL, MSFT]
```

This becomes a POST to `/api/query` with the equivalent JSON payload. The `GraphicalHandler` resolves fields via `FieldResolver`, builds SQL against Silver Delta tables, and returns `GraphicalResponse` with series data.

**Sidebar filters cascading into exhibit queries:**

Context filters from the sidebar are merged into each exhibit's `filters` array. The `page_filters.ignore` field allows individual exhibits to opt out of specific sidebar filters:

```python
payload = {
    "type": "table.pivot",
    "rows": "corporate.entity.company_name",
    "measures": [{"key": "revenue", "field": "corporate.finance.total_revenue", "aggregation": "SUM"}],
    "filters": [
        {"field": "corporate.entity.sector", "op": "in", "value": ["TECHNOLOGY"]}
    ],
    "page_filters": {"ignore": []}  # inherit all sidebar filters
}
```

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `400: Unknown block type 'xxx'` | The `type` field in the payload does not match any handler's `handles` set | Check valid types: `table.pivot`, `table.data`, `plotly.line`, `plotly.bar`, `cards.metric`, `plotly.box`, etc. |
| `400: 'type' field is required` | Payload is missing the `type` key | Ensure the exhibit block has a `type:` line |
| `422: Validation error` | Pydantic rejected the payload (wrong field types, missing required fields) | Check the error detail for which field failed validation (e.g. `rows` must be str or list) |
| `500: Query failed: Catalog Error: Table ... does not exist` | Silver Delta table path does not exist or is not built yet | Run `python -m scripts.build.build_models --model <domain>` to build the missing Silver tables |
| `500: Pivot column cross-product has N+ unique combinations` | Unfiltered pivot has too many distinct column values (>200) | Add filters to reduce the column dimension cardinality |
| Pivot response is truncated / missing rows | Result exceeded `MAX_HTML_ROWS` (400) without totals enabled | Either add `totals: {rows: true}` for expandable mode, or add filters to reduce row count |
| Graphical response has `"truncated": true` | Series data exceeded `max_response_mb` cap | Add filters to reduce data volume, or increase `api.max_response_mb` in storage.json |
| Dimension endpoint returns empty values | Silver table exists but has no data for that column, or field reference is wrong | Verify the field reference with `GET /api/domains` and check that the Silver table has data |

### Debug Checklist

- [ ] Verify the API is running: `curl http://localhost:8765/api/health`
- [ ] Check field catalog: `curl http://localhost:8765/api/domains` to confirm your domain.field references are valid
- [ ] Check API logs for the SQL being generated: look for `Graphical SQL:`, `Pivot SQL:`, `Table SQL:`, or `Metrics SQL:` in debug output
- [ ] Verify Silver tables exist on disk at the path shown in the resolver catalog
- [ ] For pivot issues, check the column discovery pre-query: look for `Pivot pre-query (col discovery)` in debug logs
- [ ] For response size issues, check for `truncated to N rows` or `series capped to N points` in info logs
- [ ] For join issues, check that all referenced fields belong to domains connected in the domain graph

### Common Pitfalls

1. **Using `rows` as a string vs list in pivots**: `PivotQueryRequest.rows` accepts both `str` and `list[str]`. Multi-level pivots require a list (e.g. `rows: [corporate.entity.sector, corporate.entity.company_name]`), but forgetting the list brackets sends a single dotted string.

2. **Computed measures referencing undefined keys**: In `MeasureTuple`, the `field` can be a dict like `{fn: "divide", args: [revenue, shares]}`. The `args` reference prior measure keys, which must appear earlier in the `measures` list. Out-of-order references produce NULL values.

3. **Filter domain scoping**: Filters on fields outside the exhibit's core domains are silently dropped. If a filter seems to have no effect, check that its domain is reachable from the exhibit's core fields via the domain graph.

4. **Layout affects aggregation semantics**: The `layout` field (`by_measure`, `by_column`, `by_dimension`) controls both visual layout (spanner labels) and the order of conditional aggregation columns. Changing layout changes the column order in the SQL SELECT, which must match `_build_wide_columns` metadata.

5. **CORS errors from Obsidian**: The CORS middleware only allows `app://obsidian.md` and local addresses. If testing from a different origin, add it to the `allow_origins` list in `main.py`.

## File Reference

| File | Purpose | Key Exports |
|------|---------|-------------|
| `src/de_funk/api/handlers/base.py` | ExhibitHandler — abstract base class for all exhibit execution families. | `ExhibitHandler` |
| `src/de_funk/api/handlers/box.py` | BoxHandler — executes box plot and OHLCV candlestick queries. | `BoxHandler` |
| `src/de_funk/api/handlers/formatting.py` | Shared formatting utilities for all exhibit handlers. | — |
| `src/de_funk/api/handlers/graphical.py` | GraphicalHandler — executes plotly.* chart queries. | `GraphicalHandler` |
| `src/de_funk/api/handlers/gt_formatter.py` | Great Tables formatter — converts pivot DataFrames into styled HTML. | — |
| `src/de_funk/api/handlers/metrics.py` | MetricsHandler — executes cards.metric / KPI queries. | `MetricsHandler` |
| `src/de_funk/api/handlers/pivot.py` | PivotHandler — single exhibit handler for all pivot table queries. | `PivotHandler` |
| `src/de_funk/api/handlers/reshape.py` | Pivot reshape utilities — column key construction and 1D window calculations. | — |
| `src/de_funk/api/handlers/table_data.py` | TableDataHandler — executes flat table.data queries. | `TableDataHandler` |
| `src/de_funk/api/models/requests.py` | Pydantic request and response models for the de_funk API. | `FilterSpec`, `PageFilters`, `SortSpec`, `BucketSpec`, `WindowSpec`, `TotalsSpec`, `SortConfig`, `MeasureTuple`, `ColumnTuple`, `GraphicalQueryRequest`, `BoxQueryRequest`, `TableDataQueryRequest`, `PivotQueryRequest`, `MetricQueryRequest`, `SeriesData`, `GraphicalResponse`, `TableColumn`, `TableResponse`, `ExpandableData`, `GreatTablesResponse`, `MetricValue`, `MetricResponse`, `DimensionValuesResponse`, `HealthResponse` |
| `src/de_funk/api/routers/bronze.py` | Bronze layer API routes — query, dimensions, and catalog for raw Bronze data. | — |
| `src/de_funk/api/routers/dimensions.py` | GET /api/dimensions/{ref} — return distinct values for a domain.field (for sidebar dropdowns). | — |
| `src/de_funk/api/routers/domains.py` | GET /api/domains — return the full field catalog for all domains. | — |
| `src/de_funk/api/routers/health.py` | GET /api/health — liveness check. | — |
| `src/de_funk/api/routers/models.py` | Model registry endpoint — browse trained ML models. | — |
| `src/de_funk/api/routers/predict.py` | Model prediction endpoint — serve inference from trained artifacts. | — |
| `src/de_funk/api/routers/query.py` | POST /api/query — registry-based dispatch to exhibit handlers. | — |
| `src/de_funk/api/main.py` | de_funk FastAPI application. | — |
