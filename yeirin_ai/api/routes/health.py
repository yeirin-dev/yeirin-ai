"""Health check API routes."""

from fastapi import APIRouter

from yeirin_ai.core.config.settings import settings
from yeirin_ai.core.models.api import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="서비스 상태를 확인합니다.",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns:
        Service health status
    """
    return HealthCheckResponse(
        status="healthy",
        version=settings.app_version,
        service=settings.app_name,
    )
