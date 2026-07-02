"""
Source file processing for domain v4 configs.

Handles:
- aliases → SQL SELECT expression list for Bronze→Silver transforms
- domain_source, entry_type, event_type — discriminator injection
- transform: unpivot + unpivot_aliases — wide-to-long transformation
- Multi-source grouping by maps_to target for UNION
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def build_select_expressions(
    aliases: List[List],
    domain_source: Optional[str] = None,
    entry_type: Optional[str] = None,
    event_type: Optional[str] = None,
) -> List[str]:
    """
    Convert alias pairs to SQL SELECT expressions.

    aliases:
      - [canonical_name, source_expression]
      - [entity_id, "ABS(HASH(name))"]

    Result:
      ["ABS(HASH(name)) AS entity_id", ...]

    Args:
        aliases: List of [canonical_name, expression] pairs
        domain_source: Optional literal column (e.g., "'alpha_vantage'")
        entry_type: Optional entry_type discriminator value
        event_type: Optional event_type discriminator value

    Returns:
        List of SQL SELECT expressions
    """
    select_list = []

    for alias in aliases:
        if not isinstance(alias, list) or len(alias) < 2:
            continue
        canonical_name = alias[0]
        expression = str(alias[1])
        select_list.append(f"{expression} AS {canonical_name}")

    # Inject discriminator columns
    if domain_source:
        select_list.append(f"{domain_source} AS domain_source")

    if entry_type:
        select_list.append(f"'{entry_type}' AS entry_type")

    if event_type:
        select_list.append(f"'{event_type}' AS event_type")

    return select_list


def group_sources_by_target(
    sources: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group source configs by their maps_to target table.

    Sources mapping to the same target are UNIONed during build.

    Args:
        sources: Dict of source_name → source_config

    Returns:
        Dict of target_table → list of source configs
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for source_name, source_config in sources.items():
        target = source_config.get("maps_to", "")
        if not target:
            logger.warning(f"Source '{source_name}' has no maps_to target")
            continue

        if target not in grouped:
            grouped[target] = []

        # Include the source name in the config for reference
        config_with_name = dict(source_config)
        config_with_name["_source_name"] = source_name
        grouped[target].append(config_with_name)

    return grouped


def build_unpivot_plan(
    source_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate an unpivot transformation spec from source config.

    Given:
        transform: unpivot
        unpivot_aliases:
          - [totalRevenue, TOTAL_REVENUE]
          - [costOfRevenue, COST_OF_REVENUE]

    Produces a plan dict with:
        - value_column: "amount" (the column that receives the unpivoted value)
        - key_column: "account_code" (the column that receives the row key)
        - mappings: [(source_col, key_value), ...]

    Args:
        source_config: Source config with transform: unpivot

    Returns:
        Unpivot plan dict, or empty dict if not an unpivot source
    """
    if source_config.get("transform") != "unpivot":
        return {}

    unpivot_aliases = source_config.get("unpivot_aliases", [])
    if not unpivot_aliases:
        return {}

    mappings = []
    for alias in unpivot_aliases:
        if isinstance(alias, list) and len(alias) >= 2:
            mappings.append((alias[0], alias[1]))

    return {
        "transform": "unpivot",
        "value_column": "amount",
        "key_column": "account_code",
        "mappings": mappings,
        "source_columns": [m[0] for m in mappings],
        "key_values": [m[1] for m in mappings],
    }


def process_source_config(
    source_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a single source config — generate select expressions and unpivot plan.

    Args:
        source_config: Raw source config from markdown front matter

    Returns:
        Enriched source config with _select_expressions and _unpivot_plan
    """
    aliases = source_config.get("aliases", [])
    domain_source = source_config.get("domain_source")
    entry_type = source_config.get("entry_type")
    event_type = source_config.get("event_type")

    # Build SELECT expressions
    select_exprs = build_select_expressions(
        aliases,
        domain_source=domain_source,
        entry_type=entry_type,
        event_type=event_type,
    )
    source_config["_select_expressions"] = select_exprs

    # Build unpivot plan if applicable
    unpivot_plan = build_unpivot_plan(source_config)
    if unpivot_plan:
        source_config["_unpivot_plan"] = unpivot_plan

    return source_config


def process_all_sources(
    sources: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process all sources for a model — generate select expressions,
    unpivot plans, and group by target.

    Args:
        sources: Dict of source_name → source_config

    Returns:
        Dict with:
          - sources: processed source configs
          - by_target: sources grouped by maps_to target
    """
    processed = {}
    for source_name, source_config in sources.items():
        processed[source_name] = process_source_config(source_config)

    by_target = group_sources_by_target(processed)

    return {
        "sources": processed,
        "by_target": by_target,
    }
