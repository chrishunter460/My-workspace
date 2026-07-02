---
type: exhibit-type-definition
catalog_key: control.config
display_name: Config Controls
aliases: [config]
data_mode: ~
status: stable
version: 1.0
renderer: config-panel

base_data:
  required: []
  optional: [dimensions, measures, sort_by, sort_order, color_palette, shading, show_totals, show_legend, show_subtotals, select, multiselect]
  field_roles:
    dimensions:    {description: "Available dimension fields for selection"}
    measures:      {description: "Available measure fields for selection"}
    sort_by:       {description: "Dropdown of measure keys for sort target"}
    sort_order:    {description: "Toggle: asc | desc"}
    color_palette: {description: "Color palette selector"}
    shading:       {description: "Toggle for conditional formatting on linked exhibits"}
    show_totals:   {description: "Checkbox — show totals row/col in linked pivot"}
    show_legend:   {description: "Checkbox — show legend in linked charts"}
    show_subtotals:{description: "Checkbox — show subtotals in linked pivot"}
    select:        {description: "Generic single-select controls list"}
    multiselect:   {description: "Generic multi-select controls list"}

base_formatting:
  defaults:
    title: Controls
  fields: [title, description]
---

## Config Controls

A `control.config` block renders in **two places simultaneously**:

1. **Inline** — an interactive panel where the block appears in the note
2. **Sidebar** — the Controls section of the de-funk sidebar panel

Exhibits link to a control block via `config_ref: {id}` in their `config:` section.
When a control value changes, all linked exhibits re-query and re-render.

### Sidebar layout

```
┌─────────────────────────────┐
│ ▼ Note Filters              │
│   ticker   [AAPL, MSFT ▾]   │
│   date     [90d      ▾]     │
├─────────────────────────────┤
│ ▼ Controls                  │
│   ▼ controls                │  ← this block's id
│     Group by  [Ticker ▾]    │
│     Measure   [Close  ▾]    │
│   ▶ detail-controls         │  ← another block (collapsed)
└─────────────────────────────┘
```

### `data:` fields

| Field | Widget | Description |
|-------|--------|-------------|
| `dimensions` | dropdown | Available dimension fields |
| `measures` | dropdown (multi) | Available measure fields |
| `sort_by` | dropdown | Measure key to sort by |
| `sort_order` | toggle | `asc` / `desc` |
| `color_palette` | dropdown | Visual color scheme |
| `shading` | toggle | Enable/disable gradient shading |
| `show_totals` | checkbox | Show totals row/col |
| `show_legend` | checkbox | Show series legend |
| `show_subtotals` | checkbox | Show subtotals |
| `select` | dropdown(s) | Generic single-select list |
| `multiselect` | chips | Generic multi-select list |

### `config:` fields

| Field | Description |
|-------|-------------|
| `id` | Identifier — referenced by `config_ref` on other blocks |

### Examples

**Dimension + measure selector:**
```yaml
type: control.config
data:
  dimensions: [securities.stocks.ticker, corporate.entity.sector, securities.stocks.exchange_id]
  measures:   [securities.stocks.adjusted_close, securities.stocks.volume, securities.stocks.high]
formatting:
  title: Analysis Controls
config:
  id: controls
```

**Full controls panel:**
```yaml
type: control.config
data:
  dimensions:    [securities.stocks.ticker, corporate.entity.sector]
  measures:      [securities.stocks.adjusted_close, securities.stocks.volume]
  sort_by:       [exposed, deaths, ae_ratio]
  sort_order:    {type: toggle, values: [asc, desc]}
  color_palette: {available: [default, pastel, high_contrast, blues, reds]}
  shading:       {type: toggle, label: "Gradient shading"}
  show_totals:   {type: checkbox, default: true}
  show_legend:   {type: checkbox, default: true}
  select:
    - {id: plan_type, label: "Plan Type", source: securities.stocks.policy_type, multi: false}
  multiselect:
    - {id: regions, label: "Regions", source: corporate.entity.region, multi: true}
config:
  id: controls
```

**Linking exhibits to a control block:**
```yaml
type: plotly.line
data:
  x: temporal.date
formatting:
  title: Configurable Chart
config:
  config_ref: controls     # ← links to control.config block with id: controls
```

### Notes

- A note can have multiple `control.config` blocks with different `id` values
- Exhibits reference a specific block via `config_ref: {id}`
- The sidebar shows each block as a collapsible group identified by its `id`
- Control changes trigger re-query — no caching between state changes
