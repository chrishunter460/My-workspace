"""
Federation configuration processing for domain v4 configs.

Handles:
- Federation participant detection (federation.enabled on domain models)
- Federation model resolution (federation.children, union_of tables)
- Union table config extraction (union_of references, schema: inherited)
- Cross-model dependency validation
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def is_federation_participant(
    model_config: Dict[str, Any],
) -> bool:
    """Check if a model participates in federation."""
    federation = model_config.get("federation", {})
    if not isinstance(federation, dict):
        return False
    return federation.get("enabled", False)


def is_federation_model(
    model_config: Dict[str, Any],
) -> bool:
    """Check if a model IS a federation model (creates UNION views)."""
    federation = model_config.get("federation", {})
    if not isinstance(federation, dict):
        return False
    return bool(federation.get("children"))


def get_federation_config(
    model_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract and normalize federation configuration.

    Returns:
        Dict with:
          - enabled: bool (is participant)
          - is_federation_model: bool (creates UNIONs)
          - union_key: column name for federation key
          - children: list of child model specs
          - union_tables: dict of table_name → union_of references
    """
    federation = model_config.get("federation", {})
    if not isinstance(federation, dict):
        return {
            "enabled": False,
            "is_federation_model": False,
            "union_key": "",
            "children": [],
            "union_tables": {},
        }

    children = _normalize_children(federation.get("children", []))
    union_tables = _extract_union_tables(model_config.get("tables", {}))

    return {
        "enabled": federation.get("enabled", bool(children)),
        "is_federation_model": bool(children),
        "union_key": federation.get("union_key", "domain_source"),
        "children": children,
        "union_tables": union_tables,
    }


def _normalize_children(
    raw_children: List,
) -> List[Dict[str, str]]:
    """
    Normalize federation children list.

    Handles:
      - [{model: municipal_finance, domain_source: chicago}, ...]
    """
    children = []
    for child in raw_children:
        if isinstance(child, dict) and "model" in child:
            children.append({
                "model": child["model"],
                "domain_source": child.get("domain_source", ""),
            })
    return children


def _extract_union_tables(
    tables: Dict[str, Dict],
) -> Dict[str, Dict[str, Any]]:
    """
    Extract tables that have union_of references.

    Returns:
        Dict of table_name → {union_of: [...], schema_mode: "inherited"|"explicit"}
    """
    union_tables = {}
    for table_name, table_config in tables.items():
        if not isinstance(table_config, dict):
            continue

        union_of = table_config.get("union_of")
        if not union_of:
            continue

        if not isinstance(union_of, list):
            union_of = [union_of]

        schema_mode = "inherited" if table_config.get("schema") == "inherited" else "explicit"

        union_tables[table_name] = {
            "union_of": union_of,
            "schema_mode": schema_mode,
            "primary_key": table_config.get("primary_key", []),
            "partition_by": table_config.get("partition_by", []),
            "description": table_config.get("description", ""),
        }

    return union_tables


def resolve_union_references(
    union_of: List[str],
) -> List[Dict[str, str]]:
    """
    Parse union_of references into model + table pairs.

    Args:
        union_of: List of "model.table" references

    Returns:
        List of {model: str, table: str} dicts
    """
    refs = []
    for ref in union_of:
        if not isinstance(ref, str):
            continue
        parts = ref.split(".", 1)
        if len(parts) == 2:
            refs.append({"model": parts[0], "table": parts[1]})
        else:
            logger.warning(f"Invalid union_of reference: {ref} (expected model.table)")
    return refs


def validate_federation(
    model_config: Dict[str, Any],
    all_model_names: Optional[List[str]] = None,
) -> List[str]:
    """
    Validate federation configuration for consistency.

    Checks:
      - Children reference known models
      - union_of references are valid model.table format
      - depends_on includes all children

    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []
    fed = get_federation_config(model_config)

    if not fed["is_federation_model"]:
        return warnings

    depends_on = set(model_config.get("depends_on", []))

    # Check children are in depends_on
    for child in fed["children"]:
        child_model = child["model"]
        if all_model_names and child_model not in all_model_names:
            warnings.append(
                f"Federation child '{child_model}' not found in available models"
            )
        if child_model not in depends_on:
            warnings.append(
                f"Federation child '{child_model}' not in depends_on"
            )

    # Check union_of references
    for table_name, union_config in fed["union_tables"].items():
        for ref in union_config["union_of"]:
            parts = ref.split(".", 1)
            if len(parts) != 2:
                warnings.append(
                    f"Table '{table_name}' has invalid union_of ref: '{ref}'"
                )

    return warnings
