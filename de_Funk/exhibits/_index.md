---
title: Exhibit Types Catalog
description: All de_funk block types — scanned from exhibits/types/*.md at plugin startup
version: 2.0

catalog:
  - key: plotly.line
    aliases: [line, line_chart, time_series]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.line.md

  - key: plotly.bar
    aliases: [bar, bar_chart]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.bar.md

  - key: plotly.scatter
    aliases: [scatter]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.scatter.md

  - key: plotly.area
    aliases: [area]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.area.md

  - key: plotly.pie
    aliases: [pie]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.pie.md

  - key: plotly.heatmap
    aliases: [heatmap]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.heatmap.md

  - key: plotly.box
    aliases: [box, ohlcv, candlestick]
    data_mode: graphical
    renderer: graphical
    file: types/plotly.box.md

  - key: table.data
    aliases: [data_table]
    data_mode: tabular
    renderer: tabular
    file: types/table.data.md

  - key: table.pivot
    aliases: [pivot_table, pivot, great_table, gt]
    data_mode: tabular
    renderer: pivot
    file: types/table.pivot.md

  - key: cards.metric
    aliases: [metric_cards, kpi]
    data_mode: metric
    renderer: metric-cards
    file: types/cards.metric.md

  - key: control.config
    aliases: [config]
    data_mode: ~
    renderer: config-panel
    file: types/control.config.md
---

# Exhibit Types Catalog

The plugin scans `exhibits/types/*.md` at startup and builds this catalog from frontmatter.
No separate registry file — the markdown files ARE the registry.

## Type Catalog

| Key | Aliases | Mode | Description |
|-----|---------|------|-------------|
| `plotly.line` | `line`, `line_chart` | graphical | Time-series or categorical line chart |
| `plotly.bar` | `bar`, `bar_chart` | graphical | Grouped or stacked bar chart |
| `plotly.scatter` | `scatter` | graphical | X-Y scatter with optional size/color |
| `plotly.area` | `area` | graphical | Filled area chart |
| `plotly.pie` | `pie` | graphical | Proportional pie/donut chart |
| `plotly.heatmap` | `heatmap` | graphical | 2D color matrix |
| `plotly.box` | `box`, `ohlcv` | graphical | Box-and-whisker / OHLCV candlestick |
| `table.data` | `data_table` | tabular | Scrollable flat data table |
| `table.pivot` | `pivot`, `gt` | tabular | Pivot table with optional AG Grid rendering |
| `cards.metric` | `kpi` | metric | KPI metric cards |
| `control.config` | `config` | — | Interactive control panel |

`table.pivot` with `formatting.renderer: great_tables` enables AG Grid styled output.
`gt` and `great_table` are aliases that set this renderer as the default.

## Base Files

| File | Purpose |
|------|---------|
| [`_base/exhibit.md`](_base/exhibit.md) | Base defaults all types inherit |
| [`_base/computations.md`](_base/computations.md) | Typed function catalog for derived measures |

## Quick Start

```yaml
type: plotly.line
data:
  x: temporal.date
  y: securities.stocks.adjusted_close
  group_by: securities.stocks.ticker
formatting:
  title: Daily Close Prices
  height: 420
```

See [`testing/stock_analysis_test.md`](testing/stock_analysis_test.md) for a full example note
with all block types.

## Notes

- `temporal` is always auto-injected — omit it from `models:` in note frontmatter
- Field references use `domain.field` dot notation resolved by the backend
- All multi-field lists use positional tuple syntax: `[key, field, aggregation, format, label]`
- Derived measures use the computation catalog — see `_base/computations.md`
