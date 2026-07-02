# de_funk API -- A Practical Walkthrough

**Base URL**: `http://localhost:8765/api`

This guide walks through the de_funk query API the way you would explore it in a
Jupyter notebook: start the server, poke at endpoints with curl, then graduate
to Python `requests` and finally understand the internals.

---

## Getting Started

Start the server and verify it responds.

```bash
# Start the API (development mode with auto-reload)
python -m scripts.serve.run_api --port 8765 --reload

# Verify it's running
curl http://localhost:8765/api/health
```

Expected output:

```json
{"status": "ok", "version": "1.0"}
```

The server reads `configs/storage.json` on startup to find Silver table paths,
Bronze provider configs, and runtime limits. If required keys are missing, it
exits with an explicit error. Interactive API docs are available at
`http://localhost:8765/api/docs` (Swagger) and
`http://localhost:8765/api/redoc` (ReDoc).

The API serves two query layers:
- **Silver** (`/api/query`) — dimensional star schemas with automatic joins via BFS
- **Bronze** (`/api/bronze/query`) — raw provider tables queried by `provider.endpoint.field` references

**Source files**:
- Server entry: `scripts/serve/run_api.py`
- App factory: `src/de_funk/api/main.py`
- Silver resolver: `src/de_funk/api/resolver.py`
- Bronze resolver: `src/de_funk/api/bronze_resolver.py`
- Bronze router: `src/de_funk/api/routers/bronze.py`

---

## Part 1: Endpoints

### GET /api/health

Liveness check. Returns immediately, no database work.

```bash
curl http://localhost:8765/api/health
```

```json
{"status": "ok", "version": "1.0"}
```

Python equivalent:

```python
import requests

resp = requests.get("http://localhost:8765/api/health")
print(resp.json())
# {'status': 'ok', 'version': '1.0'}
```

**Source**: `src/de_funk/api/routers/health.py`

---

### GET /api/domains

List every domain, field, table, column, and format code the resolver knows
about. This is the field catalog -- the basis for building queries.

```bash
curl http://localhost:8765/api/domains | python -m json.tool
```

Response structure:

```json
{
  "municipal.public_safety": {
    "fields": {
      "ward":           {"table": "fact_crimes", "column": "ward", "format": null},
      "community_area": {"table": "fact_crimes", "column": "community_area", "format": null},
      "arrest_made":    {"table": "fact_crimes", "column": "arrest_made", "format": null}
    }
  },
  "municipal.finance": {
    "fields": {
      "amount":              {"table": "fact_budget_events", "column": "amount", "format": "$"},
      "department_description": {"table": "fact_budget_events", "column": "department_description", "format": null},
      "fiscal_year":         {"table": "fact_budget_events", "column": "fiscal_year", "format": null}
    }
  },
  "municipal.regulatory": {
    "fields": {
      "result":        {"table": "fact_food_inspections", "column": "result", "format": null},
      "facility_name": {"table": "dim_facility", "column": "facility_name", "format": null},
      "risk_level":    {"table": "dim_facility", "column": "risk_level", "format": null}
    }
  }
}
```

Python -- enumerate all domains:

```python
import requests

domains = requests.get("http://localhost:8765/api/domains").json()
for name, info in domains.items():
    n_fields = len(info["fields"])
    tables = {f["table"] for f in info["fields"].values()}
    print(f"{name}: {n_fields} fields across {len(tables)} tables")

# municipal.public_safety: 15 fields across 3 tables
# municipal.finance: 22 fields across 5 tables
# municipal.geospatial: 18 fields across 4 tables
# ...
```

**Source**: `src/de_funk/api/routers/domains.py` delegates to
`FieldResolver.get_field_catalog()` in `src/de_funk/api/resolver.py`.

---

### GET /api/dimensions/{field}

Return sorted distinct values for a single field. Powers sidebar filter
dropdowns.

**Path parameter**: `field` -- fully qualified domain.field reference, e.g.
`municipal.geospatial.community_name`. Slashes in the URL path are converted to dots
internally, so `municipal.geospatial/community_name` also works.

**Query parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_by` | string | Optional domain.field to rank values by (e.g. `municipal.public_safety.crime_count`) |
| `order_dir` | string | `asc` or `desc` (default `desc`) |
| `filters` | string | JSON array of `{field, value}` context filters |

#### Basic usage

```bash
# Get all community area names
curl "http://localhost:8765/api/dimensions/municipal.geospatial.community_name"
```

```json
{
  "field": "municipal.geospatial.community_name",
  "values": ["ALBANY PARK", "ARCHER HEIGHTS", "ARMOUR SQUARE", "ASHBURN",
             "AUBURN GRESHAM", "AUSTIN", "AVALON PARK", "AVONDALE",
             "BELMONT CRAGIN", "BEVERLY"],
  "count": 77
}
```

#### With context filters (cascading)

Restrict returned values to those consistent with active page filters. For
example, get only crime types where an arrest was made:

```bash
# URL-encoded: filters=[{"field":"municipal.public_safety.arrest_made","value":true}]
curl "http://localhost:8765/api/dimensions/municipal.public_safety.primary_type?filters=%5B%7B%22field%22%3A%22municipal.public_safety.arrest_made%22%2C%22value%22%3Atrue%7D%5D"
```

#### Ordered by measure

```bash
# Community areas sorted by descending crime count
curl "http://localhost:8765/api/dimensions/municipal.geospatial.community_name?order_by=municipal.public_safety.crime_count&order_dir=desc"
```

Python equivalents:

```python
import json
import requests

