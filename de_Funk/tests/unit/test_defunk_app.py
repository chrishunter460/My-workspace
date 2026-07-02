"""Tests for the DeFunk application class and core infrastructure."""
import pytest
from pathlib import Path


class TestDataClasses:
    """Test typed data classes mirror YAML correctly."""

    def test_domain_model_config_defaults(self):
        from de_funk.config.data_classes import DomainModelConfig
        config = DomainModelConfig(model="test.model")
        assert config.model == "test.model"
        assert config.version == "1.0"
        assert config.status == "active"
        assert config.tables == {}
        assert config.sources == {}
        assert config.extends == []
        assert config.depends_on == []

    def test_table_config_fields(self):
        from de_funk.config.data_classes import TableConfig, SchemaField
        field = SchemaField(name="id", type="integer", nullable=False, description="PK")
        table = TableConfig(table="dim_test", table_type="dimension", schema=[field])
        assert table.table == "dim_test"
        assert len(table.schema) == 1
        assert table.schema[0].name == "id"
        assert table.schema[0].nullable is False

    def test_edge_spec(self):
        from de_funk.config.data_classes import EdgeSpec
        edge = EdgeSpec(
            name="prices_to_stock",
            from_table="fact_prices",
            to_table="dim_stock",
            join_keys=["security_id=security_id"],
            cardinality="many_to_one",
        )
        assert edge.from_table == "fact_prices"
        assert edge.join_keys == ["security_id=security_id"]

    def test_hook_def(self):
        from de_funk.config.data_classes import HookDef
        hook = HookDef(fn="plugins.company_cik.fix_ids", params={"ticker_col": "ticker"})
        assert hook.fn == "plugins.company_cik.fix_ids"
        assert hook.params["ticker_col"] == "ticker"

    def test_pipeline_step(self):
        from de_funk.config.data_classes import PipelineStep
        step = PipelineStep(op="filter", params={"conditions": ["active = true"]})
        assert step.op == "filter"
        assert step.fn is None

    def test_hooks_config(self):
        from de_funk.config.data_classes import HooksConfig, HookDef
        hooks = HooksConfig(
            after_build=[HookDef(fn="plugins.test.my_hook")],
        )
        assert len(hooks.after_build) == 1
        assert hooks.pre_build == []

    def test_provider_config(self):
        from de_funk.config.data_classes import ProviderConfig
        provider = ProviderConfig(
            provider_id="alpha_vantage",
            provider="Alpha Vantage",
            base_url="https://api.example.com",
            rate_limit_per_sec=1.0,
        )
        assert provider.provider_id == "alpha_vantage"
        assert provider.rate_limit_per_sec == 1.0

    def test_base_template(self):
        from de_funk.config.data_classes import BaseTemplate, SchemaField
        template = BaseTemplate(
            model="securities",
            canonical_fields=[
                SchemaField(name="ticker", type="string", nullable=False),
            ],
        )
        assert template.type == "domain-base"
        assert len(template.canonical_fields) == 1

    def test_measure_def(self):
        from de_funk.config.data_classes import MeasureDef
        measure = MeasureDef(
            name="avg_close",
            aggregation="avg",
            field="fact_prices.adjusted_close",
            label="Average Close",
            format="$2",
        )
        assert measure.name == "avg_close"
        assert measure.format == "$2"


