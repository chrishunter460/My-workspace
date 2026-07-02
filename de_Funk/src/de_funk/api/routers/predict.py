"""Model prediction endpoint — serve inference from trained artifacts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from de_funk.config.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/predict/{model_name}")
async def predict(request: Request, model_name: str, horizon: int = 7):
    """Run inference using a trained model from ArtifactStore.

    Args:
        model_name: Name of the trained model (e.g. "stock_predictor")
        horizon: Forecast horizon in days
    """
    defunk = getattr(request.app.state, 'defunk', None)
    if defunk is None or defunk.artifact_store is None:
        raise HTTPException(503, "ArtifactStore not available")

    result = defunk.artifact_store.latest(model_name)
    if result is None:
        raise HTTPException(404, f"No trained model: {model_name}")

    artifact, model_object = result

    response = {
        "model_name": artifact.model_name,
        "version": artifact.version,
        "trained_at": artifact.trained_at,
        "metrics": artifact.metrics,
        "status": artifact.status,
    }

    # If the model supports prediction, run it
    if model_object is not None and hasattr(model_object, 'predict'):
        try:
            # For sklearn models, we'd need feature data — return metadata for now
            response["note"] = "Model loaded successfully. Feature data required for live predictions."
            response["model_type"] = type(model_object).__name__
        except Exception as e:
            response["error"] = str(e)
    else:
        response["note"] = "Model metadata only (no predict method)"

    return response