BASE = "http://localhost:8765/api"

# Plain distinct values
resp = requests.get(f"{BASE}/dimensions/municipal.geospatial.community_name")
print(resp.json()["values"][:5])
# ['ALBANY PARK', 'ARCHER HEIGHTS', 'ARMOUR SQUARE', 'ASHBURN', 'AUBURN GRESHAM']

# Cascading: only crime types with arrests
resp = requests.get(f"{BASE}/dimensions/municipal.public_safety.primary_type", params={
    "filters": json.dumps([
        {"field": "municipal.public_safety.arrest_made", "value": True}
    ])
})
print(f"{len(resp.json()['values'])} crime types with arrests")

# Ordered by crime count
resp = requests.get(f"{BASE}/dimensions/municipal.geospatial.community_name", params={
    "order_by": "municipal.public_safety.crime_count",
    "order_dir": "desc",
})
print(resp.json()["values"][:10])
# ['AUSTIN', 'SOUTH SHORE', 'NEAR NORTH SIDE', 'NEAR WEST SIDE', 'NORTH LAWNDALE', ...]
```

**Source**: `src/de_funk/api/routers/dimensions.py` calls
`Engine.distinct_values()` or `Engine.distinct_values_by_measure()`
in `src/de_funk/api/executor.py`.

---

### POST /api/query

Execute an exhibit query. The `type` field selects the handler, which
determines what fields are required, what SQL is generated, and the
response shape.

**Full request body**:

```python
import requests

response = requests.post("http://localhost:8765/api/query", json={
    "type": "plotly.line",
    "x": "temporal.year",
    "y": ["municipal.public_safety.crime_count"],
    "aggregation": "sum",
    "filters": [
        {"field": "municipal.public_safety.primary_type", "operator": "eq", "value": "THEFT"}
    ],
    "sort": {"by": "temporal.year", "order": "asc"},
})
print(response.json())
```

**Payload fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | Exhibit type key (see Part 3 for the full list) |
| `x` | string | varies | X-axis domain.field (graphical types) |
| `y` | string or string[] | varies | Y-axis measure field(s) (graphical types) |
| `rows` | string or string[] | varies | Row dimension field(s) (pivot, table types) |
| `cols` | string or string[] | no | Column dimension field(s) (2D pivots) |
| `measures` | MeasureTuple[] | varies | Measure definitions with key, field, aggregation, format, label |
| `metrics` | MeasureTuple[] | varies | Metric definitions (cards.metric type) |
| `columns` | ColumnTuple[] | varies | Column definitions (table.data type) |
| `filters` | FilterSpec[] | no | Filter predicates (see Part 4) |
| `aggregation` | string | no | Default aggregation for graphical types (AVG, SUM, COUNT, COUNT_DISTINCT) |
| `group_by` | string | no | Grouping dimension for multi-series charts |
| `sort` | SortSpec | no | Sort directive |
| `totals` | TotalsSpec | no | Backend-computed totals (`{rows: true, cols: true}`) |
| `windows` | WindowSpec[] | no | Row-over-row calculations (pct_change, diff) |
| `layout` | string | no | Pivot layout: `by_measure`, `by_column`, `by_dimension` |
| `page_filters` | PageFilters | no | Page-level filter inheritance control |
| `models` | string[] | no | Reserved for future domain scoping |
| `formatting` | object | no | Pass-through formatting hints for the frontend |

**Source**: `src/de_funk/api/routers/query.py` dispatches to the handler
registry. Request models are defined in `src/de_funk/api/models/requests.py`.

---

## Part 1b: Bronze Query Endpoints

The Bronze query layer provides direct access to raw provider data without
requiring Silver model builds. Field references use `provider.endpoint.field`
format (e.g., `chicago.crimes.primary_type`).

**Source files**:
- Resolver: `src/de_funk/api/bronze_resolver.py`
- Router: `src/de_funk/api/routers/bronze.py`
- Handlers: `src/de_funk/api/handlers/bronze_*.py`

### GET /api/bronze/endpoints

List all available Bronze providers, endpoints, and fields.

```bash
curl http://localhost:8765/api/bronze/endpoints | python -m json.tool
```

Response structure:

```json
{
  "chicago": {
    "endpoints": {
      "crimes": {
        "fields": ["id", "case_number", "date", "primary_type", "description",
                   "arrest", "domestic", "district", "ward", "year"],
        "row_count": 8478133
      },
      "budget_appropriations": {
        "fields": ["fund_code", "department_description", "amount"],
        "row_count": 4521
      }
    }
  },
  "alpha_vantage": {
    "endpoints": {
      "daily_adjusted": { "fields": ["date", "open", "high", "low", "close", "volume"], "row_count": 2841000 }
    }
  }
}
```

**Source**: `src/de_funk/api/routers/bronze.py` delegates to
`BronzeResolver.get_endpoints_catalog()`.

---

### GET /api/bronze/dimensions/{provider}/{endpoint}/{field}

Return sorted distinct values for a Bronze field. Powers sidebar filter
dropdowns on `layer: bronze` pages.

```bash
curl "http://localhost:8765/api/bronze/dimensions/chicago/crimes/primary_type"
```

```json
{
  "field": "chicago.crimes.primary_type",
  "values": ["ARSON", "ASSAULT", "BATTERY", "BURGLARY", "CRIM SEXUAL ASSAULT",
             "CRIMINAL DAMAGE", "CRIMINAL TRESPASS", "DECEPTIVE PRACTICE",
             "HOMICIDE", "KIDNAPPING", "MOTOR VEHICLE THEFT", "NARCOTICS",
             "OTHER OFFENSE", "ROBBERY", "SEX OFFENSE", "THEFT",
             "WEAPONS VIOLATION"]
}
```

**Query parameters**: Same as Silver dimensions — `order_by`, `order_dir`, `filters`.

**Source**: `src/de_funk/api/routers/bronze.py` calls
`BronzeResolver.distinct_values()`.

---

### POST /api/bronze/query

Execute a query against Bronze tables. Same exhibit types as Silver
(`plotly.line`, `plotly.bar`, `table.pivot`, `cards.metric`, etc.), but field
references use `provider.endpoint.field` instead of `domain.field`.

**Key difference from Silver**: No automatic joins. All fields in a single
query must come from the same endpoint (same Bronze table). Cross-endpoint
queries are not supported — use Silver for that.

**Metric cards example**:

```bash
curl -X POST http://localhost:8765/api/bronze/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "cards.metric",
    "metrics": [
      {"key": "total", "field": "chicago.crimes.id", "aggregation": "count", "label": "Total Incidents"},
      {"key": "arrests", "field": "chicago.crimes.arrest", "aggregation": "sum", "label": "Total Arrests"},
      {"key": "districts", "field": "chicago.crimes.district", "aggregation": "count_distinct", "label": "Districts"}
    ]
  }'
