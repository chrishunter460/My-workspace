# Obsidian Plugin -- Practical Guide

The de_funk Obsidian plugin turns markdown notes into live data dashboards. You write YAML inside fenced code blocks, and the plugin renders interactive Plotly charts, pivot tables, metric cards, and data tables -- powered by both the **Silver layer** (dimensional star schemas) and the **Bronze layer** (raw provider data) through a FastAPI backend.

This guide walks through everything from installation to building a multi-exhibit dashboard.

---

## Getting Started

### Prerequisites

Before the plugin can render anything, you need two things running:

1. **Data layer available.** The plugin can query two layers:
   - **Silver** (dimensional models) — requires ingestion + model build
   - **Bronze** (raw provider data) — only requires ingestion, no build step

   For Silver queries:
   ```bash
   python -m scripts.seed.seed_calendar --storage-path /shared/storage
   python -m scripts.ingest.run_bronze_ingestion --domains municipal
   python -m scripts.build.build_models
   ```

   For Bronze-only queries, skip the build step — just ingest:
   ```bash
   python -m scripts.ingest.run_bronze_ingestion --domains municipal
   ```

2. **FastAPI backend running on localhost:8765.** The plugin POSTs query payloads to this server and gets back rendered data. Start it with:

   ```bash
   python -m scripts.serve.run_api
   ```

   The server URL is configurable in plugin settings (default: `http://localhost:8765`).

### Installation

```bash
cd obsidian-plugin
npm install
npm run build    # production build -> main.js
npm run deploy   # build + copy to Obsidian vault plugins/de-funk/
```

`npm run deploy` copies `main.js`, `manifest.json`, and `styles.css` into your Obsidian vault's `plugins/de-funk/` directory. The vault path is configured in `obsidian-plugin/scripts/deploy.mjs`.

After deploying, open Obsidian, go to **Settings > Community Plugins**, and enable **de-funk**. You should see a bar-chart icon in the ribbon and a sidebar panel.

### Plugin Settings

Open **Settings > de-funk** to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| Server URL | `http://localhost:8765` | FastAPI backend address |
| API Key | *(blank)* | Optional `X-API-Key` header for authenticated servers |
| Cache TTL | `30` seconds | How long query results are cached. `0` disables caching. |
| Sidebar position | `right` | Which side the filter/controls panel opens on |

These map to the `DeFunkSettings` interface in `settings.ts`:

```typescript
export interface DeFunkSettings {
  serverUrl: string;
  apiKey: string;
  cacheTtlSeconds: number;
  sidebarPosition: "left" | "right";
}
```

---

## Part 1: Your First Exhibit

Create a new note in Obsidian and add this fenced code block:

````markdown
```de_funk
type: plotly.line
data:
  rows: [temporal.year]
  measures:
    - [municipal.public_safety.crime_count, "#,##0", count]
```
````

Save the note and switch to Reading View. You should see a line chart showing crime counts by year.

### What Happens Under the Hood

When Obsidian renders this block, the plugin executes an 8-step pipeline:

1. **Block detection.** Obsidian sees the `de_funk` language tag and calls the registered block processor (`processors/de-funk.ts`).

2. **YAML parsing.** The `parseBlock()` function in `resolver.ts` parses the YAML body into a `DeFunkBlock` object with `type`, `data`, `formatting`, and `config` sections.

3. **Frontmatter merge.** The processor reads the note's YAML frontmatter via `frontmatter.ts` to collect page-level filters and control state.

4. **Control state merge.** If the block has a `config_ref`, the processor reads the current state from the config panel store (`config-panel.ts`).

5. **Payload construction.** `buildRequest()` in `resolver.ts` merges the block data, active note filters, exhibit-level filters, and control state into a single JSON payload.

6. **API call.** The `ApiClient` POSTs the payload to the appropriate endpoint based on the page's `layer` setting:
   - Silver (default): `POST /api/query`
   - Bronze: `POST /api/bronze/query`

7. **Rendering.** Based on the `type` field, the processor dispatches to the correct renderer:
   - Chart types --> `render/graphical.ts` (Plotly.js)
   - `table.data` --> `render/tabular.ts`
   - `table.pivot` --> `render/pivot.ts`
   - `cards.metric` --> `render/metric-cards.ts`

8. **Event subscription.** The block subscribes to the filter bus so it re-renders automatically when any filter or control changes.

---

## Part 2: Exhibit Block Reference

Every `de_funk` code block is structured as YAML with up to four top-level sections:

