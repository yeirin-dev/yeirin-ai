"""문서 첨삭 API 라우터.

추후 구현 예정: 상담 보고서 첨삭 기능 엔드포인트입니다.
기획 확정 후 구체적인 API를 구현합니다.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/editing", tags=["editing"])


# =============================================================================
# 요청/응답 모델 (Placeholder)
# =============================================================================


class EditingRequestModel(BaseModel):
    """첨삭 요청 모델 (Placeholder).

    TODO: 기획 확정 후 구체화
    """

    text_content: str = Field(..., description="첨삭할 텍스트")


class EditingResponseModel(BaseModel):
    """첨삭 응답 모델 (Placeholder).

    TODO: 기획 확정 후 구체화
    """

    message: str = Field(..., description="응답 메시지")
    status: str = Field(..., description="상태")


# =============================================================================
# 엔드포인트 (Placeholder)
# =============================================================================


@router.post(
    "/",
    response_model=EditingResponseModel,
    summary="문서 첨삭 (미구현)",
    description="기획 확정 후 구현 예정입니다",
)
async def edit_document(request: EditingRequestModel) -> EditingResponseModel:
    """문서를 첨삭합니다.

    TODO: 기획 확정 후 구현 예정
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="첨삭 기능은 기획 확정 후 구현 예정입니다",
    )


@router.get(
    "/status",
    response_model=EditingResponseModel,
    summary="첨삭 서비스 상태",
    description="첨삭 서비스 구현 상태를 확인합니다",
)
async def get_editing_status() -> EditingResponseModel:
    """첨삭 서비스 상태를 반환합니다."""
    return EditingResponseModel(
        message="첨삭 기능은 기획 확정 후 구현 예정입니다",
        status="not_implemented",
    )
