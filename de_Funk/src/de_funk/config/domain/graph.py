"""
Graph configuration processing for domain v4 configs.

Handles:
- Edge parsing from graph.edges (tabular format)
- Auto-edge resolution from base template inheritance chain
- Optional edge detection (LEFT JOIN for nullable FKs)
- Path validation and resolution (multi-hop traversals)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_edge(
    edge: List,
) -> Optional[Dict[str, Any]]:
    """
    Parse a single edge from tabular format.

    Format: [edge_name, from, to, on, type, cross_model, optional: true]

    Returns:
        Parsed edge dict, or None if invalid
    """
    if not isinstance(edge, list) or len(edge) < 5:
        return None

    edge_name = edge[0]
    from_table = edge[1]
    to_table = edge[2]
    on_spec = edge[3]
    join_type = edge[4]
    cross_model = edge[5] if len(edge) > 5 else None
    optional = False

    # Handle optional flag — can be in position 6 as dict or string
    if len(edge) > 6:
        opt_val = edge[6]
        if isinstance(opt_val, dict):
            optional = opt_val.get("optional", False)
        elif isinstance(opt_val, str) and opt_val.startswith("optional"):
            optional = True
        elif isinstance(opt_val, bool):
            optional = opt_val

    # Parse join conditions
    join_on = _parse_on_spec(on_spec)

    # Determine if this is a cross-model reference
    is_cross_model = False
    target_model = None
    target_table = to_table

    if cross_model and cross_model != "null":
        is_cross_model = True
        target_model = cross_model
        # Also extract table name from dot notation if present
        if isinstance(to_table, str) and "." in to_table:
            target_table = to_table.split(".", 1)[1]
    elif isinstance(to_table, str) and "." in to_table:
        is_cross_model = True
        parts = to_table.split(".", 1)
        target_model = parts[0]
        target_table = parts[1]

    return {
        "name": edge_name,
        "from": from_table,
        "to": to_table,
        "target_table": target_table,
        "target_model": target_model,
        "on": join_on,
        "type": join_type,
        "cross_model": is_cross_model,
        "optional": optional,
    }


def _parse_on_spec(
    on_spec: Any,
) -> List[Tuple[str, str]]:
    """Parse join-on specifications."""
    if isinstance(on_spec, str):
        on_spec = [on_spec]

    if not isinstance(on_spec, list):
        return []

    pairs = []
    for item in on_spec:
        if isinstance(item, str) and "=" in item:
            left, right = item.split("=", 1)
            pairs.append((left.strip(), right.strip()))
        elif isinstance(item, list) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))

    return pairs


def parse_graph_config(
    model_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract and normalize graph configuration from a model config.

    Returns:
        Dict with:
          - edges: list of parsed edge dicts
          - paths: dict of path_name → path config
          - auto_edges: list of auto-edge dicts (from base inheritance)
    """
    graph = model_config.get("graph", {})
    if not isinstance(graph, dict):
        return {"edges": [], "paths": {}, "auto_edges": []}

    # Parse explicit edges
    raw_edges = graph.get("edges", [])
    edges = []
    for edge in raw_edges:
        parsed = parse_edge(edge)
        if parsed:
            edges.append(parsed)

    # Parse paths
    paths = _normalize_paths(graph.get("paths", {}))

    # Auto-edges come from base inheritance
    auto_edges = _normalize_auto_edges(model_config.get("auto_edges", []))

    return {
        "edges": edges,
        "paths": paths,
        "auto_edges": auto_edges,
    }