```yaml
type: plotly.line          # Required -- what to render
data:                       # The query: rows, measures, filters
  rows: [...]
  measures: [...]
formatting:                 # Visual options: title, height, colors
  title: "My Chart"
  height: 500
config:                     # Wiring: config_ref, page_filter overrides
  config_ref: my-controls
```

### Block Fields

| Field | Section | Type | Description | Example |
|-------|---------|------|-------------|---------|
| `type` | *(top)* | string | Exhibit type | `plotly.line` |
| `rows` | data | string[] | Row dimensions | `[temporal.year]` |
| `cols` | data | string[] | Column dimensions (pivots) | `[municipal.finance.department_description]` |
| `measures` | data | tuple[] | `[field, format, agg]` tuples | `[[municipal.finance.amount, "$,.0f", sum]]` |
| `filters` | data | object[] | `{field, op, value}` objects | see below |
| `columns` | data | tuple[] | Column definitions (data tables) | `[[department, municipal.finance.department_description]]` |
| `metrics` | data | tuple[] | Metric definitions (KPI cards) | see below |
| `sort` | data | object | Sort configuration | `{by: year, order: desc}` |
| `limit` | data | number | Row limit | `1000` |
| `config_ref` | config | string | Control group ID | `budget-explorer` |
| `page_filters` | config | object | Filter override rules | `{ignore: ["*"]}` |
| `title` | formatting | string | Display title | `"Revenue by Year"` |
| `height` | formatting | number | Chart height in pixels | `500` |
| `show_legend` | formatting | boolean | Show/hide legend | `true` |
| `color_palette` | formatting | string | Named color palette | `"blues"` |

### Measure Tuples

Measures are arrays with positional elements:

```yaml
measures:
  - [key, field, aggregation, format, label]
```

In the simplest form, `key` and `field` are the same domain reference:

```yaml
measures:
  - [municipal.finance.amount, "$,.0f", sum]
```

The resolver normalizes this into a `MeasureTuple` object:

```typescript
interface MeasureTuple {
  key: string;
  field: string | Record<string, unknown>;
  aggregation?: string | null;   // sum, avg, count, min, max
  format?: string | null;        // "$,.2f", "#,##0", "%"
  label?: string | null;         // Display label
}
```

### Inline Filters

Block-level filters narrow the query for a single exhibit:

```yaml
data:
  filters:
    - field: municipal.finance.department_description
      op: eq
      value: DEPARTMENT OF POLICE
    - field: temporal.year
      op: gte
      value: 2020
```

Supported operators: `eq`, `in`, `gte`, `lte`, `between`, `like`.

---

## Part 3: Exhibit Types Catalog

### Charts (Plotly.js)

All chart types are rendered by `render/graphical.ts` using Plotly.js.

**Line Chart** -- time series and trends:

````markdown
```de_funk
type: plotly.line
data:
  rows: [temporal.year]
  measures:
    - [municipal.transportation.rides, "#,##0", sum]
  filters:
    - field: temporal.year
      op: gte
      value: 2010
formatting:
  title: "CTA Rail Ridership Over Time"
  height: 400
  line_shape: spline
```
````

**Bar Chart** -- categorical comparison:

````markdown
```de_funk
type: plotly.bar
data:
  rows: [municipal.finance.department_description]
  measures:
    - [municipal.finance.amount, "$,.0f", sum]
formatting:
  title: "Budget by Department"
  barmode: group
  orientation: v
```
````

**Scatter Plot** -- correlation analysis:

````markdown
```de_funk
type: plotly.scatter
data:
  x: municipal.finance.amount
  y: municipal.public_safety.crime_count
  group_by: municipal.geospatial.community_name
formatting:
  title: "Budget vs Crime by Community Area"
  marker_size: 8
  opacity: 0.7
```
````

**Area Chart** -- stacked trends:

````markdown
```de_funk
type: plotly.area
data:
  rows: [temporal.year]
  measures:
    - [municipal.operations.request_count, "#,##0", count]
  group_by: municipal.operations.sr_type
formatting:
  fill: tozeroy
```
````

**Heatmap** -- matrix visualization:

````markdown
```de_funk
type: plotly.heatmap
data:
  rows: [municipal.geospatial.community_name]
  cols: [temporal.year]
  measures:
    - [municipal.public_safety.crime_count, "#,##0", count]
formatting:
  title: "Crimes by Community Area and Year"
  color_scale: "YlOrRd"
```
````

**Pie Chart** -- proportions:

