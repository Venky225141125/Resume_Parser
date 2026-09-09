from fastapi import APIRouter, Depends

from app.api.deps import settings_dep
from app.core.config import Settings
from app.core.versions import PHASE
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(settings_dep)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        phase=PHASE,
        environment=settings.environment,
        llm_enabled=settings.llm_enabled,
    )


@router.get("/ready", response_model=HealthResponse)
def ready(settings: Settings = Depends(settings_dep)) -> HealthResponse:
    """Readiness probe. DB checks will be added when persistence lands."""
    return HealthResponse(
        status="ready",
        phase=PHASE,
        environment=settings.environment,
        llm_enabled=settings.llm_enabled,
    )
