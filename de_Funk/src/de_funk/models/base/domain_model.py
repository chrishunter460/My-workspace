"""
DomainModel - BaseModel subclass for multi-file domain configs.

Handles domain-config-specific build behaviors that can't be expressed in
standard graph.nodes:
- Seed/static tables (inline data blocks)
- Multi-source UNION tables
- Transform-based sources (unpivot, aggregate, distinct)

Works with translated configs from config_translator.translate_domain_config(),
which synthesizes graph.nodes from tables + sources.
"""

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import logging

from de_funk.models.base.model import BaseModel
from de_funk.config.domain.config_translator import _normalize_from

logger = logging.getLogger(__name__)

# Type alias for DataFrame (can be Spark or DuckDB)
DataFrame = Any

import re as _re


def _find_derived_source_cols(
    schema: List,
    group_by: List[str],
    available_columns: List[str],
) -> List[str]:
    """
    Identify source columns referenced by derived expressions in the schema.

    For a distinct transform, group_by columns are always kept. But derived
    expressions may reference other source columns — either as simple passthrough
    (e.g., ``{derived: "fund_description"}``) or embedded in expressions
    (e.g., ``CASE WHEN event_type = 'REVENUE' ...``).

    We scan each derived expression for tokens that match actual source column
    names. This is safe because SQL keywords/functions won't collide with
    column names in practice.

    Returns a deduplicated list of extra source column names not already in group_by.
    """
    group_set = set(group_by)
    # Build a set of candidate source columns (excluding group_by, already included)
    candidates = {c for c in available_columns if c not in group_set}
    if not candidates:
        return []

    extras = []
    seen = set()

    for col_def in schema:
        if not isinstance(col_def, list) or len(col_def) < 5:
            continue
        options = col_def[4]
        if not isinstance(options, dict) or "derived" not in options:
            continue

        expr = str(options["derived"])

        # Extract all identifier-like tokens from the expression
        tokens = set(_re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr))

        # Include any token that matches an actual source column name
        for token in tokens:
            if token in candidates and token not in seen:
                extras.append(token)
                seen.add(token)

    return extras


