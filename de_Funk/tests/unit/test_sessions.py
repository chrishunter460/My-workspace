"""Tests for Sessions — Phase 5."""
import pytest
from de_funk.core.sessions import Session, BuildSession, QuerySession, IngestSession
from de_funk.core.storage import StorageRouter


@pytest.fixture
def engine():
    from de_funk.core.engine import Engine
    return Engine.for_duckdb(
        storage_config={
            "roots": {"raw": "/raw", "bronze": "/bronze", "silver": "/silver", "models": "/models"},
            "domain_roots": {},
        },
        memory_limit="256MB",
    )


@pytest.fixture
def storage_config():
    return {
        "roots": {"raw": "/raw", "bronze": "/bronze", "silver": "/silver", "models": "/models"},
        "domain_roots": {"securities.stocks": "stocks"},
    }


@pytest.fixture
def models():
    return {
        "temporal": {"model": "temporal", "depends_on": []},
        "corporate.entity": {"model": "corporate.entity", "depends_on": ["temporal"]},
        "securities.stocks": {"model": "securities.stocks", "depends_on": ["temporal", "corporate.entity"]},
    }


class TestSessionBase:
    def test_composes_storage_router(self, engine, storage_config):
        session = BuildSession(engine=engine, models={}, storage_config=storage_config)
        assert isinstance(session.storage_router, StorageRouter)

    def test_raw_path_delegates(self, engine, storage_config):
        session = BuildSession(engine=engine, models={}, storage_config=storage_config)
        assert session.raw_path("alpha", "daily") == "/raw/alpha/daily"

    def test_bronze_path_delegates(self, engine, storage_config):
        session = BuildSession(engine=engine, models={}, storage_config=storage_config)
        assert session.bronze_path("alpha", "daily") == "/bronze/alpha/daily"

    def test_silver_path_delegates(self, engine, storage_config):
        session = BuildSession(engine=engine, models={}, storage_config=storage_config)
        assert session.silver_path("securities.stocks") == "/silver/stocks"

    def test_model_path(self, engine, storage_config):
        session = BuildSession(engine=engine, models={}, storage_config=storage_config)
        assert session.model_path("arima", "v1") == "/models/arima/v1"


class TestBuildSession:
    def test_get_model(self, engine, models, storage_config):
        session = BuildSession(engine=engine, models=models, storage_config=storage_config)
        model = session.get_model("temporal")
        assert model["model"] == "temporal"

    def test_get_model_not_found(self, engine, models, storage_config):
        session = BuildSession(engine=engine, models=models, storage_config=storage_config)
        with pytest.raises(KeyError):
            session.get_model("nonexistent")

    def test_get_dependencies(self, engine, models, storage_config):
        session = BuildSession(engine=engine, models=models, storage_config=storage_config)
        deps = session.get_dependencies("securities.stocks")
        assert "temporal" in deps
        assert "corporate.entity" in deps

    def test_topological_sort(self, engine, models, storage_config):
        session = BuildSession(engine=engine, models=models, storage_config=storage_config)
        order = session._topological_sort()
        # temporal must come before corporate.entity and securities.stocks
        assert order.index("temporal") < order.index("corporate.entity")
        assert order.index("temporal") < order.index("securities.stocks")
        assert order.index("corporate.entity") < order.index("securities.stocks")


class TestQuerySession:
    def test_resolve_without_resolver_raises(self, engine, models, storage_config):
        session = QuerySession(engine=engine, models=models, storage_config=storage_config)
        with pytest.raises(RuntimeError):
            session.resolve("securities.stocks.close")

    def test_find_join_path_without_resolver(self, engine, models, storage_config):
        session = QuerySession(engine=engine, models=models, storage_config=storage_config)
        assert session.find_join_path("a", "b") == []


class TestIngestSession:
    def test_get_provider(self, engine, storage_config):
        session = IngestSession(
            engine=engine,
            providers={"alpha_vantage": {"id": "av"}},
            endpoints={},
            storage_config=storage_config,
        )
        assert session.get_provider("alpha_vantage")["id"] == "av"

    def test_get_provider_not_found(self, engine, storage_config):
        session = IngestSession(engine=engine, providers={}, endpoints={}, storage_config=storage_config)
        with pytest.raises(KeyError):
            session.get_provider("nonexistent")

    def test_get_endpoint(self, engine, storage_config):
        session = IngestSession(
            engine=engine, providers={},
            endpoints={"av.daily": {"id": "daily"}},
            storage_config=storage_config,
        )
        assert session.get_endpoint("av", "daily")["id"] == "daily"
