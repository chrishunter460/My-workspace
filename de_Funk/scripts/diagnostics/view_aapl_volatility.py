"""Quick view of AAPL volatility data."""
from de_funk.utils.repo import setup_repo_imports
setup_repo_imports()

import pandas as pd
from pathlib import Path

prices_path = Path("storage/silver/stocks/facts/fact_stock_prices")
df = pd.read_parquet(prices_path)
aapl = df[df['ticker'] == 'AAPL'].sort_values('trade_date')

cols = ['trade_date', 'close', 'daily_return', 'volatility_20d', 'volatility_60d']
cols = [c for c in cols if c in aapl.columns]

print(f"AAPL: {len(aapl)} rows, {aapl['trade_date'].min()} to {aapl['trade_date'].max()}\n")
print("First 30 rows:")
print(aapl[cols].head(30).to_string())
print("\nRows 60-65 (should have valid vol_60d):")
print(aapl[cols].iloc[60:66].to_string())
print("\nLast 10 rows:")
print(aapl[cols].tail(10).to_string())

# Stats
print(f"\n--- Stats ---")
print(f"volatility_20d: {aapl['volatility_20d'].notna().sum()}/{len(aapl)} valid ({aapl['volatility_20d'].notna().mean()*100:.1f}%)")
print(f"volatility_60d: {aapl['volatility_60d'].notna().sum()}/{len(aapl)} valid ({aapl['volatility_60d'].notna().mean()*100:.1f}%)")