````markdown
```de_funk
type: plotly.pie
data:
  labels: municipal.finance.event_type
  values: municipal.finance.amount
  aggregation: sum
formatting:
  title: "Budget Distribution by Type"
  hole: 0.4
```
````

**Box Chart** -- statistical distribution:

````markdown
```de_funk
type: plotly.box
data:
  category: municipal.public_safety.primary_type
  rows: [municipal.operations.days_to_close]
formatting:
  title: "311 Response Time by Crime Type"
```
````

**Type aliases.** The processor recognizes short names. All of these are equivalent:

| Canonical | Aliases |
|-----------|---------|
| `plotly.line` | `line`, `line_chart` |
| `plotly.bar` | `bar`, `bar_chart` |
| `plotly.scatter` | `scatter` |
| `plotly.area` | `area` |
| `plotly.pie` | `pie` |
| `plotly.heatmap` | `heatmap` |
| `plotly.box` | `box`, `ohlcv`, `candlestick` |

### Tables

**Data Table** -- flat sortable rows rendered by `render/tabular.ts`:

````markdown
```de_funk
type: table.data
data:
  columns:
    - [department, municipal.finance.department_description]
    - [amount, municipal.finance.amount, null, "$,.0f"]
    - [event_type, municipal.finance.event_type]
    - [fiscal_year, municipal.finance.fiscal_year]
  sort_by: amount
  sort_order: desc
formatting:
  page_size: 50
  download: true
```
````

**Pivot Table** -- row/column grouping rendered by `render/pivot.ts`:

````markdown
```de_funk
type: table.pivot
data:
  rows: [municipal.finance.department_description]
  cols: [temporal.year]
  measures:
    - [municipal.finance.amount, "$,.0f", sum]
  totals:
    rows: true
    cols: true
formatting:
  renderer: great_tables
```
````

**Table type aliases:**

| Canonical | Aliases |
|-----------|---------|
| `table.data` | `data_table` |
| `table.pivot` | `pivot`, `pivot_table`, `great_table`, `gt` |

### Metric Cards

KPI tiles rendered by `render/metric-cards.ts`:

````markdown
```de_funk
type: cards.metric
data:
  metrics:
    - [total_crimes, municipal.public_safety.incident_id, count, "#,##0", "Total Crimes"]
    - [total_budget, municipal.finance.amount, sum, "$,.0f", "Total Budget"]
    - [dept_count, municipal.finance.department_description, count, "#,##0", "Departments"]
formatting:
  title: "Chicago Overview"
  columns: 3
```
````

**Metric type aliases:** `cards.metric`, `kpi`, `metric_cards`.

---

## Part 3b: Bronze Layer Exhibits

Bronze exhibits query raw provider data directly — no Silver build required. Add `layer: bronze` to the frontmatter and use `provider.endpoint.field` references instead of Silver domain.field references.

### Bronze Frontmatter

```yaml
---
title: Chicago Crime Analysis
layer: bronze
models: [chicago.crimes]
filters:
  crime_type:
    source: chicago.crimes.primary_type
    type: select
    multi: true
    layer: bronze
  year_range:
    source: chicago.crimes.year
    type: range
    layer: bronze
    default: [2020, 2025]
---
```

The `layer: bronze` in frontmatter tells the plugin to route all queries to `/api/bronze/query` instead of `/api/query`. Each filter also needs `layer: bronze` so the sidebar fetches distinct values from `/api/bronze/dimensions/` instead of `/api/dimensions/`.

### Bronze Exhibit Blocks

Bronze blocks use the same `type:` values as Silver. The only difference is the field reference format:

**Silver**: `municipal.public_safety.primary_type` (domain.field → resolved via joins)
**Bronze**: `chicago.crimes.primary_type` (provider.endpoint.field → single table scan)

````markdown
```de_funk
type: cards.metric
data:
  metrics:
    - [total, chicago.crimes.id, count, "#,##0", Total Incidents]
    - [arrests, chicago.crimes.arrest, sum, "#,##0", Total Arrests]
    - [districts, chicago.crimes.district, count_distinct, "#,##0", Districts]
```
````

````markdown
```de_funk
type: plotly.bar
data:
  x: chicago.crimes.primary_type
  y: chicago.crimes.id
  aggregation: count
formatting:
  title: "Top Crime Types"
```
````

````markdown
```de_funk
type: plotly.line
data:
  x: chicago.crimes.year
  y: chicago.crimes.id
  aggregation: count
formatting:
  title: "Crimes by Year"
```
````

