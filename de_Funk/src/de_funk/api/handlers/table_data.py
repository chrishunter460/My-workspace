"""TableDataHandler — executes flat table.data queries."""
from __future__ import annotations

from typing import Any

from de_funk.api.executor import truncate_to_mb
from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.formatting import parse_format_section, resolve_format
from de_funk.api.models.requests import (
    TableColumn,
    TableDataQueryRequest,
    TableResponse,
)
from de_funk.api.resolver import FieldResolver
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class TableDataHandler(ExhibitHandler):
    handles = {"table.data", "data_table"}

    def execute(self, payload: dict[str, Any], resolver: FieldResolver) -> TableResponse:
        req = TableDataQueryRequest(**payload)
        formatting = payload.get("formatting", {})
        fmt_overrides = parse_format_section(formatting.get("format"))

        resolved_cols = [(col, resolver.resolve(col.field)) for col in req.columns]
        core_fields = [r for _, r in resolved_cols]
        core_tables, core_domains = self._collect_tables_with_domains(core_fields)
        allowed = resolver.reachable_domains(core_domains)
        filter_tables = self._resolve_filter_tables(req.filters, resolver, allowed_domains=allowed)
        tables = self._collect_tables(core_fields + filter_tables)
        from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
        where_clauses = self._build_where(req.filters, resolver)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        select_parts = []
        for col, r in resolved_cols:
            if col.aggregation:
                agg = col.aggregation.upper()
                if agg == "COUNT_DISTINCT":
                    expr = f'COUNT(DISTINCT "{r.table_name}"."{r.column}")'
                else:
                    expr = f'{agg}("{r.table_name}"."{r.column}")'
            else:
                expr = f'"{r.table_name}"."{r.column}"'
            select_parts.append(f"{expr} AS {col.key}")

        order_col = None
        if req.sort_by:
            sort_resolved = resolver.resolve(req.sort_by)
            order_col = f'"{sort_resolved.table_name}"."{sort_resolved.column}" {req.sort_order.upper()}'

        order_clause = f"ORDER BY {order_col}" if order_col else ""
        sql = f"SELECT {', '.join(select_parts)} FROM {from_clause} {where_clause} {order_clause}"
        logger.debug(f"Table SQL: {sql}")
        rows = self._execute(sql)

        columns = [
            TableColumn(
                key=col.key,
                label=col.label or col.key.replace("_", " ").title(),
                format=resolve_format(col.key, col.format or r.format_code, fmt_overrides),
            )
            for col, r in resolved_cols
        ]
        row_list = [list(row) for row in rows]
        row_list, truncated = truncate_to_mb(row_list, columns, self.max_response_mb)
        if truncated:
            logger.info(f"Table response truncated to {len(row_list)} rows ({self.max_response_mb}MB cap)")
        return TableResponse(
            columns=columns,
            rows=row_list,
            truncated=truncated,
            formatting=formatting if formatting else None,
        )
