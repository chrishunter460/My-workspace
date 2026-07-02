---
type: exhibit-type-definition
catalog_key: plotly.scatter
display_name: Scatter Chart
aliases: [scatter]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [x, y]
  optional: [group_by, size, color, sort]
  field_roles:
    x:       {role: measure, description: "X axis — numeric measure"}
    y:       {role: measure, description: "Y axis — numeric measure"}
    group_by:{role: dimension, description: "Series grouping — one series per distinct value"}
    size:    {role: measure, description: "Point size — numeric measure"}
    color:   {role: dimension, description: "Point color dimension (overrides group_by for color)"}
    sort:    {description: "ORDER BY directive applied at query level"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: default
  fields: [title, description, height, show_legend, color_palette, opacity, marker_size]

render_options:
  opacity:     {type: number, min: 0, max: 1, default: 0.7}
  marker_size: {type: number, default: 8}
---

## Scatter Chart

X-Y scatter plot for correlations and distributions. Supports bubble chart via `size:`.

### Data contract

Backend returns `{series: [{name, x: [], y: [], size: []}]}`.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `x` | yes | X axis numeric measure |
| `y` | yes | Y axis numeric measure |
| `group_by` | no | One series (color) per distinct value |
| `size` | no | Bubble size dimension — creates bubble chart |
| `color` | no | Color by dimension (alternative to group_by) |
| `sort` | no | ORDER BY at query level |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | true | Show legend |
| `color_palette` | default | Color scheme |
| `opacity` | 0.7 | Point opacity |
| `marker_size` | 8 | Default marker size (overridden by `size:`) |

### Examples

**Correlation scatter:**
```yaml
type: plotly.scatter
data:
  x: securities.stocks.volume
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Volume vs Price
  opacity: 0.6
```

**Bubble chart:**
```yaml
type: plotly.scatter
data:
  x: corporate.entity.revenue
  y: corporate.entity.profit_margin
  size: corporate.entity.market_cap
  color: corporate.entity.sector
formatting:
  title: Revenue vs Margin (sized by market cap)
  height: 500
```
