---
type: domain-base
model: calendar
version: 3.0
description: "Daily calendar dimension (date_id = YYYYMMDD integer)"

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [date_id, integer, nullable: false, description: "PK - YYYYMMDD integer"]
  - [date, date, nullable: false, description: "Calendar date"]
  - [year, integer, nullable: false, description: "Calendar year"]
  - [quarter, integer, nullable: false, description: "Calendar quarter (1-4)"]
  - [month, integer, nullable: false, description: "Month (1-12)"]
  - [day_of_week, integer, nullable: false, description: "Day of week (1=Mon, 7=Sun)"]
  - [is_weekend, boolean, nullable: false, description: "Saturday or Sunday"]
  - [is_weekday, boolean, nullable: false, description: "Monday through Friday"]
  - [fiscal_year, integer, nullable: false, description: "Fiscal year"]
  - [fiscal_quarter, integer, nullable: false, description: "Fiscal quarter"]

tables:
  dim_calendar:
    type: dimension
    primary_key: [date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [date_id, integer, false, "PK (YYYYMMDD)", {derived: "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"}]
      - [date, date, false, "Calendar date", {unique: true}]
      - [year, integer, false, "Calendar year"]
      - [year_month, string, false, "YYYY-MM"]
      - [year_quarter, string, false, "YYYY-Q#"]
      - [quarter, integer, false, "Quarter (1-4)"]
      - [month, integer, false, "Month (1-12)"]
      - [month_name, string, false, "Full month name"]
      - [month_abbr, string, false, "3-letter abbreviation"]
      - [week_of_year, integer, false, "ISO week (1-53)"]
      - [day_of_week, integer, false, "Day (1=Mon, 7=Sun)"]
      - [day_of_week_name, string, false, "Full day name"]
      - [day_of_month, integer, false, "Day (1-31)"]
      - [day_of_year, integer, false, "Day (1-366)"]
      - [is_weekend, boolean, false, "Sat or Sun"]
      - [is_weekday, boolean, false, "Mon-Fri"]
      - [is_month_start, boolean, false, "First day of month"]
      - [is_month_end, boolean, false, "Last day of month"]
      - [is_quarter_start, boolean, false, "First day of quarter"]
      - [is_quarter_end, boolean, false, "Last day of quarter"]
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_quarter, integer, false, "Fiscal quarter"]
      - [fiscal_month, integer, false, "Fiscal month"]
      - [is_trading_day, boolean, true, "Market trading day", {default: true}]
      - [is_holiday, boolean, true, "Holiday flag", {default: false}]

    measures:
      - [day_count, count, date_id, "Number of days", {format: "#,##0"}]
      - [weekday_count, count, date_id, "Weekdays", {format: "#,##0", filter: "is_weekday = true"}]

graph:
  edges: []

generation:
  description: "Self-generating dimension — no bronze source. Models override these defaults."
  params:
    start_date: {type: date, default: "2000-01-01", description: "First calendar date"}
    end_date: {type: date, default: "2050-12-31", description: "Last calendar date"}
    fiscal_year_start_month: {type: integer, default: 1, description: "Fiscal year start month (1=Jan)"}
    holidays: {type: string, default: "US_FEDERAL", description: "Holiday calendar to apply"}

behaviors: []  # Target dimension — other templates FK to this, not the other way

domain: temporal
tags: [base, template, calendar]
status: active
---

## Calendar Base Template

Master calendar dimension. All fact tables FK to this via integer `date_id` (YYYYMMDD).

### date_id Pattern

```
date: 2025-01-16 → date_id: 20250116
```

All facts use `date_id` (integer FK), never raw date columns, for join efficiency.

### Generation

Self-generating — no bronze source needed. Override `generation.params` in your model's `calendar_config:`:

```yaml
calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"
  fiscal_year_start_month: 1   # 1=Jan (calendar year = fiscal year)
```

### Usage

```yaml
extends: _base.temporal.calendar
```
