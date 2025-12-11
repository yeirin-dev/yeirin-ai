"""API 요청/응답 모델 (DTO)."""

from pydantic import BaseModel, Field

from yeirin_ai.domain.recommendation.models import InstitutionRecommendation


class RecommendationRequestDTO(BaseModel):
    """상담 기관 추천 요청 DTO.

    클라이언트에서 전송하는 추천 요청의 형식을 정의합니다.
    """

    counsel_request_text: str = Field(
        min_length=10,
        max_length=5000,
        description="상담 의뢰지 텍스트 (10-5000자)",
        examples=[
            "7세 아들이 ADHD 진단을 받았습니다. 학교에서 집중하지 못하고 친구들과 자주 다툽니다. "
            "전문적인 심리 상담과 행동 치료가 필요할 것 같습니다."
        ],
    )


class RecommendationResponseDTO(BaseModel):
    """상담 기관 추천 응답 DTO.

    AI 추천 결과를 클라이언트에 반환하는 형식을 정의합니다.
    """

    recommendations: list[InstitutionRecommendation] = Field(
        description="추천된 기관 목록 (점수 순으로 정렬)"
    )
    total_institutions: int = Field(description="전체 등록 기관 수")
    request_text: str = Field(description="원본 요청 텍스트")

    class Config:
        """Pydantic 설정."""

        json_schema_extra = {
            "example": {
                "recommendations": [
                    {
                        "institution_id": "uuid-here",
                        "center_name": "서울아동심리상담센터",
                        "score": 0.95,
                        "reasoning": "ADHD 전문 상담사가 3명 있으며, 종합심리검사를 제공합니다.",
                        "address": "서울시 강남구 테헤란로 123",
                        "average_rating": 4.8,
                    }
                ],
                "total_institutions": 5,
                "request_text": "7세 아들이 ADHD 진단을 받았습니다...",
            }
        }


class HealthCheckResponse(BaseModel):
    """헬스 체크 응답 모델.

    서비스 상태 확인 API의 응답 형식을 정의합니다.
    """

    status: str = Field(default="healthy", description="서비스 상태")
    version: str = Field(description="애플리케이션 버전")
    service: str = Field(description="서비스 이름")
