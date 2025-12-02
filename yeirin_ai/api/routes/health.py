"""헬스 체크 API 라우터."""

from fastapi import APIRouter

from yeirin_ai.core.config.settings import settings
from yeirin_ai.core.models.api import HealthCheckResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthCheckResponse,
    summary="헬스 체크",
    description="서비스 상태를 확인합니다.",
)
async def health_check() -> HealthCheckResponse:
    """헬스 체크 엔드포인트.

    서비스의 상태, 버전, 이름을 반환합니다.
    Kubernetes Liveness/Readiness 프로브에서 사용됩니다.

    Returns:
        서비스 상태 정보
    """
    return HealthCheckResponse(
        status="healthy",
        version=settings.app_version,
        service=settings.app_name,
    )
