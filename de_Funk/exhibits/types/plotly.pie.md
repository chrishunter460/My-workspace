---
type: exhibit-type-definition
catalog_key: plotly.pie
display_name: Pie Chart
aliases: [pie]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [labels, values]
  optional: [sort]
  field_roles:
    labels: {role: dimension, description: "Slice labels — category dimension"}
    values: {role: measure, description: "Slice sizes — numeric measure"}
    sort:   {description: "ORDER BY at query level — affects which slices appear (use with limit)"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: default
    hole: 0
  fields: [title, description, height, show_legend, color_palette, hole]

render_options:
  hole: {type: number, min: 0, max: 0.9, default: 0, description: "Donut hole size 0=pie, 0.5=donut"}
---

## Pie Chart

Proportional pie or donut chart. Use for part-of-whole distributions.
Avoid when there are more than ~8 categories — use a bar chart instead.

### Data contract

Backend returns `{labels: [], values: []}`.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `labels` | yes | Category dimension for slice labels |
| `values` | yes | Numeric measure for slice sizes |
| `sort` | no | ORDER BY at query level |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | true | Show legend |
| `color_palette` | default | Color scheme |
| `hole` | 0 | Donut hole size: `0` = solid pie, `0.5` = half donut |

### Examples

**Simple pie:**
```yaml
type: plotly.pie
data:
  labels: corporate.entity.sector
  values: securities.stocks.market_cap
  aggregation: sum
formatting:
  title: Market Cap by Sector
```

**Donut chart:**
```yaml
type: plotly.pie
data:
  labels: municipal.department_name
  values: municipal.total_paid
formatting:
  title: Spend by Department
  hole: 0.4
  height: 420
```
