#!/usr/bin/env python3
"""
Verify cross-model edges across all domain models.
Ensures no deprecated 'company' model references exist.
"""
import yaml
from pathlib import Path
from collections import defaultdict


def verify_cross_model_edges():
    """Verify all cross-model edges are valid and no deprecated references exist."""
    configs_dir = Path("configs/models")

    results = {
        'total_models': 0,
        'cross_model_edges': [],
        'deprecated_references': [],
        'valid_edges': [],
        'missing_edges': []
    }

    deprecated_model = 'company'
    valid_models = {'core', 'macro', 'corporate', 'equity', 'city_finance', 'etf', 'forecast'}

    print("=" * 80)
    print("CROSS-MODEL EDGE VERIFICATION")
    print("=" * 80)
    print()

    for model_file in sorted(configs_dir.glob("*.yaml")):
        model_name = model_file.stem

        # Skip deprecated model
        if model_name == deprecated_model:
            print(f"⚠️  Skipping deprecated model: {model_name}")
            continue

        results['total_models'] += 1

        with open(model_file) as f:
            config = yaml.safe_load(f)

        print(f"\n{'─' * 80}")
        print(f"📦 Model: {model_name}")
        print(f"{'─' * 80}")

        # Check depends_on
        depends_on = config.get('depends_on', [])
        if depends_on:
            print(f"  depends_on: {', '.join(depends_on)}")

            # Check for deprecated dependencies
            if deprecated_model in depends_on:
                results['deprecated_references'].append({
                    'model': model_name,
                    'type': 'depends_on',
                    'reference': deprecated_model,
                    'location': f"{model_file.name}:depends_on"
                })
                print(f"  ❌ DEPRECATED dependency: {deprecated_model}")

        # Check graph edges
        graph = config.get('graph', {})
        edges = graph.get('edges', [])

        if edges:
            print(f"\n  Edges ({len(edges)} total):")

            for i, edge in enumerate(edges, 1):
                from_node = edge.get('from', '')
                to_node = edge.get('to', '')
                on_clause = edge.get('on', edge.get(True, []))  # Handle YAML 1.1 'on' -> True quirk
                edge_type = edge.get('type', '')
                description = edge.get('description', '')

                # Check if it's a cross-model edge
                is_cross_model = '.' in to_node

                if is_cross_model:
                    target_model = to_node.split('.')[0]

                    # Check for deprecated reference
                    if target_model == deprecated_model:
                        results['deprecated_references'].append({
                            'model': model_name,
                            'type': 'edge',
                            'from': from_node,
                            'to': to_node,
                            'location': f"{model_file.name}:graph.edges[{i-1}]"
                        })
                        print(f"    {i}. ❌ {from_node} → {to_node}")
                        print(f"       DEPRECATED: References '{deprecated_model}' model")
                    else:
                        results['cross_model_edges'].append({
                            'model': model_name,
                            'from': from_node,
                            'to': to_node,
                            'on': on_clause,
                            'type': edge_type
                        })
                        results['valid_edges'].append({
                            'model': model_name,
                            'from': from_node,
                            'to': to_node
                        })
                        print(f"    {i}. ✅ {from_node} → {to_node}")
                        print(f"       on: {on_clause}, type: {edge_type}")
                else:
                    print(f"    {i}. {from_node} → {to_node} (internal)")

        # Check measures for cross-model references
        measures = config.get('measures', {})
        for measure_name, measure_def in measures.items():
            source = measure_def.get('source', '')

            # Check if source references another model
            if '.' in source and source.split('.')[0] in valid_models | {deprecated_model}:
                source_model = source.split('.')[0]

                if source_model == deprecated_model:
                    results['deprecated_references'].append({
                        'model': model_name,
                        'type': 'measure',
                        'measure': measure_name,
                        'source': source,
                        'location': f"{model_file.name}:measures.{measure_name}.source"
                    })
                    print(f"\n  ❌ Measure '{measure_name}' references DEPRECATED '{deprecated_model}': {source}")

    # Summary
    print(f"\n{'=' * 80}")
    print("VERIFICATION SUMMARY")
    print(f"{'=' * 80}\n")

    print(f"Total models verified: {results['total_models']}")
    print(f"Cross-model edges found: {len(results['cross_model_edges'])}")
    print(f"Valid edges: {len(results['valid_edges'])}")
    print(f"Deprecated references: {len(results['deprecated_references'])}")

    if results['deprecated_references']:
        print(f"\n❌ DEPRECATED REFERENCES FOUND:")
        for ref in results['deprecated_references']:
            print(f"\n  Model: {ref['model']}")
            print(f"  Type: {ref['type']}")
            if ref['type'] == 'depends_on':
                print(f"  Reference: {ref['reference']}")
            elif ref['type'] == 'edge':
                print(f"  Edge: {ref['from']} → {ref['to']}")
            elif ref['type'] == 'measure':
                print(f"  Measure: {ref['measure']}")
                print(f"  Source: {ref['source']}")
            print(f"  Location: {ref['location']}")
        print(f"\n❌ VERIFICATION FAILED - Found {len(results['deprecated_references'])} deprecated references")
        return False
    else:
        print(f"\n✅ VERIFICATION PASSED - No deprecated references found!")

        # Show cross-model connection matrix
        print(f"\n{'─' * 80}")
        print("CROSS-MODEL CONNECTION MATRIX")
        print(f"{'─' * 80}\n")

        connections = defaultdict(list)
        for edge in results['cross_model_edges']:
            source_model = edge['model']
            target_model = edge['to'].split('.')[0]
            connections[source_model].append(target_model)

        for model, targets in sorted(connections.items()):
            print(f"  {model:15} → {', '.join(sorted(set(targets)))}")

        return True


if __name__ == "__main__":
    import sys
    success = verify_cross_model_edges()
    sys.exit(0 if success else 1)
