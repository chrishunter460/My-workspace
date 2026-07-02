"""MetricsHandler — executes cards.metric / KPI queries."""
from __future__ import annotations

from typing import Any

from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.formatting import parse_format_section, resolve_format
from de_funk.api.measures import build_measure_sql
from de_funk.api.models.requests import (
    MetricQueryRequest,
    MetricResponse,
    MetricValue,
)
from de_funk.api.resolver import FieldResolver
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


class MetricsHandler(ExhibitHandler):
    handles = {"cards.metric", "kpi", "metric_cards"}

    def execute(self, payload: dict[str, Any], resolver: FieldResolver) -> MetricResponse:
        req = MetricQueryRequest(**payload)
        formatting = payload.get("formatting", {})
        fmt_overrides = parse_format_section(formatting.get("format"))

        prior_keys: dict[str, str] = {}
        select_parts = []
        metric_meta = []

        for m in req.metrics:
            expr = build_measure_sql(m, resolver, prior_keys)
            prior_keys[m.key] = expr
            select_parts.append(f"{expr} AS {m.key}")
            resolved_f = resolver.resolve(m.field) if isinstance(m.field, str) else None
            metric_meta.append((m, resolved_f))

        metric_tables = [
            resolver.resolve(m.field) for m in req.metrics
            if isinstance(m.field, str)
        ]
        core_tables, core_domains = self._collect_tables_with_domains(metric_tables)
        allowed = resolver.reachable_domains(core_domains)
        filter_tables = self._resolve_filter_tables(req.filters, resolver, allowed_domains=allowed)
        tables = self._collect_tables(metric_tables + filter_tables)
        from_clause = self._build_from(tables, resolver, allowed_domains=allowed)
        where_clauses = self._build_where(req.filters, resolver)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"SELECT {', '.join(select_parts)} FROM {from_clause} {where_clause}"
        logger.debug(f"Metrics SQL: {sql}")
        rows = self._execute(sql, max_rows=1)
        row = rows[0] if rows else None

        metrics = []
        for i, (m, resolved_f) in enumerate(metric_meta):
            value = row[i] if row else None
            base_fmt = m.format or (resolved_f.format_code if resolved_f else None)
            fmt = resolve_format(m.key, base_fmt, fmt_overrides)
            label = m.label or m.key.replace("_", " ").title()
            metrics.append(MetricValue(key=m.key, label=label, value=value, format=fmt))

        return MetricResponse(metrics=metrics)
