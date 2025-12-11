"""통합 보고서 API 라우터.

상담의뢰지 + KPRC 검사지 통합 보고서 생성 엔드포인트를 제공합니다.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel, Field

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.integrated_report.models import IntegratedReportRequest

router = APIRouter(prefix="/integrated-reports", tags=["integrated-reports"])

logger = logging.getLogger(__name__)


# =============================================================================
# 요청/응답 모델
# =============================================================================


class IntegratedReportAcceptedResponse(BaseModel):
    """통합 보고서 생성 요청 수락 응답."""

    status: str = Field(default="accepted", description="요청 상태")
    counsel_request_id: str = Field(..., description="상담의뢰지 ID")
    message: str = Field(..., description="응답 메시지")


# =============================================================================
# 의존성
# =============================================================================


def validate_internal_api_key(x_internal_api_key: str = Header(...)) -> None:
    """내부 API 키를 검증합니다.

    Args:
        x_internal_api_key: 내부 서비스 API 키 헤더

    Raises:
        HTTPException: 인증 실패 시
    """
    if x_internal_api_key != settings.internal_api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 내부 API 키입니다",
        )


# =============================================================================
# 엔드포인트
# =============================================================================


@router.post(
    "",
    response_model=IntegratedReportAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="통합 보고서 생성 요청",
    description="상담의뢰지 데이터와 KPRC 검사지를 병합하여 통합 보고서를 생성합니다",
)
async def request_integrated_report(
    request: IntegratedReportRequest,
    background_tasks: BackgroundTasks,
    x_internal_api_key: str = Header(..., description="내부 서비스 API 키"),
) -> IntegratedReportAcceptedResponse:
    """통합 보고서 생성을 요청합니다.

    yeirin 메인 백엔드에서 상담의뢰지 생성 후 호출됩니다:
    1. 요청 수신 → 즉시 202 Accepted 응답
    2. 백그라운드에서 DOCX 템플릿 채우기, PDF 변환, PDF 병합
    3. 완료 후 yeirin에 Webhook으로 결과 전송
    """
    # 내부 API 키 검증
    validate_internal_api_key(x_internal_api_key)

    logger.info(
        "[API] 통합 보고서 생성 요청 수신",
        extra={
            "counsel_request_id": request.counsel_request_id,
            "child_name": request.child_name,
            "assessment_report_s3_key": request.assessment_report_s3_key,
        },
    )

    # 백그라운드 태스크로 처리
    from yeirin_ai.services.integrated_report_service import process_integrated_report_sync

    background_tasks.add_task(
        process_integrated_report_sync,
        request_dict=request.model_dump(),
    )

    logger.info(
        "[API] 백그라운드 태스크 등록 완료",
        extra={"counsel_request_id": request.counsel_request_id},
    )

    return IntegratedReportAcceptedResponse(
        status="accepted",
        counsel_request_id=request.counsel_request_id,
        message="통합 보고서 생성 요청이 수락되었습니다. 백그라운드에서 처리됩니다.",
    )