### Bronze vs Silver: When to Use Which

| Scenario | Layer | Why |
|----------|-------|-----|
| Exploring a new data source | **Bronze** | No build step, see raw data immediately |
| Cross-domain analysis (crimes + budgets) | **Silver** | Automatic joins via graph edges |
| Quick KPIs on a single endpoint | **Bronze** | Faster, simpler field refs |
| Dimensional rollups (by community area, department) | **Silver** | Dimension tables with clean labels |
| Validating ingested data | **Bronze** | See exactly what the API returned |

### Limitations

- All fields in a Bronze query must come from the **same endpoint** (no cross-endpoint joins)
- No computed measures, no graph-based joins, no dimension lookups
- Filter cascading works within the endpoint but cannot cross to Silver dimensions

---

## Part 4: Frontmatter Filters

Filters declared in note frontmatter create interactive controls in the sidebar that apply to every exhibit on the page.

```yaml
---
models: [municipal.finance, municipal.public_safety, municipal.geospatial]
filters:
  community_area:
    source: municipal.geospatial.community_name
    type: select
    multi: true
  department:
    source: municipal.finance.department_description
    type: select
    multi: true
    context_filters: true
  year:
    source: temporal.year
    type: range
---
```

The `models` list tells the backend which domains to join. Each filter entry needs:

- **`source`**: The fully qualified field reference (e.g., `municipal.finance.department_description`).
- **`type`**: What kind of control to render.
- **`multi`**: Whether multiple values can be selected (for `select` type).

### Filter Types

| Type | Renders As | When to Use |
|------|-----------|-------------|
| `select` | Tag picker with search | Categorical fields (department, community area, ward) |
| `date_range` | Date input | Date fields |
| `range` | Numeric from/to inputs | Numeric fields (amount, year, rides) |

### How Filters Flow

1. On note open, the sidebar reads `filters:` from frontmatter via `parseFrontmatter()`.
2. For each `select` filter, the sidebar calls `GET /api/dimensions/{domain}/{field}` to fetch distinct values.
3. The user picks values in the sidebar. Each change calls `notifyFilterChanged()` on the global event bus.
4. Every subscribed exhibit re-runs its query with the new filter values included in the payload.

### Context Filters (Cascading)

When `context_filters: true` is set on a filter, its picker values re-fetch whenever other filters change. This creates cascading behavior:

```yaml
---
filters:
  community_area:
    source: municipal.geospatial.community_name
    type: select
    multi: true
  department:
    source: municipal.finance.department_description
    type: select
    multi: true
    context_filters: true    # picker values update when community_area changes
---
```

Here is the flow:

1. User selects **community_area = LOOP** in the sidebar.
2. The plugin calls `handleFilterChange()` in `main.ts`, which fires `notifyFilterChanged()`.
3. `main.ts` also calls `sidebar.refreshContextFilters("community_area")`.
4. The department picker (which has `context_filters: true`) re-fetches from `GET /api/dimensions/municipal.finance/department_description?filters=[{"field":"municipal.geospatial.community_name","value":["LOOP"]}]`.
5. The dimension endpoint returns only departments with budget activity in the Loop.
6. The department picker updates to show only those departments.
7. If previously selected departments are no longer in the new set, they are automatically deselected.

### Sort-By-Measure Filters

You can order picker values by a measure rather than alphabetically:

```yaml
filters:
  department:
    source: municipal.finance.department_description
    type: select
    multi: true
    sort_by_measure: municipal.finance.amount
    sort_dir: desc    # largest budget first
```

### Default Values

Set initial filter selections that apply before the user interacts:

```yaml
filters:
  community_area:
    source: municipal.geospatial.community_name
    type: select
    multi: true
    default: [LOOP, NEAR NORTH SIDE, LINCOLN PARK]
```

### Ignoring Page Filters

A specific exhibit can opt out of page-level filters:

````markdown
```de_funk
type: plotly.bar
data:
  rows: [municipal.finance.department_description]
  measures:
    - [municipal.finance.amount, "$,.0f", sum]
config:
  page_filters:
    ignore: ["department"]     # this exhibit ignores the department filter
```
````

Use `ignore: ["*"]` to ignore all page filters for a standalone exhibit.

---

## Part 5: Controls (config_ref)

Controls let users change what an exhibit displays without editing the note. They are defined in frontmatter and rendered as interactive widgets in the sidebar.

### Defining Controls

