---
id: custom_notebook_example
title: Custom Notebook Example - Complete Guide
description: Comprehensive example showing all filter types and exhibit types
tags: [example, tutorial, filters, exhibits]
models: [company, macro]
author: de_Funk Team
created: 2024-11-08
updated: 2024-11-08
---

<!--
================================================================================
CUSTOM NOTEBOOK EXAMPLE

This notebook demonstrates ALL available features:
- All filter types
- All exhibit types
- Multi-model queries
- Markdown features
- Best practices

Based on existing notebooks in /home/user/de_Funk/configs/notebooks/

NOTEBOOK STRUCTURE:
1. Frontmatter (YAML metadata above)
2. Filters (interactive controls)
3. Markdown content with exhibits
4. Exhibits (data visualizations)

================================================================================
-->

<!-- ========================================
SECTION 1: FILTER TYPES
All available filter types demonstrated
======================================== -->

## Filters Overview

This section demonstrates all available filter types in de_Funk notebooks.

### Date Range Filter

Select a date range for time-based filtering:

$filter${
  id: date_range
  type: date_range
  label: Analysis Period
  operator: between
  default: {start: "2024-01-01", end: "2024-01-31"}
  help_text: Select the date range for analysis
}

### Select Filter (Single)

Choose one ticker from available options:

$filter${
  id: primary_ticker
  type: select
  label: Primary Stock
  multi: false
  source: {model: company, table: fact_prices, column: ticker}
  default: "AAPL"
  help_text: Select a single stock ticker
}

### Select Filter (Multi)

Choose multiple tickers to compare:

$filter${
  id: comparison_tickers
  type: select
  label: Comparison Stocks
  multi: true
  source: {model: company, table: fact_prices, column: ticker}
  default: ["AAPL", "MSFT", "GOOGL"]
  help_text: Select multiple stocks for comparison
}

### Slider Filter (Numeric Range)

Filter by volume threshold:

$filter${
  id: min_volume
  type: slider
  label: Minimum Trading Volume
  min_value: 0
  max_value: 100000000
  step: 1000000
  default: 10000000
  operator: gte
  help_text: Filter out low-volume trading days
}

### Text Input Filter

Filter by text matching:

$filter${
  id: company_name_search
  type: text
  label: Company Name Search
  operator: contains
  default: ""
  help_text: Search for companies by name (partial match)
  optional: true
}

### Checkbox Filter

Boolean filter for including/excluding data:

$filter${
  id: include_high_volatility
  type: checkbox
  label: Include High Volatility Days
  default: true
  help_text: Include days with >5% price change
}

### Static Options Filter

Select from predefined options:

$filter${
  id: exchange
  type: select
  label: Stock Exchange
  multi: false
  options: ["XNAS", "XNYS", "ARCX"]
  default: "XNAS"
  help_text: Filter by stock exchange
}

---

<!-- ========================================
SECTION 2: EXHIBIT TYPES
All available exhibit (visualization) types
======================================== -->

## Data Visualizations

This section demonstrates all available exhibit types.

### Metric Cards

Summary statistics displayed as cards:

$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    {
      measure: close,
      label: "Avg Close Price",
      aggregation: avg,
      format: "${:.2f}"
    },
    {
      measure: volume,
      label: "Total Volume",
      aggregation: sum,
      format: "{:,.0f}"
    },
    {
      measure: high,
      label: "Peak Price",
      aggregation: max,
      format: "${:.2f}"
    },
    {
      measure: low,
      label: "Lowest Price",
      aggregation: min,
      format: "${:.2f}"
    }
  ]
}

### Line Chart

Time series visualization for trends:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Daily Closing Prices
  x_label: Date
  y_label: Price ($)
  height: 400
}

### Bar Chart

Compare values across categories:

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: volume
  color: ticker
  title: Total Trading Volume by Stock
  x_label: Ticker
  y_label: Total Volume
  aggregation: sum
  height: 400
}

### Scatter Plot

Show relationships between two variables:

$exhibits${
  type: scatter
  source: company.fact_prices
  x: volume
  y: close
  color: ticker
  size: high
  title: Volume vs Price
  x_label: Trading Volume
  y_label: Closing Price ($)
  height: 400
}

### Area Chart

Cumulative or stacked visualization:

$exhibits${
  type: area_chart
  source: company.fact_prices
  x: trade_date
  y: volume
  color: ticker
  title: Trading Volume Over Time
  stacked: false
  height: 400
}

### Histogram

Distribution visualization:

$exhibits${
  type: histogram
  source: company.fact_prices
  x: close
  bins: 50
  title: Price Distribution
  x_label: Closing Price ($)
  y_label: Frequency
  height: 400
}

### Box Plot

Statistical distribution summary:

$exhibits${
  type: box_plot
  source: company.fact_prices
  x: ticker
  y: close
  title: Price Distribution by Stock
  x_label: Ticker
  y_label: Closing Price ($)
  height: 400
}

### Heatmap

Two-dimensional data visualization:

$exhibits${
  type: heatmap
  source: company.fact_prices
  x: ticker
  y: trade_date
  z: close
  title: Price Heatmap
  colorscale: Viridis
  height: 400
}