```

```json
{
  "metrics": [
    {"key": "total", "label": "Total Incidents", "value": 8478133, "format": null},
    {"key": "arrests", "label": "Total Arrests", "value": 2133691, "format": null},
    {"key": "districts", "label": "Districts", "value": 25, "format": null}
  ]
}
```

**Bar chart example**:

```bash
curl -X POST http://localhost:8765/api/bronze/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "plotly.bar",
    "x": "chicago.crimes.primary_type",
    "y": "chicago.crimes.id",
    "aggregation": "count"
  }'
```

**Line chart example**:

```bash
curl -X POST http://localhost:8765/api/bronze/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "plotly.line",
    "x": "chicago.crimes.year",
    "y": "chicago.crimes.id",
    "aggregation": "count"
  }'
```

**Pivot table example**:

```bash
curl -X POST http://localhost:8765/api/bronze/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "table.pivot",
    "rows": "chicago.crimes.primary_type",
    "measures": [
      {"key": "incidents", "field": "chicago.crimes.id", "aggregation": "count", "label": "Incidents"}
    ]
  }'
```

**How Bronze resolution works**:

```
Field: "chicago.crimes.primary_type"
  |
  v
1. Split: provider="chicago", endpoint="crimes", field="primary_type"
2. Lookup: BronzeResolver index -> bronze_path=/shared/storage/bronze/chicago/crimes
3. Validate: "primary_type" exists in endpoint schema
4. Return: BronzeResolvedField(table="chicago__crimes", column="primary_type", path=...)
```

All fields in a query are validated against the same endpoint. If fields from
different endpoints are mixed, the query returns a 400 error.

**Source**: `src/de_funk/api/routers/bronze.py` dispatches to the same handler
registry used by Silver, but with `BronzeResolver` for field resolution.

---

## Part 2: Query Flow (Step-by-Step)

Here is exactly what happens when `POST /api/query` is called. Follow along
in the source to see each step.

```
POST /api/query
  |
  v
1. Parse "type" field from payload
   |  routers/query.py: block_type = payload.get("type")
   v
2. Look up handler from registry
   |  registry.get("plotly.line") -> GraphicalHandler
   |  Source: handlers/__init__.py (HandlerRegistry)
   v
3. Handler validates request via Pydantic model
   |  GraphicalQueryRequest(**payload)
   |  Source: models/requests.py
   v
4. Resolve field references via FieldResolver
   |  resolver.resolve("municipal.public_safety.crime_count")
   |    -> FieldRef: domain="municipal.public_safety", field="crime_count"
   |    -> ResolvedField(table=fact_crimes, column=incident_id,
   |                     silver_path=/shared/storage/silver/municipal/public_safety/facts/fact_crimes)
   |  resolver.resolve("temporal.year")
   |    -> ResolvedField(table=dim_calendar, column=year,
   |                     silver_path=/shared/storage/silver/temporal/dims/dim_calendar)
   |  Source: resolver.py (FieldResolver._build_index, FieldRef._match_domain)
   v
