"""
ExhibitHandler — abstract base class for all exhibit execution families.

Each handler subclass declares a `handles` set of type strings it owns
and implements `execute()` to process the request and return a response.

Handlers access the Engine directly for all SQL operations.
Planning-layer methods (table collection, filter resolution) are
static utilities with no backend dependency.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from de_funk.api.resolver import ResolvedField
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class ExhibitHandler(ABC):
    """Base class for exhibit handlers.

    Infrastructure is injected by the HandlerRegistry:
        _engine: Engine instance (for SQL operations)
        _resolver: FieldResolver (optional, for field resolution)
        max_response_mb: Response size cap
        storage_root: Silver storage root path
    """

    handles: set[str]

    # Injected by HandlerRegistry
    _engine: Any = None
    max_response_mb: float = 4.0
    storage_root: Any = None
    _max_sql_rows: int = 30000
    _max_dimension_values: int = 10000

    @abstractmethod
    def execute(self, payload: dict[str, Any], resolver: Any) -> Any:
        """Execute the exhibit query and return a response model."""
        ...

    # ── SQL execution ─────────────────────────────────────

    def _execute(self, sql: str, max_rows: int | None = None) -> list:
        """Execute SQL and return rows."""
        limit = max_rows if max_rows is not None else self._max_sql_rows
        return self._engine.execute_sql(sql, max_rows=limit)

    def _safe_scan(self, path: str) -> str:
        """Return a scan expression for a storage path."""
        return self._engine.scan(path)

    def _build_from(self, tables: dict[str, str], resolver=None,
                    allowed_domains: set[str] | None = None) -> str:
        """Build FROM clause with automatic join resolution."""
        return self._engine.build_from(tables, resolver, allowed_domains)

    def _build_where(self, filters, resolver, *, from_tables=None) -> list[str]:
        """Build WHERE clause fragments from filter specs."""
        return self._engine.build_where(filters, resolver, from_tables)

    def distinct_values(self, resolved, extra_filters=None, resolver=None) -> list:
        """Return distinct values for a dimension field."""
        return self._engine.distinct_values(resolved, extra_filters, resolver)

    def distinct_values_by_measure(self, resolved, order_by, order_dir="desc",
                                   extra_filters=None, resolver=None) -> list:
        """Return distinct values ordered by aggregated measure."""
        # This uses raw SQL — delegate to the connection
        dim_col = f'"{resolved.table_name}"."{resolved.column}"'
        measure_col = f'"{order_by.table_name}"."{order_by.column}"'
        dir_sql = "DESC" if order_dir.lower() == "desc" else "ASC"

        extra = self._build_extra_where(extra_filters)
        tables = self._collect_tables(
            [resolved, order_by] + self._extra_filter_fields(extra_filters)
        )

        if len(tables) == 1:
            name, path = next(iter(tables.items()))
            from_clause = f'{self._safe_scan(path)} AS "{name}"'
        else:
            from_clause = self._build_from(tables, resolver)

        sql = f"""
            SELECT {dim_col}, AVG({measure_col}) AS _sort_val
            FROM {from_clause}
            WHERE {dim_col} IS NOT NULL{extra}
            GROUP BY {dim_col}
            ORDER BY _sort_val {dir_sql}
        """
        result = self._execute(sql, max_rows=self._max_dimension_values)
        return [row[0] for row in result]

    # ── SQL builders (no backend dependency) ──────────────

    def _build_order(self, sort, x_resolved, resolver=None,
                     y_resolved: list | None = None) -> str:
        """Build ORDER BY clause from sort spec or default to x axis.

        When sorting by a measure that appears in y_resolved, use the
        aggregate alias (y0, y1, ...) instead of the raw column — the raw
        column isn't valid in a grouped query's ORDER BY.
        """
        if sort:
            direction = sort.order.upper() if sort.order else "ASC"
            if sort.by:
                # Resolve domain-qualified field names
                if resolver and "." in sort.by:
                    try:
                        resolved = resolver.resolve(sort.by)
                        # Check if sort field matches a y-axis measure → use alias
                        if y_resolved:
                            for i, yr in enumerate(y_resolved):
                                if yr.table_name == resolved.table_name and yr.column == resolved.column:
                                    return f"ORDER BY y{i} {direction}"
                        return f'ORDER BY "{resolved.table_name}"."{resolved.column}" {direction}'
                    except (ValueError, AttributeError):
                        pass
                return f"ORDER BY {sort.by} {direction}"
        if x_resolved:
            return f'ORDER BY "{x_resolved.table_name}"."{x_resolved.column}" ASC'
        return ""

    @staticmethod
    def _build_extra_where(extra_filters: list[tuple[ResolvedField | str, Any]] | None) -> str:
        """Build AND-joined WHERE fragments from context filter pairs."""
        if not extra_filters:
            return ""
        parts: list[str] = []
        for field_or_col, val in extra_filters:
            if isinstance(field_or_col, ResolvedField):
                col_ref = f'"{field_or_col.table_name}"."{field_or_col.column}"'
            else:
                col_ref = f'"{field_or_col}"'
            if isinstance(val, list):
                if not val:
                    continue
                placeholders = ", ".join(
                    f"'{v}'" if isinstance(v, str) else str(v) for v in val
                )
                parts.append(f'{col_ref} IN ({placeholders})')
            else:
                quoted = f"'{val}'" if isinstance(val, str) else str(val)
                parts.append(f'{col_ref} = {quoted}')
        return (" AND " + " AND ".join(parts)) if parts else ""

    # ── Planning layer (static, backend-agnostic) ─────────

    @staticmethod
    def _collect_tables(resolved_fields: list[ResolvedField | None]) -> dict[str, str]:
        """Collect unique table_name → Silver path mappings from resolved fields."""
        tables: dict[str, str] = {}
        for r in resolved_fields:
            if r is None:
                continue
            tables[r.table_name] = str(r.silver_path)
        return tables

    @staticmethod
    def _collect_tables_with_domains(
        resolved_fields: list[ResolvedField | None],
    ) -> tuple[dict[str, str], set[str]]:
        """Collect tables AND their canonical domains from resolved fields."""
        tables: dict[str, str] = {}
        domains: set[str] = set()
        for r in resolved_fields:
            if r is None:
                continue
            tables[r.table_name] = str(r.silver_path)
            domains.add(r.domain)
        return tables, domains

    @staticmethod
    def _resolve_filter_tables(
        filters,
        resolver: Any,
        *,
        allowed_domains: set[str] | None = None,
        **_kw,
    ) -> list[ResolvedField]:
        """Resolve filter fields so their tables enter the FROM clause."""
        resolved = []
        for f in (filters or []):
            try:
                r = resolver.resolve(f.field)
            except ValueError:
                continue
            if allowed_domains is not None and r.domain not in allowed_domains:
                logger.info(
                    f"Skipping out-of-scope filter '{f.field}' — "
                    f"domain '{r.domain}' not in {allowed_domains}"
                )
                continue
            resolved.append(r)
        return resolved

    @staticmethod
    def _extra_filter_fields(
        extra_filters: list[tuple[ResolvedField | str, Any]] | None,
    ) -> list[ResolvedField]:
        """Extract ResolvedField objects from extra_filters for table collection."""
        if not extra_filters:
            return []
        return [f for f, _ in extra_filters if isinstance(f, ResolvedField)]

    # ── FROM tables tracking ──────────────────────────────

    @property
    def _from_tables(self):
        """Tables included in the most recent FROM clause."""
        if self._engine and hasattr(self._engine, '_sql') and hasattr(self._engine._sql, '_from_tables'):
            return self._engine._sql._from_tables
        return set()