### Data Table

Interactive table with sorting and filtering:

$exhibits${
  type: data_table
  source: company.fact_prices
  columns: [trade_date, ticker, open, high, low, close, volume]
  page_size: 20
  sortable: true
  searchable: true
  download: true
}

### Pivot Table

Aggregated cross-tabulation:

$exhibits${
  type: pivot_table
  source: company.fact_prices
  rows: [ticker]
  columns: [trade_date]
  values: close
  aggregation: avg
}

---

<!-- ========================================
SECTION 3: MULTI-MODEL QUERIES
Using data from multiple models
======================================== -->

## Multi-Model Analysis

Combining data from company and macro models:

### Economic Context

Add macro economic indicators to the analysis:

$filter${
  id: macro_indicator
  type: select
  label: Economic Indicator
  multi: false
  source: {model: macro, table: fact_employment, column: indicator_name}
  default: "unemployment_rate"
  help_text: Select macro indicator to overlay
}

### Stock Prices with Economic Context

Visualize stock performance alongside economic indicators:

$exhibits${
  type: line_chart
  sources: [
    {model: company, table: fact_prices, y: close, label: "Stock Price"},
    {model: macro, table: fact_employment, y: value, label: "Indicator Value"}
  ]
  x: date
  title: Stock Performance vs Economic Indicator
  height: 400
  dual_axis: true
}

---

<!-- ========================================
SECTION 4: MARKDOWN FEATURES
Rich text and formatting
======================================== -->

## Markdown Formatting

### Text Formatting

You can use **bold**, *italic*, ~~strikethrough~~, and `inline code`.

### Lists

Unordered list:
- First item
- Second item
  - Nested item
  - Another nested item
- Third item

Ordered list:
1. First step
2. Second step
3. Third step

### Code Blocks

```python
# Example code block
import pandas as pd

df = session.get_table('company', 'fact_prices')
print(df.head())
```

### Blockquotes

> This is a blockquote. Use it for important notes or quotes.
>
> It can span multiple lines.

### Tables

| Metric | Value | Change |
|--------|-------|--------|
| Price | $150.25 | +2.5% |
| Volume | 1,250,000 | -5.2% |
| Market Cap | $2.5T | +1.8% |

### Links

[View Documentation](../docs/guide/README.md)
[External Link](https://example.com)

### Images

![Chart Example](./images/example-chart.png)

### Horizontal Rules

Use three dashes for a horizontal rule:

---

### Collapsible Sections

<details>
<summary>Click to expand detailed analysis</summary>

This content is hidden by default and expands when clicked.

You can include any markdown here:
- Lists
- **Formatting**
- Even exhibits!

$exhibits${
  type: data_table
  source: company.fact_prices
  columns: [trade_date, ticker, close]
  page_size: 10
}

</details>

---

<!-- ========================================
SECTION 5: ADVANCED FEATURES
======================================== -->

## Advanced Features

### Conditional Content

You can show/hide content based on filter values:

<!-- Only shown when primary_ticker is AAPL -->
$if{primary_ticker == "AAPL"}$
### Apple-Specific Analysis

This section only appears when analyzing Apple stock.

$exhibits${
  type: metric_cards
  source: company.fact_prices
  filter: {ticker: "AAPL"}
  metrics: [
    {measure: close, label: "AAPL Avg Close", aggregation: avg}
  ]
}
$endif$

### Custom Aggregations

Define custom calculations in exhibits:

$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    {
      measure: "(high - low) / open * 100",
      label: "Avg Daily Range %",
      aggregation: avg,
      format: "{:.2f}%"
    },
    {
      measure: "volume * close",
      label: "Dollar Volume",
      aggregation: sum,
      format: "${:,.0f}"
    }
  ]
}

### Nested Filters

Filters can depend on other filters:

$filter${
  id: sector
  type: select
  label: Sector
  source: {model: company, table: dim_company, column: sector}
  multi: false
}

$filter${
  id: company_in_sector
  type: select
  label: Company
  source: {
    model: company,
    table: dim_company,
    column: ticker,
    filter: {sector: "$sector"}  # Depends on sector filter
  }
  multi: false
}

### Chart Customization

Full control over chart appearance:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Customized Stock Chart
  x_label: Trading Date
  y_label: Closing Price (USD)
  height: 500
  theme: plotly_dark
  show_legend: true
  legend_position: right
  line_width: 2
  marker_size: 5
  grid: true
}

---

<!-- ========================================
SECTION 6: BEST PRACTICES
======================================== -->

## Best Practices

### Organization

