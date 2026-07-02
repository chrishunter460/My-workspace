---
type: exhibit-type-definition
catalog_key: plotly.box
display_name: Box / OHLCV Chart
aliases: [box, ohlcv, candlestick]
data_mode: graphical
status: stable
version: 1.0
renderer: graphical

base_data:
  required: [category]
  optional: [open, high, low, close, y, sort]
  field_roles:
    category: {role: dimension, description: "X axis grouping — one box per distinct value"}
    open:     {role: measure, description: "OHLCV open price — enables candlestick mode"}
    high:     {role: measure, description: "OHLCV high price"}
    low:      {role: measure, description: "OHLCV low price"}
    close:    {role: measure, description: "OHLCV close price"}
    y:        {role: measure, description: "Generic numeric measure — used when OHLCV not specified"}
    sort:     {description: "ORDER BY at query level"}

base_formatting:
  defaults:
    height: 400
    show_legend: false
    color_palette: default
  fields: [title, description, height, show_legend, color_palette, box_mode]

render_options:
  box_mode: {type: enum, values: [box, violin], default: box}
---

## Box / OHLCV Chart

Box-and-whisker chart. Two modes:

1. **OHLCV mode** — when `open`, `high`, `low`, `close` are all specified, renders as
   candlestick/OHLCV box showing price range distribution by `category`
2. **Generic mode** — when only `y` is specified, renders as standard statistical box plot

### Data contract

OHLCV mode: `{series: [{name, open: [], high: [], low: [], close: []}]}`
Generic mode: `{series: [{name, y: []}]}`

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `category` | yes | X axis — one box per distinct value |
| `open` | OHLCV | Opening price |
| `high` | OHLCV | High price |
| `low` | OHLCV | Low price |
| `close` | OHLCV | Closing price |
| `y` | generic | Numeric measure for generic box plot |
| `sort` | no | ORDER BY at query level |

Either all four OHLCV fields must be present, or just `y` — not a mix.

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Chart title |
| `height` | 400 | Chart height in px |
| `show_legend` | false | Show legend |
| `color_palette` | default | Color scheme |
| `box_mode` | box | `box` or `violin` (generic mode only) |

### Examples

**OHLCV price distribution by ticker:**
```yaml
type: plotly.box
data:
  category: securities.stocks.ticker
  open:  securities.stocks.open
  high:  securities.stocks.high
  low:   securities.stocks.low
  close: securities.stocks.adjusted_close
formatting:
  title: Price Distribution by Ticker
  height: 420
```

**Generic box — days to close by request type:**
```yaml
type: plotly.box
data:
  category: municipal.request_type
  y: municipal.days_to_close
formatting:
  title: Days to Close by Request Type
  box_mode: violin
```
