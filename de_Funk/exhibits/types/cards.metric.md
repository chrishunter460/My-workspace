---
type: exhibit-type-definition
catalog_key: cards.metric
display_name: Metric Cards
aliases: [metric_cards, kpi]
data_mode: metric
status: stable
version: 1.0
renderer: metric-cards

base_data:
  required: [metrics]
  optional: []
  field_roles:
    metrics: {description: "List of metric tuples: [key, domain.field, aggregation, format, label]"}

base_formatting:
  defaults:
    columns: 4
    color_palette: default
  fields: [title, description, columns, color_palette]
---

## Metric Cards

KPI card display — a row of labeled metric tiles. Each card shows a single aggregated value.

### Data contract

Backend returns `{metrics: [{key, label, value, format}]}`.

### Metric tuple syntax

```yaml
metrics:
  - [key,  domain.field,  aggregation,  format,  label]
```

Same positional tuple as `measures:` everywhere else.

| Position | Required | Description |
|----------|----------|-------------|
| `key` | yes | Internal identifier |
| `domain.field` | yes | Field to aggregate |
| `aggregation` | yes | `sum` · `avg` · `count` · `count_distinct` · `min` · `max` |
| `format` | no | Format code override |
| `label` | no | Display label (key with `_` → space if omitted) |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Section title above cards |
| `columns` | 4 | Cards per row |
| `color_palette` | default | Card accent color scheme |

### Examples

**Stock summary KPIs:**
```yaml
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]
    - [high_52w,   securities.stocks.high,            max,  $,      52w High]
    - [low_52w,    securities.stocks.low,             min,  $,      52w Low]
```

**Inline `#`-commented metrics:**
```yaml
type: cards.metric
data:
  metrics:
    - [avg_close,  securities.stocks.adjusted_close,  avg,  $,      Avg Close]    # avg close price
    - [total_vol,  securities.stocks.volume,          sum,  number, Total Volume]  # shares traded
    # - [beta, securities.stocks.beta, avg, decimal2, Beta]                        # commented out
```

**Municipal finance summary:**
```yaml
type: cards.metric
data:
  metrics:
    - [total_spend,     municipal.transaction_amount,  sum,    $M,     Total Spend]
    - [vendor_count,    municipal.vendor_id,           count_distinct, number, Vendors]
    - [contract_count,  municipal.contract_id,         count_distinct, number, Contracts]
    - [avg_payment,     municipal.transaction_amount,  avg,    $K,     Avg Payment]
formatting:
  columns: 4
  title: Finance Summary
```

### Notes

- The `key` becomes the display label if `label` is omitted — underscores converted to spaces
- All page-level and exhibit-level filters apply to the aggregation
- Cards render horizontally up to `columns` per row, then wrap