1. **Use clear section headers** - H2 (##) for major sections, H3 (###) for subsections
2. **Group related filters** - Keep filters near the exhibits they affect
3. **Add help text** - Every filter should have descriptive help_text
4. **Provide context** - Use markdown to explain what users are seeing

### Performance

1. **Limit data** - Use filters to reduce data volume
2. **Appropriate aggregation** - Pre-aggregate when showing summaries
3. **Page size** - Keep data tables to reasonable page sizes
4. **Lazy loading** - Use collapsible sections for expensive exhibits

### User Experience

1. **Sensible defaults** - Default filter values should show meaningful data
2. **Clear labels** - Use descriptive labels for filters and metrics
3. **Format numbers** - Use appropriate formatting for currency, percentages, etc.
4. **Progressive disclosure** - Hide complex options in collapsible sections

### Accessibility

1. **Alt text for images** - Provide descriptive alt text
2. **Color choice** - Use colorblind-friendly color schemes
3. **Font size** - Ensure text is readable
4. **Keyboard navigation** - All filters should be keyboard accessible

---

<!-- ========================================
SECTION 7: COMMON PATTERNS
======================================== -->

## Common Patterns

### Executive Summary Pattern

Start with high-level metrics, drill down to details:

$exhibits${
  type: metric_cards
  source: company.fact_prices
  metrics: [
    {measure: close, label: "Avg Price", aggregation: avg},
    {measure: volume, label: "Total Volume", aggregation: sum}
  ]
}

<details>
<summary>View Detailed Breakdown</summary>

$exhibits${
  type: data_table
  source: company.fact_prices
  download: true
}

</details>

### Comparison Pattern

Compare multiple entities side-by-side:

$filter${
  id: compare_tickers
  type: select
  label: Stocks to Compare
  multi: true
  source: {model: company, table: fact_prices, column: ticker}
  default: ["AAPL", "MSFT"]
}

$exhibits${
  type: bar_chart
  source: company.fact_prices
  x: ticker
  y: close
  aggregation: avg
  title: Average Price Comparison
}

### Trend Analysis Pattern

Show trends over time with context:

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: close
  color: ticker
  title: Price Trends
}

$exhibits${
  type: line_chart
  source: company.fact_prices
  x: trade_date
  y: volume
  color: ticker
  title: Volume Trends
}

### Distribution Analysis Pattern

Examine statistical distributions:

$exhibits${
  type: histogram
  source: company.fact_prices
  x: close
  bins: 30
  title: Price Distribution
}

$exhibits${
  type: box_plot
  source: company.fact_prices
  x: ticker
  y: close
  title: Price Range by Stock
}

---

<!-- ========================================
SECTION 8: TROUBLESHOOTING
======================================== -->

## Troubleshooting

### Common Issues

**Issue: Filter not working**
- Check filter ID matches in exhibit source
- Verify column exists in table
- Check operator is appropriate for data type

**Issue: No data in exhibit**
- Verify filters aren't too restrictive
- Check date range includes data
- Verify model and table names are correct

**Issue: Chart not rendering**
- Check exhibit type is spelled correctly
- Verify required fields (x, y for line chart)
- Check data has values for specified columns

**Issue: Performance is slow**
- Add more restrictive filters
- Reduce date range
- Use aggregation instead of raw data
- Consider pre-aggregating in model

---

<!-- ========================================
SECTION 9: REFERENCE
======================================== -->

## Quick Reference

### Filter Types

| Type | Use Case | Required Fields | Example |
|------|----------|----------------|---------|
| `date_range` | Date filtering | `default: {start, end}` | Date picker |
| `select` | Choose from list | `source` or `options` | Dropdown |
| `slider` | Numeric range | `min_value`, `max_value` | Slider |
| `text` | Text search | `operator` | Text input |
| `checkbox` | Boolean | `default` | Checkbox |

### Exhibit Types

| Type | Use Case | Required Fields | Best For |
|------|----------|----------------|----------|
| `metric_cards` | Summary stats | `metrics` | KPIs |
| `line_chart` | Trends | `x`, `y` | Time series |
| `bar_chart` | Comparisons | `x`, `y` | Categories |
| `scatter` | Relationships | `x`, `y` | Correlation |
| `area_chart` | Cumulative | `x`, `y` | Totals |
| `histogram` | Distribution | `x`, `bins` | Frequencies |
| `box_plot` | Statistics | `x`, `y` | Outliers |
| `heatmap` | 2D patterns | `x`, `y`, `z` | Matrices |
| `data_table` | Raw data | `columns` | Details |
| `pivot_table` | Cross-tab | `rows`, `columns`, `values` | Summaries |

### Aggregation Types

- `sum` - Total
- `avg` - Average
- `count` - Count
- `count_distinct` - Unique count
- `min` - Minimum
- `max` - Maximum
- `median` - Median value
- `std` - Standard deviation

### Operators

- `eq` - Equals
- `ne` - Not equals
- `gt` - Greater than
- `gte` - Greater than or equal
- `lt` - Less than
- `lte` - Less than or equal
- `between` - Between (for date ranges)
- `contains` - Contains text
- `in` - In list

---

<!-- ========================================
FOOTER
======================================== -->

## Learn More

- [Notebook Documentation](../../docs/guide/1-getting-started/notebooks.md)
- [Filter Reference](../../docs/guide/1-getting-started/filters.md)
- [Exhibit Reference](../../docs/guide/1-getting-started/exhibits.md)
- [Model Documentation](../../docs/guide/2-models/README.md)

---

**Questions?** Contact de_Funk Team or open an issue on GitHub.

**Version:** 1.0
**Last Updated:** 2024-11-08
