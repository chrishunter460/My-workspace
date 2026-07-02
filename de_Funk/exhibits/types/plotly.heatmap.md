---
type: exhibit-type-definition
catalog_key: plotly.heatmap
display_name: Heatmap
aliases: [heatmap]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [x, y, z]
  optional: [aggregation, sort]
  field_roles:
    x: {role: dimension, description: "X axis — column dimension"}
    y: {role: dimension, description: "Y axis — row dimension"}
    z: {role: measure, description: "Cell value — numeric measure (determines color)"}
    aggregation: {description: "Aggregation for z: sum | avg | count | min | max"}
    sort:        {description: "ORDER BY directive at query level"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: blues
  fields: [title, description, height, show_legend, color_palette, shading]

render_options:
  color_scale: {type: enum, values: [blues, reds, greens, viridis, rdbu], default: blues}
  reverse_scale: {type: boolean, default: false}
  show_values:   {type: boolean, default: false}
---

## Heatmap

2D color matrix — rows × columns with color intensity representing a measure.
Best for showing density, correlation matrices, or temporal patterns.

### Data contract

Backend returns `{x: [], y: [], z: [[row0_vals], [row1_vals], ...]}` — a 2D matrix.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `x` | yes | Column dimension |
| `y` | yes | Row dimension |
| `z` | yes | Cell value measure (drives color) |
| `aggregation` | no | Override aggregation for z |
| `sort` | no | ORDER BY at query level |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `color_palette` | blues | Color scale: `blues` · `reds` · `greens` · `viridis` · `rdbu` |
| `reverse_scale` | false | Reverse the color scale direction |
| `show_values` | false | Show numeric values inside cells |
| `shading` | — | Conditional formatting: `{on: measure_key, palette: blues}` |

### Examples

**Monthly ridership heatmap:**
```yaml
type: plotly.heatmap
data:
  x: temporal.month
  y: temporal.year
  z: municipal.total_rides
  aggregation: sum
formatting:
  title: Monthly Ridership
  color_palette: blues
  show_values: true
```

**Correlation matrix:**
```yaml
type: plotly.heatmap
data:
  x: securities.stocks.ticker
  y: securities.stocks.ticker
  z: securities.stocks.price_correlation
formatting:
  title: Price Correlation Matrix
  color_palette: rdbu
  height: 600
```
