"""
View configuration processing for domain v4 configs.

Handles:
- View type discrimination (derived, rollup)
- Assumption processing (base defaults + model overrides)
- View dependency chain resolution (view → view layering)
- View assembly (merge model overrides onto base templates)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_view_config(
    view_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract and normalize a view configuration.

    Returns:
        Normalized view config with:
          - view_type: "derived" or "rollup"
          - from: source table or view name
          - grain: list of GROUP BY columns (rollup only)
          - assumptions: normalized assumption specs
          - schema: output columns (with {derived:} expressions)
          - join: join specs for assumptions
          - measures: view-level measures
    """
    view_type = view_config.get("view_type") or view_config.get("type", "derived")
    from_source = view_config.get("from", "")
    grain = view_config.get("grain", [])

    assumptions = _normalize_assumptions(view_config.get("assumptions", {}))
    join_specs = _normalize_join_specs(view_config.get("join", []))

    return {
        "view_type": view_type,
        "from": from_source,
        "grain": grain if isinstance(grain, list) else [grain],
        "assumptions": assumptions,
        "join": join_specs,
        "schema": view_config.get("schema", []),
        "measures": view_config.get("measures", []),
        "description": view_config.get("description", ""),
    }


def _normalize_assumptions(
    raw_assumptions: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Normalize assumption definitions.

    Base template assumptions have: type, default, description, source
    Model implementations override with: source (table.column), join_on
    """
    if not isinstance(raw_assumptions, dict):
        return {}

    normalized = {}
    for name, spec in raw_assumptions.items():
        if not isinstance(spec, dict):
            continue

        normalized[name] = {
            "name": name,
            "type": spec.get("type"),
            "default": spec.get("default"),
            "description": spec.get("description", ""),
            "source": spec.get("source", ""),
            "join_on": _parse_join_on(spec.get("join_on", [])),
        }

    return normalized


def _parse_join_on(
    join_on: Any,
) -> List[Tuple[str, str]]:
    """
    Parse join_on specifications into (left, right) column pairs.

    Handles:
      - List of strings: ["township_code=township_code", "year=tax_year"]
      - Single string: "township_code=township_code"
    """
    if isinstance(join_on, str):
        join_on = [join_on]

    if not isinstance(join_on, list):
        return []

    pairs = []
    for item in join_on:
        if isinstance(item, str) and "=" in item:
            left, right = item.split("=", 1)
            pairs.append((left.strip(), right.strip()))

    return pairs


def _normalize_join_specs(
    raw_joins: Any,
) -> List[Dict[str, Any]]:
    """
    Normalize view-level join specs (from base templates).

    Base templates define joins as:
      join: [{table: _dim_tax_district, on: [...], fields: [...]}]
    """
    if not isinstance(raw_joins, list):
        return []

    specs = []
    for item in raw_joins:
        if not isinstance(item, dict):
            continue
        specs.append({
            "table": item.get("table", ""),
            "on": _parse_join_on(item.get("on", [])),
            "fields": item.get("fields", []),
        })

    return specs


def resolve_view_chain(
    views: Dict[str, Dict[str, Any]],
) -> List[str]:
    """
    Topological sort of view dependencies.

    Views can reference other views via `from:`. This resolves the
    build order so dependencies are built first.

    Args:
        views: Dict of view_name → view_config

    Returns:
        Ordered list of view names (dependencies first)
    """
    # Build dependency graph
    deps: Dict[str, List[str]] = {}
    view_names = set(views.keys())

    for view_name, view_config in views.items():
        from_source = view_config.get("from", "")
        # Strip leading underscore for base template references
        clean_from = from_source.lstrip("_")

        # Check if from: references another view in this set
        view_deps = []
        for other_name in view_names:
            clean_other = other_name.lstrip("_")
            if clean_from == clean_other or from_source == other_name:
                if other_name != view_name:
                    view_deps.append(other_name)
        deps[view_name] = view_deps

    # Kahn's algorithm
    in_degree = {v: 0 for v in view_names}
    for view_name, view_deps in deps.items():
        for dep in view_deps:
            if dep in in_degree:
                in_degree[view_name] += 1

    queue = sorted(v for v in view_names if in_degree[v] == 0)
    result = []

    while queue:
        view_name = queue.pop(0)
        result.append(view_name)
        for other, other_deps in deps.items():
            if view_name in other_deps:
                in_degree[other] -= 1
                if in_degree[other] == 0 and other not in result:
                    queue.append(other)

    # Handle circular deps
    if len(result) != len(view_names):
        missing = view_names - set(result)
        logger.warning(f"Circular view dependencies detected: {missing}")
        result.extend(sorted(missing))

    return result


def assemble_views(
    model_views: Dict[str, Dict],
    base_views: Dict[str, Dict],
) -> Dict[str, Dict]:
    """
    Merge model view overrides onto base view templates.

    Model views can override:
      - assumptions (bind to concrete data sources)
      - measures (add model-specific measures)

    Args:
        model_views: View configs from model.md
        base_views: View configs from base template

    Returns:
        Merged view configs
    """
    merged = {}

    for view_name, model_config in model_views.items():
        if not isinstance(model_config, dict):
            continue

        # Find base view — try exact match, then with underscore prefix
        base = base_views.get(view_name) or base_views.get(f"_{view_name}", {})

        if base:
            # Merge: base provides structure, model provides bindings
            result = dict(base)

            # Override assumptions with model bindings
            if "assumptions" in model_config:
                base_assumptions = result.get("assumptions", {})
                for name, override in model_config["assumptions"].items():
                    if isinstance(override, dict):
                        if name in base_assumptions and isinstance(base_assumptions[name], dict):
                            merged_assumption = dict(base_assumptions[name])
                            merged_assumption.update(override)
                            base_assumptions[name] = merged_assumption
                        else:
                            base_assumptions[name] = override
                result["assumptions"] = base_assumptions

            # Override measures
            if "measures" in model_config:
                result["measures"] = model_config["measures"]

            merged[view_name] = result
        else:
            merged[view_name] = model_config

    # Include any base views not explicitly referenced by model
    for view_name, base_config in base_views.items():
        if view_name not in merged and not view_name.startswith("_"):
            merged[view_name] = base_config

    return merged


def get_derived_columns(
    schema: List[List],
) -> List[Dict[str, Any]]:
    """
    Extract columns with {derived: "expression"} from a view schema.

    Returns:
        List of dicts with: name, type, nullable, description, expression
    """
    derived = []
    for col in schema:
        if not isinstance(col, list) or len(col) < 2:
            continue

        options = col[4] if len(col) > 4 and isinstance(col[4], dict) else {}
        if "derived" in options:
            derived.append({
                "name": col[0],
                "type": col[1],
                "nullable": col[2] if len(col) > 2 else True,
                "description": col[3] if len(col) > 3 else "",
                "expression": options["derived"],
            })

    return derived
