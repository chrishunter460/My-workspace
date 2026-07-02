#!/usr/bin/env python3
"""
Quick test for storage path resolution.

Usage:
    python -m scripts.test.test_path_resolution
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup repo imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def main():
from de_funk.config.domain import get_domain_loader

    repo_root = Path(__file__).resolve().parents[2]
    domains_dir = repo_root / "domains"

    print(f"Repo root: {repo_root}")
    print(f"Domains dir: {domains_dir}")

    # Load stocks config
    loader = get_domain_loader(domains_dir)
    stocks_config = loader.load_model_config('stocks')

    print("\n=== STOCKS MODEL CONFIG ===")
    print(f"Model name: {stocks_config.get('model')}")

    storage_cfg = stocks_config.get('storage', {})
    print(f"\nStorage config:")
    print(f"  format: {storage_cfg.get('format')}")
    print(f"  bronze: {storage_cfg.get('bronze')}")
    print(f"  silver: {storage_cfg.get('silver')}")

    silver_root = storage_cfg.get('silver', {}).get('root')
    print(f"\nSilver root from config: {silver_root}")

    if silver_root:
        full_silver_path = repo_root / silver_root
        print(f"Full silver path: {full_silver_path}")
        print(f"Exists: {full_silver_path.exists()}")

        if full_silver_path.exists():
            print(f"Contents: {list(full_silver_path.iterdir())}")
    else:
        print("WARNING: No silver root specified in stocks config!")

    # Test tables
    print("\n=== TABLES CONFIG ===")
    tables_cfg = stocks_config.get('tables', {})
    for table_name, table_config in tables_cfg.items():
        print(f"\n  {table_name}:")
        print(f"    type: {table_config.get('type')}")
        print(f"    path: {table_config.get('path', 'not specified')}")

    # Test what paths UniversalSession would construct
    print("\n=== PATH RESOLUTION TEST ===")

    # Simulate session path construction
    model_silver_root = storage_cfg.get('silver', {}).get('root')
    global_silver_root = 'storage/silver'  # From storage.json

    if model_silver_root:
        base_path = repo_root / model_silver_root
        print(f"Would use model-specific silver root: {base_path}")
    else:
        base_path = repo_root / global_silver_root / 'stocks'
        print(f"Would use global silver root + model name: {base_path}")

    for table_name in ['dim_stock', 'fact_stock_prices']:
        table_cfg = tables_cfg.get(table_name, {})
        table_path = table_cfg.get('path', table_name)

        possible_paths = [
            base_path / table_path,
            base_path / f"facts/{table_name}",
            base_path / f"dims/{table_name}",
        ]

        print(f"\n  {table_name}:")
        for p in possible_paths:
            exists = p.exists()
            delta = (p / "_delta_log").exists() if p.exists() else False
            print(f"    {p}: exists={exists}, delta={delta}")


if __name__ == "__main__":
    main()
