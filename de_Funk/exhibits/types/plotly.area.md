---
type: exhibit-type-definition
catalog_key: plotly.area
display_name: Area Chart
aliases: [area]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [x, y]
  optional: [group_by, sort]
  field_roles:
    x:        {role: dimension, description: "X axis — date or ordered category"}
    y:        {role: measure, multi: true, description: "Y axis — numeric measure(s)"}
    group_by: {role: dimension, description: "Series grouping — stacked area per value"}
    sort:     {description: "ORDER BY directive applied at query level"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: default
    fill_mode: tozeroy
  fields: [title, description, height, show_legend, color_palette, fill_mode, opacity]

render_options:
  fill_mode: {type: enum, values: [tozeroy, tonexty], default: tozeroy}
  opacity:   {type: number, min: 0, max: 1, default: 0.4}
---

## Area Chart

Filled area chart — same as `plotly.line` with `fill: tozeroy` defaulted on.
Best for showing cumulative values or stacked proportions over time.

### Data contract

Same as `plotly.line` — backend returns `{series: [{name, x: [], y: []}]}`.
`fill_mode: tonexty` stacks series on top of each other.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `x` | yes | X axis — date or ordered category |
| `y` | yes | Y axis numeric measure(s) |
| `group_by` | no | One filled series per distinct value |
| `sort` | no | ORDER BY at query level |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | true | Show legend |
| `color_palette` | default | Color scheme |
| `fill_mode` | tozeroy | `tozeroy` (fill to zero) · `tonexty` (stacked) |
| `opacity` | 0.4 | Fill opacity |

### Examples

**Cumulative area:**
```yaml
type: plotly.area
data:
  x: temporal.date
  y: municipal.total_paid
formatting:
  title: Cumulative Spend Over Time
  opacity: 0.5
```

**Stacked area by sector:**
```yaml
type: plotly.area
data:
  x: temporal.year
  y: securities.stocks.volume
  group_by: corporate.entity.sector
formatting:
  title: Volume by Sector (Stacked)
  fill_mode: tonexty
  height: 450
```
