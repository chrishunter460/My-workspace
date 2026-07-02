"""
Domain config translator for model builds.

Converts domain model config (tables + sources + build phases) into
build-compatible config with synthesized `graph.nodes` that GraphBuilder
can process directly.

The translator produces one graph.node entry per table by combining:
- Source config -> node `from` (Bronze path) + `select` (alias dict)
- Table config -> node `derive` (from schema {derived:}), `filters`, `unique_key`
- Enrich specs -> node `join` entries (dimension lookups)
- Seed/static -> flagged for custom_node_loading in DomainModel
"""

import logging
from typing import Dict, Any, List, Optional

from de_funk.config.domain.sources import (
    group_sources_by_target,
    process_source_config,
)
from de_funk.config.domain.build import (
    parse_build_config,
    get_table_build_flags,
    extract_seed_data,
    process_enrich_specs,
)

logger = logging.getLogger(__name__)


def translate_domain_config(domain_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate a domain model config into build-compatible format with graph.nodes.

    The output preserves all domain-specific keys (tables, sources, build, views)
    and ADDS a synthesized `graph.nodes` dict so GraphBuilder can process it.

    Args:
        domain_config: Config dict from DomainConfigLoader.load_model_config()

    Returns:
        Translated config dict with graph.nodes added
    """
    config = dict(domain_config)
    tables = config.get("tables", {})
    sources = config.get("sources", {})

    # Process all sources to get select expressions
    processed_sources = {}
    for name, src in sources.items():
        processed_sources[name] = process_source_config(dict(src))

    # Group sources by their target table
    by_target = group_sources_by_target(processed_sources)

    # Parse build config for phase ordering
    build_config = parse_build_config(config)

    # Build ordered table list from phases
    ordered_tables = _get_phase_ordered_tables(build_config, tables)

    # Synthesize graph.nodes
    nodes = {}
    for table_name in ordered_tables:
        table_config = tables.get(table_name, {})
        if not isinstance(table_config, dict):
            continue

        node = _synthesize_node(
            table_name, table_config, by_target.get(table_name, [])
        )
        if node:
            nodes[table_name] = node

    # Inject synthesized nodes into config
    # Merge: synthesized nodes fill gaps, existing nodes take precedence
    graph = config.get("graph", {})
    if not isinstance(graph, dict):
        graph = {}
    existing_nodes = graph.get("nodes", {})
    merged_nodes = {**nodes, **existing_nodes}
    graph["nodes"] = merged_nodes
    config["graph"] = graph

    # Store build metadata for DomainModel
    config["_domain_build"] = build_config
    config["_domain_sources_by_target"] = by_target

    return config


# Keep backward-compatible alias
translate_v4_config = translate_domain_config


def _get_phase_ordered_tables(
    build_config: Dict[str, Any],
    tables: Dict[str, Any],
) -> List[str]:
    """
    Get tables in build-phase order (dims before facts).

    If phases are defined, returns tables in phase order.
    Otherwise, returns dims first, then facts (alphabetical within each group).
    """
    phases = build_config.get("phases", [])

    if phases:
        ordered = []
        for phase in sorted(phases, key=lambda p: p["phase_num"]):
            for t in phase["tables"]:
                if t not in ordered and t in tables:
                    ordered.append(t)
        # Add any tables not in phases (shouldn't happen, but be safe)
        for t in tables:
            if t not in ordered:
                ordered.append(t)
        return ordered

    # No phases — dims first, then facts
    dims = sorted(t for t in tables if t.startswith("dim_"))
    facts = sorted(t for t in tables if t.startswith("fact_"))
    others = sorted(t for t in tables if t not in dims and t not in facts)
    return dims + others + facts


def _synthesize_node(
    table_name: str,
    table_config: Dict[str, Any],
    matching_sources: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Synthesize a single graph.node from table + source configs.

    Args:
        table_name: Name of the table (e.g., "dim_parcel")
        table_config: Table config from domain model
        matching_sources: Source configs that map_to this table

    Returns:
        Build-compatible node dict, or None if cannot be built
    """
    flags = get_table_build_flags(table_config)

    # Seed/static tables — mark for custom_node_loading
    if flags["static"]:
        seed_data = extract_seed_data(table_config)
        return {
            "from": "__seed__",
            "type": _table_type(table_name),
            "_seed": True,
            "_seed_data": seed_data,
            "_schema": table_config.get("schema", []),
            "primary_key": flags["primary_key"],
            "unique_key": flags["unique_key"],
        }

    # Generated tables — mark for custom_node_loading
    if flags["generated"]:
        return {
            "from": "__generated__",
            "type": _table_type(table_name),
            "_generated": True,
            "_table_config": table_config,
            "primary_key": flags["primary_key"],
            "unique_key": flags["unique_key"],
        }

    # Window-transform tables — computed from a sibling Silver node via indicator configs
    if flags.get("transform") == "window":
        return {
            "from": "__window__",
            "type": _table_type(table_name),
            "_transform": "window",
            "_window_source": table_config.get("from", ""),
            "_schema": table_config.get("schema", []),
            "primary_key": flags["primary_key"],
            "unique_key": flags["unique_key"],
        }

    # Distinct/aggregate-transform tables — GROUP BY group_by cols, then derive
    if flags.get("transform") in ("distinct", "aggregate"):
        direct_from = table_config.get("from")
        if direct_from:
            # Normalize only if it's a Bronze reference (has dot notation)
            normalized_from = (
                _normalize_from(direct_from) if "." in direct_from else direct_from
            )
            union_from = table_config.get("union_from", [])
            enrich_specs = process_enrich_specs(table_config)
            return {
                "from": "__distinct__",
                "type": _table_type(table_name),
                "_distinct": True,
                "_aggregate": flags["transform"] == "aggregate",
                "_distinct_from": normalized_from,
                "_distinct_union_from": union_from,
                "_distinct_group_by": flags.get("group_by", []),
                "_schema": table_config.get("schema", []),
                "_enrich": enrich_specs,
                "primary_key": flags["primary_key"],
                "unique_key": flags["unique_key"],
            }

    # Standard table — needs at least one source
    if not matching_sources:
        # Check for union_from: references to internal tables (silver intermediates)
        union_from = table_config.get("union_from", [])
        if union_from:
            internal_sources = [{"from": tbl, "aliases": []} for tbl in union_from]
            return _build_union_node(table_name, table_config, internal_sources, flags)

        # Table has no source — might inherit from parent or be enrichment-only
        # Check if table has a `from` key directly (some tables do)
        direct_from = table_config.get("from")
        if direct_from:
            node = _build_node_from_table(table_name, table_config, direct_from)
            return node
        logger.debug(
            f"Table '{table_name}' has no matching source and no 'from' — "
            f"will need custom_node_loading or cross-model reference"
        )
        return None

    # Single source -> straightforward node
    if len(matching_sources) == 1:
        source = matching_sources[0]
        return _build_node_from_source(table_name, table_config, source, flags)

    # Multiple sources -> UNION node (handled by DomainModel.custom_node_loading)
    return _build_union_node(table_name, table_config, matching_sources, flags)


def _build_node_from_source(
    table_name: str,
    table_config: Dict[str, Any],
    source: Dict[str, Any],
    flags: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a node from a single source mapping."""
    # Convert source `from` to bronze path format
    from_spec = _normalize_from(source.get("from", ""))

    # Convert aliases to select dict: {canonical_name: expression}
    select = _aliases_to_select_dict(source.get("aliases", []))

    # Add discriminator columns to select
    if source.get("domain_source"):
        select["domain_source"] = source["domain_source"]
    if source.get("entry_type"):
        select["entry_type"] = f"'{source['entry_type']}'"
    if source.get("event_type"):
        select["event_type"] = f"'{source['event_type']}'"

    # Extract derive expressions from table schema {derived:} options
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    # Also include derivations map if present
    derivations = table_config.get("derivations", {})
    if isinstance(derivations, dict):
        derive.update(derivations)

    # Remove derive entries for columns already computed by source select.
    # Source aliases handle the Bronze->canonical mapping during the select phase;
    # keeping a derive for the same column would fail because derives run AFTER
    # select and reference pre-select (raw Bronze) column names that no longer exist.
    if select and derive:
        overlap = set(derive.keys()) & set(select.keys())
        if overlap:
            logger.debug(
                f"Table '{table_name}': removing {len(overlap)} derive entries "
                f"already covered by source select: {sorted(overlap)}"
            )
            derive = {k: v for k, v in derive.items() if k not in select}

    # Build enrich -> join specs
    join_specs = _enrich_to_join_specs(table_config)

    node = {
        "from": from_spec,
        "type": _table_type(table_name),
    }

    if select:
        node["select"] = select

    # Merge filters from both table config and source config
    filters = list(flags.get("filters") or [])
    source_filter = source.get("filter")
    if source_filter:
        if isinstance(source_filter, list):
            filters.extend(source_filter)
        else:
            filters.append(source_filter)
    if filters:
        node["filters"] = filters
    if derive:
        node["derive"] = derive
    if flags.get("unique_key"):
        node["unique_key"] = flags["unique_key"]
    elif flags.get("primary_key"):
        node["unique_key"] = flags["primary_key"]
    if join_specs:
        node["join"] = join_specs

    # Pass optional flag for nodes with potentially missing Bronze data
    if table_config.get("optional"):
        node["optional"] = True

    # Store transform metadata for advanced processing
    if source.get("transform"):
        node["_transform"] = source["transform"]
        if source.get("_unpivot_plan"):
            node["_unpivot_plan"] = source["_unpivot_plan"]

    return node


def _build_node_from_table(
    table_name: str,
    table_config: Dict[str, Any],
    from_spec: str,
) -> Dict[str, Any]:
    """Build a node from a table config that has a direct `from` key."""
    from_normalized = _normalize_from(from_spec)
    flags = get_table_build_flags(table_config)
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    node = {
        "from": from_normalized,
        "type": _table_type(table_name),
    }

    if flags.get("filters"):
        node["filters"] = flags["filters"]
    if derive:
        node["derive"] = derive
    if flags.get("unique_key"):
        node["unique_key"] = flags["unique_key"]
    elif flags.get("primary_key"):
        node["unique_key"] = flags["primary_key"]

    if table_config.get("optional"):
        node["optional"] = True

    return node


def _build_union_node(
    table_name: str,
    table_config: Dict[str, Any],
    sources: List[Dict[str, Any]],
    flags: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a UNION node for tables with multiple sources."""
    derive = _extract_derive_from_schema(table_config.get("schema", []))

    return {
        "from": "__union__",
        "type": _table_type(table_name),
        "_union": True,
        "_union_sources": sources,
        "_schema": table_config.get("schema", []),
        "derive": derive if derive else {},
        "unique_key": flags.get("unique_key") or flags.get("primary_key", []),
    }


def _normalize_from(from_spec: str) -> str:
    """
    Normalize a `from` spec to build format.

    Sources use underscores: "bronze.alpha_vantage_company_overview"
    StorageRouter expects dots:  "bronze.alpha_vantage.company_overview"

    Conversion: split known provider prefix from table name with a dot.

    "bronze.alpha_vantage_company_overview" -> "bronze.alpha_vantage.company_overview"
    "bronze.cook_county_parcel_sales"       -> "bronze.cook_county.parcel_sales"
    "bronze.chicago_crimes"                 -> "bronze.chicago.crimes"
    "silver.temporal.dim_calendar"          -> "temporal.dim_calendar"
    """
    if not from_spec:
        return from_spec

    parts = from_spec.split(".", 1)
    if parts[0] == "silver" and len(parts) > 1:
        return parts[1]  # Strip "silver." prefix for GraphBuilder

    if parts[0] == "bronze" and len(parts) > 1:
        table_part = parts[1]
        # Already has dots (e.g., "alpha_vantage.listing_status") — pass through
        if "." in table_part:
            return from_spec
        # Convert provider_table underscore to dot for StorageRouter
        # Known providers ordered longest-first to avoid partial matches
        for provider in ["alpha_vantage", "cook_county", "chicago"]:
            prefix = provider + "_"
            if table_part.startswith(prefix):
                table_name = table_part[len(prefix):]
                return f"bronze.{provider}.{table_name}"
        # Unknown provider — return as-is (StorageRouter may have a mapping)
        logger.debug(f"Unknown bronze provider in from spec: {from_spec}")

    return from_spec


def _aliases_to_select_dict(aliases: List[List]) -> Dict[str, str]:
    """
    Convert alias pairs to select dict.

    aliases: [["parcel_id", "LPAD(pin, 14, '0')"], ["sale_date", "sale_date"]]
    select:  {"parcel_id": "LPAD(pin, 14, '0')", "sale_date": "sale_date"}
    """
    select = {}
    for alias in aliases:
        if isinstance(alias, list) and len(alias) >= 2:
            canonical_name = alias[0]
            expression = str(alias[1])
            select[canonical_name] = expression
    return select


def _extract_derive_from_schema(schema: List) -> Dict[str, str]:
    """
    Extract {derived: "expr"} from schema column definitions.

    Schema format: [name, type, nullable, description, {options}]
    Options may contain: {derived: "SQL_EXPRESSION"}

    Returns:
        Dict of column_name -> derive expression
    """
    derive = {}
    for col in schema:
        if not isinstance(col, list) or len(col) < 5:
            continue
        options = col[4] if len(col) > 4 else None
        if isinstance(options, dict) and "derived" in options:
            derive[col[0]] = options["derived"]
    return derive


def _enrich_to_join_specs(table_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert enrich specs to join format.

    enrich: [{join: dim_x, on: [col1=col2], fields: [field1]}]
    join:   [{table: dim_x, on: ["col1=col2"], type: "left"}]
    """
    enrich_specs = process_enrich_specs(table_config)
    join_specs = []

    for spec in enrich_specs:
        if spec["type"] == "lookup":
            # Compact dimension lookup
            on_pairs = spec.get("on", [])
            on_strings = [f"{left}={right}" for left, right in on_pairs]
            join_specs.append({
                "table": spec["join"],
                "on": on_strings,
                "type": "left",
                "_fields": spec.get("fields", []),
            })
        elif spec["type"] == "join":
            # Standard enrich from fact table
            on_pairs = spec.get("join", [])
            on_strings = [f"{left}={right}" for left, right in on_pairs]
            join_specs.append({
                "table": spec["from"],
                "on": on_strings,
                "type": "left",
                "filter": spec.get("filter"),
                "_columns": spec.get("columns", []),
            })

    return join_specs


def _table_type(table_name: str) -> str:
    """Infer table type from naming convention."""
    if table_name.startswith("dim_"):
        return "dimension"
    elif table_name.startswith("fact_"):
        return "fact"
    return "other"
