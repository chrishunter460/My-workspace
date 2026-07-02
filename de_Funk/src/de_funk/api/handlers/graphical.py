"""GraphicalHandler — executes plotly.* chart queries."""
from __future__ import annotations

import json
from typing import Any

from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.formatting import parse_format_section
from de_funk.api.models.requests import (
    GraphicalQueryRequest,
    GraphicalResponse,
    SeriesData,
)
from de_funk.api.resolver import FieldResolver
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class GraphicalHandler(ExhibitHandler):
    handles = {
        "plotly.line", "line", "line_chart",
        "plotly.bar", "bar", "bar_chart",
        "plotly.scatter", "scatter",
        "plotly.area", "area",
        "plotly.pie", "pie",
        "plotly.heatmap", "heatmap",
    }

    def execute(self, payload: dict[str, Any], resolver: FieldResolver) -> GraphicalResponse:
        req = GraphicalQueryRequest(**payload)
        formatting = payload.get("formatting", {})

        # Pie charts use labels/values — map to x/y for unified handling
        x_field = req.x or req.labels
        y_input = req.y or req.values
        x_resolved = resolver.resolve(x_field) if x_field else None
        y_fields = y_input if isinstance(y_input, list) else ([y_input] if y_input else [])
        y_resolved = [resolver.resolve(f) for f in y_fields]
        group_by_resolved = resolver.resolve(req.group_by) if req.group_by else None

        core_fields = [x_resolved] + y_resolved + ([group_by_resolved] if group_by_resolved else [])
        core_tables, core_domains = self._collect_tables_with_domains(core_fields)
        allowed = resolver.reachable_domains(core_domains)
        filter_tables = self._resolve_filter_tables(req.filters, resolver, allowed_domains=allowed)
        tables = self._collect_tables(core_fields + filter_tables)
        where_clauses = self._build_where(req.filters, resolver)

        select_parts = []
        if x_resolved:
            select_parts.append(f'"{x_resolved.table_name}"."{x_resolved.column}" AS x')
        if group_by_resolved:
            select_parts.append(f'"{group_by_resolved.table_name}"."{group_by_resolved.column}" AS grp')

        # Apply format overrides from formatting section
        fmt_overrides = parse_format_section(formatting.get("format"))

        for i, yr in enumerate(y_resolved):
            agg = (req.aggregation or "AVG").upper()
            col = f'"{yr.table_name}"."{yr.column}"'
            if agg == "COUNT_DISTINCT":
                expr = f"COUNT(DISTINCT {col})"
            else:
                expr = f"{agg}({col})"
            select_parts.append(f"{expr} AS y{i}")

        group_cols = []
        if x_resolved:
            group_cols.append(f'"{x_resolved.table_name}"."{x_resolved.column}"')
        if group_by_resolved:
            group_cols.append(f'"{group_by_resolved.table_name}"."{group_by_resolved.column}"')

        from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        group_clause = f"GROUP BY {', '.join(group_cols)}" if group_cols else ""
        order_clause = self._build_order(req.sort, x_resolved, resolver=resolver, y_resolved=y_resolved)

        limit_clause = f"LIMIT {req.limit}" if req.limit else ""

        sql = f"""
            SELECT {', '.join(select_parts)}
            FROM {from_clause}
            {where_clause}
            {group_clause}
            {order_clause}
            {limit_clause}
        """
        logger.debug(f"Graphical SQL: {sql}")
        rows = self._execute(sql)

        response = self._shape_graphical(rows, group_by_resolved is not None, len(y_resolved))

        # Attach formatting metadata for the frontend renderer
        if formatting:
            response.formatting = formatting

        return response

    def _shape_graphical(self, rows, has_group: bool, y_count: int) -> GraphicalResponse:
        """Shape flat query rows into series format, capped at max_response_mb."""
        max_bytes = int(self.max_response_mb * 1024 * 1024)

        if not has_group:
            series_list = []
            for yi in range(y_count):
                xs = [row[0] for row in rows] if rows else []
                ys = [row[1 + yi] for row in rows] if rows else []
                series_list.append(SeriesData(name=f"Series {yi+1}", x=xs, y=ys))
        else:
            groups: dict[str, tuple[list, list]] = {}
            for row in rows:
                x_val = row[0]
                grp = str(row[1])
                y_val = row[2] if len(row) > 2 else None
                if grp not in groups:
                    groups[grp] = ([], [])
                groups[grp][0].append(x_val)
                groups[grp][1].append(y_val)
            series_list = [
                SeriesData(name=grp, x=xs, y=ys)
                for grp, (xs, ys) in sorted(groups.items())
            ]

        response = GraphicalResponse(series=series_list)
        size = len(json.dumps(response.model_dump(), default=str).encode())
        if size > max_bytes and series_list:
            est_per_point = size / max(1, sum(len(s.x) for s in series_list))
            cap_points = max(10, int(max_bytes / max(1, est_per_point)))
            for s in series_list:
                s.x = s.x[:cap_points]
                s.y = s.y[:cap_points]
            logger.info(f"Graphical series capped to {cap_points} points ({self.max_response_mb}MB cap)")
            response = GraphicalResponse(series=series_list, truncated=True)

        return response
