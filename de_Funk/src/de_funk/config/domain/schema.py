"""
Schema processing for domain v4 configs.

Handles:
- canonical_fields → schema array conversion
- additional_schema merging onto inherited schema
- derivations: flat map overriding {derived:} on inherited columns
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def canonical_fields_to_schema(canonical_fields: List) -> List[List]:
    """
    Convert canonical_fields format to schema array format.

    canonical_fields:
      - [name, type, nullable: true, description: "..."]

    schema:
      - [name, type, true, "..."]

    The canonical format uses keyword args (nullable:, description:)
    while schema uses positional args.
    """
    schema = []
    for field in canonical_fields:
        if not isinstance(field, list) or len(field) < 2:
            continue

        name = field[0]
        field_type = field[1]

        # Extract nullable and description from keyword-style entries
        nullable = True
        description = ""

        for item in field[2:]:
            if isinstance(item, str):
                # Could be a plain description string
                if item not in ("true", "false"):
                    description = item
                else:
                    nullable = item == "true"
            elif isinstance(item, bool):
                nullable = item
            elif isinstance(item, dict):
                if "nullable" in item:
                    nullable = item["nullable"]
                if "description" in item:
                    description = item["description"]

        schema.append([name, field_type, nullable, description])

    return schema


def merge_additional_schema(
    base_schema: List[List],
    additional: List[List],
) -> List[List]:
    """
    Append additional_schema columns to inherited base schema.

    Columns already present in base (by name) are skipped to avoid duplicates.

    Args:
        base_schema: Inherited schema array
        additional: Extra columns to append

    Returns:
        Combined schema array
    """
    existing_names = {col[0] for col in base_schema if isinstance(col, list)}
    result = list(base_schema)

    for col in additional:
        if isinstance(col, list) and len(col) >= 2:
            if col[0] not in existing_names:
                result.append(col)
                existing_names.add(col[0])
            else:
                logger.debug(
                    f"additional_schema column '{col[0]}' already in base, skipping"
                )

    return result


def apply_derivations(
    schema: List[List],
    derivations: Dict[str, str],
) -> List[List]:
    """
    Override {derived:} expressions on schema columns using a flat derivations map.

    derivations:
      parcel_id: "LPAD(pin, 14, '0')"
      bedrooms: "bdrm"

    For each column matching a key in derivations, update or add the
    {derived: "expression"} option.

    Args:
        schema: Schema array to update (modified in place and returned)
        derivations: Map of column_name → expression

    Returns:
        Updated schema array
    """
    if not derivations:
        return schema

    result = []
    for col in schema:
        if not isinstance(col, list) or len(col) < 2:
            result.append(col)
            continue

        col_name = col[0]
        if col_name not in derivations:
            result.append(col)
            continue

        # Clone the column to avoid mutating shared references
        new_col = list(col)

        # Find or create the options dict (position 4)
        while len(new_col) < 5:
            if len(new_col) == 4:
                new_col.append({})
            elif len(new_col) == 3:
                new_col.append("")  # description placeholder
            elif len(new_col) == 2:
                new_col.append(True)  # nullable placeholder

        options = new_col[4]
        if not isinstance(options, dict):
            options = {}
            new_col[4] = options

        options["derived"] = derivations[col_name]
        result.append(new_col)

    return result


def process_table_schema(
    table_config: Dict[str, Any],
    base_table_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Process a table's schema through the full pipeline:
    1. Start with base schema (from extends)
    2. Merge additional_schema
    3. Apply derivations

    Args:
        table_config: The table configuration dict
        base_table_config: Resolved base table config (if extends was used)

    Returns:
        Updated table config with processed schema
    """
    # Start with base schema or existing schema
    if base_table_config and "schema" in base_table_config:
        schema = list(base_table_config["schema"])
    else:
        schema = list(table_config.get("schema", []))

    # Merge additional_schema
    additional = table_config.get("additional_schema")
    if additional:
        schema = merge_additional_schema(schema, additional)

    # Apply derivations
    derivations = table_config.get("derivations")
    if derivations:
        schema = apply_derivations(schema, derivations)

    table_config["schema"] = schema
    return table_config
