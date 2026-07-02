"""
DataOps — backend-agnostic DataFrame operation interfaces.

DataOps defines the contract for all DataFrame operations.
DuckDBOps and SparkOps implement it for their respective backends.

Engine delegates all operations to the active DataOps implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class DataOps(ABC):
    """Abstract interface for backend-agnostic DataFrame operations."""

    @abstractmethod
    def read(self, path: str, format: str = "delta") -> Any:
        """Read a table from storage."""
        ...

    @abstractmethod
    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        """Write a DataFrame to storage."""
        ...

    @abstractmethod
    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        """Create a DataFrame from rows and schema."""
        ...

    @abstractmethod
    def select(self, df: Any, columns: list[str]) -> Any:
        """Select columns from a DataFrame."""
        ...

    @abstractmethod
    def drop(self, df: Any, columns: list[str]) -> Any:
        """Drop columns from a DataFrame."""
        ...

    @abstractmethod
    def derive(self, df: Any, col: str, expr: str) -> Any:
        """Add a computed column via SQL expression."""
        ...

    @abstractmethod
    def filter(self, df: Any, conditions: list[str]) -> Any:
        """Filter rows by SQL conditions."""
        ...

    @abstractmethod
    def dedup(self, df: Any, subset: list[str]) -> Any:
        """Deduplicate rows by column subset."""
        ...

    @abstractmethod
    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        """Join two DataFrames."""
        ...

    @abstractmethod
    def union(self, dfs: list[Any]) -> Any:
        """Vertically stack multiple DataFrames."""
        ...

    @abstractmethod
    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        """Melt wide columns into long format."""
        ...

    @abstractmethod
    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        """Add a window function column."""
        ...

    @abstractmethod
    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        """Pivot rows to columns with aggregation."""
        ...

    @abstractmethod
    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        """Group and aggregate."""
        ...

    @abstractmethod
    def count(self, df: Any) -> int:
        """Count rows."""
        ...

    @abstractmethod
    def to_pandas(self, df: Any) -> Any:
        """Convert to pandas DataFrame."""
        ...

    @abstractmethod
    def columns(self, df: Any) -> list[str]:
        """Get column names."""
        ...


class DuckDBOps(DataOps):
    """DuckDB implementation of DataOps — analysis queries only.

    All operations use DuckDB SQL via relations. No pandas.
    DuckDB relations stay lazy until explicitly materialized.
    """

    def __init__(self, conn=None, memory_limit: str = "3GB"):
        import duckdb
        self._conn = conn or duckdb.connect()
        if conn is None:
            self._conn.execute(f"SET memory_limit='{memory_limit}'")
        self._view_counter = 0
        try:
            self._conn.execute("INSTALL delta; LOAD delta;")
            self._delta_available = True
        except Exception:
            self._delta_available = False

    def _next_view(self) -> str:
        self._view_counter += 1
        return f"__v{self._view_counter}"

    def _as_rel(self, df: Any):
        """Coerce df to a DuckDB relation if it isn't already."""
        import duckdb
        if isinstance(df, duckdb.DuckDBPyRelation):
            return df
        # PyArrow table
        if hasattr(df, 'schema') and hasattr(df, 'num_rows'):
            return self._conn.from_arrow(df)
        raise TypeError(f"DuckDBOps: unsupported type {type(df).__name__}")

    def _scan_expr(self, path: str) -> str:
        if self._delta_available:
            try:
                self._conn.execute(f"SELECT 1 FROM delta_scan('{path}') LIMIT 0")
                return f"delta_scan('{path}')"
            except Exception:
                pass
        return f"read_parquet('{path}/*.parquet')"

    def read(self, path: str, format: str = "delta") -> Any:
        scan = self._scan_expr(path)
        return self._conn.sql(f"SELECT * FROM {scan}")

    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        import os
        import pyarrow.parquet as pq
        os.makedirs(path, exist_ok=True)
        rel = self._as_rel(df)
        table = rel.arrow()
        pq.write_table(table, f"{path}/data.parquet")

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        import pyarrow as pa
        type_map = {"string": pa.string(), "int": pa.int64(), "integer": pa.int64(),
                     "float": pa.float64(), "double": pa.float64(), "boolean": pa.bool_()}
        fields = [pa.field(name, type_map.get(dtype, pa.string())) for name, dtype in schema]
        cols = {s[0]: [row[i] for row in rows] for i, s in enumerate(schema)}
        table = pa.table(cols, schema=pa.schema(fields))
        return self._conn.from_arrow(table)

    def select(self, df: Any, columns: list[str]) -> Any:
        rel = self._as_rel(df)
        return rel.select(*[f'"{c}"' for c in columns])

    def drop(self, df: Any, columns: list[str]) -> Any:
        rel = self._as_rel(df)
        keep = [c for c in rel.columns if c not in set(columns)]
        return rel.select(*[f'"{c}"' for c in keep])

    def derive(self, df: Any, col: str, expr: str) -> Any:
        rel = self._as_rel(df)
        return rel.project(f"*, ({expr}) AS \"{col}\"")

    def filter(self, df: Any, conditions: list[str]) -> Any:
        rel = self._as_rel(df)
        for cond in conditions:
            rel = rel.filter(cond)
        return rel

    def dedup(self, df: Any, subset: list[str]) -> Any:
        rel = self._as_rel(df)
        v = self._next_view()
        self._conn.register(v, rel)
        cols = ", ".join(f'"{c}"' for c in rel.columns)
        gb = ", ".join(f'"{c}"' for c in subset)
        result = self._conn.sql(
            f"SELECT DISTINCT ON ({gb}) {cols} FROM {v}"
        )
        self._conn.unregister(v)
        return result

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        l_rel = self._as_rel(left)
        r_rel = self._as_rel(right)
        vl, vr = self._next_view(), self._next_view()
        self._conn.register(vl, l_rel)
        self._conn.register(vr, r_rel)
        on_clause = " AND ".join(f'{vl}."{c}" = {vr}."{c}"' for c in on)
        l_cols = [f'{vl}."{c}"' for c in l_rel.columns]
        r_cols = [f'{vr}."{c}"' for c in r_rel.columns if c not in set(on)]
        all_cols = ", ".join(l_cols + r_cols)
        result = self._conn.sql(
            f"SELECT {all_cols} FROM {vl} {how.upper()} JOIN {vr} ON {on_clause}"
        )
        self._conn.unregister(vl)
        self._conn.unregister(vr)
        return result

    def union(self, dfs: list[Any]) -> Any:
        rels = [self._as_rel(df) for df in dfs]
        views = []
        parts = []
        for rel in rels:
            v = self._next_view()
            self._conn.register(v, rel)
            views.append(v)
            parts.append(f"SELECT * FROM {v}")
        result = self._conn.sql(" UNION ALL ".join(parts))
        for v in views:
            self._conn.unregister(v)
        return result

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        rel = self._as_rel(df)
        v = self._next_view()
        self._conn.register(v, rel)
        id_str = ", ".join(f'"{c}"' for c in id_cols)
        val_str = ", ".join(f'"{c}"' for c in value_cols)
        result = self._conn.sql(
            f'UNPIVOT {v} ON {val_str} INTO NAME "{var_name}" VALUE "{val_name}"'
        )
        self._conn.unregister(v)
        return result

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        rel = self._as_rel(df)
        v = self._next_view()
        self._conn.register(v, rel)
        partition_str = ", ".join(f'"{c}"' for c in partition) if partition else "1"
        order_str = ", ".join(f'"{c}"' for c in order) if order else "1"
        all_cols = ", ".join(f'"{c}"' for c in rel.columns)
        result = self._conn.sql(
            f'SELECT {all_cols}, {expr} OVER '
            f'(PARTITION BY {partition_str} ORDER BY {order_str}) AS "{alias}" '
            f'FROM {v}'
        )
        self._conn.unregister(v)
        return result

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        rel = self._as_rel(df)
        v = self._next_view()
        self._conn.register(v, rel)
        group_cols = rows + cols
        agg_parts = []
        for m in measures:
            agg = m.get("aggregation", "SUM")
            field = m.get("field", "")
            name = m.get("name", field)
            agg_parts.append(f'{agg}("{field}") AS "{name}"')
        group_str = ", ".join(f'"{c}"' for c in group_cols)
        agg_str = ", ".join(agg_parts)
        result = self._conn.sql(
            f"SELECT {group_str}, {agg_str} FROM {v} GROUP BY {group_str}"
        )
        self._conn.unregister(v)
        return result

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        rel = self._as_rel(df)
        v = self._next_view()
        self._conn.register(v, rel)
        agg_parts = []
        for a in aggs:
            func = a.get("func", "SUM")
            col = a.get("col", "")
            alias = a.get("alias", f"{func}_{col}")
            agg_parts.append(f'{func}("{col}") AS "{alias}"')
        agg_str = ", ".join(agg_parts)
        if group_by:
            group_str = ", ".join(f'"{c}"' for c in group_by)
            result = self._conn.sql(
                f"SELECT {group_str}, {agg_str} FROM {v} GROUP BY {group_str}"
            )
        else:
            result = self._conn.sql(f"SELECT {agg_str} FROM {v}")
        self._conn.unregister(v)
        return result

    def count(self, df: Any) -> int:
        rel = self._as_rel(df)
        return rel.aggregate("count(*)").fetchone()[0]

    def to_pandas(self, df: Any) -> Any:
        rel = self._as_rel(df)
        return rel.df()

    def columns(self, df: Any) -> list[str]:
        rel = self._as_rel(df)
        return rel.columns