5. Collect tables: {fact_crimes, dim_calendar, dim_crime_type}
   |  Includes filter-referenced tables
   |  Source: executor.py (_collect_tables_with_domains)
   v
6. Build FROM clause with auto-joins via BFS
   |  fact_crimes (base)
   |  JOIN dim_calendar ON fact.date_id = dim_calendar.date_id
   |  JOIN dim_crime_type ON fact.crime_type_id = dim_crime_type.crime_type_id
   |  Source: executor.py (_build_from, resolver.find_join_path)
   v
7. Build WHERE clause from filter specs
   |  WHERE "dim_crime_type"."primary_type" = 'THEFT'
   |  Filters referencing tables not in FROM are silently skipped
   |  Source: executor.py (_build_where)
   v
8. Build SELECT / GROUP BY (handler-specific)
   |  SELECT "dim_calendar"."year" AS x, COUNT(DISTINCT "fact_crimes"."incident_id") AS y0
   |  GROUP BY "dim_calendar"."year"
   |  ORDER BY "dim_calendar"."year" ASC
   v
9. Execute SQL via DuckDB
   |  delta_scan('/shared/storage/silver/municipal/public_safety/facts/fact_crimes') AS "fact_crimes"
   |  Source: executor.py (_execute, _safe_scan)
   v
10. Format response (handler-specific)
    |  {"series": [{"name": "Series 1", "x": [2020, 2021, ...], "y": [68421, 72104, ...]}],
    |   "truncated": false}
```

**Key internals**:

- **FieldResolver** (`src/de_funk/api/resolver.py`) scans `domains/models/`
  on first use and builds an index of `{domain: {field: (table, format, subdir)}}`.
  It also populates a bidirectional join graph from `graph.edges` in each
  `model.md` file.

- **BFS join resolution**: `find_join_path(src, dst, allowed_domains)` walks
  the join graph to find the shortest chain of JOINs between any two tables.
  Domain scoping prevents unrelated tables from being pulled in (e.g. a
  corporate filter on a municipal exhibit).

- **delta_scan vs read_parquet**: `_safe_scan()` probes each path once,
  caching whether `delta_scan()` succeeds. Falls back to
  `read_parquet('path/*.parquet')` automatically.

---

## Part 3: Exhibit Type Handlers

Each handler is a class that inherits from both `ExhibitHandler` (abstract
interface) and `Engine` (shared DuckDB infrastructure). All handlers live
in `src/de_funk/api/handlers/`.

### GraphicalHandler

**Source**: `src/de_funk/api/handlers/graphical.py`

**Types**: `plotly.line`, `line`, `line_chart`, `plotly.bar`, `bar`, `bar_chart`,
`plotly.scatter`, `scatter`, `plotly.area`, `area`, `plotly.pie`, `pie`,
`plotly.heatmap`, `heatmap`

**Request fields**: `x`, `y` (string or list), `group_by`, `aggregation`
(AVG, SUM, COUNT, COUNT_DISTINCT), `sort`, `filters`

**SQL pattern**:

```sql
SELECT "dim_calendar"."year" AS x, COUNT(DISTINCT "fact_crimes"."incident_id") AS y0
FROM delta_scan('...') AS "fact_crimes"
JOIN delta_scan('...') AS "dim_calendar" ON "fact_crimes"."date_id" = "dim_calendar"."date_id"
JOIN delta_scan('...') AS "dim_crime_type" ON "fact_crimes"."crime_type_id" = "dim_crime_type"."crime_type_id"
WHERE "dim_crime_type"."primary_type" = 'THEFT'
GROUP BY "dim_calendar"."year"
ORDER BY "dim_calendar"."year" ASC
```

With `group_by`, a `grp` column is added and the result is pivoted into
per-group series.

**Complete curl example**:

```bash
curl -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "plotly.line",
    "x": "temporal.year",
    "y": ["municipal.public_safety.crime_count"],
    "aggregation": "sum",
    "filters": [
      {"field": "municipal.public_safety.primary_type", "operator": "eq", "value": "THEFT"}
    ]
  }'
```

**Response**:

```json
{
  "series": [
    {
      "name": "Series 1",
      "x": [2020, 2021, 2022, 2023, 2024],
      "y": [48213, 52870, 61445, 68421, 72104],
      "size": null
    }
  ],
  "truncated": false,
  "formatting": null
}
```

**Python**:

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "plotly.bar",
    "x": "municipal.geospatial.community_name",
    "y": ["municipal.public_safety.crime_count"],
    "aggregation": "sum",
})
data = resp.json()
for series in data["series"]:
    print(f"{series['name']}: {len(series['x'])} groups")
```

**Multi-series with group_by**:

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "plotly.line",
    "x": "temporal.year",
    "y": ["municipal.public_safety.crime_count"],
    "group_by": "municipal.public_safety.crime_category",
    "aggregation": "sum",
})
# Each crime category (VIOLENT, PROPERTY, OTHER) becomes a separate series
for s in resp.json()["series"]:
    print(f"{s['name']}: {len(s['x'])} points")