```yaml
---
controls:
  budget-explorer:
    dimensions:
      - temporal.year
      - municipal.finance.department_description
      - municipal.finance.event_type
    measures:
      - [municipal.finance.amount, "$,.0f", sum]
      - [municipal.public_safety.crime_count, "#,##0", count]
      - [municipal.transportation.rides, "#,##0", sum]
    sort_order: [asc, desc]
---
```

This creates a sidebar panel named "budget-explorer" with:
- A **Rows** picker (checkbox list of dimension options)
- A **Measures** picker (checkbox list of measure options)
- An **Order** toggle button (cycles between asc/desc)

### Referencing Controls from Exhibits

Exhibits reference a control group with `config_ref`:

````markdown
```de_funk
type: plotly.line
config:
  config_ref: budget-explorer
```
````

The exhibit inherits `rows`, `cols`, and `measures` from the control's current state. When the user changes a control in the sidebar, all exhibits referencing that `config_ref` re-render automatically.

### Control Options

| Key | Sidebar Widget | What It Drives |
|-----|---------------|----------------|
| `dimensions` | Checkbox picker | Chart x-axis / pivot rows |
| `cols` | Checkbox picker | Pivot columns |
| `measures` | Checkbox picker | Chart y-axis / pivot values |
| `sort_by` | Dropdown | Sort field |
| `sort_order` | Toggle button | Sort direction (asc/desc) |
| `color_palette` | Dropdown | Chart color palette |

### Measure Format Propagation

When you define measures as tuples, the format and aggregation are preserved:

```yaml
controls:
  my-panel:
    measures:
      - [municipal.finance.amount, "$,.0f", sum]
      - municipal.public_safety.crime_count               # string shorthand, no format
      - [municipal.transportation.rides, "#,##0"]          # tuple without aggregation
```

The sidebar stores format/aggregation metadata via `_measure_meta` in the config panel state. When the user selects measures, the resolver reads this metadata and builds properly formatted measure tuples for the API payload.

### Persisting Control State

When a user changes a control, the plugin writes the selection back to the note's frontmatter under `current:`:

```yaml
controls:
  budget-explorer:
    dimensions: [temporal.year, municipal.finance.department_description]
    measures:
      - [municipal.finance.amount, "$,.0f", sum]
    current:                    # written by the plugin
      dimensions: [temporal.year]
      measures: [municipal.finance.amount]
```

On the next note open, the `current` values are restored so the user's selections survive across sessions.

---

## Part 6: Building a Complete Dashboard

Here is a full multi-exhibit note that combines filters, controls, and several exhibit types:

```yaml
---
models: [municipal.finance, municipal.public_safety, municipal.geospatial]
filters:
  community_area:
    source: municipal.geospatial.community_name
    type: select
    multi: true
  department:
    source: municipal.finance.department_description
    type: select
    multi: true
    context_filters: true
    sort_by_measure: municipal.finance.amount
    sort_dir: desc
  year:
    source: temporal.year
    type: range
controls:
  crime-trends:
    dimensions:
      - temporal.year
      - municipal.geospatial.community_name
      - municipal.public_safety.primary_type
    measures:
      - [municipal.public_safety.crime_count, "#,##0", count]
      - [municipal.public_safety.arrest_rate, "#,##0.0%", avg]
---
```

````markdown
# Chicago Municipal Dashboard

## Summary Metrics

```de_funk
type: cards.metric
data:
  metrics:
    - [total_crimes, municipal.public_safety.incident_id, count, "#,##0", "Total Crimes"]
    - [total_budget, municipal.finance.amount, sum, "$,.0f", "Total Budget"]
formatting:
  columns: 2
```

## Crime Trends

```de_funk
type: plotly.line
config:
  config_ref: crime-trends
formatting:
  title: "Crime Trends"
  height: 450
  line_shape: spline
```

## Budget by Department

```de_funk
type: plotly.bar
data:
  rows: [municipal.finance.department_description]
  measures:
    - [municipal.finance.amount, "$,.0f", sum]
formatting:
  title: "Budget by Department"
  orientation: v
config:
  page_filters:
    ignore: ["department"]
```

## Budget Detail

```de_funk
type: table.data
data:
  columns:
    - [department, municipal.finance.department_description]
    - [amount, municipal.finance.amount, null, "$,.0f", "Amount"]
    - [event_type, municipal.finance.event_type]
    - [fiscal_year, municipal.finance.fiscal_year]
  sort_by: amount
  sort_order: desc
formatting:
  page_size: 50
```
````

When you open this note:

