---
type: computation-catalog
version: 1.0
description: Typed function catalog for derived measures — no freeform SQL strings

functions:
  divide:
    signature: "{fn: divide, of: a, by: b}"
    expression: "a / NULLIF(b, 0)"
    description: "Safe division — returns null when denominator is zero"

  rate:
    signature: "{fn: rate, events: a, exposed: b}"
    expression: "a / NULLIF(b, 0)"
    description: "Actuarial alias for divide — events over exposure"

  subtract:
    signature: "{fn: subtract, from: a, subtract: b}"
    expression: "a - b"
    description: "Simple subtraction"

  add:
    signature: "{fn: add, fields: [a, b, c]}"
    expression: "a + b + c"
    description: "Sum of two or more measure keys"

  multiply:
    signature: "{fn: multiply, a: x, by: y}"
    expression: "x * y"
    description: "Multiplication of two measure keys"

  delta:
    signature: "{fn: delta, of: a}"
    expression: "current row − prior row (window)"
    description: "Row-over-row difference using LAG window"

  pct_delta:
    signature: "{fn: pct_delta, of: a}"
    expression: "(current − prior) / prior (window)"
    description: "Row-over-row percent change using LAG window"

  share:
    signature: "{fn: share, of: a, total: b}"
    expression: "a / NULLIF(SUM(b), 0)"
    description: "Share of total — fraction of group sum"
---

## Computation Catalog

Typed function configs for derived measures in exhibit blocks. Use these instead of raw SQL strings — the backend resolves function keys to the correct SQL expression.

Measure keys referenced in `events:`, `exposed:`, `of:`, `from:`, `subtract:`, `fields:`, `a:`, `by:`, `total:` are resolved from the **previously defined measure keys** in the same `measures:` list, in order. This is the same dependency chain used by the indicator catalog in `src/de_funk/models/base/indicators.py`.

### Usage

Replace the `field_or_expression` position in a measure tuple with a function config:

```yaml
measures:
  - [exposed,   securities.stocks.policies_exposed,                         sum,  number,  Exposed]
  - [deaths,    securities.stocks.death_count,                              sum,  number,  Deaths]
  - [ae_ratio,  {fn: rate, events: deaths, exposed: exposed},   null, decimal, AE Ratio]
  - [ae_yoy,    {fn: pct_delta, of: ae_ratio},                  null, "%",     AE YoY]
```

### Function Reference

| Key | Signature | SQL equivalent |
|-----|-----------|----------------|
| `divide` | `{fn: divide, of: a, by: b}` | `a / NULLIF(b, 0)` |
| `rate` | `{fn: rate, events: a, exposed: b}` | `a / NULLIF(b, 0)` |
| `subtract` | `{fn: subtract, from: a, subtract: b}` | `a - b` |
| `add` | `{fn: add, fields: [a, b, c]}` | `a + b + c` |
| `multiply` | `{fn: multiply, a: x, by: y}` | `x * y` |
| `delta` | `{fn: delta, of: a}` | `a - LAG(a) OVER (ORDER BY ...)` |
| `pct_delta` | `{fn: pct_delta, of: a}` | `(a - LAG(a)) / LAG(a) OVER (...)` |
| `share` | `{fn: share, of: a, total: b}` | `a / NULLIF(SUM(b) OVER (...), 0)` |

### Notes

- `rate` is an alias for `divide` — prefer `rate` for actuarial / frequency contexts, `divide` for general ratios
- Window functions (`delta`, `pct_delta`) follow the `rows:` or `cols:` ordering of the enclosing pivot or chart
- `share` uses a window SUM partitioned by the grouping dimension, not a global total
- Nested function configs are not supported — flatten into sequential measure keys