```

---

### BoxHandler

**Source**: `src/de_funk/api/handlers/box.py`

**Types**: `plotly.box`, `box`, `ohlcv`, `candlestick`

**Dual-mode detection**: When all four of `open`, `high`, `low`, `close` are
present in the payload, the handler enters OHLCV candlestick mode. Otherwise
it runs a generic box plot with `category` and `y`.

**Generic box plot request** (the primary mode for municipal data):

```bash
curl -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "plotly.box",
    "category": "municipal.geospatial.community_name",
    "y": "municipal.housing.estimated_cost",
    "filters": [
      {"field": "temporal.year", "operator": "eq", "value": 2024}
    ]
  }'
```

**Response**:

```json
{
  "series": [
    ["LOOP", 850000],
    ["LOOP", 1200000],
    ["NEAR NORTH SIDE", 450000],
    ["NEAR NORTH SIDE", 2300000]
  ],
  "mode": "box",
  "formatting": {}
}
```

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "plotly.box",
    "category": "municipal.finance.org_unit_name",
    "y": "municipal.finance.amount",
})
# mode will be "box"
```

**SQL**: Generic box mode selects `category, y` for client-side box-whisker
computation. OHLCV mode selects raw `category, open, high, low, close` columns
with no aggregation.

---

### TableDataHandler

**Source**: `src/de_funk/api/handlers/table_data.py`

**Types**: `table.data`, `data_table`

**What it does**: Flat tabular SELECT with optional per-column aggregation. No
pivoting, no GROUP BY unless at least one column has an aggregation.

**Request fields**: `columns` (list of ColumnTuple with key, field, optional
aggregation, format, label), `sort_by`, `sort_order`, `filters`

**curl example**:

```bash
curl -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "table.data",
    "columns": [
      {"key": "community", "field": "municipal.geospatial.community_name"},
      {"key": "crime_type", "field": "municipal.public_safety.primary_type"},
      {"key": "ward", "field": "municipal.public_safety.ward"},
      {"key": "crimes", "field": "municipal.public_safety.crime_count", "aggregation": "sum", "format": "#,##0"}
    ],
    "sort_by": "municipal.public_safety.crime_count",
    "sort_order": "desc",
    "filters": [
      {"field": "temporal.year", "operator": "eq", "value": 2024}
    ]
  }'
```

**Response**:

```json
{
  "columns": [
    {"key": "community", "label": "Community", "format": null, "group": null},
    {"key": "crime_type", "label": "Crime Type", "format": null, "group": null},
    {"key": "ward", "label": "Ward", "format": null, "group": null},
    {"key": "crimes", "label": "Crimes", "format": "#,##0", "group": null}
  ],
  "rows": [
    ["AUSTIN", "THEFT", 29, 3412],
    ["NEAR NORTH SIDE", "THEFT", 42, 3105]
  ],
  "truncated": false,
  "formatting": null
}
```

**Python**:

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "table.data",
    "columns": [
        {"key": "department", "field": "municipal.finance.org_unit_name"},
        {"key": "avg_budget", "field": "municipal.finance.amount",
         "aggregation": "avg", "format": "$,.2f"},
    ],
    "filters": [
        {"field": "municipal.finance.event_type", "operator": "eq", "value": "APPROPRIATION"}
    ],
})
for row in resp.json()["rows"][:5]:
    print(f"{row[0]}: {row[1]}")
```

When any column specifies an `aggregation`, the handler adds GROUP BY on the
non-aggregated columns automatically.

---

### PivotHandler

**Source**: `src/de_funk/api/handlers/pivot.py`

**Types**: `table.pivot`, `pivot`, `pivot_table`, `great_table`, `great_tables`, `gt`

The most complex handler. Supports:
- 1D pivots (rows only, measures as flat columns)
- 2D pivots (rows x cols) via SQL conditional aggregation
- Three layout modes: `by_measure`, `by_column`, `by_dimension`
- GROUPING SETS for row/column totals
- Window calculations (pct_change, diff) via DuckDB `LAG()`
- Expandable hierarchical pivots for large datasets (>400 rows)
- Sort by resolved field (e.g. sort by display_order dimension)

**Request fields**: `rows`, `cols`, `measures` (MeasureTuple[]), `layout`,
`totals`, `windows`, `sort`, `buckets`, `filters`

#### 1D Pivot

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "table.pivot",
    "rows": ["municipal.geospatial.community_name"],
    "measures": [
        {"key": "total_crimes", "field": "municipal.public_safety.crime_count",
         "aggregation": "sum", "format": "#,##0", "label": "Total Crimes"},
        {"key": "arrest_rate", "field": "municipal.public_safety.arrest_rate",
         "aggregation": "avg", "format": "#,##0.0%", "label": "Arrest Rate"},
    ],
})
# Returns HTML rendered by Great Tables
print(resp.json().keys())
# dict_keys(['html', 'expandable'])
```

