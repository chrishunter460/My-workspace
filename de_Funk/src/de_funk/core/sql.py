"""
SqlOps — backend-agnostic SQL operation interfaces.

SqlOps defines the contract for SQL-level operations (execute, scan,
FROM clause building, WHERE clause building, distinct values).

Engine delegates SQL operations to the active SqlOps implementation.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any, Optional

from de_funk.config.logging import get_logger

logger = get_logger(__name__)


def _eval_date_expr(expr: object) -> str | None:
    """Evaluate frontmatter date expressions to ISO date strings."""
    if expr is None:
        return None
    s = str(expr).strip()
    today = date.today()
    if s == "current_date":
        return str(today)
    m = re.match(r"current_date\s*-\s*(\d+)", s)
    if m:
        return str(today - timedelta(days=int(m.group(1))))
    m = re.match(r"current_date\s*\+\s*(\d+)", s)
    if m:
        return str(today + timedelta(days=int(m.group(1))))
    if s == "year_start":
        return str(today.replace(month=1, day=1))
    return s


class SqlOps(ABC):
    """Abstract interface for SQL operations."""

    @abstractmethod
    def execute_sql(self, sql: str, max_rows: int = 30000) -> list:
        """Execute raw SQL and return rows."""
        ...

    @abstractmethod
    def scan(self, path: str) -> str:
        """Return a backend-specific scan expression for a storage path."""
        ...

    @abstractmethod
    def build_from(self, tables: dict[str, str], resolver: Any = None,
                   allowed_domains: set[str] | None = None) -> str:
        """Build a FROM clause with automatic join resolution."""
        ...

    @abstractmethod
    def build_where(self, filters: list, resolver: Any = None,
                    from_tables: set[str] | None = None) -> list[str]:
        """Build WHERE clause fragments from filter specs."""
        ...

    @abstractmethod
    def distinct_values(self, resolved: Any,
                        extra_filters: list | None = None,
                        resolver: Any = None,
                        max_values: int = 10000) -> list:
        """Return sorted distinct values for a dimension field."""
        ...


class DuckDBSql(SqlOps):
    """DuckDB implementation of SqlOps."""

    def __init__(self, conn, max_sql_rows: int = 30000,
                 max_dimension_values: int = 10000):
        self._conn = conn
        self._max_sql_rows = max_sql_rows
        self._max_dimension_values = max_dimension_values
        self._scan_cache: dict[str, str] = {}
        try:
            self._conn.execute("INSTALL delta; LOAD delta;")
            self._delta_available = True
        except Exception:
            self._delta_available = False

    def execute_sql(self, sql: str, max_rows: int = 0) -> list:
        limit = max_rows if max_rows > 0 else self._max_sql_rows
        return self._conn.execute(sql).fetchmany(limit)

    def scan(self, path: str) -> str:
        if path in self._scan_cache:
            return self._scan_cache[path]
        if not self._delta_available:
            expr = f"read_parquet('{path}/*.parquet')"
        else:
            try:
                self._conn.execute(f"SELECT 1 FROM delta_scan('{path}') LIMIT 0")
                expr = f"delta_scan('{path}')"
            except Exception:
                expr = f"read_parquet('{path}/*.parquet')"
        self._scan_cache[path] = expr
        return expr

    def build_from(self, tables: dict[str, str], resolver: Any = None,
                   allowed_domains: set[str] | None = None) -> str:
        if not tables:
            raise ValueError("No tables to query")
        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            self._from_tables = {name}
            return f'{self.scan(path)} AS "{name}"'

        names = sorted(tables.keys(), key=lambda n: (n.startswith("dim_"), n))
        base = names[0]
        included: dict[str, str] = {base: tables[base]}
        parts = [f'{self.scan(tables[base])} AS "{base}"']

        for target_name in names[1:]:
            if target_name in included:
                continue
            path_steps = None
            for already_in in included:
                steps = (resolver.find_join_path(already_in, target_name,
                         allowed_domains=allowed_domains) if resolver else None)
                if steps is not None:
                    path_steps = steps
                    break

            if path_steps is None:
                parts.append(f'CROSS JOIN {self.scan(tables[target_name])} AS "{target_name}"')
                included[target_name] = tables[target_name]
                continue

            current = already_in
            for (next_table, col_on_current, col_on_next) in path_steps:
                if next_table in included:
                    current = next_table
                    continue
                next_path = tables.get(next_table)
                if next_path is None and resolver:
                    next_path = self._resolve_intermediate_path(next_table, resolver)
                if next_path is None:
                    break
                parts.append(
                    f'LEFT JOIN {self.scan(next_path)} AS "{next_table}"'
                    f' ON "{current}"."{col_on_current}" = "{next_table}"."{col_on_next}"'
                )
                included[next_table] = next_path
                current = next_table

        self._from_tables = set(included)
        return " ".join(parts)

    def _resolve_intermediate_path(self, table_name: str, resolver: Any) -> str | None:
        if resolver is None or not hasattr(resolver, '_index'):
            return None
        for domain, fields in resolver._index.items():
            for tbl, _, subdir in fields.values():
                if tbl == table_name:
                    domain_path = domain.replace(".", "/")
                    domain_root = resolver._domain_overrides.get(
                        domain, resolver.storage_root / domain_path
                    )
                    return str(domain_root / subdir / table_name) if subdir else str(domain_root / table_name)
        return None

    def build_where(self, filters: list, resolver: Any = None,
                    from_tables: set[str] | None = None) -> list[str]:
        joined = from_tables
        if joined is None and hasattr(self, "_from_tables"):
            joined = self._from_tables

        clauses = []
        for f in (filters or []):
            try:
                resolved = resolver.resolve(f.field)
            except (ValueError, AttributeError):
                continue
            if joined is not None and resolved.table_name not in joined:
                continue
            col = f'"{resolved.table_name}"."{resolved.column}"'
            op = f.operator
            val = f.value

            if op == "in":
                if isinstance(val, str):
                    clauses.append(f"{col} = '{val}'")
                    continue
                values = list(val) if not isinstance(val, list) else val
                if not values:
                    continue
                placeholders = ", ".join(
                    f"'{v}'" if isinstance(v, str) else str(v) for v in values)
                clauses.append(f"{col} IN ({placeholders})")
            elif op == "eq":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} = {v}")
            elif op == "gte":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} >= {v}")
            elif op == "lte":
                v = f"'{val}'" if isinstance(val, str) else str(val)
                clauses.append(f"{col} <= {v}")
            elif op == "like" and isinstance(val, str):
                clauses.append(f"{col} LIKE '{val}'")
            elif op == "between" and isinstance(val, dict):
                lo = _eval_date_expr(val.get("from"))
                hi = _eval_date_expr(val.get("to"))
                def _q(v):
                    return str(v) if isinstance(v, (int, float)) else f"'{v}'"
                if lo and hi:
                    clauses.append(f"{col} BETWEEN {_q(lo)} AND {_q(hi)}")
                elif lo:
                    clauses.append(f"{col} >= {_q(lo)}")
                elif hi:
                    clauses.append(f"{col} <= {_q(hi)}")
        return clauses

    def distinct_values(self, resolved: Any,
                        extra_filters: list | None = None,
                        resolver: Any = None,
                        max_values: int = 0) -> list:
        limit = max_values if max_values > 0 else self._max_dimension_values
        col = f'"{resolved.table_name}"."{resolved.column}"'
        from_clause = f'{self.scan(str(resolved.silver_path))} AS "{resolved.table_name}"'
        sql = f"SELECT DISTINCT {col} FROM {from_clause} WHERE {col} IS NOT NULL ORDER BY {col}"
        result = self.execute_sql(sql, max_rows=limit)
        return [row[0] for row in result]


class SparkSql(SqlOps):
    """Spark implementation of SqlOps."""

    def __init__(self, spark_session):
        self._spark = spark_session

    def execute_sql(self, sql: str, max_rows: int = 30000) -> list:
        result = self._spark.sql(sql)
        return [list(row) for row in result.limit(max_rows).collect()]

    def scan(self, path: str) -> str:
        return f"delta.`{path}`"

    def build_from(self, tables: dict[str, str], resolver: Any = None,
                   allowed_domains: set[str] | None = None) -> str:
        if not tables:
            raise ValueError("No tables to query")
        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            return f"{self.scan(path)} AS {name}"
        parts = []
        for name, path in tables.items():
            if not parts:
                parts.append(f"{self.scan(path)} AS {name}")
            else:
                parts.append(f"CROSS JOIN {self.scan(path)} AS {name}")
        return " ".join(parts)

    def build_where(self, filters: list, resolver: Any = None,
                    from_tables: set[str] | None = None) -> list[str]:
        return []

    def distinct_values(self, resolved: Any,
                        extra_filters: list | None = None,
                        resolver: Any = None,
                        max_values: int = 10000) -> list:
        path = str(resolved.silver_path)
        df = self._spark.read.format("delta").load(path)
        return [row[0] for row in df.select(resolved.column).distinct().limit(max_values).collect()]
