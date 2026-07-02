---
type: exhibit-type-definition
catalog_key: plotly.line
display_name: Line Chart
aliases: [line, line_chart, time_series]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [x, y]
  optional: [group_by, sort]
  field_roles:
    x:        {role: dimension, description: "X axis — date or category"}
    y:        {role: measure, multi: true, description: "Y axis — numeric measure(s)"}
    group_by: {role: dimension, description: "Series grouping — one line per distinct value"}
    sort:     {description: "ORDER BY directive — applied at query level before response"}

base_formatting:
  defaults:
    height: 400
    show_legend: true
    color_palette: default
  fields: [title, description, height, show_legend, color_palette]

render_options:
  line_shape: {type: enum, values: [linear, spline, hv], default: linear}
  fill:       {type: enum, values: [none, tozeroy, tonexty], default: none}
  markers:    {type: boolean, default: false}
---

## Line Chart

Time-series lines or categorical trend lines. The most common exhibit type — use for any
continuous series over a date axis or ordered category axis.

### Data contract

Backend returns `{series: [{name, x: [], y: []}]}` — one entry per `group_by` value or
one entry per `y` field when multiple `y` fields are declared.

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `x` | yes | X axis — date or ordered category field |
| `y` | yes | Y axis — one or more measure fields |
| `group_by` | no | Series grouping — one line per distinct value |
| `sort` | no | ORDER BY directive applied at query level |

`group_by` and multiple `y` fields are mutually exclusive — use one or the other.

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | true | Show series legend |
| `color_palette` | default | Color scheme for lines |
| `line_shape` | linear | `linear` · `spline` · `hv` (step) |
| `fill` | none | Fill under line: `none` · `tozeroy` · `tonexty` |
| `markers` | false | Show data point markers |

### Examples

**Minimal:**
```yaml
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
```

**Multi-series by group:**
```yaml
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Daily Close by Ticker
  height: 420
  show_legend: true
config:
  page_filters:
    ignore: [sector]
```

**Multiple Y measures:**
```yaml
type: plotly.line
data:
  x: temporal.date
  y: [securities.stocks.open, securities.stocks.close, securities.stocks.high, securities.stocks.low]
formatting:
  title: OHLC Lines
```

### Notes

- When `group_by` is set, the backend returns one series per distinct value — high cardinality
  dimensions (e.g., 500 tickers) will produce 500 lines. Filter first.
- `fill: tozeroy` fills from each line down to the zero axis — useful for area charts.
  Use `plotly.area` for the same with better defaults.
