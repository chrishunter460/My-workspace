---
type: domain-model-table
table: fact_stock_technicals
table_type: fact
extends: _base.finance.securities._fact_technicals
transform: window
from: fact_stock_prices
primary_key: [technical_id]
partition_by: [date_id]

# Schema and indicator configs fully inherited from _base.finance.securities._fact_technicals.
# Indicators are computed in column order by indicators.apply_indicator() —
# see src/de_funk/models/base/indicators.py for full catalog and param docs.

# Measures inherited from base: avg_rsi, avg_volatility, avg_atr
---

## Stock Technicals Fact Table

Inherits `_base.finance.securities._fact_technicals`. Built in phase 3 (after
`fact_stock_prices` in phase 2) via `transform: window`.

Each column is driven by a typed indicator config — e.g.
`{indicator: sma, period: 20, source: adjusted_close}` — rather than free-form
SQL strings. The indicator library (`indicators.py`) maps short codes to full
definitions and Spark window implementations.

### Dependency order (schema column order matters)

```
sma_20, sma_50, sma_200           (no deps)
ema_12, ema_26                    (no deps)
macd          ← ema_12, ema_26
macd_signal   ← macd
macd_histogram← macd, macd_signal
rsi_14                            (no deps beyond source col)
atr_14                            (requires high, low, close)
bollinger_*   ← sma_20
volatility_*                      (no deps beyond source col)
volume_sma_20                     (no deps)
volume_ratio  ← volume_sma_20
```
