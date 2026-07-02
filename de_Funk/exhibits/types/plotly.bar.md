---
type: exhibit-type-definition
catalog_key: plotly.bar
display_name: Bar Chart
aliases: [bar, bar_chart]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [x, y]
  optional: [group_by, aggregation, sort]
  field_roles:
    x:           {role: dimension, description: "X axis — category field"}
    y:           {role: measure, multi: true, description: "Bar height — numeric measure(s)"}
    group_by:    {role: dimension, description: "Series grouping — grouped or stacked bars"}
    aggregation: {description: "Override aggregation: sum | avg | count | count_distinct | min | max"}
    sort:        {description: "ORDER BY directive — applied at query level before response"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: default
  fields: [title, description, height, show_legend, color_palette, orientation, barmode]

render_options:
  orientation: {type: enum, values: [v, h], default: v}
  barmode:     {type: enum, values: [group, stack, relative], default: group}
---

## Bar Chart

Categorical bar chart. Supports grouped, stacked, and horizontal layouts.

### Data contract

Backend returns `{series: [{name, x: [], y: []}]}`. When `group_by` is set, each distinct
value becomes a series and the bars are grouped or stacked per `barmode`.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `x` | yes | Category dimension for bar positions |
| `y` | yes | Measure for bar height (or length if horizontal) |
| `group_by` | no | Creates grouped/stacked bars by dimension |
| `aggregation` | no | Override aggregation type |
| `sort` | no | ORDER BY directive applied at query level |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | true | Show series legend |
| `color_palette` | default | Color scheme |
| `orientation` | v | `v` (vertical) or `h` (horizontal) |
| `barmode` | group | `group` · `stack` · `relative` (100% stack) |

### Examples

**Simple count by category:**
```yaml
type: plotly.bar
data:
  x: corporate.entity.sector
  y: securities.stocks.ticker
  aggregation: count_distinct
formatting:
  title: Companies by Sector
```

**Grouped bars:**
```yaml
type: plotly.bar
data:
  x: temporal.year
  y: municipal.total_paid
  group_by: municipal.department_name
formatting:
  title: Spend by Department × Year
  barmode: group
  height: 450
```

**Horizontal sorted:**
```yaml
type: plotly.bar
data:
  x: securities.stocks.ticker
  y: securities.stocks.volume
  aggregation: sum
  sort: {by: securities.stocks.volume, order: desc}
formatting:
  orientation: h
  title: Total Volume by Ticker
```
