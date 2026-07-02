"""
NodeExecutor — config-driven pipeline executor.

Dispatches operations from a registry against the Engine.
Each pipeline step is a PipelineStep dataclass with {op, fn, params}.
Built-in ops map directly to Engine methods. Custom ops registered
via register_op() or @pipeline_hook decorator.

Usage:
    executor = NodeExecutor(session)
    results = executor.execute_all(nodes_config)
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class NodeExecutor:
    """Config-driven pipeline executor for build operations."""

    def __init__(self, session):
        self.session = session
        self.engine = session.engine
        self._ops: dict[str, Callable] = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register all built-in pipeline operations."""
        self._ops["filter"] = self._op_filter
        self._ops["join"] = self._op_join
        self._ops["select"] = self._op_select
        self._ops["derive"] = self._op_derive
        self._ops["dedup"] = self._op_dedup
        self._ops["drop"] = self._op_drop
        self._ops["enrich"] = self._op_enrich
        self._ops["window"] = self._op_window
        self._ops["unpivot"] = self._op_unpivot
        self._ops["pivot"] = self._op_pivot
        self._ops["aggregate"] = self._op_aggregate
        self._ops["hook"] = self._op_hook

    def register_op(self, name: str, handler: Callable):
        """Register a custom pipeline operation."""
        self._ops[name] = handler
        logger.debug(f"Registered op: {name}")

    def get_op(self, name: str) -> Callable | None:
        """Get an operation handler by name."""
        return self._ops.get(name)

    def list_ops(self) -> list[str]:
        """List all registered operation names."""
        return sorted(self._ops.keys())

    # ── Orchestration ─────────────────────────────────────

    def execute_all(self, nodes_config: dict) -> dict[str, Any]:
        """Execute all nodes in order, returning {node_id: DataFrame}."""
        built: dict[str, Any] = {}
        for node_id, node_cfg in nodes_config.items():
            if isinstance(node_cfg, dict):
                built[node_id] = self.execute_node(node_id, node_cfg, built)
            else:
                logger.warning(f"Skipping node {node_id}: config is not a dict")
        return built

    def execute_node(self, node_id: str, config: dict, built: dict) -> Any:
        """Execute a single node: load source → run pipeline → return DF."""
        from de_funk.core.error_handling import ErrorContext
        logger.info(f"Executing node: {node_id}")

        # Check for special node types
        node_type = config.get("type", "standard")
        if node_type == "seed":
            return self._build_seed(config)
        if node_type == "union":
            return self._build_union(config, built)
        if node_type == "distinct":
            return self._build_distinct(config, built)
        if node_type == "generated":
            return self._build_generated(config)

        # Standard node: load source → run pipeline
        source_ref = config.get("from", "")
        df = self._load_source(source_ref, built)
        if df is None:
            logger.warning(f"Node {node_id}: could not load source '{source_ref}'")
            return None

        # Execute pipeline steps
        pipeline = config.get("pipeline", [])
        if pipeline:
            df = self.execute_pipeline(df, pipeline)

        return df

    def execute_pipeline(self, df: Any, steps: list) -> Any:
        """Execute a sequence of pipeline steps on a DataFrame."""
        for step in steps:
            if isinstance(step, dict):
                op = step.get("op", "")
                handler = self._ops.get(op)
                if handler is None:
                    logger.warning(f"Unknown pipeline op: {op}")
                    continue
                df = handler(df, step)
            elif hasattr(step, 'op'):
                # PipelineStep dataclass
                handler = self._ops.get(step.op)
                if handler is None:
                    logger.warning(f"Unknown pipeline op: {step.op}")
                    continue
                step_dict = {"op": step.op, "fn": step.fn, "params": step.params}
                df = handler(df, step_dict)
        return df

    # ── Source loading ────────────────────────────────────

    def _load_source(self, source_ref: str, built: dict) -> Any:
        """Load a source by reference (bronze ref, silver ref, or built node)."""
        if not source_ref:
            return None

        # Reference to previously built node
        if source_ref in built:
            return built[source_ref]

        # Bronze reference: bronze.provider.endpoint
        if source_ref.startswith("bronze."):
            return self._load_bronze(source_ref)

        # Silver reference: domain.table
        if "." in source_ref:
            parts = source_ref.split(".", 1)
            return self._load_silver(parts[0], parts[1] if len(parts) > 1 else "")

        # Try as built node name
        if source_ref in built:
            return built[source_ref]

        return None

    def _load_from_node(self, node_id: str, built: dict) -> Any:
        """Load DataFrame from a previously built node."""
        if node_id in built:
            return built[node_id]
        return None

    def _load_bronze(self, ref: str) -> Any:
        """Load from Bronze storage."""
        path = self.session.storage_router.resolve(ref)
        try:
            return self.engine.read(path)
        except Exception as e:
            logger.warning(f"Could not read bronze {ref} at {path}: {e}")
            return None

    def _load_silver(self, domain: str, table: str) -> Any:
        """Load from Silver storage."""
        path = self.session.silver_path(domain, table)
        try:
            return self.engine.read(path)
        except Exception as e:
            logger.warning(f"Could not read silver {domain}/{table} at {path}: {e}")
            return None

    # ── Built-in operations ──────────────────────────────

    def _op_filter(self, df: Any, step: dict) -> Any:
        conditions = step.get("conditions", step.get("params", {}).get("conditions", []))
        if conditions:
            return self.engine.filter(df, conditions)
        return df

    def _op_join(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        right_ref = params.get("right", params.get("with", ""))
        on = params.get("on", [])
        how = params.get("how", "inner")
        # right_ref could be a path or a node reference — for now, try reading
        try:
            right = self.engine.read(right_ref) if isinstance(right_ref, str) else right_ref
            return self.engine.join(df, right, on=on, how=how)
        except Exception as e:
            logger.warning(f"Join failed: {e}")
            return df

    def _op_select(self, df: Any, step: dict) -> Any:
        columns = step.get("columns", step.get("params", {}).get("columns", []))
        if columns:
            return self.engine.select(df, columns)
        return df

    def _op_derive(self, df: Any, step: dict) -> Any:
        expressions = step.get("expressions", step.get("params", {}).get("expressions", {}))
        for col, expr in expressions.items():
            df = self.engine.derive(df, col, expr)
        return df

    def _op_dedup(self, df: Any, step: dict) -> Any:
        keys = step.get("keys", step.get("params", {}).get("keys", []))
        if keys:
            return self.engine.dedup(df, keys)
        return df

    def _op_drop(self, df: Any, step: dict) -> Any:
        columns = step.get("columns", step.get("params", {}).get("columns", []))
        if columns:
            return self.engine.drop(df, columns)
        return df

    def _op_enrich(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        from_table = params.get("from_table", "")
        join_keys = params.get("join", [])
        columns = params.get("columns", [])
        try:
            right = self.engine.read(from_table) if isinstance(from_table, str) else from_table
            if join_keys:
                enriched = self.engine.join(df, right, on=join_keys, how="left")
                if columns:
                    keep_cols = list(df.columns) + columns
                    enriched = self.engine.select(enriched, keep_cols)
                return enriched
        except Exception as e:
            logger.warning(f"Enrich failed: {e}")
        return df

    def _op_window(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        partition = params.get("partition", [])
        order = params.get("order", [])
        expr = params.get("expr", "")
        alias = params.get("alias", "window_col")
        if expr:
            return self.engine.window(df, partition, order, expr, alias)
        return df

    def _op_unpivot(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        id_cols = params.get("id_cols", [])
        value_cols = params.get("value_cols", [])
        var_name = params.get("var_name", "variable")
        val_name = params.get("val_name", "value")
        if id_cols and value_cols:
            return self.engine.unpivot(df, id_cols, value_cols, var_name, val_name)
        return df

    def _op_pivot(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        rows = params.get("rows", [])
        cols = params.get("cols", [])
        measures = params.get("measures", [])
        return self.engine.pivot(df, rows, cols, measures)

    def _op_aggregate(self, df: Any, step: dict) -> Any:
        params = step.get("params", {})
        group_by = params.get("group_by", [])
        aggs = params.get("aggs", [])
        return self.engine.aggregate(df, group_by, aggs)

    def _op_hook(self, df: Any, step: dict) -> Any:
        """Execute a Python hook function."""
        fn_path = step.get("fn", step.get("params", {}).get("fn", ""))
        params = step.get("params", {})
        if not fn_path:
            logger.warning("Hook step missing 'fn' path")
            return df

        try:
            fn = self._import_fn(fn_path)
            result = fn(df, engine=self.engine, config=self.session.get_model(
                self.session._kwargs.get("model_name", "")
            ) if hasattr(self.session, 'get_model') else {}, **params)
            return result if result is not None else df
        except Exception as e:
            logger.warning(f"Hook {fn_path} failed: {e}")
            return df

    @staticmethod
    def _import_fn(dotted_path: str) -> Callable:
        """Import a function by dotted path (e.g. 'de_funk.plugins.company_cik.fix_ids')."""
        module_path, fn_name = dotted_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, fn_name)

    # ── Special node types ───────────────────────────────

    def _build_seed(self, config: dict) -> Any:
        """Create DataFrame from inline seed data."""
        rows = config.get("data", [])
        schema = config.get("schema", [])
        if rows and schema:
            return self.engine.create_df(rows, schema)
        return None

    def _build_union(self, config: dict, built: dict) -> Any:
        """Union multiple source DataFrames."""
        sources = config.get("sources", [])
        dfs = []
        for src in sources:
            if src in built and built[src] is not None:
                dfs.append(built[src])
            else:
                try:
                    df = self.engine.read(self.session.storage_router.resolve(src))
                    dfs.append(df)
                except Exception as e:
                    logger.warning(f"Union source {src} failed: {e}")
        if dfs:
            return self.engine.union(dfs)
        return None

    def _build_distinct(self, config: dict, built: dict) -> Any:
        """Read and deduplicate."""
        source = config.get("from", "")
        keys = config.get("keys", [])
        df = self._load_source(source, built)
        if df is not None and keys:
            return self.engine.dedup(df, keys)
        return df

    def _build_generated(self, config: dict) -> Any:
        """Execute SQL or call generator function."""
        sql = config.get("sql", "")
        if sql:
            result = self.engine.execute_sql(sql)
            if result:
                return self.engine.create_df(
                    result,
                    [(f"col_{i}", "string") for i in range(len(result[0]))]
                )
        return None
