#!/usr/bin/env python3
"""
Debug Node Config - Print the actual node configuration being used at build time.

This diagnoses why derived columns (price_id, security_id, date_id) aren't being written.

Usage:
    python -m scripts.diagnostics.debug_node_config
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from de_funk.config.domain import get_domain_loader


def main():
    domains_dir = project_root / "domains"
    loader = get_domain_loader(domains_dir)

    print("=" * 70)
    print("DEBUG: Domain Config Loading for stocks")
    print("=" * 70)

    # Load stocks config
    config = loader.load_model_config("securities.stocks")

    print(f"\nModel: {config.get('model')}")
    print(f"Extends: {config.get('extends')}")

    # Check graph nodes
    graph = config.get('graph', {})
    nodes = graph.get('nodes', {})

    print(f"\n{'=' * 70}")
    print("GRAPH NODES:")
    print("=" * 70)

    for node_id, node_config in nodes.items():
        print(f"\n{node_id}:")
        print(f"  from: {node_config.get('from')}")
        print(f"  type: {node_config.get('type')}")

        # Check select
        select = node_config.get('select')
        if select:
            print(f"  select type: {type(select).__name__}")
            if isinstance(select, dict):
                print(f"  select (dict): {select}")
            elif isinstance(select, list):
                print(f"  select (list - PROBLEM!): {select}")
        else:
            print(f"  select: NOT PRESENT")

        # Check derive
        derive = node_config.get('derive')
        if derive:
            print(f"  derive type: {type(derive).__name__}")
            print(f"  derive: {derive}")
        else:
            print(f"  derive: NOT PRESENT")

        # Check filters
        filters = node_config.get('filters')
        if filters:
            print(f"  filters: {filters}")

        # Check extends
        extends = node_config.get('extends')
        if extends:
            print(f"  extends: {extends}")

    # Also check _base.finance.securities to compare
    print(f"\n{'=' * 70}")
    print("BASE CONFIG: _base.finance.securities._fact_prices_base")
    print("=" * 70)

    try:
        base_ref = "_base.finance.securities._fact_prices_base"
        base_config = loader._resolve_extends_reference(base_ref)
        print(f"\nResolved from: {base_ref}")
        print(f"  from: {base_config.get('from')}")
        print(f"  select type: {type(base_config.get('select')).__name__ if base_config.get('select') else 'None'}")
        print(f"  select: {base_config.get('select')}")
        print(f"  derive: {base_config.get('derive')}")
    except Exception as e:
        print(f"Error loading base: {e}")

    print(f"\n{'=' * 70}")
    print("ANALYSIS:")
    print("=" * 70)

    # Check if fact_stock_prices has everything needed
    fact_prices = nodes.get('fact_stock_prices', {})

    issues = []

    if not fact_prices.get('from'):
        issues.append("- Missing 'from' (bronze source)")

    select = fact_prices.get('select')
    if not select:
        issues.append("- Missing 'select' - columns won't be selected from bronze")
    elif isinstance(select, list):
        issues.append(f"- 'select' is a LIST instead of DICT - _select_columns will fail!")
        issues.append(f"  List value: {select}")

    derive = fact_prices.get('derive')
    if not derive:
        issues.append("- Missing 'derive' - primary keys won't be computed!")
    elif 'price_id' not in derive or 'security_id' not in derive or 'date_id' not in derive:
        issues.append(f"- 'derive' missing required keys. Has: {list(derive.keys())}")

    if issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues:
            print(issue)
    else:
        print("\n✓ Config looks correct")
        print("  - 'from' specifies bronze source")
        print("  - 'select' is a dict with column mappings")
        print("  - 'derive' has price_id, security_id, date_id")


if __name__ == "__main__":
    main()
