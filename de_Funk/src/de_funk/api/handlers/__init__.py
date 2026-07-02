"""
Handler registry — discovers handlers and maps type strings to instances.

Usage:
    registry = build_registry(engine)
    handler = registry.get("plotly.line")
    result = handler.execute(payload, resolver)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from de_funk.api.handlers.base import ExhibitHandler
from de_funk.api.handlers.graphical import GraphicalHandler
from de_funk.api.handlers.box import BoxHandler
from de_funk.api.handlers.table_data import TableDataHandler
from de_funk.api.handlers.pivot import PivotHandler
from de_funk.api.handlers.metrics import MetricsHandler

_HANDLER_CLASSES: list[type[ExhibitHandler]] = [
    GraphicalHandler,
    BoxHandler,
    TableDataHandler,
    PivotHandler,
    MetricsHandler,
]


class HandlerRegistry:
    """Maps block type strings to handler instances."""

    def __init__(self) -> None:
        self._handlers: dict[str, ExhibitHandler] = {}

    def register(self, handler: ExhibitHandler) -> None:
        for type_str in handler.handles:
            self._handlers[type_str] = handler

    def get(self, type_str: str) -> ExhibitHandler | None:
        return self._handlers.get(type_str)

    @property
    def supported_types(self) -> set[str]:
        return set(self._handlers.keys())


def build_registry(
    storage_root: Path | None = None,
    memory_limit: str = "3GB",
    max_sql_rows: int = 30000,
    max_dimension_values: int = 10000,
    max_response_mb: float = 4.0,
    engine=None,
) -> HandlerRegistry:
    """Build the handler registry with a shared Engine.

    Creates or uses an Engine with DuckDB backend, then injects it
    into each handler. All handlers share one DuckDB connection.

    Args:
        storage_root: Silver storage root (used for legacy QueryEngine path)
        memory_limit: DuckDB memory limit
        max_sql_rows: Max rows per query
        max_dimension_values: Max dimension values
        max_response_mb: Max response size in MB
        engine: Optional pre-built Engine instance
    """
    registry = HandlerRegistry()

    if engine is not None:
        # New path: use provided Engine directly
        for cls in _HANDLER_CLASSES:
            handler = cls.__new__(cls)
            handler._engine = engine
            handler.max_response_mb = max_response_mb
            handler.storage_root = storage_root
            handler._max_sql_rows = max_sql_rows
            handler._max_dimension_values = max_dimension_values
            registry.register(handler)
        return registry

    # Create Engine from params
    from de_funk.core.engine import Engine
    eng = Engine.for_duckdb(
        memory_limit=memory_limit,
        max_sql_rows=max_sql_rows,
        max_dimension_values=max_dimension_values,
    )

    for cls in _HANDLER_CLASSES:
        handler = cls.__new__(cls)
        handler._engine = eng
        handler.max_response_mb = max_response_mb
        handler.storage_root = storage_root
        handler._max_sql_rows = max_sql_rows
        handler._max_dimension_values = max_dimension_values
        registry.register(handler)

    # Store shared engine on registry for dimension endpoint
    registry.shared_engine = eng

    return registry
