"""GET /api/health — liveness check."""
from fastapi import APIRouter
from de_funk.api.models.requests import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
