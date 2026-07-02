#!/usr/bin/env python3
"""
Quick verification script for forecast model configuration.
Validates YAML syntax and join specifications without requiring Spark.
"""
import yaml
from pathlib import Path


def verify_forecast_config():
    """Verify forecast.yaml has correct join syntax."""
    config_path = Path("configs/models/forecast.yaml")

    print(f"Loading forecast config from: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    print("✓ YAML syntax is valid")

    # Check graph edges have correct format
    graph = config.get('graph', {})
    edges = graph.get('edges', [])

    print(f"\nFound {len(edges)} edges in graph:")
    for i, edge in enumerate(edges, 1):
        from_node = edge.get('from')
        to_node = edge.get('to')
        on_clause = edge.get('on')
        join_type = edge.get('type')

        print(f"\n  Edge {i}:")
        print(f"    From: {from_node}")
        print(f"    To: {to_node}")
        print(f"    On: {on_clause}")
        print(f"    Type: {join_type}")

        # Validate join specification format
        if on_clause is None:
            print("    ⚠ WARNING: Missing 'on' clause")
        elif not isinstance(on_clause, list):
            print(f"    ✗ ERROR: 'on' should be list, got {type(on_clause)}")
        elif len(on_clause) == 0:
            print("    ⚠ WARNING: Empty 'on' clause")
        else:
            # Check format: should be ["left_col=right_col"]
            for join_spec in on_clause:
                if '=' not in join_spec:
                    print(f"    ✗ ERROR: Invalid join spec '{join_spec}' (should be 'col1=col2')")
                elif ' ' in join_spec:
                    print(f"    ⚠ WARNING: Join spec '{join_spec}' contains spaces (may cause parsing issues)")
                else:
                    print(f"    ✓ Valid join spec: {join_spec}")

    # Check measures
    measures = config.get('measures', {})
    print(f"\n\nFound {len(measures)} measures:")
    for measure_name, measure_def in measures.items():
        desc = measure_def.get('description', 'No description')
        agg = measure_def.get('aggregation', 'none')
        fmt = measure_def.get('format', 'none')
        print(f"  - {measure_name}: {desc} (agg={agg}, fmt={fmt})")

    print("\n✓ Forecast config verification complete!")
    return True


if __name__ == "__main__":
    try:
        verify_forecast_config()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