**SQL generated (1D)**:

```sql
SELECT "dim_community_area"."community_name" AS row_key_0,
       COUNT(DISTINCT "fact_crimes"."incident_id") AS total_crimes,
       AVG(100.0 * SUM(CASE WHEN arrest_made THEN 1 ELSE 0 END) / COUNT(*)) AS arrest_rate
FROM delta_scan('...') AS "fact_crimes"
JOIN delta_scan('...') AS "dim_community_area" ON ...
GROUP BY "dim_community_area"."community_name"
ORDER BY row_key_0
```

#### 2D Pivot

When `cols` is present, the handler pre-queries distinct column combinations,
then generates conditional aggregation with `FILTER (WHERE ...)` clauses.

```bash
curl -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "table.pivot",
    "rows": ["municipal.finance.org_unit_name"],
    "cols": ["temporal.year"],
    "measures": [
      {"key": "budget", "field": "municipal.finance.amount",
       "aggregation": "sum", "format": "$,.0f"}
    ],
    "layout": "by_column"
  }'
```

**SQL generated (2D, conditional aggregation)**:

```sql
SELECT "dim_department"."org_unit_name" AS row_key_0,
       SUM("fact_budget_events"."amount") FILTER (WHERE "dim_calendar"."year" = 2022) AS "2022|budget",
       SUM("fact_budget_events"."amount") FILTER (WHERE "dim_calendar"."year" = 2023) AS "2023|budget",
       SUM("fact_budget_events"."amount") FILTER (WHERE "dim_calendar"."year" = 2024) AS "2024|budget"
FROM delta_scan('...') AS "fact_budget_events"
JOIN ...
GROUP BY "dim_department"."org_unit_name"
ORDER BY row_key_0
```

The column alias pattern is `"{col_value}|{measure_key}"` so the frontend
knows how to build spanners and sub-columns.

#### Layout modes

| Layout | Outer grouping (spanners) | Inner grouping (sub-columns) |
|--------|--------------------------|------------------------------|
| `by_measure` (default) | Measure labels | Column dimension values |
| `by_column` | Column dimension values | Measure labels |
| `by_dimension` | First column dimension | Remaining column values |

#### With totals and windows

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "table.pivot",
    "rows": ["municipal.finance.org_unit_name"],
    "cols": ["temporal.year"],
    "measures": [
        {"key": "budget", "field": "municipal.finance.amount",
         "aggregation": "sum", "format": "$,.0f"},
    ],
    "totals": {"rows": True},
    "windows": [
        {"key": "yoy", "source": "budget", "type": "pct_change", "label": "YoY %"}
    ],
    "layout": "by_column",
})
```

The window calculation wraps the base query in a CTE and uses `LAG()`:

```sql
WITH pivot_base AS (
    SELECT row_key_0,
           SUM(amount) FILTER (WHERE year = 2023) AS "2023|budget",
           SUM(amount) FILTER (WHERE year = 2024) AS "2024|budget"
    FROM ... GROUP BY GROUPING SETS ((row_key_0), ())
    ORDER BY row_key_0
)
SELECT *,
       ROUND(("2024|budget" - LAG("2024|budget") OVER (ORDER BY row_key_0))
             / NULLIF(LAG("2024|budget") OVER (ORDER BY row_key_0), 0), 4) AS "2024|yoy"
FROM pivot_base
```

#### Expandable mode

When the result exceeds 400 rows AND `totals.rows` is true AND there are
multiple row fields, the handler splits the result:
- **HTML**: subtotal/total rows only (rendered via Great Tables)
- **JSON**: detail rows keyed by parent value, for client-side expand/collapse

```json
{
  "html": "<table>...</table>",
  "expandable": {
    "columns": [{"key": "row_key_0", "label": "Community Area"}, {"key": "budget", "label": "Budget", "format": "$,.0f"}],
    "children": {
      "AUSTIN": [["AUSTIN", "APPROPRIATION", 15000000], ["AUSTIN", "REVENUE", 12000000]],
      "LOOP": [["LOOP", "APPROPRIATION", 28000000]]
    },
    "total_rows": 1200
  }
}
```

The 400-row cap (`MAX_HTML_ROWS`) and 200-column cap (`MAX_PIVOT_COLUMNS`) are
defined at the top of `pivot.py`.

**Response**: Always a `GreatTablesResponse` with an `html` field (server-side
rendered HTML table) and an optional `expandable` field.

---

### MetricsHandler

**Source**: `src/de_funk/api/handlers/metrics.py`

**Types**: `cards.metric`, `kpi`, `metric_cards`

**What it does**: Returns a single aggregated row. Supports computed measures
(divide, subtract, multiply via the computation catalog in
`src/de_funk/api/measures.py`). No grouping, no window functions.

**Request fields**: `metrics` (MeasureTuple[]), `filters`

**curl example**:

```bash
curl -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "type": "cards.metric",
    "metrics": [
      {"key": "total_budget", "field": "municipal.finance.amount",
       "aggregation": "sum", "format": "$,.0f", "label": "Total Budget"},
      {"key": "crime_count", "field": "municipal.public_safety.crime_count",
       "aggregation": "sum", "format": "#,##0", "label": "Total Crimes"},
      {"key": "dept_count", "field": "municipal.finance.department_count",
       "aggregation": "sum", "label": "Departments"}
    ],
    "filters": [
      {"field": "temporal.year", "operator": "eq", "value": 2024}
    ]
  }'
