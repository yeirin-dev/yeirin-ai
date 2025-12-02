"""추천 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.core.models.api import RecommendationRequestDTO, RecommendationResponseDTO
from yeirin_ai.domain.recommendation.models import RecommendationRequest
from yeirin_ai.infrastructure.database.connection import get_db
from yeirin_ai.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationResponseDTO,
    summary="상담 기관 추천",
    description="상담 의뢰지 텍스트를 기반으로 최적의 상담 기관을 추천합니다.",
)
async def create_recommendation(
    request: RecommendationRequestDTO,
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponseDTO:
    """상담 기관 추천 API.

    상담 의뢰지 내용을 분석하여 가장 적합한 바우처 상담 기관을
    추천합니다. OpenAI GPT-4o-mini를 활용한 의미론적 분석을 수행합니다.

    Args:
        request: 추천 요청 (상담 의뢰지 텍스트 포함)
        db: 비동기 데이터베이스 세션

    Returns:
        추천 결과 (기관 목록, 점수, 추천 이유)

    Raises:
        HTTPException: 400 - 유효성 검증 실패, 500 - 서비스 오류
    """
    try:
        # 도메인 요청 객체 생성
        domain_request = RecommendationRequest(
            counsel_request_text=request.counsel_request_text
        )

        # 추천 실행
        service = RecommendationService(db)
        result = await service.get_recommendations(domain_request)

        # 응답 생성
        return RecommendationResponseDTO(
            recommendations=result.recommendations,
            total_institutions=result.total_count,
            request_text=result.request_text,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"내부 서버 오류: {str(e)}")
