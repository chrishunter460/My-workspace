---
type: domain-model
model: temporal
version: 3.0
description: "Master calendar dimension - foundation for all time-series joins"
extends: _base.temporal.calendar
depends_on: []

storage:
  format: delta
  silver:
    root: storage/silver/temporal/

calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1

graph:
  nodes:
    dim_calendar:
      from: self
      type: dimension
      primary_key: [date_id]
  edges: {}

build:
  partitions: []
  sort_by: [date_id]
  optimize: true

tables:
  dim_calendar:
    table_type: dimension
    primary_key: [date_id]
    schema:
      - [date_id, integer, false, "PK (YYYYMMDD)", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
      - [date, date, false, "Calendar date"]
      - [year, integer, false, "Calendar year"]
      - [year_month, string, false, "YYYY-MM"]
      - [year_quarter, string, false, "YYYY-Q#"]
      - [quarter, integer, false, "Quarter (1-4)"]
      - [is_quarter_start, boolean, false, "First day of quarter"]
      - [is_quarter_end, boolean, false, "Last day of quarter"]
      - [month, integer, false, "Month (1-12)"]
      - [month_name, string, false, "Full month name"]
      - [month_abbr, string, false, "3-letter abbreviation"]
      - [days_in_month, integer, false, "Days in month"]
      - [is_month_start, boolean, false, "First day of month"]
      - [is_month_end, boolean, false, "Last day of month"]
      - [week_of_year, integer, false, "ISO week (1-53)"]
      - [day_of_week, integer, false, "Day of week (1=Mon)"]
      - [day_of_week_name, string, false, "Full day name"]
      - [day_of_week_abbr, string, false, "3-letter day abbr"]
      - [is_weekend, boolean, false, "Saturday or Sunday"]
      - [is_weekday, boolean, false, "Monday-Friday"]
      - [day_of_month, integer, false, "Day of month"]
      - [day_of_year, integer, false, "Day of year"]
      - [is_year_start, boolean, false, "January 1st"]
      - [is_year_end, boolean, false, "December 31st"]
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_quarter, integer, false, "Fiscal quarter"]
      - [fiscal_month, integer, false, "Fiscal month"]
      - [is_trading_day, boolean, true, "NYSE trading day", {default: true}]
      - [is_holiday, boolean, true, "US federal holiday", {default: false}]
    measures:
      - [day_count, count, date_id, "Number of days", {format: "#,##0"}]
      - [trading_day_count, count, date_id, "Trading days", {format: "#,##0", filter: "is_trading_day = true"}]

metadata:
  domain: temporal
  owner: data_engineering
status: active
---

## Temporal Model

Master calendar dimension (2000-2050). Self-generating, no bronze dependency.
All date columns in fact tables should use `date_id` (integer YYYYMMDD) FK.