```

**Response**:

```json
{
  "metrics": [
    {"key": "total_budget", "label": "Total Budget", "value": 16800000000, "format": "$,.0f"},
    {"key": "crime_count", "label": "Total Crimes", "value": 261742, "format": "#,##0"},
    {"key": "dept_count", "label": "Departments", "value": 35, "format": null}
  ]
}
```

**Computed measures** can reference prior measures by key. The computation
catalog (`src/de_funk/api/measures.py`) supports these functions:

| Function | Template | Example |
|----------|----------|---------|
| `divide` | `a / NULLIF(b, 0)` | Budget per department |
| `subtract` | `from - subtract` | Budget surplus |
| `multiply` | `a * by` | Weighted score |
| `add` | `f1 + f2 + ...` | Combined total |
| `rate` | `events / NULLIF(exposed, 0)` | Arrest rate |
| `delta` | `of - LAG(of)` | Period change (window) |
| `pct_delta` | `(of - LAG(of)) / LAG(of)` | Percent change (window) |
| `share` | `of / SUM(total)` | Share of total (window) |

```python
# Computed measure example: budget per department
resp = requests.post(f"{BASE}/query", json={
    "type": "cards.metric",
    "metrics": [
        {"key": "total_budget", "field": "municipal.finance.amount",
         "aggregation": "sum", "format": "$,.0f"},
        {"key": "departments", "field": "municipal.finance.org_unit_name",
         "aggregation": "count_distinct"},
        {"key": "budget_per_dept", "field": {"fn": "divide", "a": "total_budget", "b": "departments"},
         "format": "$,.0f", "label": "Budget per Department"},
    ],
})
```

---

## Part 4: Filter Operators

Filters are applied as WHERE clauses. Every handler accepts a `filters` array.

| Operator | SQL | Example |
|----------|-----|---------|
| `eq` | `= value` | `{"field": "municipal.public_safety.primary_type", "operator": "eq", "value": "THEFT"}` |
| `in` | `IN (values)` | `{"field": "municipal.geospatial.community_name", "operator": "in", "value": ["AUSTIN", "LOOP", "NEAR NORTH SIDE"]}` |
| `gte` | `>= value` | `{"field": "municipal.finance.amount", "operator": "gte", "value": 1000000}` |
| `lte` | `<= value` | `{"field": "municipal.finance.amount", "operator": "lte", "value": 5000000}` |
| `between` | `BETWEEN a AND b` | `{"field": "temporal.date", "operator": "between", "value": {"from": "2024-01-01", "to": "2024-12-31"}}` |
| `like` | `LIKE pattern` | `{"field": "municipal.regulatory.facility_name", "operator": "like", "value": "%PIZZA%"}` |

**Default operator**: When `operator` is omitted, it defaults to `in`.

**Date expressions**: The `between` operator supports dynamic date expressions
in addition to literal strings:

| Expression | Evaluates to |
|------------|-------------|
| `current_date` | Today's date (ISO format) |
| `current_date - 30` | 30 days ago |
| `current_date + 7` | 7 days from now |
| `year_start` | January 1 of the current year |

Example with date expression:

```python
resp = requests.post(f"{BASE}/query", json={
    "type": "plotly.line",
    "x": "temporal.date",
    "y": ["municipal.public_safety.crime_count"],
    "filters": [
        {"field": "municipal.public_safety.primary_type", "operator": "eq", "value": "BATTERY"},
        {"field": "temporal.date", "operator": "between",
         "value": {"from": "current_date - 365", "to": "current_date"}},
    ],
})
```

**Domain scoping**: Filters referencing tables not in the query's FROM clause
are silently skipped. This prevents cross-domain page filters (e.g. a
`county.property` filter on a municipal-only exhibit) from injecting
unreachable table references or pulling unrelated domains into the join graph.

**Source**: `src/de_funk/api/executor.py` (`_build_where`, `_eval_date_expr`)

---

## Part 5: Error Handling

The API returns structured errors at three levels.

### 400 Bad Request

Returned when the request is syntactically valid JSON but semantically wrong.

```bash
# Unknown handler type
curl -s -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{"type": "unknown.widget"}'
```

```json
{"detail": "Unknown block type 'unknown.widget'. See exhibits/_index.md for valid types."}
```

```bash
# Missing type field
curl -s -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{"x": "temporal.year"}'
```

```json
{"detail": "'type' field is required"}
```

```bash
# Unknown domain in field reference
curl -s -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{"type": "plotly.line", "x": "nonexistent.domain.field", "y": ["municipal.public_safety.crime_count"]}'
```

```json
{"detail": "Domain 'nonexistent' not found. Available domains: ['municipal.public_safety', 'municipal.finance', 'municipal.geospatial', 'temporal']"}
```

### 422 Validation Error

Returned when the payload fails Pydantic model validation.

```bash
# Missing required field for table.data (columns is required)
curl -s -X POST http://localhost:8765/api/query \
  -H "Content-Type: application/json" \
  -d '{"type": "table.data"}'
