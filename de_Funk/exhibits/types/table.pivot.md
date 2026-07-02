---
type: exhibit-type-definition
catalog_key: table.pivot
display_name: Pivot Table
aliases: [pivot_table, pivot, great_table, gt]
data_mode: tabular
status: stable
version: 1.0
renderer: pivot

base_data:
  required: [rows, measures]
  optional: [cols, layout, buckets, windows, totals, sort]
  field_roles:
    rows:     {role: dimension, description: "Row grouping dimension"}
    cols:     {role: dimension, description: "Column grouping dimension (empty [] = by_measure layout)"}
    measures: {description: "List of measure tuples: [key, field_or_fn, aggregation, format, label]"}
    layout:   {description: "by_dimension (default) | by_measure — drives column layout"}
    buckets:  {description: "Bin a dimension into equal-width, custom, or quantile groups"}
    windows:  {description: "Row-over-row window calculations on computed measures"}
    totals:   {description: "Backend computes summary rows/cols: {rows: true, cols: true}"}
    sort:     {description: "Sort rows or cols by measure or value"}

base_formatting:
  defaults:
    height: 400
    renderer: default
    theme: default
  fields: [title, description, height, renderer, theme, shading]

render_options:
  renderer: {type: enum, values: [default, ag_grid], default: default}
  theme:    {type: enum, values: [default, financial, dark, striped, minimal], default: default}
---

## Pivot Table

Cross-tabulation with optional binning, window functions, and AG Grid rendering.

`gt` and `great_table` are aliases that default `formatting.renderer: ag_grid`.
AG Grid renders as styled HTML — the backend returns `{"html": "..."}` for that renderer.

### Data contract

Default renderer: `{columns: [{key, label, format}], rows: [[val, ...]]}`.
AG Grid renderer: `{"html": "<table ...>"}` — plugin injects directly into the note.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `rows` | yes | Row grouping dimension |
| `cols` | no | Column dimension; `[]` triggers `by_measure` layout |
| `measures` | yes | List of measure tuples |
| `layout` | no | `by_dimension` (default) · `by_measure` |
| `buckets` | no | Bin config per dimension |
| `windows` | no | Window calculation list |
| `totals` | no | `{rows: true, cols: true}` — backend computes summaries |
| `sort` | no | Sort config for rows or cols |

### Measure tuple syntax

```yaml
measures:
  - [key,      domain.field or {fn: ...},  aggregation,  format,   label]
```

Derived measures use the computation catalog (see `_base/computations.md`):
```yaml
measures:
  - [exposed,   securities.stocks.policies_exposed,                         sum,  number, Exposed]
  - [deaths,    securities.stocks.death_count,                              sum,  number, Deaths]
  - [ae_ratio,  {fn: rate, events: deaths, exposed: exposed},   null, decimal, AE Ratio]
```

### Bucket config

| Config | Behavior |
|--------|----------|
| `{size: 5}` | Equal-width bins of width 5 |
| `{edges: [0,5,10,25]}` | Custom break points |
| `{count: 10}` | Equal-frequency (quantile) binning |

### Window types

| Type | Output |
|------|--------|
| `pct_change` | (current − prev) / prev |
| `diff` | current − prev |
| `running_sum` | Cumulative sum across rows |
| `rank` | Rank ascending |

Window tuple: `[key, source_measure_key, window_type, label]`

### Sort options

| Config | Behavior |
|--------|----------|
| `sort.rows: {by: measure_key, order: desc}` | Sort rows by measure |
| `sort.rows: {order: asc}` | Sort rows alphabetically |
| `sort.rows: {values: [A, B, C]}` | Prescriptive ordering |
| `sort.cols: {order: asc}` | Sort columns ascending |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Table title |
| `height` | 400 | Table height in px |
| `renderer` | default | `default` or `ag_grid` |
| `theme` | default | `default` · `financial` · `dark` · `striped` · `minimal` |
| `shading` | — | Conditional format: `{on: measure_key, palette: blues}` |

### Examples

**Simple sector × year pivot:**
```yaml
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true, cols: true}
formatting:
  title: Avg Close by Sector × Year
```

**Issue year binned pivot with windows:**
```yaml
type: table.pivot
data:
  rows:   securities.stocks.issue_year
  cols:   []
  layout: by_measure
  buckets:
    securities.stocks.issue_year: {size: 5}
  measures:
    - [exposed,   securities.stocks.policies_exposed,                         sum,  number, Exposed]
    - [deaths,    securities.stocks.death_count,                              sum,  number, Deaths]
    - [ae_ratio,  {fn: rate, events: deaths, exposed: exposed},   null, decimal, AE Ratio]
  windows:
    - [ae_yoy, ae_ratio, pct_change, AE YoY]
  totals: {rows: true, cols: true}
  sort:
    rows: {by: exposed, order: desc}
config:
  filters:
    securities.stocks.policy_type: [Perm]
```

**AG Grid styled with shading:**
```yaml
type: table.pivot
data:
  rows: corporate.entity.sector
  cols: temporal.year
  measures:
    - [avg_close, securities.stocks.adjusted_close, avg, $, Avg Close]
  totals: {rows: true}
formatting:
  renderer: ag_grid
  theme: financial
  shading: {on: avg_close, palette: blues}
  title: Sector Performance
```

### Notes

- `totals:` is a **data** field — the backend computes summary rows/cols
- `shading:` is a **formatting** field — display-only conditional formatting
- AG Grid renders server-side HTML; the plugin injects `response.html` directly
