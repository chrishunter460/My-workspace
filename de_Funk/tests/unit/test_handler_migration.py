"""Tests for Handler Migration — handlers use Engine directly, no QueryEngine."""
import pytest


class TestHandlerUsesEngine:
    def test_handler_engine_attribute(self):
        from de_funk.api.handlers.base import ExhibitHandler
        assert hasattr(ExhibitHandler, '_engine')

    def test_build_registry_sets_engine(self):
        from de_funk.api.handlers import build_registry
        from de_funk.core.engine import Engine

        engine = Engine.for_duckdb(memory_limit="256MB")
        registry = build_registry(engine=engine, max_sql_rows=100,
                                  max_dimension_values=50, max_response_mb=1.0)
        handler = registry.get("line")
        assert handler is not None
        assert handler._engine is engine

    def test_no_query_engine_class(self):
        """QueryEngine class has been removed from executor.py."""
        import de_funk.api.executor as executor_module
        assert not hasattr(executor_module, 'QueryEngine')

    def test_no_query_engine_in_handler_mro(self):
        """No handler should have QueryEngine in its MRO."""
        from de_funk.api.handlers import _HANDLER_CLASSES
        for cls in _HANDLER_CLASSES:
            for base in cls.__mro__:
                assert base.__name__ != 'QueryEngine', f"{cls.__name__} still has QueryEngine"

    def test_all_handlers_have_engine(self):
        from de_funk.api.handlers import build_registry
        from de_funk.core.engine import Engine

        engine = Engine.for_duckdb(memory_limit="256MB")
        registry = build_registry(engine=engine)
        for type_str in ["line", "bar", "pivot", "gt", "box", "table.data", "cards.metric"]:
            handler = registry.get(type_str)
            assert handler is not None, f"No handler for {type_str}"
            assert handler._engine is engine, f"{type_str} handler missing _engine"