1. The sidebar populates with **community_area** and **department** pickers plus a **year** range input.
2. The **crime-trends** control group appears with dimension and measure checkboxes.
3. All four exhibits render with data from the Silver layer.
4. Selecting a community area filters the department picker (context filters) and re-renders all exhibits.
5. Changing the dimension in the crime-trends control re-renders only the Crime Trends chart (the one using `config_ref: crime-trends`).
6. The Budget by Department bar chart ignores the department page filter (via `page_filters.ignore`) so it always shows all departments.

---

## Part 7: Plugin Architecture

### Source Files

```
obsidian-plugin/src/
├── main.ts                        # Plugin lifecycle, registers block processor
├── settings.ts                    # Settings tab (API URL, theme, cache TTL)
├── contract.ts                    # TypeScript types matching the API contract
├── api-client.ts                  # HTTP client with response caching
├── frontmatter.ts                 # Parse note frontmatter into typed objects
├── resolver.ts                    # Parse YAML block body, build API payloads
├── filter-bus.ts                  # Pub/sub event bus for filter/control changes
├── filter-sidebar.ts              # Sidebar filter UI (ItemView)
├── processors/
│   ├── de-funk.ts                 # Main block processor (dispatch to renderers)
│   ├── config-panel.ts            # Control state store (register, subscribe, update)
│   └── config-panel-renderer.ts   # Inline control.config block renderer
└── render/
    ├── graphical.ts               # Plotly chart rendering
    ├── pivot.ts                   # Pivot table rendering (Great Tables HTML)
    ├── tabular.ts                 # Data table rendering
    ├── metric-cards.ts            # KPI card rendering
    └── format.ts                  # Number/date formatting utilities
```

### Plugin Lifecycle (`main.ts`)

The `DeFunkPlugin` class extends Obsidian's `Plugin` and wires everything together:

```typescript
export default class DeFunkPlugin extends Plugin {
  settings: DeFunkSettings;
  private client: ApiClient;
  private sidebar: FilterSidebar | null;
  private currentFrontmatter: NoteFrontmatter;

  async onload(): Promise<void> {
    // 1. Load settings
    // 2. Create ApiClient
    // 3. Register settings tab
    // 4. Register sidebar view (FilterSidebar as ItemView)
    // 5. Register "de_funk" code block processor
    // 6. Open sidebar on layout ready
    // 7. Listen for active-leaf-change (clear panels on note switch)
    // 8. Listen for metadata-cache changes (re-render on frontmatter edit)
    // 9. Add ribbon icon
  }
}
```

Key behaviors:
- When the user switches notes, `clearPanels()` destroys all control state and the sidebar re-reads the new note's frontmatter.
- When sidebar focus changes (clicking the sidebar itself), the plugin detects that `getActiveFile()` returns the same path and skips the clear, preserving control state.
- When frontmatter is edited in-place, a metadata cache listener re-parses and re-renders.

### Filter Bus (`filter-bus.ts`)

A simple pub/sub event bus. Both filter changes and control changes fire the same subscriber set -- any change triggers all exhibits to re-query.

```typescript
const _subscribers = new Set<Callback>();

subscribeToFilterChanges(cb: () => void): () => void  // Returns unsubscribe fn
notifyFilterChanged(): void    // Called when sidebar filter changes
notifyControlChanged(): void   // Called when control panel changes
```

Event flow:

1. User changes a filter in the sidebar.
2. `main.ts` calls `handleFilterChange()`, which updates `currentFrontmatter`, clears the API cache, and calls `notifyFilterChanged()`.
3. All subscribed render closures execute -- each `de_funk` block re-runs its `render()` function.
4. Inside `render()`, the block reads fresh filter state and control state, builds a new payload, and POSTs to `/api/query`.

### Config Panel (`config-panel.ts`)

A state store for sidebar controls. Panels are keyed by their `id` string.

```typescript
interface ConfigPanel {
  id: string;
  state: Record<string, unknown>;
  listeners: StateListener[];
}

registerPanel(id: string, initialState?: Record<string, unknown>): void
getState(id: string): Record<string, unknown>
updateControl(id: string, key: string, value: unknown): void   // Updates + notifies
setControlSilent(id: string, key: string, value: unknown): void // Updates, no notify
notifyListeners(id: string): void  // Batch notify after silent updates
subscribe(id: string, listener: (state) => void): () => void   // Returns unsubscribe
clearPanels(): void  // Destroy all panels on note switch
```

State flow:

