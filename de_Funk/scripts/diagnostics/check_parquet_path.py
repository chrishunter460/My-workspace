#!/usr/bin/env python3
"""Check what parquet files exist and what path the model is trying to load."""

import os
from pathlib import Path

print("="*80)
print("PARQUET PATH DIAGNOSTIC")
print("="*80)

# Check what the model SHOULD be loading
schema_path = "storage/silver/forecast/facts/forecast_price"
print(f"\n[1] Schema config says path should be: {schema_path}")

# Check what the model IS ACTUALLY loading
model_path = "storage/silver/forecast/forecasts"
print(f"\n[2] Model is probably loading from: {model_path}")

# Check if directories exist
print(f"\n[3] Directory existence:")
print(f"  - {schema_path}: {os.path.exists(schema_path)}")
print(f"  - {model_path}: {os.path.exists(model_path)}")

# List actual parquet files
print(f"\n[4] Looking for parquet files in storage/silver/forecast/...")
for root, dirs, files in os.walk("storage/silver/forecast"):
    for file in files:
        if file.endswith('.parquet'):
            full_path = os.path.join(root, file)
            size = os.path.getsize(full_path)
            print(f"  ✓ Found: {full_path} ({size:,} bytes)")

# Check partition directories
print(f"\n[5] Partition directories in {schema_path}:")
if os.path.exists(schema_path):
    for item in sorted(os.listdir(schema_path)):
        item_path = os.path.join(schema_path, item)
        if os.path.isdir(item_path):
            # Count parquet files in partition
            parquet_files = [f for f in os.listdir(item_path) if f.endswith('.parquet')]
            print(f"  - {item}: {len(parquet_files)} parquet file(s)")

            # If using Spark, show total rows
            for pf in parquet_files:
                pf_path = os.path.join(item_path, pf)
                size = os.path.getsize(pf_path)
                print(f"    → {pf}: {size:,} bytes")
else:
    print(f"  ✗ Directory does not exist")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)
print("\nThe graph.yaml says:")
print("  from: silver.forecasts")
print("\nThis gets mapped to path:")
print("  storage/silver/forecast/forecasts  ← WRONG!")
print("\nBut the schema.yaml says the actual path is:")
print("  storage/silver/forecast/facts/forecast_price  ← CORRECT!")
print("\n✗ PATH MISMATCH - Model is loading from wrong directory!")
print("="*80)
