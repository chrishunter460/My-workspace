---

type: reference
description: "Complete YAML reference for measure definitions across all file types"
---

> **Implementation Status**: Simple and computed (SQL) measures are fully implemented. Python measures (NPV, sharpe_ratio, cross-table joins) are **not auto-executed** — they exist only as documentation of the intended design.


## measures Guide

### Implementation Status

| Feature | Status |
|---------|--------|
| Model-level simple measures | **IMPLEMENTED** |
| Model-level computed measures | **IMPLEMENTED** |
| Table-level measures | **IMPLEMENTED** |
| Measure options (`format`, `filters`) | **IMPLEMENTED** |
| Python measures (`python_measures:` block) | **NOT IMPLEMENTED** -- YAML syntax is documented below for future use, but no Python measure execution engine exists. Functions like `calculate_npv`, `sharpe_ratio`, `calculate_spending_velocity` are not built. |
| Cross-table python measures (`joins:` key) | **NOT IMPLEMENTED** |

---


Measures define pre-built calculations. They exist at three levels:

| Level | Where Defined | Inherited? | Description |
|-------|--------------|------------|-------------|
| **Model-level** | `model.md` → `measures:` | No | Business metrics spanning the whole model |
| **Table-level** | `tables/*.md` → `measures:` | Yes (via `extends:`) | Measures scoped to a single table |
| **Python measures** | `_base/*.md` → `python_measures:` | Yes (via `extends:` chain) | Complex calculations requiring Python |

---


### Model-Level Measures

Defined in `model.md` under the `measures:` block. Two sub-keys: `simple` and `computed`.

#### Simple Measures

Pre-defined aggregations on a single column. Format:

```yaml
measures:
  simple:
    # [name, aggregation, table.column, description, {options}]
    - [total_payments, sum, fact_ledger_entries.transaction_amount, "Total payments", {format: "$#,##0.00"}]
    - [entry_count, count_distinct, fact_ledger_entries.entry_id, "Entry count", {format: "#,##0"}]
    - [avg_amount, avg, fact_ledger_entries.transaction_amount, "Average", {format: "$#,##0.00"}]
```

Note: Model-level simple measures reference `table.column` (dot-qualified) to identify which table the column belongs to.

#### Aggregation Types

| Aggregation | SQL Equivalent | Description |
|-------------|---------------|-------------|
| `count` | `COUNT(col)` | Count non-null rows |
| `count_distinct` | `COUNT(DISTINCT col)` | Count unique values |
| `sum` | `SUM(col)` | Sum values |
| `avg` | `AVG(col)` | Average |
| `min` | `MIN(col)` | Minimum |
| `max` | `MAX(col)` | Maximum |
| `expression` | Inline SQL | Custom SQL expression (see computed) |

#### Computed Measures

SQL expressions for derived metrics. Format:

```yaml
  computed:
    # [name, expression, SQL, description, {options}]
    - [payroll_pct, expression, "SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount ELSE 0 END) / SUM(amount) * 100", "Payroll %", {format: "0.00%"}]
    - [payments_per_vendor, expression, "SUM(amount) / NULLIF(COUNT(DISTINCT vendor_id), 0)", "Avg per vendor", {format: "$#,##0.00"}]
```

#### Measure Options

| Option | Description | Example |
|--------|-------------|---------|
| `format` | Display format | `{format: "$#,##0.00"}`, `{format: "0.00%"}`, `{format: "#,##0"}` |
| `filters` | Conditional filter(s) | `{filters: ["arrest_made = true"]}` |

**Filtered measures** apply a WHERE predicate before aggregation:

```yaml
  simple:
    - [arrest_count, count, fact_crimes.incident_id, "Crimes with arrest", {filters: ["arrest_made = true"]}]
    - [domestic_crime_count, count, fact_crimes.incident_id, "Domestic crimes", {filters: ["domestic = true"]}]
```

---


### Table-Level Measures

Defined directly in `tables/*.md` files. Same tuple format but column is unqualified (scoped to the table):

```yaml
measures:
  # [name, aggregation, column, description, {options}]
  - [total_rides, sum, rides, "Total ridership", {format: "#,##0"}]
  - [avg_daily_rides, avg, rides, "Average daily ridership", {format: "#,##0"}]
  - [station_count, count_distinct, station_id, "Number of stations", {format: "#,##0"}]
```

Expression measures embed SQL as the third element:

