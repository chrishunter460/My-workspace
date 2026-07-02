---
title: Exhibit Testing Notes
description: Test notes for every de_funk block type
---

# Exhibit Testing Notes

One test note per exhibit type. Open in Obsidian after the plugin is installed and the
backend is running.

## Prerequisites

1. **Backend running**: `python -m scripts.serve.run_api` (binds to `0.0.0.0:8765`)
2. **Plugin installed**: See deploy instructions in `obsidian-plugin/README.md`
3. **Plugin enabled**: Settings → Community Plugins → de-funk → Enable
4. **Server URL set**: Settings → de-funk → `http://localhost:8765`
5. **Data ingested**: Bronze and Silver layers populated

## Test Notes

| File | Tests |
|------|-------|
| `stock_analysis_test.md` | Full example — all types together |
| `plotly_line_test.md` | config_ref, filter inherit, measure selector |
| `plotly_bar_test.md` | Grouped, stacked, horizontal, implied aggregation |
| `plotly_scatter_test.md` | Scatter, bubble chart, color dimension |
| `plotly_area_test.md` | Stacked area, fill modes |
| `plotly_pie_test.md` | Pie and donut |
| `plotly_heatmap_test.md` | Monthly matrix, color scales |
| `plotly_box_test.md` | OHLCV box, generic box, violin |
| `table_data_test.md` | Column tuples, sort, download |
| `table_pivot_test.md` | by_dimension, by_measure, buckets, windows, great_tables |
| `cards_metric_test.md` | Inline key syntax, commented metrics |
| `control_config_test.md` | Config panel → sidebar + inline, drives 3 exhibits |
| `bronze_crimes_test.md` | Bronze layer — all exhibit types against raw `chicago.crimes` data |

## Quick Backend Check

```bash
curl http://localhost:8765/api/health
# → {"status": "ok"}

curl http://localhost:8765/api/domains
# → field catalog JSON
```
