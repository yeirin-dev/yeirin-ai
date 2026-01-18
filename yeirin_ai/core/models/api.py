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


# ============================================================================
# KPRC T점수 추출 관련 DTO
# ============================================================================


class KprcTScoreExtractionRequestDTO(BaseModel):
    """KPRC T점수 추출 요청 DTO."""

    assessment_result_id: str = Field(
        description="검사 결과 ID (Soul-E assessment_results.id)"
    )
    pdf_url: str = Field(
        description="KPRC 보고서 PDF URL (S3 presigned URL)"
    )
    callback_url: str | None = Field(
        default=None,
        description="추출 완료 시 결과를 전송할 콜백 URL (선택)",
    )


class KprcTScoreDTO(BaseModel):
    """KPRC T점수 DTO."""

    # 타당도 척도
    ers_t_score: int | None = Field(None, description="ERS (자아탄력성) T점수")
    icn_t_score: int | None = Field(None, description="ICN (비일관성) T점수")
    f_t_score: int | None = Field(None, description="F (저빈도) T점수")
    vdl_t_score: int | None = Field(None, description="VDL (긍정왜곡) T점수")
    pdl_t_score: int | None = Field(None, description="PDL (부정왜곡) T점수")

    # 임상 척도
    anx_t_score: int | None = Field(None, description="ANX (불안) T점수")
    dep_t_score: int | None = Field(None, description="DEP (우울) T점수")
    som_t_score: int | None = Field(None, description="SOM (신체화) T점수")
    dlq_t_score: int | None = Field(None, description="DLQ (비행) T점수")
    hpr_t_score: int | None = Field(None, description="HPR (과잉행동) T점수")
    fam_t_score: int | None = Field(None, description="FAM (가족관계) T점수")
    soc_t_score: int | None = Field(None, description="SOC (사회관계) T점수")
    psy_t_score: int | None = Field(None, description="PSY (정신증) T점수")


class KprcTScoreExtractionResponseDTO(BaseModel):
    """KPRC T점수 추출 응답 DTO."""

    assessment_result_id: str = Field(description="검사 결과 ID")
    status: str = Field(description="추출 상태 (COMPLETED, FAILED)")
    t_scores: KprcTScoreDTO | None = Field(None, description="추출된 T점수")
    confidence: float = Field(default=0.0, description="추출 신뢰도 (0.0-1.0)")
    meets_voucher_criteria: bool = Field(
        default=False,
        description="KPRC 바우처 조건 충족 여부",
    )
    risk_scales: list[str] = Field(
        default_factory=list,
        description="위험 기준을 초과한 척도 목록",
    )
    error_message: str | None = Field(None, description="실패 시 에러 메시지")

    class Config:
        """Pydantic 설정."""

        json_schema_extra = {
            "example": {
                "assessment_result_id": "uuid-here",
                "status": "COMPLETED",
                "t_scores": {
                    "ers_t_score": 45,
                    "icn_t_score": 52,
                    "f_t_score": 48,
                    "vdl_t_score": 55,
                    "pdl_t_score": 50,
                    "anx_t_score": 68,
                    "dep_t_score": 72,
                    "som_t_score": 55,
                    "dlq_t_score": 48,
                    "hpr_t_score": 58,
                    "fam_t_score": 52,
                    "soc_t_score": 65,
                    "psy_t_score": 45,
                },
                "confidence": 0.92,
                "meets_voucher_criteria": True,
                "risk_scales": ["ANX", "DEP", "SOC"],
                "error_message": None,
            }
        }


class KprcExtractionCallbackDTO(BaseModel):
    """KPRC 추출 결과 콜백 DTO (Soul-E로 전송)."""

    assessment_result_id: str
    status: str
    t_scores: KprcTScoreDTO | None = None
    confidence: float = 0.0
    meets_voucher_criteria: bool = False
    voucher_criteria_details: dict | None = None
    error_message: str | None = None
