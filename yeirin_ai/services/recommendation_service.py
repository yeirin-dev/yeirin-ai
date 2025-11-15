"""Recommendation service - application layer."""

from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.recommendation.models import (
    RecommendationRequest,
    RecommendationResult,
)
from yeirin_ai.infrastructure.database.repository import InstitutionRepository
from yeirin_ai.infrastructure.llm.openai_client import OpenAIRecommendationClient


class RecommendationService:
    """상담 센터 추천 서비스."""

    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initialize recommendation service.

        Args:
            db_session: Database session
        """
        self.institution_repo = InstitutionRepository(db_session)
        self.llm_client = OpenAIRecommendationClient()

    async def get_recommendations(
        self, request: RecommendationRequest
    ) -> RecommendationResult:
        """
        Get institution recommendations based on counsel request.

        Args:
            request: Recommendation request with counsel text

        Returns:
            Recommendation result with top institutions

        Raises:
            ValueError: If no institutions found or LLM fails
        """
        # 1. Fetch all institutions from database
        institutions = await self.institution_repo.get_all()

        if not institutions:
            raise ValueError("No institutions found in database")

        # 2. Use LLM to analyze and recommend
        recommendations = await self.llm_client.recommend_institutions(
            counsel_request=request.counsel_request_text,
            institutions=institutions,
            max_recommendations=settings.max_recommendations,
        )

        # 3. Build result
        return RecommendationResult(
            request_text=request.counsel_request_text,
            recommendations=recommendations,
            total_count=len(institutions),
        )
