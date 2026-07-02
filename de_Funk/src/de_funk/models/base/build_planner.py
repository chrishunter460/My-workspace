"""
BuildPlanner — interprets domain config into an executable build plan.

This is the model-layer interpretation of YAML config. It reads a
DomainModelConfig (pure data) and produces a BuildPlan (executable
instructions) that DomainModel and GraphBuilder consume.

Moved from config/domain/config_translator.py to the model layer
where interpretation logic belongs. Config layer reads YAML;
model layer decides what to build.

Usage:
    from de_funk.models.base.build_planner import BuildPlanner

    planner = BuildPlanner()
    plan = planner.plan(config)  # DomainModelConfig → BuildPlan

    # BuildPlan has typed NodeSpec objects
    for node in plan.nodes.values():
        print(f"{node.node_id}: {node.node_type} from {node.from_ref}")
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


# ── Build Plan data classes ─────────────────────────────

@dataclass
class JoinSpec:
    """One join operation in a node's pipeline."""
    right_table: str
    on: list[str] = dc_field(default_factory=list)
    how: str = "left"


@dataclass
class NodeSpec:
    """Build instructions for one Silver table.

    Produced by BuildPlanner from config interpretation.
    Consumed by GraphBuilder/NodeExecutor for execution.
    """
    node_id: str
    node_type: str = "standard"        # standard, seed, union, distinct, window, unpivot
    from_ref: str = ""                 # Bronze source reference
    select: dict[str, str] = dc_field(default_factory=dict)     # {target_col: source_expr}
    derive: dict[str, str] = dc_field(default_factory=dict)     # {col: SQL_expr}
    filters: list[str] = dc_field(default_factory=list)         # WHERE conditions
    joins: list[JoinSpec] = dc_field(default_factory=list)      # JOIN operations
    dedup_keys: list[str] = dc_field(default_factory=list)      # dropDuplicates keys
    drop_cols: list[str] = dc_field(default_factory=list)       # columns to drop after derive

    # Special node type metadata
    seed_data: list[list] = dc_field(default_factory=list)      # for seed nodes
    seed_schema: list = dc_field(default_factory=list)           # for seed nodes
    union_sources: list[dict] = dc_field(default_factory=list)  # for union nodes
    window_source: str = ""                                      # for window nodes
    window_schema: list = dc_field(default_factory=list)         # for window nodes
    window_partition: str = ""                                   # for window nodes
    window_order: str = ""                                       # for window nodes
    group_by: list[str] = dc_field(default_factory=list)        # for distinct/aggregate
    aggregate_exprs: dict = dc_field(default_factory=dict)      # for aggregate nodes
    unpivot_plan: dict = dc_field(default_factory=dict)         # for unpivot nodes
    enrich_specs: list[dict] = dc_field(default_factory=list)   # post-build enrichments

    # Raw config preserved for DomainModel special handling
    _raw: dict = dc_field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        """Convert to dict format for backward compat with GraphBuilder."""
        d = dict(self._raw) if self._raw else {}
        d["from"] = self.from_ref
        if self.select:
            d["select"] = self.select
        if self.derive:
            d["derive"] = self.derive
        if self.filters:
            d["filters"] = self.filters
        if self.dedup_keys:
            d["unique_key"] = self.dedup_keys
        if self.drop_cols:
            d["drop"] = self.drop_cols
        return d


@dataclass
class BuildPlan:
    """Executable build plan for a domain model.

    Produced by BuildPlanner.plan(). Contains typed NodeSpec objects
    in phase-ordered sequence, plus metadata.
    """
    model_name: str
    nodes: dict[str, NodeSpec] = dc_field(default_factory=dict)
    phase_order: list[list[str]] = dc_field(default_factory=list)
    sources_by_target: dict[str, list] = dc_field(default_factory=dict)

    # Build settings
    partitions: list[str] = dc_field(default_factory=list)
    sort_by: list[str] = dc_field(default_factory=list)
    optimize: bool = True

    def node_ids_in_order(self) -> list[str]:
        """Return node IDs in phase-ordered sequence."""
        if self.phase_order:
            ordered = []
            for phase in self.phase_order:
                ordered.extend(phase)
            # Add any nodes not in phases
            for nid in self.nodes:
                if nid not in ordered:
                    ordered.append(nid)
            return ordered
        return list(self.nodes.keys())

    def to_translated_dict(self) -> dict:
        """Convert to the old translated dict format for backward compat.

        Returns a dict matching what config_translator.translate_domain_config()
        used to produce, so existing code (DomainModel, GraphBuilder) works
        without changes during migration.
        """
        nodes_dict = {}
        for nid, spec in self.nodes.items():
            nodes_dict[nid] = spec.to_dict()

        return {
            "graph": {"nodes": nodes_dict},
            "_domain_build": {
                "phases": {str(i+1): {"tables": phase} for i, phase in enumerate(self.phase_order)},
                "partitions": self.partitions,
                "sort_by": self.sort_by,
                "optimize": self.optimize,
            },
            "_domain_sources_by_target": self.sources_by_target,
        }


