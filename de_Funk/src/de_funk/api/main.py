"""
de_funk FastAPI application.

Startup sequence:
1. DeFunk.from_config() → loads all configs, creates engine + graph
2. Engine provides handler registry (shared DuckDB connection)
3. FieldResolver provides field resolution for queries
4. Mount routers: /api/health, /api/domains, /api/dimensions, /api/query

Run with:
    python -m scripts.serve.run_api
or:
    uvicorn de_funk.api.main:app --host 0.0.0.0 --port 8765
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from de_funk.api.routers import bronze, dimensions, domains, health, models, predict, query
from de_funk.config.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application using DeFunk."""

    fastapi_app = FastAPI(
        title="de_funk API",
        description="Query backend for the de_funk Obsidian plugin",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS — allow Obsidian app protocol + local subnets
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "app://obsidian.md",
            "capacitor://localhost",
            "http://localhost",
            "http://localhost:8765",
            "http://127.0.0.1:8765",
        ],
        allow_origin_regex=r"http://192\.168\.\d+\.\d+.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    fastapi_app.include_router(health.router, prefix="/api")
    fastapi_app.include_router(domains.router, prefix="/api")
    fastapi_app.include_router(dimensions.router, prefix="/api")
    fastapi_app.include_router(query.router, prefix="/api")
    fastapi_app.include_router(bronze.router, prefix="/api")
    fastapi_app.include_router(predict.router, prefix="/api")
    fastapi_app.include_router(models.router, prefix="/api")

    @fastapi_app.on_event("startup")
    async def startup() -> None:
        from de_funk.app import DeFunk
        from de_funk.api.resolver import FieldResolver
        from de_funk.api.bronze_resolver import BronzeResolver
        from de_funk.utils.repo import get_repo_root

        repo_root = get_repo_root()
        logger.info(f"Starting de_funk API via DeFunk.from_config()")

        # 1. Create the DeFunk application
        defunk = DeFunk.from_config(str(repo_root / "configs"))
        fastapi_app.state.defunk = defunk

        # 2. Build field resolver from domain configs
        storage_config = defunk.config.storage if hasattr(defunk.config, 'storage') else {}
        roots = storage_config.get("roots", {}) if isinstance(storage_config, dict) else {}
        silver_root = roots.get("silver", "storage/silver")
        storage_root = Path(silver_root) if Path(silver_root).is_absolute() else repo_root / silver_root

        # Build domain overrides from storage config
        domain_overrides = {}
        if isinstance(storage_config, dict):
            base = storage_root
            for domain_name, raw_path in storage_config.get("domain_roots", {}).items():
                if domain_name.startswith("_"):
                    continue
                p = Path(raw_path) if Path(raw_path).is_absolute() else base / raw_path
                domain_overrides[domain_name] = p

        fastapi_app.state.resolver = FieldResolver(
            domains_root=repo_root / "domains",
            storage_root=storage_root,
            domain_overrides=domain_overrides,
        )

        # 3. Handler registry — uses Engine directly (no QueryEngine bridge)
        api_cfg = storage_config.get("api", {}) if isinstance(storage_config, dict) else {}
        fastapi_app.state.registry = defunk.engine.get_handler_registry(
            resolver=fastapi_app.state.resolver,
            max_response_mb=float(api_cfg.get("max_response_mb", 4.0)),
            storage_root=storage_root,
        )
        # Dimension endpoint uses Engine directly
        fastapi_app.state.executor = defunk.engine

        # 4. Bronze resolver for /api/bronze endpoints
        bronze_root_raw = roots.get("bronze", "storage/bronze")
        bronze_root = Path(bronze_root_raw) if Path(bronze_root_raw).is_absolute() else repo_root / bronze_root_raw
        fastapi_app.state.bronze_resolver = BronzeResolver(
            data_sources_root=repo_root / "data_sources",
            bronze_root=bronze_root,
        )

        logger.info(
            f"de_funk API ready — {len(defunk.models)} models, "
            f"{len(defunk.providers)} providers, "
            f"silver={storage_root}"
        )

    return fastapi_app


# Module-level app instance for uvicorn
app = create_app()
