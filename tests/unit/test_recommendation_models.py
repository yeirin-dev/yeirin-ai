"""Domain model tests for recommendation."""

import pytest

from yeirin_ai.domain.recommendation.models import (
    InstitutionRecommendation,
    RecommendationRequest,
    RecommendationResult,
)


class TestRecommendationRequest:
    """RecommendationRequest 도메인 모델 테스트."""

    def test_올바른_텍스트로_요청을_생성한다(self) -> None:
        """올바른 상담 의뢰지 텍스트로 요청 객체를 생성한다."""
        # Given
        valid_text = "아이가 학교에서 집중을 못하고 산만한 모습을 보입니다."

        # When
        request = RecommendationRequest(valid_text)

        # Then
        assert request.counsel_request_text == valid_text.strip()

    def test_앞뒤_공백이_제거된다(self) -> None:
        """텍스트 앞뒤 공백이 자동으로 제거된다."""
        # Given
        text_with_spaces = "  아이 상담이 필요합니다  "

        # When
        request = RecommendationRequest(text_with_spaces)

        # Then
        assert request.counsel_request_text == "아이 상담이 필요합니다"

    def test_10자_미만_텍스트는_실패한다(self) -> None:
        """10자 미만의 텍스트는 ValueError를 발생시킨다."""
        # Given
        short_text = "짧은글"

        # When & Then
        with pytest.raises(ValueError, match="최소 10자 이상"):
            RecommendationRequest(short_text)

    def test_빈_문자열은_실패한다(self) -> None:
        """빈 문자열이나 공백만 있는 문자열은 실패한다."""
        # When & Then
        with pytest.raises(ValueError, match="최소 10자 이상"):
            RecommendationRequest("")

        with pytest.raises(ValueError, match="최소 10자 이상"):
            RecommendationRequest("   ")

    def test_5000자_초과_텍스트는_실패한다(self) -> None:
        """5000자를 초과하는 텍스트는 ValueError를 발생시킨다."""
        # Given
        long_text = "가" * 5001

        # When & Then
        with pytest.raises(ValueError, match="5000자를 초과할 수 없습니다"):
            RecommendationRequest(long_text)

    def test_정확히_5000자는_성공한다(self) -> None:
        """정확히 5000자는 허용된다."""
        # Given
        text_5000 = "가" * 5000

        # When
        request = RecommendationRequest(text_5000)

        # Then
        assert len(request.counsel_request_text) == 5000


class TestInstitutionRecommendation:
    """InstitutionRecommendation 도메인 모델 테스트."""

    def test_올바른_데이터로_추천을_생성한다(self) -> None:
        """올바른 데이터로 기관 추천 객체를 생성한다."""
        # Given & When
        recommendation = InstitutionRecommendation(
            institution_id="test-uuid",
            center_name="서울아동심리상담센터",
            score=0.95,
            reasoning="ADHD 전문 상담사 3명 보유",
            address="서울시 강남구 테헤란로 123",
            average_rating=4.8,
        )

        # Then
        assert recommendation.institution_id == "test-uuid"
        assert recommendation.center_name == "서울아동심리상담센터"
        assert recommendation.score == 0.95
        assert recommendation.reasoning == "ADHD 전문 상담사 3명 보유"
        assert recommendation.address == "서울시 강남구 테헤란로 123"
        assert recommendation.average_rating == 4.8

    def test_점수는_0_0에서_1_0_사이여야_한다(self) -> None:
        """점수는 0.0 이상 1.0 이하여야 한다."""
        # When & Then: 범위 밖 값은 Pydantic validation error
        with pytest.raises(ValueError):
            InstitutionRecommendation(
                institution_id="test",
                center_name="센터",
                score=1.5,  # 1.0 초과
                reasoning="이유",
                address="주소",
                average_rating=5.0,
            )

        with pytest.raises(ValueError):
            InstitutionRecommendation(
                institution_id="test",
                center_name="센터",
                score=-0.1,  # 0.0 미만
                reasoning="이유",
                address="주소",
                average_rating=5.0,
            )


class TestRecommendationResult:
    """RecommendationResult 도메인 모델 테스트."""

    @pytest.fixture
    def sample_recommendations(self) -> list[InstitutionRecommendation]:
        """샘플 추천 목록."""
        return [
            InstitutionRecommendation(
                institution_id="1",
                center_name="A센터",
                score=0.95,
                reasoning="최고 매칭",
                address="서울",
                average_rating=4.9,
            ),
            InstitutionRecommendation(
                institution_id="2",
                center_name="B센터",
                score=0.85,
                reasoning="좋은 매칭",
                address="경기",
                average_rating=4.5,
            ),
        ]

    def test_올바른_데이터로_결과를_생성한다(
        self, sample_recommendations: list[InstitutionRecommendation]
    ) -> None:
        """올바른 데이터로 추천 결과 객체를 생성한다."""
        # Given
        request_text = "아이 상담이 필요합니다"

        # When
        result = RecommendationResult(
            request_text=request_text,
            recommendations=sample_recommendations,
            total_count=10,
        )

        # Then
        assert result.request_text == request_text
        assert len(result.recommendations) == 2
        assert result.total_count == 10

    def test_최고_추천을_반환한다(
        self, sample_recommendations: list[InstitutionRecommendation]
    ) -> None:
        """첫 번째 추천(가장 높은 점수)을 반환한다."""
        # Given
        result = RecommendationResult(
            request_text="test",
            recommendations=sample_recommendations,
            total_count=2,
        )

        # When
        top = result.get_top_recommendation()

        # Then
        assert top is not None
        assert top.center_name == "A센터"
        assert top.score == 0.95

    def test_추천이_없으면_None을_반환한다(self) -> None:
        """추천 목록이 비어있으면 None을 반환한다."""
        # Given
        result = RecommendationResult(
            request_text="test", recommendations=[], total_count=0
        )

        # When
        top = result.get_top_recommendation()

        # Then
        assert top is None
