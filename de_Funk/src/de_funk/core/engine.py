"""
Engine — long-lived backend-agnostic data operations.

Delegates all operations to DataOps (DataFrame ops) and SqlOps (SQL ops).
Created via Engine.for_duckdb() or Engine.for_spark().

Backward compatibility: get_query_engine() and get_handler_registry()
bridge to the existing handler code during migration.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class Engine:
    """Backend-agnostic data engine.

    Provides read/write/join/filter/aggregate operations that work
    with both DuckDB and Spark via DataOps/SqlOps strategy pattern.
    """

    def __init__(self, backend: str, ops=None, sql=None,
                 conn=None, storage_config=None, **kwargs):
        self.backend = backend
        self._ops = ops
        self._sql = sql
        self._conn = conn
        self._storage_config = storage_config or {}
        self._query_engine = None  # Lazy — backward compat bridge
        self._kwargs = kwargs

    @staticmethod
    def for_duckdb(storage_config: dict = None, memory_limit: str = "3GB",
                   max_sql_rows: int = 30000, max_dimension_values: int = 10000,
                   **kwargs) -> Engine:
        """Create a DuckDB-backed engine with DataOps + SqlOps."""
        import duckdb
        conn = duckdb.connect()
        conn.execute(f"SET memory_limit='{memory_limit}'")

        from de_funk.core.ops import DuckDBOps
        from de_funk.core.sql import DuckDBSql

        ops = DuckDBOps(conn=conn, memory_limit=memory_limit)
        sql = DuckDBSql(conn, max_sql_rows=max_sql_rows,
                        max_dimension_values=max_dimension_values)

        engine = Engine(backend="duckdb", ops=ops, sql=sql, conn=conn,
                        storage_config=storage_config or {}, **kwargs)
        logger.info(f"Engine: DuckDB ready (memory={memory_limit})")
        return engine

    @staticmethod
    def for_spark(spark_session, storage_config: dict = None, **kwargs) -> Engine:
        """Create a Spark-backed engine with DataOps + SqlOps."""
        from de_funk.core.ops import SparkOps
        from de_funk.core.sql import SparkSql

        ops = SparkOps(spark_session)
        sql = SparkSql(spark_session)

        engine = Engine(backend="spark", ops=ops, sql=sql, conn=spark_session,
                        storage_config=storage_config or {}, **kwargs)
        logger.info("Engine: Spark ready")
        return engine

    # ── DataFrame operations (delegate to DataOps) ────────

    def read(self, path: str, format: str = "delta") -> Any:
        try:
            return self._ops.read(path, format)
        except Exception as e:
            from de_funk.core.exceptions import DataNotFoundError
            raise DataNotFoundError(path, f"Engine.read failed: {e}") from e

    def write(self, df: Any, path: str, format: str = "delta",
              mode: str = "overwrite") -> None:
        try:
            self._ops.write(df, path, format, mode)
        except Exception as e:
            from de_funk.core.exceptions import WriteError
            raise WriteError(path, f"Engine.write failed: {e}") from e

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        return self._ops.create_df(rows, schema)

    def select(self, df: Any, columns: list[str]) -> Any:
        return self._ops.select(df, columns)

    def drop(self, df: Any, columns: list[str]) -> Any:
        return self._ops.drop(df, columns)

    def derive(self, df: Any, col: str, expr: str) -> Any:
        return self._ops.derive(df, col, expr)

    def filter(self, df: Any, conditions: list[str]) -> Any:
        return self._ops.filter(df, conditions)

    def dedup(self, df: Any, subset: list[str]) -> Any:
        return self._ops.dedup(df, subset)

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        return self._ops.join(left, right, on, how)

    def union(self, dfs: list[Any]) -> Any:
        return self._ops.union(dfs)

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        return self._ops.unpivot(df, id_cols, value_cols, var_name, val_name)

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        return self._ops.window(df, partition, order, expr, alias)

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        return self._ops.pivot(df, rows, cols, measures)

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        return self._ops.aggregate(df, group_by, aggs)

    def count(self, df: Any) -> int:
        return self._ops.count(df)

    def to_pandas(self, df: Any) -> Any:
        return self._ops.to_pandas(df)

    def columns(self, df: Any) -> list[str]:
        return self._ops.columns(df)

    # ── SQL operations (delegate to SqlOps) ───────────────

    def execute_sql(self, sql_str: str, max_rows: int = 0) -> list:
        return self._sql.execute_sql(sql_str, max_rows)

    def scan(self, path: str) -> str:
        return self._sql.scan(path)

    def build_from(self, tables: dict[str, str], resolver=None,
                   allowed_domains: set[str] | None = None) -> str:
        return self._sql.build_from(tables, resolver, allowed_domains)

    def build_where(self, filters: list, resolver=None,
                    from_tables: set[str] | None = None) -> list[str]:
        return self._sql.build_where(filters, resolver, from_tables)

    def distinct_values(self, resolved, extra_filters=None,
                        resolver=None, max_values: int = 0) -> list:
        return self._sql.distinct_values(resolved, extra_filters, resolver, max_values)

    def distinct_values_by_measure(self, resolved, order_by, order_dir="desc",
                                   extra_filters=None, resolver=None) -> list:
        """Return distinct values ordered by aggregated measure."""
        dim_col = f'"{resolved.table_name}"."{resolved.column}"'
        measure_col = f'"{order_by.table_name}"."{order_by.column}"'
        dir_sql = "DESC" if order_dir.lower() == "desc" else "ASC"

        from de_funk.api.handlers.base import ExhibitHandler
        extra = ExhibitHandler._build_extra_where(extra_filters)
        tables = ExhibitHandler._collect_tables(
            [resolved, order_by] + ExhibitHandler._extra_filter_fields(extra_filters)
        )

        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            from_clause = f'{self.scan(path)} AS "{name}"'
        else:
            from_clause = self.build_from(tables, resolver)

        sql = f"""
            SELECT {dim_col}, AVG({measure_col}) AS _sort_val
            FROM {from_clause}
            WHERE {dim_col} IS NOT NULL{extra}
            GROUP BY {dim_col}
            ORDER BY _sort_val {dir_sql}
        """
        max_dim = self._sql._max_dimension_values if hasattr(self._sql, '_max_dimension_values') else 10000
        result = self.execute_sql(sql, max_rows=max_dim)
        return [row[0] for row in result]

    # ── Backward compatibility ─────────────────────────────

    def get_query_engine(self):
        """Deprecated: handlers now use Engine directly.

        Returns self for API compatibility with code that checks for
        a query engine instance.
        """
        return self

    def get_handler_registry(self, resolver=None, bronze_resolver=None,
                             max_response_mb: float = 4.0,
                             storage_root=None):
        """Create a HandlerRegistry using this Engine directly."""
        from de_funk.api.handlers import build_registry

        return build_registry(
            engine=self,
            storage_root=storage_root,
            max_response_mb=max_response_mb,
            max_sql_rows=self._sql._max_sql_rows if hasattr(self._sql, '_max_sql_rows') else 30000,
            max_dimension_values=self._sql._max_dimension_values if hasattr(self._sql, '_max_dimension_values') else 10000,
        )

    def __repr__(self):
        return f"Engine(backend={self.backend})"
