"""
Build configuration processing for domain v4 configs.

Handles:
- Build phase extraction and validation
- Enrich spec processing (join definitions, computed columns)
- Static/seed table data extraction
- Generated table flagging
- Phase ordering with table dependencies
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_build_config(
    model_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract and normalize the build configuration from a model config.

    Handles both explicit phase definitions and implicit single-phase builds.

    Args:
        model_config: Full model config dict

    Returns:
        Normalized build config with:
          - phases: ordered list of phase dicts
          - partitions: partition columns
          - sort_by: sort columns
          - optimize: bool
    """
    build = model_config.get("build", {})
    if not isinstance(build, dict):
        return {"phases": [], "partitions": [], "sort_by": [], "optimize": False}

    partitions = build.get("partitions", [])
    sort_by = build.get("sort_by", [])
    optimize = build.get("optimize", False)

    # Extract phases
    raw_phases = build.get("phases", {})
    phases = _normalize_phases(raw_phases, model_config)

    return {
        "phases": phases,
        "partitions": partitions if isinstance(partitions, list) else [],
        "sort_by": sort_by if isinstance(sort_by, list) else [],
        "optimize": optimize,
    }


def _normalize_phases(
    raw_phases: Dict,
    model_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Normalize phase definitions to ordered list.

    Handles:
      - Numbered phases: {1: {tables: [...]}, 2: {tables: [...]}}
      - Each phase gets: phase_num, tables, persist, enrich, description
    """
    if not raw_phases:
        # If no phases defined, create a single implicit phase with all tables
        tables = model_config.get("tables", {})
        if tables:
            return [{
                "phase_num": 1,
                "tables": sorted(tables.keys()),
                "persist": True,
                "enrich": False,
                "description": "",
            }]
        return []

    phases = []
    for phase_num in sorted(raw_phases.keys(), key=lambda x: int(x)):
        phase_config = raw_phases[phase_num]
        if not isinstance(phase_config, dict):
            continue

        phases.append({
            "phase_num": int(phase_num),
            "tables": phase_config.get("tables", []),
            "persist": phase_config.get("persist", True),
            "enrich": phase_config.get("enrich", False),
            "description": phase_config.get("description", ""),
        })

    return phases


def get_table_build_flags(
    table_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract build-relevant flags from a table config.

    Returns:
        Dict with: static, generated, persist, transform, group_by,
                    filters, partition_by
    """
    return {
        "static": table_config.get("static", False) or table_config.get("seed", False),
        "generated": table_config.get("generated", False),
        "transform": table_config.get("transform"),
        "group_by": table_config.get("group_by", []),
        "filters": table_config.get("filters", []),
        "partition_by": table_config.get("partition_by", []),
        "primary_key": table_config.get("primary_key", []),
        "unique_key": table_config.get("unique_key", []),
    }


def extract_seed_data(
    table_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract inline seed data from a static/seed table.

    Args:
        table_config: Table config with static: true and data: [...]

    Returns:
        List of row dicts from the data block, or empty list
    """
    is_static = table_config.get("static", False) or table_config.get("seed", False)
    if not is_static:
        return []

    # Data can be under "data:" key or directly under "seed:" key
    data = table_config.get("data", [])
    if not isinstance(data, list) or not data:
        # Check if seed key itself contains the data rows
        seed_val = table_config.get("seed", [])
        if isinstance(seed_val, list) and seed_val:
            data = seed_val

    if not isinstance(data, list):
        return []

    return [row for row in data if isinstance(row, dict)]


def process_enrich_specs(
    table_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Parse and normalize enrich specifications on a table.

    Handles:
      - Simple enrich: [{from: fact_x, join: [...], columns: [...]}]
      - Compact enrich: [{join: dim_y, on: [...], fields: [...]}]
      - Derived-only: [{derived: [...]}]
      - Filtered: [{from: fact_x, join: [...], filter: "...", columns: [...]}]

    Returns:
        List of normalized enrich specs
    """
    raw_enrich = table_config.get("enrich", [])
    if not raw_enrich:
        return []

    if not isinstance(raw_enrich, list):
        raw_enrich = [raw_enrich]

    specs = []
    for item in raw_enrich:
        if not isinstance(item, dict):
            continue

        if "derived" in item:
            # Computed columns — no join needed
            specs.append({
                "type": "derived",
                "columns": item["derived"],
            })
        elif "from" in item:
            # Standard enrich from fact table
            join_spec = item.get("join", [])
            specs.append({
                "type": "join",
                "from": item["from"],
                "join": _parse_join_spec(join_spec),
                "filter": item.get("filter"),
                "columns": item.get("columns", []),
            })
        elif "join" in item:
            # Compact enrich from dimension lookup
            specs.append({
                "type": "lookup",
                "join": item["join"],
                "on": _parse_join_spec(item.get("on", [])),
                "fields": item.get("fields", []),
            })

    return specs


def _parse_join_spec(
    join_spec: Any,
) -> List[Tuple[str, str]]:
    """
    Parse join specifications into (left, right) column pairs.

    Handles:
      - List of strings: ["entity_id=entity_id", "date_id=date_id"]
      - List of lists: [[entity_id, entity_id]]
      - Single string: "entity_id=entity_id"
    """
    if isinstance(join_spec, str):
        join_spec = [join_spec]

    if not isinstance(join_spec, list):
        return []

    pairs = []
    for item in join_spec:
        if isinstance(item, str) and "=" in item:
            left, right = item.split("=", 1)
            pairs.append((left.strip(), right.strip()))
        elif isinstance(item, list) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))

    return pairs


def validate_build_config(
    model_config: Dict[str, Any],
) -> List[str]:
    """
    Validate build configuration for consistency.

    Checks:
      - All tables in phases exist in model tables
      - Phase numbers are sequential
      - Enrich specs reference valid tables

    Returns:
        List of warning/error messages (empty if valid)
    """
    warnings = []
    build = parse_build_config(model_config)
    tables = model_config.get("tables", {})

    # Check that all phase tables exist
    for phase in build["phases"]:
        for table_name in phase["tables"]:
            if table_name not in tables:
                warnings.append(
                    f"Phase {phase['phase_num']}: table '{table_name}' "
                    f"not found in model tables"
                )

    # Check enrich specs reference valid sources
    for table_name, table_config in tables.items():
        if not isinstance(table_config, dict):
            continue
        for spec in process_enrich_specs(table_config):
            if spec["type"] == "join" and spec["from"] not in tables:
                warnings.append(
                    f"Table '{table_name}' enrich references "
                    f"unknown table '{spec['from']}'"
                )

    return warnings
