#!/usr/bin/env python3
"""
Test Base Inherited Measure Execution

Simple script to test if inherited base measures work.

Usage:
    python -m scripts.test.test_base_measure
"""

import sys
from pathlib import Path
from de_funk.utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

def main():
    print("=" * 80)
    print("Testing Base Inherited Measure: avg_close_price")
    print("=" * 80)

    try:
        # Import registry
from de_funk.models.registry import ModelRegistry

        # Create registry
        models_dir = Path("configs/models")
        registry = ModelRegistry(models_dir)

        print(f"\n✓ Registry created")
        print(f"  Available models: {registry.list_models()}")

        # Get stocks model config
        stocks_config = registry.get_model_config("stocks")
        print(f"\n✓ Loaded stocks config")

        # Check measures
        measures = stocks_config.get('measures', {})
        simple_measures = measures.get('simple_measures', {})

        if 'avg_close_price' in simple_measures:
            print(f"\n✓ Found inherited measure: avg_close_price")
            print(f"  Source: {simple_measures['avg_close_price'].get('source')}")
        else:
            print(f"\n✗ avg_close_price not found!")
            return

        # Now try to instantiate the model
        print(f"\n[Attempting to load model instance...]")

from de_funk.models.implemented.stocks.model import StocksModel
from de_funk.core.duckdb_connection import DuckDBConnection
        import json

        # Load storage config
        with open(repo_root / "configs" / "storage.json") as f:
            storage_cfg = json.load(f)

        # Create connection (check correct initialization)
        conn = DuckDBConnection()

        # Create model instance
        model = StocksModel(
            connection=conn,
            storage_cfg=storage_cfg,
            model_cfg=stocks_config
        )

        print(f"\n✓ Model instantiated")
        print(f"  Model name: {model.model_name}")
        print(f"  Backend: {model.backend}")

        # Try to calculate the measure
        print(f"\n[Attempting to calculate avg_close_price...]")

        result = model.calculate_measure("avg_close_price")

        print(f"\n✓ SUCCESS! Measure calculated")
        print(f"  Result type: {type(result)}")

        if hasattr(result, 'data'):
            print(f"  Result shape: {result.data.shape}")
            print(f"\nPreview:")
            print(result.data.head())
        else:
            print(f"\nPreview:")
            print(result.head())

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")

        # Show full traceback
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()

        # Provide guidance based on error
        error_str = str(e).lower()

        if "path" in error_str or "not found in model" in error_str:
            print("\n" + "=" * 80)
            print("DIAGNOSIS: Schema path resolution issue")
            print("=" * 80)
            print("The adapter is trying to resolve table paths from schema,")
            print("but v2.0 schemas don't have 'path' entries.")
            print("\nSOLUTION: Use DuckDB views instead")
            print("  1. Run: python -m scripts.setup.setup_duckdb_views")
            print("  2. This creates views that bypass path resolution")

        elif "no such table" in error_str or "does not exist" in error_str:
            print("\n" + "=" * 80)
            print("DIAGNOSIS: Missing data or views")
            print("=" * 80)
            print("Either:")
            print("  1. Silver layer data hasn't been built yet")
            print("  2. DuckDB views haven't been created")
            print("\nSOLUTION:")
            print("  1. Build silver: python -m scripts.build.build_silver_layer --model stocks")
            print("  2. Setup views: python -m scripts.setup.setup_duckdb_views")

if __name__ == "__main__":
    main()