1. Note opens. `FilterSidebar.renderControlGroup()` calls `registerPanel(id, {})` for each control definition.
2. Sidebar renders checkboxes/dropdowns and calls `setControlSilent()` for each initial value (no event fired yet).
3. After all controls are initialized, `notifyListeners(id)` fires once to trigger initial renders.
4. User clicks a checkbox. `setControlSilent()` updates state, then `notifyControlChanged()` fires the global bus.
5. Each subscribed exhibit's `render()` calls `getState(configRef)` to read the latest state.

The split between `setControlSilent` and `notifyControlChanged` avoids N render cycles during initialization -- state is set silently, then listeners fire once.

### Block Processor (`processors/de-funk.ts`)

The `createBlockProcessor()` factory returns an async function that Obsidian calls for every `de_funk` code block. Here is the full lifecycle:

```
1. parseBlock(source)               Parse YAML via js-yaml
2. getFrontmatter()                 Read current note frontmatter
3. getState(configRef)              Read control state (if config_ref set)
4. filtersToSpecs(frontmatter)      Convert active filters to FilterSpec[]
5. buildRequest(block, filters, state)  Merge everything into JSON payload
6. client.query(payload)            POST to /api/query
7. dispatch to renderer             Based on type: graphical, tabular, pivot, or metric
8. subscribeToFilterChanges(render)  Re-run on any filter/control change
```

The processor uses a `renderSeq` counter to discard stale responses. If a new render is triggered while an API call is in flight, the old response is silently dropped when it arrives.

### API Client (`api-client.ts`)

The `ApiClient` class wraps `fetch()` with caching and error handling:

```typescript
class ApiClient {
  async query(payload: unknown, layer?: string): Promise<ApiResponse>
  // layer="bronze" → POST /api/bronze/query
  // layer=undefined → POST /api/query (Silver)

  async getDimensions(ref, orderBy?, orderDir?, contextFilters?, layer?: string): Promise<DimensionValuesResponse>
  // layer="bronze" → GET /api/bronze/dimensions/{provider}/{endpoint}/{field}
  // layer=undefined → GET /api/dimensions/{domain}/{field}

  async getDomains(): Promise<Record<string, unknown>>    // GET /api/domains
  async health(): Promise<{ status: string }>             // GET /api/health
  clearCache(): void                                      // Called on filter change
}
```

Responses are cached by a key derived from method + path + body. The cache uses a configurable TTL (default 30 seconds). In-flight request deduplication prevents concurrent identical API calls from hitting the server multiple times (e.g., when a filter change triggers 10 exhibits to re-render simultaneously, only 1 API call per unique payload is made).

### Filter Sidebar (`filter-sidebar.ts`)

Registered as an Obsidian `ItemView` that appears in the left or right sidebar. It renders:

1. A **Refresh Exhibits** button that manually fires `notifyControlChanged()`.
2. A collapsible **Note Filters** section with picker/date/range controls.
3. A collapsible **Controls** section with checkbox lists, dropdowns, and toggle buttons for each control group.

The sidebar receives frontmatter updates via `updateFrontmatter()` and re-renders. It preserves in-memory filter selections when re-parsing the same note (so clicking the sidebar does not reset your choices).

---

## Part 8: Field References

All field references in exhibit blocks use a dot-separated canonical format:

```
{domain}.{subdomain}.{field}
```

The resolver uses longest-prefix matching against known domain names. Here are the key mappings:

```
municipal.finance.amount                -->  fact_budget_events.amount
municipal.finance.department_description -->  fact_budget_events.department_description
municipal.finance.event_type            -->  fact_budget_events.event_type
municipal.finance.fiscal_year           -->  fact_budget_events.fiscal_year
municipal.finance.department_count      -->  dim_department.department_count (measure)
municipal.finance.org_unit_name         -->  dim_department.org_unit_name
municipal.public_safety.incident_id     -->  fact_crimes.incident_id
municipal.public_safety.crime_count     -->  fact_crimes.crime_count (measure)
municipal.public_safety.arrest_rate     -->  fact_crimes.arrest_rate (measure)
municipal.public_safety.primary_type    -->  dim_crime_type.primary_type
municipal.public_safety.ward            -->  fact_crimes.ward
municipal.public_safety.community_area  -->  fact_crimes.community_area
municipal.geospatial.community_name     -->  dim_community_area.community_name
municipal.geospatial.ward_number        -->  dim_ward.ward_number
municipal.regulatory.result             -->  fact_food_inspections.result
municipal.regulatory.facility_name      -->  dim_facility.facility_name
municipal.transportation.rides          -->  fact_rail_ridership.rides
municipal.operations.request_count      -->  fact_service_requests.request_count (measure)
municipal.operations.days_to_close      -->  fact_service_requests.days_to_close
temporal.year                           -->  dim_calendar.year
temporal.quarter                        -->  dim_calendar.quarter
```

