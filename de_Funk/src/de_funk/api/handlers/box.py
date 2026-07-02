"""BoxHandler — executes box plot and OHLCV candlestick queries."""
from __future__ import annotations

from typing import Any

from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.models.requests import BoxQueryRequest
from de_funk.api.resolver import FieldResolver


class BoxHandler(ExhibitHandler):
    handles = {"plotly.box", "box", "ohlcv", "candlestick"}

    def execute(self, payload: dict[str, Any], resolver: FieldResolver) -> dict:
        req = BoxQueryRequest(**payload)
        formatting = payload.get("formatting", {})
        cat_resolved = resolver.resolve(req.category)
        group_resolved = resolver.resolve(req.group_by) if req.group_by else None
        ohlcv_mode = all([req.open, req.high, req.low, req.close])

        if ohlcv_mode:
            fields = {
                "category": cat_resolved,
                "open": resolver.resolve(req.open),
                "high": resolver.resolve(req.high),
                "low": resolver.resolve(req.low),
                "close": resolver.resolve(req.close),
            }
        else:
            fields = {
                "category": cat_resolved,
                "y": resolver.resolve(req.y),
            }

        core_fields = list(fields.values())
        if group_resolved:
            core_fields.append(group_resolved)
        core_tables, core_domains = self._collect_tables_with_domains(core_fields)
        allowed = resolver.reachable_domains(core_domains)
        filter_tables = self._resolve_filter_tables(req.filters, resolver, allowed_domains=allowed)
        tables = self._collect_tables(core_fields + filter_tables)
        from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
        where_clauses = self._build_where(req.filters, resolver)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        grp_col = ""
        if group_resolved:
            grp_col = f', "{group_resolved.table_name}"."{group_resolved.column}" AS grp'

        if ohlcv_mode:
            sql = f"""
                SELECT
                    "{cat_resolved.table_name}"."{cat_resolved.column}" AS category,
                    "{fields['open'].table_name}"."{fields['open'].column}" AS open,
                    "{fields['high'].table_name}"."{fields['high'].column}" AS high,
                    "{fields['low'].table_name}"."{fields['low'].column}" AS low,
                    "{fields['close'].table_name}"."{fields['close'].column}" AS close
                    {grp_col}
                FROM {from_clause}
                {where_clause}
            """
        else:
            yr = fields["y"]
            sql = f"""
                SELECT
                    "{cat_resolved.table_name}"."{cat_resolved.column}" AS category,
                    "{yr.table_name}"."{yr.column}" AS y
                    {grp_col}
                FROM {from_clause}
                {where_clause}
            """

        rows = self._execute(sql)
        result = {
            "series": rows,
            "mode": "ohlcv" if ohlcv_mode else "box",
            "grouped": group_resolved is not None,
        }
        if formatting:
            result["formatting"] = formatting
        return result
