"""Service layer tests for recommendation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yeirin_ai.domain.institution.models import Institution
from yeirin_ai.domain.recommendation.models import (
    InstitutionRecommendation,
    RecommendationRequest,
)
from yeirin_ai.services.recommendation_service import RecommendationService


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def sample_institutions() -> list[Institution]:
    """샘플 기관 목록."""
    from datetime import date

    from yeirin_ai.domain.institution.models import ServiceType, VoucherType

    return [
        Institution(
            id="inst-1",
            center_name="서울아동심리상담센터",
            representative_name="김대표",
            address="서울시 강남구",
            established_date=date(2020, 1, 1),
            operating_vouchers=[VoucherType.CHILD_PSYCHOLOGY],
            is_quality_certified=True,
            max_capacity=20,
            introduction="ADHD 전문 상담 센터",
            counselor_count=5,
            counselor_certifications=["심리상담사 1급"],
            primary_target_group="ADHD",
            secondary_target_group="학습장애",
            can_provide_comprehensive_test=True,
            provided_services=[ServiceType.COUNSELING],
            special_treatments=[],
            can_provide_parent_counseling=True,
            average_rating=4.8,
            review_count=120,
        ),
        Institution(
            id="inst-2",
            center_name="경기심리치료센터",
            representative_name="이대표",
            address="경기도 성남시",
            established_date=date(2019, 3, 15),
            operating_vouchers=[VoucherType.CHILD_PSYCHOLOGY],
            is_quality_certified=False,
            max_capacity=15,
            introduction="우울증 전문 치료",
            counselor_count=3,
            counselor_certifications=["임상심리사 2급"],
            primary_target_group="우울증",
            secondary_target_group=None,
            can_provide_comprehensive_test=False,
            provided_services=[ServiceType.COGNITIVE_THERAPY],
            special_treatments=[],
            can_provide_parent_counseling=False,
            average_rating=4.5,
            review_count=80,
        ),
    ]


@pytest.fixture
def sample_recommendations() -> list[InstitutionRecommendation]:
    """샘플 추천 결과."""
    return [
        InstitutionRecommendation(
            institution_id="inst-1",
            center_name="서울아동심리상담센터",
            score=0.95,
            reasoning="ADHD 전문 상담사가 있으며 학습장애 치료 프로그램을 운영합니다.",
            address="서울시 강남구",
            average_rating=4.8,
        ),
    ]


class TestRecommendationService:
    """RecommendationService 테스트."""

    async def test_정상적으로_추천을_반환한다(
        self,
        mock_db_session: AsyncMock,
        sample_institutions: list[Institution],
        sample_recommendations: list[InstitutionRecommendation],
    ) -> None:
        """정상적인 요청에 대해 추천 결과를 반환한다."""
        # Given
        request = RecommendationRequest("아이가 학교에서 집중을 못하고 산만합니다.")
        service = RecommendationService(mock_db_session)

        # Mock repository
        service.institution_repo.get_all = AsyncMock(return_value=sample_institutions)

        # Mock LLM client
        service.llm_client.recommend_institutions = AsyncMock(
            return_value=sample_recommendations
        )

        # When
        result = await service.get_recommendations(request)

        # Then
        assert result.request_text == request.counsel_request_text
        assert len(result.recommendations) == 1
        assert result.total_count == 2
        assert result.recommendations[0].center_name == "서울아동심리상담센터"

    async def test_기관이_없으면_ValueError를_발생시킨다(
        self, mock_db_session: AsyncMock
    ) -> None:
        """데이터베이스에 기관이 없으면 ValueError를 발생시킨다."""
        # Given
        request = RecommendationRequest("아이 상담이 필요합니다.")
        service = RecommendationService(mock_db_session)

        # Mock repository returning empty list
        service.institution_repo.get_all = AsyncMock(return_value=[])

        # When & Then
        with pytest.raises(ValueError, match="No institutions found"):
            await service.get_recommendations(request)

    async def test_LLM_클라이언트를_올바르게_호출한다(
        self,
        mock_db_session: AsyncMock,
        sample_institutions: list[Institution],
        sample_recommendations: list[InstitutionRecommendation],
    ) -> None:
        """LLM 클라이언트를 올바른 매개변수로 호출한다."""
        # Given
        request = RecommendationRequest("우울증 상담이 필요합니다.")
        service = RecommendationService(mock_db_session)

        service.institution_repo.get_all = AsyncMock(return_value=sample_institutions)
        service.llm_client.recommend_institutions = AsyncMock(
            return_value=sample_recommendations
        )

        # When
        await service.get_recommendations(request)

        # Then
        service.llm_client.recommend_institutions.assert_called_once()
        call_args = service.llm_client.recommend_institutions.call_args
        assert call_args.kwargs["counsel_request"] == "우울증 상담이 필요합니다."
        assert call_args.kwargs["institutions"] == sample_institutions
        assert "max_recommendations" in call_args.kwargs

    async def test_Repository를_올바르게_호출한다(
        self,
        mock_db_session: AsyncMock,
        sample_institutions: list[Institution],
        sample_recommendations: list[InstitutionRecommendation],
    ) -> None:
        """Institution Repository를 올바르게 호출한다."""
        # Given
        request = RecommendationRequest("아이 상담이 필요합니다.")
        service = RecommendationService(mock_db_session)

        service.institution_repo.get_all = AsyncMock(return_value=sample_institutions)
        service.llm_client.recommend_institutions = AsyncMock(
            return_value=sample_recommendations
        )

        # When
        await service.get_recommendations(request)

        # Then
        service.institution_repo.get_all.assert_called_once()
