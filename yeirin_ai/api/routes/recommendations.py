"""Recommendation API routes."""

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
    summary="Get institution recommendations",
    description="상담 의뢰지 텍스트를 기반으로 최적의 상담 기관을 추천합니다.",
)
async def create_recommendation(
    request: RecommendationRequestDTO,
    db: AsyncSession = Depends(get_db),
) -> RecommendationResponseDTO:
    """
    상담 센터 추천 API.

    Args:
        request: 추천 요청 (상담 의뢰지 텍스트)
        db: Database session

    Returns:
        추천 결과 (기관 목록, 점수, 이유)

    Raises:
        HTTPException: 400 if validation fails, 500 if service fails
    """
    try:
        # Create domain request
        domain_request = RecommendationRequest(
            counsel_request_text=request.counsel_request_text
        )

        # Get recommendations
        service = RecommendationService(db)
        result = await service.get_recommendations(domain_request)

        # Build response
        return RecommendationResponseDTO(
            recommendations=result.recommendations,
            total_institutions=result.total_count,
            request_text=result.request_text,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
