---
type: domain-base
model: corporate_action
version: 1.0
description: "Security-level corporate actions - dividends, splits, mergers, spinoffs"
extends: _base._base_.event

depends_on: [temporal]

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [action_id, integer, nullable: false, description: "Primary key"]
  - [domain_source, string, nullable: false, description: "Origin domain"]
  - [security_id, integer, nullable: false, description: "FK to security dimension"]
  - [ticker, string, nullable: false, description: "Ticker symbol"]
  - [action_type, string, nullable: false, description: "DIVIDEND, SPLIT, MERGER, SPINOFF"]
  - [effective_date, date, nullable: false, description: "Effective/ex date"]
  - [effective_date_id, integer, nullable: false, description: "FK to temporal.dim_calendar"]

tables:
  _fact_dividends:
    type: fact
    primary_key: [dividend_id]
    partition_by: [ex_dividend_date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [dividend_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(ex_dividend_date AS STRING))))"}]
      - [domain_source, string, false, "Origin domain"]
      - [security_id, integer, false, "FK to security", {derived: "ABS(HASH(ticker))"}]
      - [ex_dividend_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)"}]
      - [ex_dividend_date, date, false, "Ex-dividend date"]
      - [dividend_amount, double, false, "Dividend per share"]
      - [record_date, date, true, "Record date"]
      - [payment_date, date, true, "Payment date"]
      - [declaration_date, date, true, "Declaration date"]
      - [dividend_type, string, true, "regular, special, stock"]

    measures:
      - [total_dividends, sum, dividend_amount, "Total dividends", {format: "$#,##0.00"}]
      - [avg_dividend, avg, dividend_amount, "Average dividend", {format: "$#,##0.00"}]
      - [dividend_count, count_distinct, dividend_id, "Dividend events", {format: "#,##0"}]

  _fact_splits:
    type: fact
    primary_key: [split_id]
    partition_by: [effective_date_id]

    # [column, type, nullable, description, {options}]
    schema:
      - [split_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(ticker, '_', CAST(effective_date AS STRING))))"}]
      - [domain_source, string, false, "Origin domain"]
      - [security_id, integer, false, "FK to security", {derived: "ABS(HASH(ticker))"}]
      - [effective_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id, derived: "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)"}]
      - [effective_date, date, false, "Split effective date"]
      - [split_factor, double, false, "Split ratio (e.g., 4.0 for 4:1)"]

    measures:
      - [split_count, count_distinct, split_id, "Number of splits", {format: "#,##0"}]
      - [avg_split_ratio, avg, split_factor, "Average split ratio", {format: "#,##0.00"}]

  # Cross-table python measures (require JOIN to _fact_prices via security_id)
  python_measures:
    dividend_yield:
      function: "securities.measures.calculate_dividend_yield"
      description: "Annualized dividend yield — trailing 12-month dividends / current price"
      params:
        trailing_months: 12
      returns: [security_id, date_id, trailing_dividends, price, dividend_yield_pct]
      joins: "_fact_dividends d JOIN _fact_prices p ON d.security_id = p.security_id"

    split_adjusted_return:
      function: "securities.measures.calculate_split_adjusted_return"
      description: "Cumulative return adjusted for all historical splits"
      params:
        price_col: "close"
      returns: [security_id, date_id, raw_return, split_factor_cum, adjusted_return]
      joins: "_fact_splits s JOIN _fact_prices p ON s.security_id = p.security_id"

graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [dividend_to_calendar, _fact_dividends, temporal.dim_calendar, [ex_dividend_date_id=date_id], many_to_one, temporal]
    - [split_to_calendar, _fact_splits, temporal.dim_calendar, [effective_date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal        # Inherited from event

domain: finance
tags: [base, template, finance, corporate_action, dividend, split]
status: active
---

## Corporate Action Base Template

Events that happen TO a security — dividends, stock splits, mergers, and spinoffs. Distinct from `_base.finance.securities` which defines the security entity and price data.

### Action Types

| Type | Table | Key Date |
|------|-------|----------|
| DIVIDEND | `_fact_dividends` | ex_dividend_date |
| SPLIT | `_fact_splits` | effective_date |

### Relationship to Securities

Corporate actions reference securities via `security_id = ABS(HASH(ticker))`. The implementing model wires this FK to its security dimension:

```yaml
# In stocks model graph:
- [dividends_to_stock, fact_dividends, dim_stock, [security_id=security_id], many_to_one, null]
```

### Usage

```yaml
extends: _base.finance.corporate_action
```