def _parse_auto_edge(
    edge: List,
) -> Optional[Dict[str, Any]]:
    """
    Parse a single auto_edge from its 5-position format.

    Format: [fk_column, target, on, type, cross_model]

    Unlike regular edges, auto_edges don't have a 'from' field —
    they apply to all fact tables that have the FK column.
    """
    if not isinstance(edge, list) or len(edge) < 4:
        return None

    fk_column = edge[0]
    target = edge[1]
    on_spec = edge[2]
    join_type = edge[3]
    cross_model = edge[4] if len(edge) > 4 else None

    join_on = _parse_on_spec(on_spec)

    # Parse target for cross-model references
    target_model = None
    target_table = target

    if cross_model and cross_model != "null":
        target_model = cross_model
        if isinstance(target, str) and "." in target:
            target_table = target.split(".", 1)[1]
    elif isinstance(target, str) and "." in target:
        parts = target.split(".", 1)
        target_model = parts[0]
        target_table = parts[1]

    return {
        "fk_column": fk_column,
        "target": target,
        "target_table": target_table,
        "target_model": target_model,
        "on": join_on,
        "type": join_type,
        "cross_model": bool(target_model),
        "optional": False,
        "auto": True,
    }


def _normalize_auto_edges(
    raw_auto_edges: List,
) -> List[Dict[str, Any]]:
    """
    Normalize auto_edges from base templates.

    Auto_edges use a 5-position format: [fk_column, target, on, type, cross_model]
    """
    auto_edges = []
    for edge in raw_auto_edges:
        parsed = _parse_auto_edge(edge)
        if parsed:
            auto_edges.append(parsed)
    return auto_edges


def _normalize_paths(
    raw_paths: Dict,
) -> Dict[str, Dict[str, Any]]:
    """Normalize path definitions."""
    if not isinstance(raw_paths, dict):
        return {}

    paths = {}
    for path_name, path_config in raw_paths.items():
        if not isinstance(path_config, dict):
            continue

        steps = []
        for step in path_config.get("steps", []):
            if isinstance(step, dict):
                steps.append({
                    "from": step.get("from", ""),
                    "to": step.get("to", ""),
                    "via": step.get("via", ""),
                })

        paths[path_name] = {
            "description": path_config.get("description", ""),
            "steps": steps,
        }

    return paths


def resolve_auto_edges(
    model_config: Dict[str, Any],
    tables: Dict[str, Dict],
) -> List[Dict[str, Any]]:
    """
    Resolve auto_edges against actual table schemas.

    For each auto_edge, check which fact tables have the matching FK column
    and generate concrete edges.

    Args:
        model_config: Full model config (with auto_edges from inheritance)
        tables: Assembled table configs with schemas

    Returns:
        List of generated edge dicts
    """
    auto_edges = model_config.get("auto_edges", [])
    if not auto_edges:
        return []

    generated = []

    for auto_edge in auto_edges:
        parsed = _parse_auto_edge(auto_edge)
        if not parsed:
            continue

        fk_column = parsed["fk_column"]

        for table_name, table_config in tables.items():
            if not isinstance(table_config, dict):
                continue

            # Only apply to fact tables
            table_type = table_config.get("table_type") or table_config.get("type", "")
            if table_type != "fact":
                continue

            # Check if this fact table has the FK column
            schema = table_config.get("schema", [])
            col_names = {col[0] for col in schema if isinstance(col, list)}

            if fk_column not in col_names:
                continue

            # Generate edge name
            target_short = parsed["target_table"].lstrip("_").split(".")[-1]
            edge_name = f"{table_name}_to_{target_short}"

            generated.append({
                "name": edge_name,
                "from": table_name,
                "to": parsed["target"],
                "target_table": parsed["target_table"],
                "target_model": parsed["target_model"],
                "on": parsed["on"],
                "type": parsed["type"],
                "cross_model": parsed["cross_model"],
                "optional": parsed["optional"],
                "auto_generated": True,
            })

    return generated


def validate_paths(
    paths: Dict[str, Dict],
    edges: List[Dict],
) -> List[str]:
    """
    Validate that path steps reference known edges or tables.

    Returns:
        List of warning messages
    """
    warnings = []
    edge_tables = set()
    for edge in edges:
        edge_tables.add(edge["from"])
        edge_tables.add(edge.get("target_table", edge["to"]))

    for path_name, path_config in paths.items():
        for i, step in enumerate(path_config.get("steps", [])):
            from_table = step.get("from", "").split(".")[-1]
            to_table = step.get("to", "").split(".")[-1]
            if not step.get("via"):
                warnings.append(
                    f"Path '{path_name}' step {i}: missing 'via' column"
                )

    return warnings
