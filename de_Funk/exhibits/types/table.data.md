---
type: exhibit-type-definition
catalog_key: table.data
display_name: Data Table
aliases: [data_table]
data_mode: tabular
status: stable
version: 1.0
renderer: tabular

base_data:
  required: [columns]
  optional: [sort_by, sort_order]
  field_roles:
    columns:    {description: "List of column tuples: [key, domain.field, aggregation, format, label]"}
    sort_by:    {description: "domain.field to ORDER BY — applied at query level"}
    sort_order: {description: "asc | desc (default: asc)"}

base_formatting:
  defaults:
    height: 400
    page_size: 25
    download: false
  fields: [title, description, height, page_size, download]
---

## Data Table

Scrollable flat data table. Columns are declared as positional tuples.

### Data contract

Backend returns `{columns: [{key, label, format}], rows: [[val, val, ...], ...]}`.

### Column tuple syntax

```yaml
columns:
  - [key, domain.field, aggregation, format, label]
```

| Position | Required | Description |
|----------|----------|-------------|
| `key` | yes | Internal identifier |
| `domain.field` | yes | Field reference |
| `aggregation` | no | `sum` · `avg` · `count` etc. (`null` = raw) |
| `format` | no | Format code override (uses model default if omitted) |
| `label` | no | Display column header (uses key if omitted) |

### Format codes

| Code | Example |
|------|---------|
| `$` | $185.20 |
| `$K` | $185.2K |
| `$M` | $1.85M |
| `%` | 4.6% |
| `number` | 1,234,567 |
| `decimal` | 1.2346 |
| `decimal2` | 1.23 |
| `date` | 2024-01-02 |

### `data:` fields

| Field | Required | Description |
|-------|----------|-------------|
| `columns` | yes | List of column tuples |
| `sort_by` | no | `domain.field` ORDER BY — applied at query level |
| `sort_order` | no | `asc` or `desc` |

### `formatting:` fields

| Field | Default | Description |
|-------|---------|-------------|
| `title` | — | Table title |
| `height` | 400 | Table height in px |
| `page_size` | 25 | Rows per page |
| `download` | false | Show CSV download button |

### Examples

**OHLCV table with sorted dates:**
```yaml
type: table.data
data:
  columns:
    - [ticker,  securities.stocks.ticker]
    - [date,    temporal.date,          null, date]
    - [open,    securities.stocks.open,            null, $]
    - [high,    securities.stocks.high,            null, $]
    - [low,     securities.stocks.low,             null, $]
    - [close,   securities.stocks.adjusted_close,  null, $,    Close]
    - [volume,  securities.stocks.volume,          null, $K,   Volume]
  sort_by:    temporal.date
  sort_order: desc
formatting:
  page_size: 20
  download:  true
```

**Service request table:**
```yaml
type: table.data
data:
  columns:
    - [request_id,    municipal.request_id]
    - [type,          municipal.request_type]
    - [created,       municipal.created_date,   null, date]
    - [days_to_close, municipal.days_to_close,  null, number]
    - [ward,          municipal.ward]
  sort_by:    municipal.created_date
  sort_order: desc
formatting:
  page_size: 50
  download:  true
```

### Notes

- Omit `aggregation` (or pass `null`) for raw row-level data
- Columns with no `format` use the model's default `{format: ...}` declaration
- `sort_by` is a data concern — it drives ORDER BY at query time, not display sorting
