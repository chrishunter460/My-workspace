---
title: Bronze Layer Test — Chicago Crimes
filters:
  crime_type:
    source: chicago.crimes.primary_type
    type: select
    multi: true
    layer: bronze
    context_filters: true
  year_range:
    source: chicago.crimes.year
    type: range
    layer: bronze
    default: [2020, 2025]
---

# Bronze Layer Test — Chicago Crimes

Tests for querying Bronze (raw) data via `layer: bronze`. Field references
use `provider.endpoint.field` format instead of `domain.model.field`.

**Prerequisites**: Backend running, Chicago crimes Bronze data ingested.

```bash
curl http://localhost:8765/api/bronze/endpoints | python -m json.tool
```

---

## KPI Cards — Crime Summary

```de_funk
type: cards.metric
layer: bronze
data:
  metrics:
    - [total,      chicago.crimes.id,           count,          number, Total Incidents]
    - [arrests,    chicago.crimes.arrest,        sum,            number, Total Arrests]
    - key: arrest_pct
      field: {fn: rate, events: arrests, exposed: total}
      format: "%"
      label: Arrest Rate
    - [districts,  chicago.crimes.district,      count_distinct, number, Districts]
formatting:
  title: Crime Summary (Bronze)
```

---

## Bar Chart — Top Crime Types

```de_funk
type: plotly.bar
layer: bronze
data:
  x: chicago.crimes.primary_type
  y: chicago.crimes.id
  aggregation: count
  sort:
    by: y0
    order: desc
formatting:
  title: Top Crime Types
  height: 400
  orientation: v
```

---

## Line Chart — Crimes by Year

```de_funk
type: plotly.line
layer: bronze
data:
  x: chicago.crimes.year
  y: chicago.crimes.id
  aggregation: count
formatting:
  title: Crime Incidents by Year
  height: 350
```

---

## Pivot — Crime Type by Year

```de_funk
type: table.pivot
layer: bronze
data:
  rows: chicago.crimes.primary_type
  cols: [chicago.crimes.year]
  measures:
    - [incidents, chicago.crimes.id,    count, number, Incidents]
    - [arrests,   chicago.crimes.arrest, sum,  number, Arrests]
  totals:
    rows: true
    columns: true
  sort:
    by: incidents
    where: 2025
    order: desc
formatting:
  title: Crime Type by Year (Bronze)
```

---

## Table — Recent Crimes Sample

```de_funk
type: table.data
layer: bronze
data:
  columns:
    - [case_num,    chicago.crimes.case_number]
    - [type,        chicago.crimes.primary_type]
    - [description, chicago.crimes.description]
    - [location,    chicago.crimes.location_description]
    - [arrest,      chicago.crimes.arrest]
    - [year,        chicago.crimes.year]
  sort_by: chicago.crimes.year
  sort_order: desc
formatting:
  title: Recent Crimes (Bronze Raw)
  page_size: 25
```

---

## Pie — Crime Distribution

```de_funk
type: plotly.pie
layer: bronze
data:
  x: chicago.crimes.primary_type
  y: chicago.crimes.id
  aggregation: count
formatting:
  title: Crime Type Distribution
  height: 400
```

---

## Scatter — Arrests by District

```de_funk
type: plotly.scatter
layer: bronze
data:
  x: chicago.crimes.district
  y: chicago.crimes.arrest
  aggregation: sum
formatting:
  title: Arrests by District
  height: 350
```
