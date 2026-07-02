"""
BaseModel — builds Silver tables from domain YAML config.

Takes a BuildSession which provides Engine (for all DataFrame ops),
StorageRouter (for path resolution), and DomainGraph (for joins).

All backend-specific code is in Engine — BaseModel never checks
'spark' vs 'duckdb'. It just calls engine.read(), engine.write(), etc.

Lifecycle:
    1. __init__(session, model_cfg)
    2. build() → GraphBuilder → NodeExecutor → dims/facts
    3. write_tables() → engine.write() for each table
    4. Hooks: HookRunner dispatches YAML → decorators → class overrides
"""
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DataFrame = Any


class BaseModel:
    """Build-only model class. Session-first — all ops go through Engine."""

    def __init__(self, session, model_cfg: Dict, params: Dict = None):
        """
        Args:
            session: BuildSession with engine, storage_router, graph
            model_cfg: Translated model config from domain markdown
            params: Runtime parameters (date_from, date_to, etc.)
        """
        self.session = session
        self.build_session = session
        self.engine = session.engine
        self.storage_router = session.storage_router
        self.model_cfg = model_cfg
        self.params = params or {}
        self.model_name = model_cfg.get('model', 'unknown')

        # For backward compat with GraphBuilder/DomainModel that still
        # reference these (will be removed as those are cleaned up)
        self.connection = getattr(session.engine, '_conn', None)
        self.storage_cfg = session._storage_config
        self.repo_root = Path(self.params.get('repo_root', '.'))

        # Build output
        self._dims: Optional[Dict[str, DataFrame]] = None
        self._facts: Optional[Dict[str, DataFrame]] = None
        self._is_built = False

        # Graph builder (lazy)
        self._graph_builder = None

    @property
    def backend(self) -> str:
        """Backend type from Engine."""
        return self.engine.backend

    # ── Build lifecycle ───────────────────────────────────

    def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
        """Build Silver tables via GraphBuilder → NodeExecutor."""
        if self._graph_builder is None:
            from de_funk.models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)

        self._dims, self._facts = self._graph_builder.build()
        self._is_built = True
        return self._dims, self._facts

    def ensure_built(self):
        if not self._is_built:
            self.build()

    def write_tables(self, output_root: str = None, fmt: str = "delta",
                     mode: str = "overwrite", **kwargs):
        """Write built tables to Silver via Engine."""
        self.ensure_built()
        silver_root = output_root or self.storage_router.silver_path(self.model_name)

        for table_type, tables in [("dims", self._dims), ("facts", self._facts)]:
            for name, df in (tables or {}).items():
                path = f"{silver_root}/{table_type}/{name}"
                try:
                    self.engine.write(df, path, format=fmt, mode=mode)
                    logger.info(f"Wrote {name} to {path}")
                except Exception as e:
                    logger.error(f"Failed to write {name}: {e}")

    # ── Table access (for hooks) ──────────────────────────

    def get_table(self, name: str) -> Optional[DataFrame]:
        self.ensure_built()
        if self._dims and name in self._dims:
            return self._dims[name]
        if self._facts and name in self._facts:
            return self._facts[name]
        return None

    def has_table(self, name: str) -> bool:
        self.ensure_built()
        return (self._dims and name in self._dims) or (self._facts and name in self._facts)

    def list_tables(self) -> List[str]:
        self.ensure_built()
        tables = []
        if self._dims: tables.extend(self._dims.keys())
        if self._facts: tables.extend(self._facts.keys())
        return tables

    # ── DataFrame helpers (used by DomainModel/GraphBuilder) ──

    def _apply_filters(self, df, filters):
        """Apply filter conditions via Engine."""
        if not filters:
            return df
        return self.engine.filter(df, filters)

    def _select_columns(self, df, select_spec):
        """Apply column selection via Engine."""
        if not select_spec:
            return df
        if isinstance(select_spec, dict):
            for target, source_expr in select_spec.items():
                if source_expr != target:
                    df = self.engine.derive(df, target, source_expr)
            return self.engine.select(df, list(select_spec.keys()))
        elif isinstance(select_spec, list):
            return self.engine.select(df, select_spec)
        return df

    # ── Extension points ──────────────────────────────────

    def before_build(self):
        pass

    def after_build(self, dims, facts):
        return dims, facts

    def custom_node_loading(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        transform = node_config.get("_transform")
        if transform == "window":
            return self._build_window_node(node_id, node_config)
        return None

    def set_session(self, session):
        """Legacy compat — session is set in __init__ now."""
        self.session = session

    # ── Hook dispatch ─────────────────────────────────────

    def _run_hooks(self, hook_name: str, **context) -> None:
        """Run hooks via HookRunner — YAML config first, decorator fallback."""
        from de_funk.core.hooks import HookRunner
        runner = HookRunner(self.model_cfg, model_name=self.model_name)
        runner.run(hook_name, engine=self.engine, model=self, **context)

    # ── Window node building ──────────────────────────────

    def _build_window_node(self, node_id: str, node_config: Dict) -> Optional[DataFrame]:
        """Build a window table from a sibling node."""
        from de_funk.models.base.indicators import apply_indicator

        source = node_config.get("_window_source", "")
        schema = node_config.get("_schema", [])

        if not source:
            return None

        building = getattr(self, "_building_nodes", {})
        if source not in building:
            logger.warning(f"Window node '{node_id}': source '{source}' not yet built")
            return None

        df = building[source]
        cols = set(df.columns) if hasattr(df, 'columns') else set()

        if "security_id" in cols and "date_id" in cols:
            partition_col, order_col = "security_id", "date_id"
        elif "ticker" in cols and "trade_date" in cols:
            partition_col, order_col = "ticker", "trade_date"
        else:
            partition_col = next((c for c in cols if c.endswith("_id") and c != "date_id"), None)
            order_col = next((c for c in cols if "date" in c.lower()), None)

        if not partition_col or not order_col:
            return None

        logger.info(f"Building window table '{node_id}' from '{source}' "
                     f"(partition={partition_col}, order={order_col})")

        for col_def in schema:
            col_name = col_def[0] if isinstance(col_def, (list, tuple)) else col_def.get("name", "")
            opts = col_def[4] if isinstance(col_def, (list, tuple)) and len(col_def) > 4 else {}
            if isinstance(opts, dict) and "indicator" in opts:
                try:
                    df = apply_indicator(df, col_name, opts["indicator"],
                                         partition_col=partition_col,
                                         order_col=order_col,
                                         backend=self.backend)
                except Exception as e:
                    logger.warning(f"Indicator '{col_name}' failed: {e}")

        return df
