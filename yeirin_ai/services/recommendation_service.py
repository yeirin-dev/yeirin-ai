"""추천 서비스 - 애플리케이션 계층."""

from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.recommendation.models import (
    RecommendationRequest,
    RecommendationResult,
)
from yeirin_ai.infrastructure.database.repository import InstitutionRepository
from yeirin_ai.infrastructure.llm.openai_client import OpenAIRecommendationClient


class RecommendationService:
    """상담 기관 추천 서비스.

    상담 의뢰지 텍스트를 분석하여 최적의 바우처 상담 기관을 추천합니다.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        """추천 서비스를 초기화합니다.

        Args:
            db_session: 비동기 데이터베이스 세션
        """
        self.institution_repo = InstitutionRepository(db_session)
        self.llm_client = OpenAIRecommendationClient()

    async def get_recommendations(
        self, request: RecommendationRequest
    ) -> RecommendationResult:
        """상담 의뢰 내용을 기반으로 기관을 추천합니다.

        Args:
            request: 상담 의뢰지 텍스트가 포함된 추천 요청

        Returns:
            상위 추천 기관이 포함된 추천 결과

        Raises:
            ValueError: 기관이 없거나 LLM 호출 실패 시 발생
        """
        # 1. 데이터베이스에서 모든 기관 조회
        institutions = await self.institution_repo.get_all()

        if not institutions:
            raise ValueError("데이터베이스에 등록된 기관이 없습니다")

        # 2. LLM을 사용하여 분석 및 추천
        recommendations = await self.llm_client.recommend_institutions(
            counsel_request=request.counsel_request_text,
            institutions=institutions,
            max_recommendations=settings.max_recommendations,
        )

        # 3. 결과 생성
        return RecommendationResult(
            request_text=request.counsel_request_text,
            recommendations=recommendations,
            total_count=len(institutions),
        )
