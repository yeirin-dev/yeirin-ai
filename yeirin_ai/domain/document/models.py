"""문서 처리 도메인 모델."""

from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """문서 유형."""

    KPRC_REPORT = "kprc_report"  # KPRC 심리검사 결과 보고서
    COUNSEL_REQUEST = "counsel_request"  # 상담 의뢰서
    COUNSEL_REPORT = "counsel_report"  # 상담 결과 보고서
    OTHER = "other"  # 기타 문서


class SummaryRequest(BaseModel):
    """문서 요약 요청 모델."""

    document_type: DocumentType = Field(
        default=DocumentType.KPRC_REPORT,
        description="문서 유형",
    )
    child_name: str | None = Field(
        default=None,
        description="아동 이름 (익명화 처리용)",
    )
    include_recommendations: bool = Field(
        default=True,
        description="권장 사항 포함 여부",
    )


class DocumentSummary(BaseModel):
    """문서 요약 결과 모델."""

    document_type: DocumentType = Field(..., description="문서 유형")
    summary_lines: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="요약 문장 (최대 5줄)",
    )
    expert_opinion: str = Field(..., description="전문가 소견 형태의 종합 요약")
    key_findings: list[str] = Field(
        default_factory=list,
        description="핵심 발견 사항",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="권장 사항 (선택적)",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="요약 신뢰도 점수",
    )
