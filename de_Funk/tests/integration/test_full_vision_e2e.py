"""
End-to-end integration tests for full vision architecture.

Tests the complete chain: DeFunk → Session → Engine → Handler → Response.
Requires real config files and Silver data in storage.
"""
import pytest
from pathlib import Path


@pytest.fixture(scope="module")
def defunk():
    """Create a DeFunk app from real configs."""
    from de_funk.app import DeFunk
    return DeFunk.from_config("configs/")


@pytest.fixture(scope="module")
def resolver(defunk):
    """Create a FieldResolver from real domain configs."""
    from de_funk.api.resolver import FieldResolver
    storage = defunk.config.storage if hasattr(defunk.config, 'storage') else {}
    roots = storage.get("roots", {}) if isinstance(storage, dict) else {}
    silver_root = roots.get("silver", "storage/silver")
    base = Path(silver_root)

    domain_overrides = {}
    if isinstance(storage, dict):
        for domain_name, raw_path in storage.get("domain_roots", {}).items():
            if domain_name.startswith("_"):
                continue
            p = Path(raw_path) if Path(raw_path).is_absolute() else base / raw_path
            domain_overrides[domain_name] = p

    return FieldResolver(
        domains_root=defunk.config.models_dir,
        storage_root=base,
        domain_overrides=domain_overrides,
    )


class TestDeFunkAssembly:
    def test_models_loaded(self, defunk):
        assert len(defunk.models) > 0

    def test_providers_loaded(self, defunk):
        assert len(defunk.providers) > 0

    def test_endpoints_loaded(self, defunk):
        assert len(defunk.endpoints) > 0

    def test_graph_has_tables(self, defunk):
        assert len(defunk.graph.all_tables()) > 0

    def test_graph_has_edges(self, defunk):
        assert len(defunk.graph.all_edges()) > 0

    def test_engine_is_duckdb(self, defunk):
        assert defunk.engine.backend == "duckdb"

    def test_engine_has_ops(self, defunk):
        from de_funk.core.ops import DuckDBOps
        from de_funk.core.sql import DuckDBSql
        assert isinstance(defunk.engine._ops, DuckDBOps)
        assert isinstance(defunk.engine._sql, DuckDBSql)


class TestSessionCreation:
    def test_build_session(self, defunk):
        session = defunk.build_session()
        assert session.engine is defunk.engine
        assert len(session.models) > 0
        assert session.graph is defunk.graph

    def test_query_session(self, defunk):
        session = defunk.query_session()
        assert session.engine is defunk.engine
        assert session.resolver is not None

    def test_ingest_session(self, defunk):
        session = defunk.ingest_session()
        assert session.engine is defunk.engine
        assert len(session.providers) > 0


class TestHandlerRegistry:
    def test_registry_from_engine(self, defunk, resolver):
        registry = defunk.engine.get_handler_registry(resolver=resolver)
        assert registry is not None
        handler = registry.get("line")
        assert handler is not None
        assert handler._engine is not None

    def test_all_exhibit_types_registered(self, defunk, resolver):
        registry = defunk.engine.get_handler_registry(resolver=resolver)
        for type_str in ["line", "bar", "pivot", "gt", "box", "table.data", "cards.metric"]:
            handler = registry.get(type_str)
            assert handler is not None, f"Handler for {type_str} not registered"


class TestNoDirectImports:
    def test_no_duckdb_in_handlers(self):
        """Handlers should not import duckdb directly."""
        import importlib
        handler_modules = [
            "de_funk.api.handlers.graphical",
            "de_funk.api.handlers.pivot",
            "de_funk.api.handlers.metrics",
            "de_funk.api.handlers.box",
            "de_funk.api.handlers.table_data",
        ]
        for mod_name in handler_modules:
            mod = importlib.import_module(mod_name)
            source_file = mod.__file__
            with open(source_file) as f:
                source = f.read()
            assert "import duckdb" not in source, f"{mod_name} imports duckdb directly"

    def test_query_engine_removed(self):
        """QueryEngine class has been removed from codebase."""
        import de_funk.api.executor as executor_module
        assert not hasattr(executor_module, 'QueryEngine')


class TestFieldResolution:
    def test_resolver_resolves_field(self, resolver):
        resolved = resolver.resolve("securities.stocks.close")
        assert resolved is not None
        assert resolved.table_name == "fact_stock_prices"

    def test_graph_join_path(self, defunk):
        path = defunk.graph.find_join_path("dim_stock", "fact_stock_prices")
        assert path is not None


class TestStorageRouter:
    def test_session_has_storage_router(self, defunk):
        from de_funk.core.storage import StorageRouter
        session = defunk.build_session()
        assert isinstance(session.storage_router, StorageRouter)

    def test_silver_path_resolution(self, defunk):
        session = defunk.build_session()
        path = session.silver_path("temporal")
        assert "temporal" in path