class SparkOps(DataOps):
    """Spark implementation of DataOps."""

    def __init__(self, spark_session):
        self._spark = spark_session

    def read(self, path: str, format: str = "delta") -> Any:
        return self._spark.read.format(format).load(path)

    def write(self, df: Any, path: str, format: str = "delta", mode: str = "overwrite") -> None:
        df.write.format(format).mode(mode).save(path)

    def create_df(self, rows: list[list], schema: list[tuple[str, str]]) -> Any:
        from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, BooleanType
        type_map = {"string": StringType(), "int": IntegerType(), "float": FloatType(), "boolean": BooleanType()}
        fields = [StructField(name, type_map.get(dtype, StringType()), True) for name, dtype in schema]
        return self._spark.createDataFrame(rows, StructType(fields))

    def select(self, df: Any, columns: list[str]) -> Any:
        return df.select(*columns)

    def drop(self, df: Any, columns: list[str]) -> Any:
        return df.drop(*columns)

    def derive(self, df: Any, col: str, expr: str) -> Any:
        from pyspark.sql import functions as F
        return df.withColumn(col, F.expr(expr))

    def filter(self, df: Any, conditions: list[str]) -> Any:
        for cond in conditions:
            df = df.filter(cond)
        return df

    def dedup(self, df: Any, subset: list[str]) -> Any:
        return df.dropDuplicates(subset)

    def join(self, left: Any, right: Any, on: list[str], how: str = "inner") -> Any:
        return left.join(right, on=on, how=how)

    def union(self, dfs: list[Any]) -> Any:
        result = dfs[0]
        for df in dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)
        return result

    def unpivot(self, df: Any, id_cols: list[str], value_cols: list[str],
                var_name: str = "variable", val_name: str = "value") -> Any:
        return df.unpivot(id_cols, value_cols, var_name, val_name)

    def window(self, df: Any, partition: list[str], order: list[str],
               expr: str, alias: str) -> Any:
        from pyspark.sql import functions as F, Window
        w = Window.partitionBy(*partition).orderBy(*order)
        return df.withColumn(alias, F.expr(expr).over(w))

    def pivot(self, df: Any, rows: list[str], cols: list[str],
              measures: list[dict]) -> Any:
        from pyspark.sql import functions as F
        grouped = df.groupBy(*rows)
        if cols:
            grouped = grouped.pivot(cols[0])
        agg_exprs = []
        for m in measures:
            agg_fn = getattr(F, m.get("aggregation", "sum").lower())
            agg_exprs.append(agg_fn(m.get("field", "")).alias(m.get("name", "")))
        return grouped.agg(*agg_exprs)

    def aggregate(self, df: Any, group_by: list[str], aggs: list[dict]) -> Any:
        from pyspark.sql import functions as F
        grouped = df.groupBy(*group_by)
        agg_exprs = []
        for a in aggs:
            agg_fn = getattr(F, a.get("func", "sum").lower())
            agg_exprs.append(agg_fn(a.get("col", "")).alias(a.get("alias", "")))
        return grouped.agg(*agg_exprs)

    def count(self, df: Any) -> int:
        return df.count()

    def to_pandas(self, df: Any) -> Any:
        return df.toPandas()

    def columns(self, df: Any) -> list[str]:
        return df.columns