class TestSessions:
    """Test session abstractions."""

    def test_build_session_creation(self):
        from de_funk.core.sessions import BuildSession
        session = BuildSession(engine=None, models={"test": {"model": "test"}})
        assert len(session.models) == 1

    def test_build_session_get_model(self):
        from de_funk.core.sessions import BuildSession
        models = {"securities.stocks": {"model": "securities.stocks", "depends_on": ["temporal"]}}
        session = BuildSession(engine=None, models=models)
        model = session.get_model("securities.stocks")
        assert model["model"] == "securities.stocks"

    def test_build_session_get_model_not_found(self):
        from de_funk.core.sessions import BuildSession
        session = BuildSession(engine=None, models={})
        with pytest.raises(KeyError, match="not found"):
            session.get_model("nonexistent")

    def test_build_session_get_dependencies(self):
        from de_funk.core.sessions import BuildSession
        models = {"stocks": {"depends_on": ["temporal", "securities"]}}
        session = BuildSession(engine=None, models=models)
        deps = session.get_dependencies("stocks")
        assert deps == ["temporal", "securities"]

    def test_query_session_requires_resolver(self):
        from de_funk.core.sessions import QuerySession
        session = QuerySession(engine=None, models={})
        with pytest.raises(RuntimeError, match="no resolver"):
            session.resolve("test.field")

    def test_ingest_session_creation(self):
        from de_funk.core.sessions import IngestSession
        session = IngestSession(
            engine=None,
            providers={"av": {"provider_id": "av"}},
            endpoints={"av.daily": {"endpoint_id": "daily"}},
        )
        assert len(session.providers) == 1
        assert len(session.endpoints) == 1

    def test_ingest_session_get_provider(self):
        from de_funk.core.sessions import IngestSession
        session = IngestSession(
            engine=None,
            providers={"alpha_vantage": {"provider_id": "alpha_vantage"}},
            endpoints={},
        )
        provider = session.get_provider("alpha_vantage")
        assert provider["provider_id"] == "alpha_vantage"

    def test_session_storage_paths(self):
        from de_funk.core.sessions import BuildSession
        storage = {"roots": {"raw": "/raw", "bronze": "/bronze", "silver": "/silver"}}
        session = BuildSession(engine=None, models={}, storage_config=storage)
        assert session.raw_path("av", "daily") == "/raw/av/daily"
        assert session.bronze_path("av", "daily") == "/bronze/av/daily"
        assert session.silver_path("securities", "stocks") == "/silver/securities/stocks"


class TestHooks:
    """Test hook registry and discovery."""

    def test_hook_registration(self):
        from de_funk.core.hooks import _decorator_registry, _get_decorator_hooks
        fn = lambda df, engine, config, **params: df
        _decorator_registry.setdefault("test_hook", {}).setdefault("test.model", []).append(fn)
        hooks = _get_decorator_hooks("test_hook", "test.model")
        assert fn in hooks
        # Cleanup
        _decorator_registry["test_hook"]["test.model"].remove(fn)

    def test_hook_discovery(self):
        from de_funk.core.hooks import _decorator_registry, _get_decorator_hooks, discover_hooks
        discover_hooks("de_funk.hooks")
        # Check decorator registry has hooks from hooks/ directory
        all_hooks = {ht: {m: len(fns) for m, fns in models.items()}
                     for ht, models in _decorator_registry.items()}
        assert "after_build" in all_hooks
        assert "corporate.entity" in all_hooks["after_build"]
        assert "custom_node_loading" in all_hooks
        assert "temporal" in all_hooks["custom_node_loading"]

    def test_wildcard_hooks(self):
        from de_funk.core.hooks import _decorator_registry, _get_decorator_hooks
        fn = lambda df, engine, config, **params: df
        _decorator_registry.setdefault("wildcard_test", {}).setdefault("*", []).append(fn)
        hooks = _get_decorator_hooks("wildcard_test", "any.model")
        assert fn in hooks
        # Cleanup
        _decorator_registry["wildcard_test"]["*"].remove(fn)


class TestEngine:
    """Test Engine creation and basic operations."""

    def test_engine_for_duckdb(self):
        from de_funk.core.engine import Engine
        engine = Engine.for_duckdb(storage_config={"roots": {"silver": "/test"}})
        assert engine.backend == "duckdb"

    def test_engine_for_spark(self):
        from de_funk.core.engine import Engine
        engine = Engine.for_spark(spark_session=None, storage_config={})
        assert engine.backend == "spark"

    def test_engine_repr(self):
        from de_funk.core.engine import Engine
        engine = Engine.for_duckdb({})
        assert "duckdb" in repr(engine)


class TestDeFunkApp:
    """Test DeFunk application assembly."""

    def test_from_config_loads_models(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        assert len(app.models) > 0

    def test_from_config_loads_providers(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        assert len(app.providers) > 0

    def test_from_config_loads_endpoints(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        assert len(app.endpoints) > 0

    def test_from_config_creates_engine(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        assert app.engine is not None
        assert app.engine.backend == "duckdb"

    def test_build_session_creation(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        session = app.build_session()
        assert len(session.models) == len(app.models)

    def test_ingest_session_creation(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        session = app.ingest_session()
        assert len(session.providers) == len(app.providers)

    def test_query_session_creation(self):
        from de_funk.app import DeFunk
        app = DeFunk.from_config("configs/")
        session = app.query_session()
        assert session.resolver is not None
