"""Recommendation domain models."""

from pydantic import BaseModel, Field


class RecommendationRequest:
    """상담 센터 추천 요청 도메인 모델."""

    def __init__(self, counsel_request_text: str) -> None:
        """
        Initialize recommendation request.

        Args:
            counsel_request_text: 상담 의뢰지 텍스트 (10-5000자)
        """
        if not counsel_request_text or len(counsel_request_text.strip()) < 10:
            raise ValueError("상담 의뢰지 텍스트는 최소 10자 이상이어야 합니다")
        if len(counsel_request_text) > 5000:
            raise ValueError("상담 의뢰지 텍스트는 5000자를 초과할 수 없습니다")

        self.counsel_request_text = counsel_request_text.strip()

    def __repr__(self) -> str:
        """String representation."""
        preview = (
            self.counsel_request_text[:50] + "..."
            if len(self.counsel_request_text) > 50
            else self.counsel_request_text
        )
        return f"<RecommendationRequest text='{preview}'>"


class InstitutionRecommendation(BaseModel):
    """개별 기관 추천 결과."""

    institution_id: str = Field(description="기관 ID")
    center_name: str = Field(description="센터명")
    score: float = Field(ge=0.0, le=1.0, description="추천 점수 (0.0-1.0)")
    reasoning: str = Field(description="추천 이유")
    address: str = Field(description="주소")
    average_rating: float = Field(description="평균 별점")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "institution_id": "uuid-here",
                "center_name": "서울아동심리상담센터",
                "score": 0.95,
                "reasoning": "ADHD 전문 상담사가 3명 있으며, 종합심리검사를 제공합니다.",
                "address": "서울시 강남구 테헤란로 123",
                "average_rating": 4.8,
            }
        }


class RecommendationResult:
    """추천 결과 도메인 모델."""

    def __init__(
        self,
        request_text: str,
        recommendations: list[InstitutionRecommendation],
        total_count: int,
    ) -> None:
        """
        Initialize recommendation result.

        Args:
            request_text: 원본 요청 텍스트
            recommendations: 추천된 기관 목록 (점수 순으로 정렬됨)
            total_count: 전체 기관 수
        """
        self.request_text = request_text
        self.recommendations = recommendations
        self.total_count = total_count

    def get_top_recommendation(self) -> InstitutionRecommendation | None:
        """Get the top recommendation."""
        return self.recommendations[0] if self.recommendations else None

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<RecommendationResult "
            f"count={len(self.recommendations)} "
            f"total={self.total_count}>"
        )
