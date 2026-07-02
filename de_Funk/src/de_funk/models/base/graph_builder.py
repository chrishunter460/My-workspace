"""
GraphBuilder — builds model tables from Bronze via NodeExecutor.

Reads graph.nodes config from model YAML, translates to NodeExecutor
format, and executes through Engine ops. Custom node loading (seed,
union, distinct, window) is handled by DomainModel.custom_node_loading().

All DataFrame operations go through Engine — no direct Spark/DuckDB code.
"""
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

DataFrame = Any


class GraphBuilder:
    """Builds model tables from Bronze via NodeExecutor + Engine."""

    def __init__(self, model):
        self.model = model

    @property
    def model_cfg(self) -> Dict:
        return self.model.model_cfg

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Build model tables: hooks → NodeExecutor → separate dims/facts → hooks."""
        self.model._run_hooks("before_build")
        self.model.before_build()

        nodes = self._build_nodes(self.model.session)

        dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
        facts = {k: v for k, v in nodes.items() if k.startswith("fact_")}

        dims, facts = self.model.after_build(dims, facts)
        self.model._run_hooks("after_build", dims=dims, facts=facts)

        return dims, facts

    def _build_nodes(self, build_session) -> Dict[str, DataFrame]:
        """Build all nodes via NodeExecutor."""
        from de_funk.core.executor import NodeExecutor

        executor = NodeExecutor(build_session)
        graph = self.model_cfg.get('graph', {})
        nodes_config = graph.get('nodes', {})

        if isinstance(nodes_config, list):
            nodes_config = {nc['id']: nc for nc in nodes_config}

        self.model._building_nodes = {}

        # Translate and execute each node
        results = {}
        for node_id, node_cfg in nodes_config.items():
            # Custom loading first (seed, union, distinct, window, unpivot)
            custom_df = self.model.custom_node_loading(node_id, node_cfg)
            if custom_df is not None:
                results[node_id] = custom_df
                self.model._building_nodes[node_id] = custom_df
                continue

            # Translate to NodeExecutor format
            translated = self._translate_node_config(node_id, node_cfg)

            # Execute via NodeExecutor
            result = executor.execute_node(node_id, translated, results)
            if result is not None:
                results[node_id] = result
                self.model._building_nodes[node_id] = result

        return results

    # ── Helpers used by DomainModel custom_node_loading ─────

    def _load_bronze_table(self, table_name: str) -> DataFrame:
        """Load a Bronze table via StorageRouter + Engine."""
        table_ref = f"bronze.{table_name}"
        path = self.model.storage_router.resolve(table_ref)
        return self.model.engine.read(path)

    def _load_silver_table(self, model_name: str, table_name: str) -> DataFrame:
        """Load a Silver table from another model."""
        if table_name.startswith('dim_'):
            subdir = 'dims'
        elif table_name.startswith('fact_'):
            subdir = 'facts'
        else:
            subdir = None

        model_path = model_name.replace(".", "/")
        table_ref = f"silver.{model_path}/{subdir}/{table_name}" if subdir else f"silver.{model_path}/{table_name}"
        path = self.model.storage_router.resolve(table_ref)
        return self.model.engine.read(path)

    def _apply_derive(self, df: DataFrame, col_name: str, expr: str, node_id: str) -> DataFrame:
        """Apply a derive expression via Engine."""
        return self.model.engine.derive(df, col_name, expr)

    # ── Node config translation ───────────────────────────

    def _translate_node_config(self, node_id: str, node_cfg: Dict) -> Dict:
        """Translate graph node config to NodeExecutor format."""
        result = {"from": node_cfg.get("from", "")}

        pipeline = []

        if node_cfg.get("filters"):
            pipeline.append({"op": "filter", "conditions": node_cfg["filters"]})

        if node_cfg.get("join"):
            for join_spec in node_cfg["join"]:
                pipeline.append({"op": "join", "params": {
                    "right": join_spec.get("table", ""),
                    "on": join_spec.get("on", []),
                    "how": join_spec.get("type", "left"),
                }})

        if node_cfg.get("select"):
            if isinstance(node_cfg["select"], dict):
                # Select-as-dict is aliasing — translate to derive + select
                for target, source_expr in node_cfg["select"].items():
                    if source_expr != target:
                        pipeline.append({"op": "derive", "expressions": {target: source_expr}})
                pipeline.append({"op": "select", "columns": list(node_cfg["select"].keys())})
            else:
                pipeline.append({"op": "select", "columns": node_cfg["select"]})

        if node_cfg.get("derive"):
            pipeline.append({"op": "derive", "expressions": node_cfg["derive"]})

        if node_cfg.get("unique_key"):
            pipeline.append({"op": "dedup", "keys": node_cfg["unique_key"]})

        if node_cfg.get("drop"):
            pipeline.append({"op": "drop", "columns": node_cfg["drop"]})

        if pipeline:
            result["pipeline"] = pipeline

        # Special types
        from_spec = node_cfg.get("from", "")
        if from_spec == "__seed__":
            result["type"] = "seed"
        elif from_spec == "__union__":
            result["type"] = "union"
        elif from_spec == "__distinct__":
            result["type"] = "distinct"
        elif from_spec == "__generated__":
            result["type"] = "generated"

        if node_cfg.get("optional"):
            result["optional"] = True

        return result
