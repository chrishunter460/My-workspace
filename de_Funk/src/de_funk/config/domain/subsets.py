"""
Subset auto-absorption for domain v4 configs.

When a base template declares subsets.pattern: wide_table with a target_table,
and child templates declare subset_of pointing back to that parent, the loader
absorbs children's canonical_fields and measures into the parent's target table
as nullable columns with {subset: VALUE} metadata.

Example:
    _base/property/parcel.md:
      subsets:
        target_table: _dim_parcel
        values:
          RESIDENTIAL:
            extends: _base.property.residential

    _base/property/residential.md:
      subset_of: _base.property.parcel
      subset_value: RESIDENTIAL
      canonical_fields:
        - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
      measures:
        - [avg_bedrooms, avg, bedrooms, "Average bedrooms"]

    Result: _dim_parcel gains [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL}]
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .extends import parse_front_matter
from .schema import canonical_fields_to_schema

logger = logging.getLogger(__name__)


def absorb_subsets(
    parent_config: Dict[str, Any],
    domains_dir: Path,
    parse_cache: Optional[Dict[str, Dict]] = None,
    parent_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan for subset children and absorb their fields into the parent's target table.

    Args:
        parent_config: The parent base template config (must have subsets block)
        domains_dir: Root domains directory for scanning
        parse_cache: Optional cache of parsed configs
        parent_ref: Dotted reference used to load this config (e.g., "_base.simple.base_template")

    Returns:
        Updated parent config with absorbed columns and measures
    """
    if parse_cache is None:
        parse_cache = {}

    subsets = parent_config.get("subsets")
    if not subsets or not isinstance(subsets, dict):
        return parent_config

    target_table = subsets.get("target_table")
    if not target_table:
        return parent_config

    pattern = subsets.get("pattern", "wide_table")
    if pattern != "wide_table":
        return parent_config

    # Get the target table's schema
    tables = parent_config.get("tables", {})
    if target_table not in tables:
        logger.warning(f"Subset target_table '{target_table}' not found in tables")
        return parent_config

    target_schema = list(tables[target_table].get("schema", []))
    target_measures = list(tables[target_table].get("measures", []))

    # Find all subset children by scanning _base/ for subset_of references
    parent_model = parent_config.get("model", "")
    children = _find_subset_children(
        parent_model, domains_dir, parse_cache, parent_ref=parent_ref
    )

    for child_config in children:
        subset_value = child_config.get("subset_value", "")
        child_fields = child_config.get("canonical_fields", [])
        child_measures = child_config.get("measures", [])

        # Absorb fields as nullable columns with {subset: VALUE}
        target_schema = _absorb_fields(target_schema, child_fields, subset_value)

        # Absorb measures with subset metadata
        target_measures = _absorb_measures(target_measures, child_measures, subset_value)

    tables[target_table]["schema"] = target_schema
    tables[target_table]["measures"] = target_measures
    parent_config["tables"] = tables

    return parent_config


def _find_subset_children(
    parent_model: str,
    domains_dir: Path,
    parse_cache: Dict[str, Dict],
    parent_ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Discover all base templates that declare subset_of pointing to this parent.

    Scans all .md files in _base/ for subset_of references matching
    either the parent's dotted reference or model name.
    """
    children = []
    base_dir = domains_dir / "_base"
    if not base_dir.exists():
        return children

    for md_file in sorted(base_dir.rglob("*.md")):
        cache_key = str(md_file)
        if cache_key not in parse_cache:
            parse_cache[cache_key] = parse_front_matter(md_file)

        config = parse_cache[cache_key]
        subset_of = config.get("subset_of", "")

        if not subset_of:
            continue

        # Match by exact dotted reference (e.g., subset_of == parent_ref)
        if parent_ref and subset_of == parent_ref:
            children.append(config)
            continue

        # Match if subset_of ends with the parent model name
        # e.g., "_base.property.parcel" matches parent model "parcel"
        ref_parts = subset_of.split(".")
        ref_tail = ref_parts[-1] if ref_parts else ""

        if ref_tail == parent_model or subset_of.endswith(f".{parent_model}"):
            children.append(config)

    return children


def _absorb_fields(
    target_schema: List[List],
    child_fields: List,
    subset_value: str,
) -> List[List]:
    """
    Add child canonical_fields to target schema as nullable columns.

    Each absorbed column gets {subset: VALUE} in its options dict.
    Columns already present (by name) are skipped.
    """
    existing_names = {col[0] for col in target_schema if isinstance(col, list)}

    # Convert canonical_fields to schema format
    child_schema = canonical_fields_to_schema(child_fields)

    for col in child_schema:
        col_name = col[0]
        if col_name in existing_names:
            continue

        # Force nullable for subset columns
        new_col = list(col)
        if len(new_col) >= 3:
            new_col[2] = True  # Always nullable in wide table

        # Add {subset: VALUE} metadata
        while len(new_col) < 5:
            if len(new_col) == 4:
                new_col.append({})
            elif len(new_col) == 3:
                new_col.append(new_col[3] if len(col) > 3 else "")

        options = new_col[4] if isinstance(new_col[4], dict) else {}
        options["subset"] = subset_value
        new_col[4] = options

        target_schema.append(new_col)
        existing_names.add(col_name)

    return target_schema


def _absorb_measures(
    target_measures: List[List],
    child_measures: List,
    subset_value: str,
) -> List[List]:
    """
    Add child measures to target measures with subset metadata.

    Each absorbed measure gets {subset: VALUE} in its options dict.
    Measures already present (by name) are skipped.
    """
    existing_names = {m[0] for m in target_measures if isinstance(m, list)}

    for measure in child_measures:
        if not isinstance(measure, list) or len(measure) < 4:
            continue

        measure_name = measure[0]
        if measure_name in existing_names:
            continue

        new_measure = list(measure)

        # Add {subset: VALUE} to options (position 4)
        if len(new_measure) >= 5 and isinstance(new_measure[4], dict):
            new_measure[4] = dict(new_measure[4])
            new_measure[4]["subset"] = subset_value
        elif len(new_measure) == 4:
            new_measure.append({"subset": subset_value})
        else:
            while len(new_measure) < 5:
                new_measure.append({})
            new_measure[4] = {"subset": subset_value}

        target_measures.append(new_measure)
        existing_names.add(measure_name)

    return target_measures