The backend resolves these references to actual table.column paths and handles all joins automatically based on the `models` declared in frontmatter.

---

## Part 9: Build and Deploy

### Development Workflow

```bash
cd obsidian-plugin

npm run dev      # Watch mode -- rebuilds on every file change
npm run build    # Production build --> main.js (minified, single file)
npm run deploy   # Build + copy main.js, manifest.json, styles.css to vault
```

The build uses **esbuild** configured in `esbuild.config.mjs`. Output is a single `main.js` file that Obsidian loads as a community plugin.

`npm run deploy` runs `scripts/deploy.mjs`, which copies the built artifacts into the Obsidian vault's `plugins/de-funk/` directory. Edit `scripts/deploy.mjs` to set your vault path.

### Development Tips

- Use `npm run dev` during development. It watches for changes and rebuilds instantly.
- Open the Obsidian developer console (**Ctrl+Shift+I**) to see `[de-funk]` and `[config-panel]` log messages.
- After rebuilding, use **Ctrl+P > Reload app without saving** in Obsidian to pick up changes.
- The plugin skips rendering in Live Preview (edit mode). Switch to Reading View to see exhibits.

---

## Part 10: Troubleshooting

### Exhibits show "Query error"

**Symptom:** Red error card with a network or HTTP error message.

**Check:**
1. Is the FastAPI backend running? `curl http://localhost:8765/api/health` should return `{"status": "ok"}`.
2. Is the server URL correct in plugin settings? Open **Settings > de-funk** and verify.
3. Open the browser console (**Ctrl+Shift+I**) and look for the full error. A `POST /api/query` failure usually means the backend cannot resolve the field references or the Silver layer is missing data.

### Exhibits show "No data returned"

**Symptom:** The chart area says "No data returned. Check filters or field references."

**Check:**
1. Are your field references correct? A typo like `municipal.public_safety.crime` (instead of `crime_count`) will return empty results.
2. Are your filters too restrictive? Remove all filters temporarily and see if data appears.
3. Has the Silver layer been built? Check that `storage/silver/` contains data for the models you reference.

### Sidebar says "Open a note with de_funk filters or controls"

**Symptom:** Sidebar is empty.

**Check:**
1. Is the current note in Reading View? The sidebar reads frontmatter from the active markdown file.
2. Does the note have `filters:` or `controls:` in its YAML frontmatter?
3. Are the frontmatter keys using the correct structure? Each filter needs `source` and `type`.

### Controls do not affect exhibits

**Symptom:** Changing a control in the sidebar does not re-render the chart.

**Check:**
1. Does the exhibit have `config_ref` set to the correct control `id`?
2. Open the console and look for `[config-panel]` messages. You should see `registerPanel`, `subscribe`, and `updateControl` logs.
3. If you see "skipping render -- no control state yet", the control panel has not initialized. This can happen if the exhibit renders before the sidebar. Try clicking **Refresh Exhibits**.

### Context filters not updating

**Symptom:** Changing a filter does not update the dependent picker's values.

**Check:**
1. Does the dependent filter have `context_filters: true` in frontmatter?
2. The context filter re-fetch only runs for filters *other than* the one that changed. If you change the department filter, the department picker will not re-fetch itself.
3. Check the console for the `GET /api/dimensions/...?filters=...` call. If the query string is empty, context filters are not being gathered.

### Charts render but look wrong

**Symptom:** Data appears but the chart type or layout is unexpected.

**Check:**
1. Verify `type:` is correct. `plotly.line` vs `plotly.bar` vs `table.pivot` produce very different output.
2. For pivot tables, make sure `rows` and `cols` are both set. A pivot with only `rows` will collapse all columns.
3. Check `formatting` options. For example, `barmode: stack` vs `barmode: group` changes bar chart behavior significantly.

### Plugin does not load

**Symptom:** No ribbon icon, no sidebar, no code block rendering.

**Check:**
1. Was the plugin deployed? Check `{vault}/.obsidian/plugins/de-funk/` for `main.js` and `manifest.json`.
2. Is the plugin enabled? Go to **Settings > Community Plugins** and toggle de-funk on.
3. Check the Obsidian console for load errors. A missing dependency or build error will prevent the plugin from initializing.
