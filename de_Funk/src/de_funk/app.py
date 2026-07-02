"""
DeFunk — Top-level application class.

Assembles everything from config files into a ready-to-use application.
Follows the Flask/SQLAlchemy pattern: one object that wires everything together.

Usage:
    app = DeFunk.from_config("configs/")

    # Build Silver tables
    session = app.build_session()
    session.build("securities.stocks")

    # Query Silver tables
    session = app.query_session()
    result = session.resolve("securities.stocks.adjusted_close")

    # Ingest Bronze data
    session = app.ingest_session()
    session.ingest("alpha_vantage", work_items=["AAPL", "MSFT"])
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from de_funk.config.logging import setup_logging, get_logger

logger = get_logger(__name__)


class DeFunk:
    """Top-level application object. Assembles everything from config.

    Holds:
        config: AppConfig (infrastructure settings)
        engine: Engine (connection + backend-agnostic ops)
        graph: DomainGraph (queryable join graph)
        models: dict of DomainModelConfig (loaded domain configs)
        providers: dict of ProviderConfig
        endpoints: dict of EndpointConfig

    Creates:
        build_session() → BuildSession
        query_session() → QuerySession
        ingest_session() → IngestSession
    """

    def __init__(
        self,
        config,          # AppConfig
        engine,          # Engine
        graph,           # DomainGraph
        models: dict,    # dict[str, DomainModelConfig]
        providers: dict, # dict[str, ProviderConfig]
        endpoints: dict, # dict[str, EndpointConfig]
        artifact_store=None,  # ArtifactStore
    ):
        self.config = config
        self.engine = engine
        self.graph = graph
        self.models = models
        self.providers = providers
        self.endpoints = endpoints
        self.artifact_store = artifact_store

    @staticmethod
    def from_config(
        config_path: str | Path = "configs/",
        connection_type: str = "duckdb",
        log_level: str = "INFO",
    ) -> DeFunk:
        """Create a fully wired DeFunk app from config files.

        Steps:
            1. ConfigLoader → AppConfig
            2. DomainConfigLoader → models
            3. DomainGraph from EdgeSpecs
            4. Engine from ConnectionConfig
            5. Load providers/endpoints from Data Sources/
        """
        from de_funk.config.loader import ConfigLoader

        setup_logging()
        repo_root = Path(config_path).resolve().parent if Path(config_path).name == "configs" else Path(config_path).resolve()

        # 1. Load infrastructure config
        loader = ConfigLoader(repo_root=repo_root)
        app_config = loader.load(connection_type=connection_type)

        return DeFunk.from_app_config(app_config)

    @staticmethod
    def from_app_config(config) -> DeFunk:
        """Create DeFunk from an already-loaded AppConfig."""
        # 2. Load domain model configs
        models = _load_domain_models(config)

        # 3. Build domain graph from EdgeSpecs
        graph = _build_domain_graph(models)

        # 4. Create engine
        engine = _create_engine(config)

        # 5. Load provider/endpoint configs
        providers, endpoints = _load_provider_configs(config)

        # 6. Create ArtifactStore for ML model management
        artifact_store = _create_artifact_store(config)

        logger.info(
            f"DeFunk ready: {len(models)} models, "
            f"{len(providers)} providers, "
            f"{len(endpoints)} endpoints, "
            f"backend={engine.backend}"
        )

        return DeFunk(
            config=config,
            engine=engine,
            graph=graph,
            models=models,
            providers=providers,
            endpoints=endpoints,
            artifact_store=artifact_store,
        )

    def build_session(self, **kwargs):
        """Create a BuildSession for building Silver tables."""
        # Lazy import to avoid circular deps during startup
        from de_funk.core.sessions import BuildSession
        return BuildSession(
            engine=self.engine,
            models=self.models,
            graph=self.graph,
            storage_config=self.config.storage,
            **kwargs,
        )

    def query_session(self, **kwargs):
        """Create a QuerySession for interactive queries."""
        from de_funk.core.sessions import QuerySession
        from de_funk.api.resolver import FieldResolver

        # Build resolver from models (indexes fields + join graph)
        resolver = FieldResolver(
            domains_root=self.config.models_dir,
            storage_root=Path(self.config.storage.get("roots", {}).get("silver", "storage/silver")),
            domain_overrides=_build_domain_overrides(self.config),
        )

        return QuerySession(
            engine=self.engine,
            models=self.models,
            resolver=resolver,
            storage_config=self.config.storage,
            **kwargs,
        )

    def ingest_session(self, **kwargs):
        """Create an IngestSession for data ingestion."""
        from de_funk.core.sessions import IngestSession
        return IngestSession(
            engine=self.engine,
            providers=self.providers,
            endpoints=self.endpoints,
            run_config=getattr(self.config, 'run', {}),
            storage_config=self.config.storage,
            **kwargs,
        )


# ── Private helpers ──────────────────────────────────────

def _load_domain_models(config) -> dict:
    """Load all domain model configs from markdown."""
    try:
        from de_funk.config.domain import get_domain_loader
        domains_dir = getattr(config, 'models_dir', None)
        if domains_dir is None:
            domains_dir = Path(config.repo_root) / "domains"
        loader = get_domain_loader(domains_dir)

        # Discover all models
        models = {}
        models_root = domains_dir / "models"
        if models_root.exists():
            for model_file in models_root.rglob("model.md"):
                from de_funk.config.domain.extends import parse_front_matter
                fm = parse_front_matter(model_file)
                if fm.get("type") == "domain-model" and fm.get("model"):
                    model_name = fm["model"]
                    try:
                        config_dict = loader.load_model_config(model_name)
                        from de_funk.config.data_classes import DomainModelConfig
                        models[model_name] = DomainModelConfig.from_dict(config_dict)
                    except Exception as e:
                        logger.warning(f"Failed to load model {model_name}: {e}")

        logger.info(f"Loaded {len(models)} domain models")
        return models
    except Exception as e:
        logger.warning(f"Could not load domain models: {e}")
        return {}


def _build_domain_graph(models: dict):
    """Build DomainGraph from all EdgeSpecs across models."""
    from de_funk.core.graph import DomainGraph
    graph = DomainGraph(models)
    return graph


def _create_engine(config):
    """Create Engine from AppConfig."""
    from de_funk.core.engine import Engine

    storage = config.storage if hasattr(config, 'storage') else {}
    conn_type = getattr(config.connection, 'type', 'duckdb') if hasattr(config, 'connection') else 'duckdb'

    # Extract API limits from storage config
    api_cfg = storage.get("api", {}) if isinstance(storage, dict) else {}
    memory_limit = api_cfg.get("duckdb_memory_limit", "3GB")
    max_sql_rows = api_cfg.get("max_sql_rows", 30000)
    max_dimension_values = api_cfg.get("max_dimension_values", 10000)

    if conn_type == 'spark':
        from de_funk.orchestration.common.spark_session import get_spark
        spark = get_spark("DeFunk")
        return Engine.for_spark(spark, storage_config=storage)
    else:
        return Engine.for_duckdb(storage_config=storage, memory_limit=memory_limit,
                                 max_sql_rows=max_sql_rows, max_dimension_values=max_dimension_values)


def _load_provider_configs(config) -> tuple[dict, dict]:
    """Load provider and endpoint configs from Data Sources markdown."""
    providers = {}
    endpoints = {}

    try:
        data_sources_dir = Path(config.repo_root) / "domains" / "Data Sources"
        if not data_sources_dir.exists():
            # Try alternate location
            data_sources_dir = Path(config.repo_root) / "data_sources"

        if data_sources_dir.exists():
            from de_funk.config.domain.extends import parse_front_matter

            # Load providers
            providers_dir = data_sources_dir / "Providers"
            if providers_dir.exists():
                for f in providers_dir.glob("*.md"):
                    fm = parse_front_matter(f)
                    if fm.get("type") == "api-provider" and fm.get("provider_id"):
                        providers[fm["provider_id"]] = fm

            # Load endpoints
            endpoints_dir = data_sources_dir / "Endpoints"
            if endpoints_dir.exists():
                for f in endpoints_dir.rglob("*.md"):
                    fm = parse_front_matter(f)
                    if fm.get("type") == "api-endpoint" and fm.get("endpoint_id"):
                        provider = fm.get("provider", "").lower().replace(" ", "_")
                        key = f"{provider}.{fm['endpoint_id']}"
                        endpoints[key] = fm

        logger.info(f"Loaded {len(providers)} providers, {len(endpoints)} endpoints")
    except Exception as e:
        logger.warning(f"Could not load provider configs: {e}")

    return providers, endpoints


def _create_artifact_store(config):
    """Create ArtifactStore for ML model lifecycle management."""
    from de_funk.core.artifacts import ArtifactStore

    storage = config.storage if hasattr(config, 'storage') else {}
    roots = storage.get("roots", {}) if isinstance(storage, dict) else {}
    models_root = roots.get("models", "storage/models")

    return ArtifactStore(models_root=models_root)


def _build_domain_overrides(config) -> dict:
    """Build domain path overrides from storage config."""
    storage = config.storage if hasattr(config, 'storage') else {}
    if isinstance(storage, dict):
        return {k: Path(v) for k, v in storage.get("domain_roots", {}).items()}
    return {}