class DomainModel(BaseModel):
    """
    BaseModel subclass that handles domain config specifics.

    This class is used by DomainBuilderFactory to build models defined in
    the multi-file domain config format (markdown + YAML front matter).

    Usage:
        from de_funk.models.base.build_planner import BuildPlanner
        plan = BuildPlanner().plan(domain_config)
        model = DomainModel(session, {**domain_config, **plan.to_translated_dict()}, params)
        model.build()
    """

    def __init__(self, session, model_cfg: Dict, params: Dict = None):
        super().__init__(session, model_cfg, params)

        # Domain-config-specific state
        self._domain_build = model_cfg.get("_domain_build", {})
        self._domain_sources_by_target = model_cfg.get("_domain_sources_by_target", {})

    def custom_node_loading(
        self,
        node_id: str,
        node_config: Dict,
    ) -> Optional[DataFrame]:
        """
        Handle domain-config-specific node types that GraphBuilder can't process.

        Resolution order:
        1. Check @pipeline_hook("custom_node_loading") for this model
        2. Handle built-in markers: __seed__, __union__, __distinct__, __generated__
        3. Handle transforms: window, unpivot
        4. Return None → GraphBuilder handles it as standard node
        """
        # 1. Check hooks (e.g. temporal calendar generation)
        from de_funk.core.hooks import HookRunner
        runner = HookRunner(self.model_cfg, model_name=self.model_name)
        engine = self.build_session.engine if self.build_session and hasattr(self.build_session, 'engine') else None
        hook_result = runner.run("custom_node_loading",
                                 engine=engine, model=self,
                                 node_id=node_id, node_config=node_config)
        if hook_result is not None:
            return hook_result

        # 2. Built-in markers
        from_spec = node_config.get("from", "")

        if from_spec == "__seed__":
            return self._build_seed_node(node_id, node_config)

        if from_spec == "__union__":
            return self._build_union_node(node_id, node_config)

        if from_spec == "__generated__":
            # Generated tables are built in after_build, skip here
            logger.info(f"Deferring generated table '{node_id}' to after_build")
            try:
                return self._create_empty_df(node_config)
            except Exception as e:
                logger.warning(f"Could not create empty schema for generated table '{node_id}': {e}")
                return None

        if from_spec == "__distinct__":
            return self._build_distinct_node(node_id, node_config)

        # Check for transform-based sources
        if node_config.get("_transform") == "window":
            return self._build_window_node(node_id, node_config)

        if node_config.get("_transform") == "unpivot":
            return self._build_unpivot_node(node_id, node_config)

        # Default: let GraphBuilder handle it
        return None

    def _build_seed_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> DataFrame:
        """Create a DataFrame from inline seed data, then apply derived columns."""
        seed_data = node_config.get("_seed_data", [])
        schema = node_config.get("_schema", [])

        if not seed_data:
            logger.warning(f"Seed table '{node_id}' has no data rows")
            return self._create_empty_df(node_config)

        logger.info(f"Building seed table '{node_id}' with {len(seed_data)} rows")

        if self.backend == "spark":
            df = self._seed_to_spark_df(seed_data, schema)
        else:
            df = self._seed_to_duckdb_df(seed_data, schema)

        # Apply derived expressions from schema (e.g., {derived: "ABS(HASH(col))"})
        df = self._apply_seed_derived_columns(df, schema, node_id)

        return df

    def _build_union_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> DataFrame:
        """Load multiple sources and UNION them."""
        sources = node_config.get("_union_sources", [])
        if not sources:
            logger.warning(f"Union table '{node_id}' has no sources")
            return self._create_empty_df(node_config)

        logger.info(
            f"Building UNION table '{node_id}' from {len(sources)} sources"
        )

        dfs = []
        for source in sources:
            from_spec = source.get("from", "")
            if not from_spec:
                continue

            # Normalize provider_table underscore to dot for StorageRouter
            from_spec = _normalize_from(from_spec)

            # Load the source table
            if "." in from_spec:
                layer, table = from_spec.split(".", 1)
                if layer == "bronze":
                    try:
                        df = self.graph_builder._load_bronze_table(table)
                    except Exception as e:
                        logger.warning(
                            f"Skipping source '{source.get('_source_name', '?')}' "
                            f"for union '{node_id}': {e}"
                        )
                        continue
                else:
                    try:
                        df = self.graph_builder._load_silver_table(layer, table)
                    except Exception as e:
                        logger.warning(
                            f"Skipping source for union '{node_id}': {e}"
                        )
                        continue
            else:
                # Internal table reference — look in in-progress build nodes
                try:
                    df = self._load_internal_or_bronze(from_spec, node_id)
                except (ValueError, Exception) as e:
                    logger.warning(
                        f"Union source '{from_spec}' not found: {e}"
                    )
                    continue

            # Apply unpivot transform if source requires it
            if source.get("transform") == "unpivot":
                unpivot_aliases = source.get("unpivot_aliases", [])
                if unpivot_aliases and self.backend == "spark":
                    df = self._apply_unpivot(df, unpivot_aliases, node_id)

            # Apply aliases as select
            aliases = source.get("aliases", [])
            if aliases:
                select_dict = {}
                for alias in aliases:
                    if isinstance(alias, list) and len(alias) >= 2:
                        select_dict[alias[0]] = str(alias[1])
                if select_dict:
                    df = self._select_columns(df, select_dict)

            # Inject discriminators
            if source.get("domain_source"):
                df = self._apply_derive(
                    df, "domain_source", source["domain_source"], node_id
                )
            if source.get("entry_type"):
                df = self._apply_derive(
                    df, "entry_type", f"'{source['entry_type']}'", node_id
                )
            if source.get("event_type"):
                df = self._apply_derive(
                    df, "event_type", f"'{source['event_type']}'", node_id
                )

            dfs.append(df)

        if not dfs:
            return self._create_empty_df(node_config)

        # UNION all DataFrames
        result = dfs[0]
        for df in dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)

        return result

    def _load_internal_or_bronze(self, from_spec: str, node_id: str) -> DataFrame:
        """Load a table from model's own built tables or from Bronze."""
        if "." in from_spec:
            # Normalize provider underscores to dots for StorageRouter
            from_spec = _normalize_from(from_spec)
            layer, table = from_spec.split(".", 1)
            if layer == "bronze":
                return self.graph_builder._load_bronze_table(table)
            else:
                return self.graph_builder._load_silver_table(layer, table)
        else:
            # Internal table reference — look in in-progress build nodes
            building = getattr(self, '_building_nodes', {})
            if from_spec in building:
                logger.debug(f"  {node_id}: reading from in-progress node '{from_spec}'")
                return building[from_spec]
            raise ValueError(
                f"Table '{node_id}' references '{from_spec}' which hasn't been "
                f"built yet. Check build phase ordering."
            )

    def _build_distinct_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> DataFrame:
        """
        Build a dimension from SELECT DISTINCT group_by cols, then derive.

        Supports both Bronze sources and internal model tables (Phase 1 facts).
        When union_from is specified, unions multiple tables before applying DISTINCT.
        """
        from_spec = node_config.get("_distinct_from", "")
        union_from = node_config.get("_distinct_union_from", [])
        group_by = node_config.get("_distinct_group_by", [])
        schema = node_config.get("_schema", [])
        is_aggregate = node_config.get("_aggregate", False)

        if not from_spec or not group_by:
            logger.warning(
                f"Distinct table '{node_id}' missing from or group_by"
            )
            return self._create_empty_df(node_config)

        transform_type = "AGGREGATE" if is_aggregate else "DISTINCT"
        logger.info(
            f"Building {transform_type} table '{node_id}' from {from_spec} "
            f"group_by={group_by}"
        )

        # Load source table(s)
        if union_from and len(union_from) > 1:
            # Union multiple internal tables
            dfs = []
            for src in union_from:
                try:
                    src_df = self._load_internal_or_bronze(src, node_id)
                    dfs.append(src_df)
                    logger.debug(f"  {node_id}: loaded '{src}' for union")
                except Exception as e:
                    logger.warning(f"  {node_id}: skipping '{src}': {e}")

            if not dfs:
                return self._create_empty_df(node_config)

            df = dfs[0]
            for extra_df in dfs[1:]:
                df = df.unionByName(extra_df, allowMissingColumns=True)
        else:
            df = self._load_internal_or_bronze(from_spec, node_id)

        if is_aggregate:
            # GROUP BY with aggregate expressions via Spark SQL
            view_name = f"_agg_src_{node_id}"
            df.createOrReplaceTempView(view_name)

            select_parts = []
            for col_def in schema:
                col_name = col_def[0]
                options = col_def[4] if len(col_def) > 4 else None
                if isinstance(options, dict) and "derived" in options:
                    expr = options["derived"]
                    select_parts.append(f"{expr} AS {col_name}")
                elif col_name in group_by:
                    select_parts.append(col_name)

            if not select_parts:
                select_parts = group_by

            group_clause = ", ".join(group_by)
            select_clause = ", ".join(select_parts)
            sql = f"SELECT {select_clause} FROM {view_name} GROUP BY {group_clause}"

            logger.debug(f"  Aggregate SQL: {sql}")
            df = self.connection.sql(sql)
        else:
            # DISTINCT — select group_by columns + source columns needed by
            # derived expressions, then deduplicate on group_by only.
            available = df.columns
            extra_source_cols = _find_derived_source_cols(
                schema, group_by, available,
            )
            select_cols = list(group_by) + extra_source_cols
            select_cols = [c for c in select_cols if c in set(available)]
            df = df.select(*select_cols).dropDuplicates(group_by)

            # Apply derived columns from schema
            df = self._apply_seed_derived_columns(df, schema, node_id)

        row_count = df.count()
        logger.info(f"  {node_id}: {row_count} {transform_type.lower()} values")

        # Apply enrichment JOINs (aggregate columns from fact tables)
        enrich_specs = node_config.get("_enrich", [])
        if enrich_specs:
            df = self._apply_distinct_enrichments(df, enrich_specs, node_id)

        return df

    def _apply_distinct_enrichments(
        self,
        df: DataFrame,
        enrich_specs: List[Dict],
        node_id: str,
    ) -> DataFrame:
        """
        Apply enrich specs to a distinct dimension table.

        Handles:
          - type=join: Load source fact table, apply optional filter, GROUP BY
            the join key, compute aggregate columns, LEFT JOIN onto dimension.
          - type=derived: Compute expressions from already-enriched columns.
        """
        from pyspark.sql import functions as F  # noqa: PLC0415

        for spec in enrich_specs:
            spec_type = spec.get("type")

            if spec_type == "join":
                source_table = spec["from"]
                join_pairs = spec.get("join", [])
                columns = spec.get("columns", [])
                filter_expr = spec.get("filter")

                if not join_pairs or not columns:
                    continue

                # join_pairs: list of (left_col, right_col)
                left_col, right_col = join_pairs[0]

                try:
                    source_df = self._load_internal_or_bronze(source_table, node_id)
                except Exception as e:
                    logger.warning(
                        f"  {node_id} enrich: cannot load '{source_table}': {e}"
                    )
                    continue

                # Apply filter if specified
                if filter_expr:
                    source_df = source_df.filter(filter_expr)

                # Build aggregate expressions from column schema
                # Column format: [name, type, nullable, description, {options}]
                agg_exprs = []
                col_names = []
                for col_def in columns:
                    if not isinstance(col_def, list) or len(col_def) < 5:
                        continue
                    col_name = col_def[0]
                    options = col_def[4]
                    if isinstance(options, dict) and "derived" in options:
                        expr = options["derived"]
                        agg_exprs.append(F.expr(expr).alias(col_name))
                        col_names.append(col_name)

                if not agg_exprs:
                    continue

                agg_df = source_df.groupBy(left_col).agg(*agg_exprs)

                # Rename the join key in agg_df to avoid column ambiguity
                # after the join (Spark's .drop(agg_df[col]) can fail to
                # resolve correctly when multiple DataFrames share a name).
                join_key_alias = f"__enrich_jk_{left_col}"
                agg_df = agg_df.withColumnRenamed(left_col, join_key_alias)

                # LEFT JOIN the aggregated results onto the dimension
                df = df.join(
                    agg_df,
                    df[right_col] == agg_df[join_key_alias],
                    how="left",
                ).drop(join_key_alias)

                logger.debug(
                    f"  {node_id} enrich: joined {len(col_names)} columns "
                    f"from {source_table}"
                )

            elif spec_type == "derived":
                # Computed columns from already-enriched columns
                for col_def in spec.get("columns", []):
                    if not isinstance(col_def, list) or len(col_def) < 5:
                        continue
                    col_name = col_def[0]
                    options = col_def[4]
                    if isinstance(options, dict) and "derived" in options:
                        expr = options["derived"]
                        try:
                            df = df.withColumn(col_name, F.expr(expr))
                            logger.debug(
                                f"  {node_id} enrich: derived '{col_name}' = {expr}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"  {node_id} enrich: failed derived "
                                f"'{col_name}': {e}"
                            )

        return df

    def _build_window_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> Optional[DataFrame]:
        """
        Build a table by applying indicator configs from the schema to a sibling node.

        Each schema column with {indicator: <code>, ...params} is dispatched to
        indicators.apply_indicator(). Columns with {derived: "expr"} are computed
        via standard SQL expressions (e.g. surrogate PKs). Schema column ORDER
        matters for dependent indicators (ema before macd_line, etc.).

        Config keys:
          _window_source: sibling node name (must be built in an earlier phase)
          _schema:        table schema list driving indicator computation
        """
        from de_funk.models.base.indicators import apply_indicator

        source = node_config.get("_window_source", "")
        schema = node_config.get("_schema", [])

        if not source:
            logger.warning(f"Window node '{node_id}': no source specified — skipping")
            return self._create_empty_df(node_config)

        if source not in self._building_nodes:
            logger.warning(
                f"Window node '{node_id}': source '{source}' not yet built — "
                f"ensure it is in an earlier phase"
            )
            return self._create_empty_df(node_config)

        df = self._building_nodes[source]
        cols = set(df.columns)

        if "security_id" in cols and "date_id" in cols:
            partition_col, order_col = "security_id", "date_id"
        elif "ticker" in cols and "trade_date" in cols:
            partition_col, order_col = "ticker", "trade_date"
        else:
            logger.error(
                f"Window node '{node_id}': cannot determine partition/order columns "
                f"from source '{source}' columns: {sorted(cols)[:10]}"
            )
            return self._create_empty_df(node_config)

        logger.info(
            f"Building window table '{node_id}' from '{source}' "
            f"(partition={partition_col}, order={order_col})"
        )

        for col_def in schema:
            if not isinstance(col_def, list):
                continue
            col_name = col_def[0]
            options  = col_def[4] if len(col_def) >= 5 else {}
            if not isinstance(options, dict):
                continue

            if "indicator" in options:
                try:
                    df = apply_indicator(df, col_name, options, partition_col, order_col)
                except Exception as e:
                    logger.error(
                        f"Window node '{node_id}': indicator '{col_name}' "
                        f"({options.get('indicator')}) failed: {e}",
                        exc_info=True,
                    )
            elif "derived" in options:
                df = self._apply_derive(df, col_name, options["derived"], node_id)

        col_names = [c[0] for c in schema if isinstance(c, list)]
        available = [c for c in col_names if c in df.columns]
        if available:
            df = df.select(*available)

        return df

    def _build_unpivot_node(
        self,
        node_id: str,
        node_config: Dict,
    ) -> Optional[DataFrame]:
        """Handle unpivot transform on a source."""
        unpivot_plan = node_config.get("_unpivot_plan", {})
        if not unpivot_plan:
            return None

        # Load the base table normally first
        from_spec = node_config.get("from", "")
        if not from_spec or from_spec.startswith("__"):
            return None

        # Let GraphBuilder load the raw table, then apply unpivot in after_build
        # For now, return None to let normal loading proceed
        return None

    def _create_empty_df(self, node_config: Dict) -> DataFrame:
        """Create an empty DataFrame with schema from node config."""
        schema = node_config.get("_schema", [])
        col_names = [col[0] for col in schema if isinstance(col, list)]

        from pyspark.sql.types import StructType, StructField, StringType
        spark_schema = StructType([
            StructField(name, StringType(), True) for name in col_names
        ])
        return self.connection.createDataFrame([], spark_schema)

    def _seed_to_spark_df(
        self,
        seed_data: List[Dict],
        schema: List,
    ) -> DataFrame:
        """Convert seed data to a Spark DataFrame."""
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType,
            LongType, DoubleType, BooleanType,
        )

        type_map = {
            "string": StringType(),
            "int": IntegerType(),
            "integer": IntegerType(),
            "long": LongType(),
            "double": DoubleType(),
            "float": DoubleType(),
            "boolean": BooleanType(),
            "bool": BooleanType(),
        }

        fields = []
        for col in schema:
            if isinstance(col, list) and len(col) >= 2:
                col_name = col[0]
                col_type = str(col[1]).lower()
                nullable = col[2] if len(col) > 2 and isinstance(col[2], bool) else True
                # Derived columns start as NULL and are filled in later,
                # so force them nullable in the initial schema
                options = col[4] if len(col) > 4 else None
                if isinstance(options, dict) and "derived" in options:
                    nullable = True
                spark_type = type_map.get(col_type, StringType())
                fields.append(StructField(col_name, spark_type, nullable))

        spark_schema = StructType(fields) if fields else None

        # Columns with {derived:} expressions should be NULL in the initial
        # DataFrame — _apply_seed_derived_columns will compute them afterward.
        # The data: block may contain the expression string as a value (e.g.,
        # "ABS(HASH(...))"), which Spark can't cast to IntegerType directly.
        derived_cols = set()
        for col in schema:
            if isinstance(col, list) and len(col) > 4:
                options = col[4]
                if isinstance(options, dict) and "derived" in options:
                    derived_cols.add(col[0])

        if derived_cols:
            cleaned_data = []
            for row in seed_data:
                cleaned_row = dict(row)
                for col_name in derived_cols:
                    if col_name in cleaned_row:
                        cleaned_row[col_name] = None
                cleaned_data.append(cleaned_row)
            seed_data = cleaned_data

        return self.connection.createDataFrame(seed_data, spark_schema)

    def _seed_to_duckdb_df(
        self,
        seed_data: List[Dict],
        schema: List,
    ) -> DataFrame:
        """Convert seed data to a Spark DataFrame (builds always use Spark)."""
        return self._seed_to_spark_df(seed_data, schema)

    def _apply_seed_derived_columns(
        self,
        df: DataFrame,
        schema: List,
        node_id: str,
    ) -> DataFrame:
        """
        Apply {derived: "expr"} from schema to a seed DataFrame.

        Seed data doesn't include derived columns (they aren't in the inline
        data rows), so we compute them after creating the DataFrame.

        Schema format: [name, type, nullable, description, {options}]
        Options may contain: {derived: "SQL_EXPRESSION"}
        """
        for col_def in schema:
            if not isinstance(col_def, list) or len(col_def) < 5:
                continue
            options = col_def[4]
            if isinstance(options, dict) and "derived" in options:
                col_name = col_def[0]
                expr = options["derived"]
                logger.debug(
                    f"Seed table '{node_id}': deriving column "
                    f"'{col_name}' = {expr}"
                )
                df = self._apply_derive(df, col_name, expr, node_id)
        return df

    @property
    def graph_builder(self):
        """Access the graph builder (lazy-loaded by BaseModel)."""
        if self._graph_builder is None:
            from de_funk.models.base.graph_builder import GraphBuilder
            self._graph_builder = GraphBuilder(self)
        return self._graph_builder

    def _apply_derive(self, df, out_name, expr, node_id):
        """Delegate to graph_builder's derive logic."""
        return self.graph_builder._apply_derive(df, out_name, expr, node_id)

    def _apply_unpivot(
        self,
        df: DataFrame,
        unpivot_aliases: List,
        node_id: str,
    ) -> DataFrame:
        """
        Unpivot wide-format data to long format using Spark SQL STACK.

        Wide: ticker | fiscal_date | total_revenue | cost_of_revenue | ...
        Long: ticker | fiscal_date | line_item_code | value

        unpivot_aliases: [[source_col, canonical_code], ...]
          e.g., [["total_revenue", "TOTAL_REVENUE"], ["cost_of_revenue", "COST_OF_REVENUE"]]
        """
        if not unpivot_aliases:
            return df

        # Identify non-unpivot columns to keep
        unpivot_source_cols = {a[0] for a in unpivot_aliases if isinstance(a, list)}
        id_cols = [c for c in df.columns if c not in unpivot_source_cols]

        # Build STACK expression
        n = len(unpivot_aliases)
        stack_parts = []
        for alias in unpivot_aliases:
            if isinstance(alias, list) and len(alias) >= 2:
                src_col, canonical = alias[0], alias[1]
                stack_parts.append(f"'{canonical}', CAST(`{src_col}` AS DOUBLE)")

        stack_expr = f"STACK({n}, {', '.join(stack_parts)}) AS (line_item_code, value)"
        id_cols_str = ", ".join(f"`{c}`" for c in id_cols)

        view_name = f"_unpivot_{node_id}_{id(df)}"
        df.createOrReplaceTempView(view_name)

        sql = f"SELECT {id_cols_str}, {stack_expr} FROM {view_name}"
        logger.debug(f"  Unpivot SQL for {node_id}: {sql[:200]}...")

        spark = self.connection
        result = spark.sql(sql)

        # Filter out NULL values (columns that didn't exist in this row)
        result = result.filter("value IS NOT NULL")
        logger.info(f"  Unpivoted {node_id}: {len(unpivot_aliases)} columns -> long format")

        return result