```

```json
{
  "detail": [
    {"loc": ["columns"], "msg": "field required", "type": "value_error.missing"}
  ]
}
```

### 500 Internal Server Error

Returned when an unhandled exception occurs during query execution. The full
stack trace is logged server-side.

```json
{"detail": "Query failed: <exception message>"}
```

### 404 Not Found

Returned by the dimensions endpoint for unknown field references.

```bash
curl -s "http://localhost:8765/api/dimensions/nonexistent.field"
```

```json
{"detail": "Domain 'nonexistent' not found. Available domains: [...]"}
```

---

## Part 6: Response Size Capping

All handlers enforce `max_response_mb` from `configs/storage.json` (default
4.0 MB). The capping algorithm:

1. Take a 50-row sample from the result set
2. JSON-serialize the sample and measure bytes
3. Estimate bytes per row: `sample_bytes / sample_size`
4. Compute estimated total: `bytes_per_row * total_rows`
5. If estimated total exceeds the cap, truncate to `max_mb / bytes_per_row` rows

When truncation occurs:
- `"truncated": true` is set in the response
- A log message records the number of rows kept

For graphical responses, capping works per-series on point count rather than
row count -- each series is trimmed to stay within the byte budget.

**Source**: `src/de_funk/api/executor.py` (`truncate_to_mb`)

---

## Part 7: CORS Configuration

The API allows cross-origin requests from these sources:

| Origin | Purpose |
|--------|---------|
| `app://obsidian.md` | Obsidian desktop app |
| `capacitor://localhost` | Obsidian mobile app |
| `http://localhost` | Local development (any port) |
| `http://localhost:8765` | Default API port |
| `http://127.0.0.1:8765` | Loopback address |
| `http://192.168.*.*` | Local network devices (regex match) |

All HTTP methods and headers are allowed. Credentials are enabled.

**Source**: `src/de_funk/api/main.py` (`CORSMiddleware` configuration)

---

## Part 8: Configuration

Runtime limits are set in `configs/storage.json` under the `api` key. All four
keys are required -- the server refuses to start if any are missing.

| Key | Default | Description |
|-----|---------|-------------|
| `duckdb_memory_limit` | `3GB` | DuckDB per-connection memory cap |
| `max_sql_rows` | `30000` | Maximum rows fetched per query (`fetchmany` limit) |
| `max_dimension_values` | `10000` | Maximum distinct values returned by `/api/dimensions` |
| `max_response_mb` | `4.0` | Maximum JSON response size before truncation |

Additional internal constants (defined in handler source, not in config):

| Constant | Value | Location | Description |
|----------|-------|----------|-------------|
| `MAX_HTML_ROWS` | 400 | `handlers/pivot.py` | Threshold for expandable pivot mode |
| `MAX_PIVOT_COLUMNS` | 200 | `handlers/pivot.py` | Max distinct column combinations before error |

To change limits, edit `configs/storage.json`:

```json
{
  "api": {
    "duckdb_memory_limit": "4GB",
    "max_sql_rows": 50000,
    "max_dimension_values": 20000,
    "max_response_mb": 8.0
  }
}
```

---

## Part 9: Running the Server

### CLI options

```bash
python -m scripts.serve.run_api [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address (0.0.0.0 = all interfaces) |
| `--port` | `8765` | Bind port |
| `--reload` | off | Auto-reload on code changes (development mode) |
| `--workers` | `1` | Number of uvicorn workers (ignored when `--reload` is set) |

### Examples

```bash
# Development: auto-reload on code changes
python -m scripts.serve.run_api --port 8765 --reload

# Production: multiple workers, bound to all interfaces
python -m scripts.serve.run_api --host 0.0.0.0 --port 8765 --workers 4

# Direct uvicorn (bypasses the CLI script)
uvicorn de_funk.api.main:app --host 0.0.0.0 --port 8765

# Find your LAN IP for access from other devices
ip addr show | grep "inet " | grep -v 127.0.0.1
```

### Startup sequence

1. `create_app()` reads `configs/storage.json` for Silver/Bronze root paths and API limits
2. CORS middleware is configured
3. Routers are mounted at `/api/health`, `/api/domains`, `/api/dimensions`, `/api/query`, `/api/bronze/*`
4. On `startup` event:
   - `FieldResolver` scans `domains/models/` and builds the Silver field index + join graph
   - `BronzeResolver` scans `data_sources/Endpoints/` and builds the Bronze field index
     (providers, endpoints, fields, Delta paths)
   - `Engine` initializes a DuckDB connection with the configured memory limit,
     installs and loads the Delta extension
   - `HandlerRegistry` instantiates all five handler classes with shared config
5. Server is ready at `http://{host}:{port}`

**Source**: `src/de_funk/api/main.py` (`create_app`, `startup` event)