```yaml
measures:
  - [avg_tax_per_parcel, expression, "SUM(transaction_amount) / NULLIF(COUNT(DISTINCT parcel_id), 0)", "Average tax per parcel", {format: "$#,##0.00"}]
  - [fully_paid_count, expression, "SUM(CASE WHEN is_fully_paid THEN 1 ELSE 0 END)", "Contracts fully paid", {format: "#,##0"}]
```

Table-level measures are also declared in base template tables (inside `_base/*.md` `tables:` blocks) and inherited by concrete tables via `extends:`.

---


### Python Measures (Base-Level)

> **NOT IMPLEMENTED** — The YAML syntax below is documented for planned future use.
> No Python measure execution engine exists. The `function:` paths (e.g.,
> `accounting.measures.calculate_npv`, `finance.measures.calculate_dividend_yield`)
> do not resolve to real Python modules. The config loader does not process
> `python_measures:` blocks.

Complex calculations that require Python (rolling windows, statistical models, NPV). Defined on base templates inside a table block, inherited by all extending models.

#### Full Definition (parent base)

```yaml
tables:
  _fact_financial_events:
    # ... schema ...
    python_measures:
      net_present_value:
        function: "accounting.measures.calculate_npv"
        description: "NPV of cash flows discounted to earliest date"
        params:
          discount_rate: 0.05
          amount_col: "amount"
          date_col: "date_id"
        returns: [legal_entity_id, event_type, npv]
      spending_velocity:
        function: "accounting.measures.calculate_spending_velocity"
        description: "Rolling spend rate — trailing 30/90/365-day totals and trend"
        params:
          amount_col: "amount"
          date_col: "date_id"
          windows: [30, 90, 365]
          partition_cols: [legal_entity_id, event_type]
        returns: [legal_entity_id, event_type, date_id, spend_30d, spend_90d, spend_365d, trend]
```

#### Python Measure Keys

| Key | Required | Description |
|-----|----------|-------------|
| `function` | Yes | Dotted path to Python function: `"module.measures.function_name"` |
| `description` | Yes | Human-readable explanation |
| `params` | Yes | Named parameters with defaults (overridable at runtime) |
| `returns` | Yes | Output column names |
| `joins` | No | Cross-table join for multi-table measures (see below) |

#### Override Pattern (child base)

Child base templates inherit the `function` and override only `params` to match their schema:

```yaml
# _base/accounting/ledger_entry.md (extends financial_event)
tables:
  _fact_ledger_entries:
    python_measures:
      # Inherited from _base.accounting.financial_event, params overridden
      net_present_value:
        params:
          amount_col: "transaction_amount"
          date_col: "transaction_date"
      spending_velocity:
        params:
          amount_col: "transaction_amount"
          date_col: "transaction_date"
          partition_cols: [domain_source, entry_type]
```

#### Cross-Table Python Measures

Some python measures require data from multiple tables. Use the `joins:` key:

```yaml
python_measures:
  dividend_yield:
    function: "finance.measures.calculate_dividend_yield"
    description: "Annualized dividend yield from action history"
    params:
      price_col: "close"
      dividend_col: "amount"
    joins:
      - {table: _fact_prices, on: [security_id = security_id, date_id = date_id]}
    returns: [security_id, date_id, dividend_yield]
```

#### Which Bases Define Python Measures

| Base Template | Measures | Table |
|--------------|---------|-------|
| `_base.accounting.financial_event` | `net_present_value`, `spending_velocity` | `_fact_financial_events` |
| `_base.accounting.ledger_entry` | Override params for above | `_fact_ledger_entries` |
| `_base.accounting.financial_statement` | Override params for above | `_fact_financial_statements` |
| `_base.finance.securities` | `sharpe_ratio`, `drawdown`, `rolling_beta`, `momentum_score`, `volatility_regime`, `relative_strength` | `_fact_prices` |
| `_base.finance.corporate_action` | `dividend_yield`, `split_adjusted_return` | Top-level (cross-table) |
| `_base.corporate.earnings` | `eps_trend`, `estimate_accuracy` | `_fact_earnings` |
| `_base.regulatory.inspection` | `compliance_trend`, `repeat_offender_score` | `_fact_inspections` |

---


### Measure Levels Summary

```
model.md                        ← model-level (simple + computed)
  └── tables/fact_*.md          ← table-level (same tuple format)
        └── extends: _base.*    ← base template (table-level + python_measures)
```

All three levels coexist. Model-level measures aggregate across the model. Table-level measures are scoped to one table. Python measures are inherited from bases and execute Python functions.
