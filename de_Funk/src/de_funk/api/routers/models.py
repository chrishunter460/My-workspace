"""Model registry endpoint — browse trained ML models."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from de_funk.config.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/models")
async def list_models(request: Request):
    """List all trained model names."""
    defunk = getattr(request.app.state, 'defunk', None)
    if defunk is None or defunk.artifact_store is None:
        raise HTTPException(503, "ArtifactStore not available")

    store = defunk.artifact_store
    models_root = store.models_root

    if not models_root.exists():
        return {"models": []}

    model_names = [d.name for d in models_root.iterdir() if d.is_dir()]
    return {"models": sorted(model_names)}


@router.get("/models/{model_name}")
async def list_versions(request: Request, model_name: str):
    """List all versions of a trained model."""
    defunk = getattr(request.app.state, 'defunk', None)
    if defunk is None or defunk.artifact_store is None:
        raise HTTPException(503, "ArtifactStore not available")

    versions = defunk.artifact_store.list_versions(model_name)
    return {
        "model_name": model_name,
        "versions": [v.to_dict() for v in versions],
        "count": len(versions),
    }


@router.get("/models/{model_name}/{version}")
async def get_model_info(request: Request, model_name: str, version: str):
    """Get metadata and metrics for a specific model version."""
    defunk = getattr(request.app.state, 'defunk', None)
    if defunk is None or defunk.artifact_store is None:
        raise HTTPException(503, "ArtifactStore not available")

    try:
        artifact, _ = defunk.artifact_store.load(model_name, version)
        return artifact.to_dict()
    except FileNotFoundError:
        raise HTTPException(404, f"Model {model_name}/{version} not found")