# ── BuildPlanner ────────────────────────────────────────

class BuildPlanner:
    """Interprets DomainModelConfig into an executable BuildPlan.

    This is the model-layer interpretation that was previously in
    config/domain/config_translator.py. It reads typed config objects
    and produces typed BuildPlan/NodeSpec objects.

    The actual logic delegates to config_translator functions during
    migration. Once all callers use BuildPlan directly, the translator
    functions can be inlined here.
    """

    def plan(self, config) -> BuildPlan:
        """Interpret a domain model config into a build plan.

        Args:
            config: DomainModelConfig or raw dict

        Returns:
            BuildPlan with typed NodeSpec objects
        """
        # Get raw dict for config_translator (migration compat)
        if hasattr(config, '_raw') and config._raw:
            raw = config._raw
        elif isinstance(config, dict):
            raw = config
        else:
            raw = {}

        # Delegate to existing config_translator for the heavy lifting
        from de_funk.config.domain.config_translator import translate_domain_config
        translated = translate_domain_config(raw)

        # Convert translated dict → typed BuildPlan
        model_name = raw.get("model", "")
        nodes = {}
        graph_nodes = translated.get("graph", {}).get("nodes", {})

        for nid, ncfg in graph_nodes.items():
            from_ref = ncfg.get("from", "")

            # Determine node type from from_ref
            if from_ref == "__seed__":
                node_type = "seed"
            elif from_ref == "__union__":
                node_type = "union"
            elif from_ref == "__distinct__":
                node_type = "distinct"
            elif from_ref == "__window__":
                node_type = "window"
            elif from_ref == "__unpivot__":
                node_type = "unpivot"
            elif from_ref == "__generated__":
                node_type = "generated"
            elif from_ref == "self":
                node_type = "generated"
            else:
                node_type = "standard"

            # Parse joins
            joins = []
            for jspec in ncfg.get("join", []):
                if isinstance(jspec, dict):
                    joins.append(JoinSpec(
                        right_table=jspec.get("table", ""),
                        on=jspec.get("on", []),
                        how=jspec.get("type", "left"),
                    ))

            nodes[nid] = NodeSpec(
                node_id=nid,
                node_type=node_type,
                from_ref=from_ref,
                select=ncfg.get("select", {}),
                derive=ncfg.get("derive", {}),
                filters=ncfg.get("filters", []),
                joins=joins,
                dedup_keys=ncfg.get("unique_key", []),
                drop_cols=ncfg.get("drop", []),
                seed_data=ncfg.get("_seed_data", []),
                seed_schema=ncfg.get("_schema", ncfg.get("schema", [])),
                union_sources=ncfg.get("_union_sources", []),
                window_source=ncfg.get("_window_source", ""),
                window_schema=ncfg.get("_schema", []),
                window_partition=ncfg.get("_window_partition", ""),
                window_order=ncfg.get("_window_order", ""),
                group_by=ncfg.get("_group_by", ncfg.get("group_by", [])),
                aggregate_exprs=ncfg.get("_aggregate", {}),
                unpivot_plan=ncfg.get("_unpivot_plan", {}),
                enrich_specs=ncfg.get("_enrich", []),
                _raw=ncfg,
            )

        # Extract build metadata
        domain_build = translated.get("_domain_build", {})
        phases_raw = domain_build.get("phases", {})
        phase_order = []
        if isinstance(phases_raw, dict):
            for k in sorted(phases_raw.keys(), key=lambda x: int(x)):
                tables = phases_raw[k].get("tables", []) if isinstance(phases_raw[k], dict) else []
                phase_order.append(tables)
        elif isinstance(phases_raw, list):
            for phase in phases_raw:
                if isinstance(phase, dict):
                    phase_order.append(phase.get("tables", []))
                elif isinstance(phase, list):
                    phase_order.append(phase)

        return BuildPlan(
            model_name=model_name,
            nodes=nodes,
            phase_order=phase_order,
            sources_by_target=translated.get("_domain_sources_by_target", {}),
            partitions=domain_build.get("partitions", []),
            sort_by=domain_build.get("sort_by", []),
            optimize=domain_build.get("optimize", True),
        )
