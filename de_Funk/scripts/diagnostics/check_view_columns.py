#!/usr/bin/env python
"""Quick check of columns in DuckDB views vs expected from YAML."""
from pathlib import Path
from de_funk.utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

import duckdb

db_path = repo_root / "storage" / "duckdb" / "analytics.db"
conn = duckdb.connect(str(db_path))

print("=" * 60)
print("COLUMNS IN stocks.fact_stock_prices VIEW")
print("=" * 60)

# Get actual columns
result = conn.execute("SELECT * FROM stocks.fact_stock_prices LIMIT 0")
actual_cols = [desc[0] for desc in result.description]
print(f"\nActual columns ({len(actual_cols)}):")
for col in sorted(actual_cols):
    print(f"  - {col}")

# Expected derived columns from graph.yaml
expected_derived = [
    'daily_return', 'sma_20', 'sma_50', 'sma_200',
    'price_change', 'gain', 'loss', 'avg_gain_14', 'avg_loss_14',
    'rs_14', 'rsi_14', 'volatility_20d', 'volatility_60d',
    'bollinger_middle', 'bollinger_upper', 'bollinger_lower',
    'volume_sma_20', 'volume_ratio'
]

print(f"\nExpected derived columns from graph.yaml ({len(expected_derived)}):")
missing = []
present = []
for col in expected_derived:
    if col in actual_cols:
        present.append(col)
        print(f"  ✅ {col}")
    else:
        missing.append(col)
        print(f"  ❌ {col} (MISSING)")

print(f"\n{'='*60}")
print(f"SUMMARY: {len(present)}/{len(expected_derived)} derived columns present")
if missing:
    print(f"\nMissing columns need to be computed by rebuilding Silver layer with Spark:")
    print("  python -m scripts.build_silver_layer")
print("=" * 60)
