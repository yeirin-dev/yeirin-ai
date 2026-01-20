"""Soul-E 데이터베이스 ORM 모델 (읽기 전용).

Soul-E의 검사 관련 테이블 스키마를 반영합니다.
이 서비스에서는 읽기 전용으로만 사용됩니다.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class SoulEBase(DeclarativeBase):
    """Soul-E ORM 모델의 기본 클래스."""

    pass


# =============================================================================
# Enum 정의
# =============================================================================


class AssessmentStatus(str, enum.Enum):
    """심리검사 세션 상태."""

    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    FAILED = "FAILED"


class TScoreExtractionStatus(str, enum.Enum):
    """KPRC T점수 추출 상태."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# =============================================================================
# 심리검사 세션 모델
# =============================================================================


class AssessmentSessionORM(SoulEBase):
    """심리검사 세션 ORM 모델 (읽기 전용).

    Soul-E의 assessment_sessions 테이블과 매핑됩니다.
    """

    __tablename__ = "assessment_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        comment="세션 고유 식별자",
    )
    child_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="yeirin DB의 아동 ID",
    )
    guardian_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="yeirin DB의 보호자 ID",
    )
    chat_session_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        comment="연관된 채팅 세션 ID",
    )

    # 아동 정보 (검사 시점 스냅샷)
    child_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="아동 이름",
    )
    child_gender: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment="아동 성별 (M/F)",
    )
    child_birth_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="아동 생년월일",
    )
    child_school_grade: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="아동 학년",
    )

    # 검사 정보
    assessment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="검사 유형",
    )
    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="전체 문항 수",
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, native_enum=False),
        nullable=False,
        comment="세션 상태",
    )

    # 답변 데이터
    answers: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="답변 데이터",
    )
    answered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="응답 완료 문항 수",
    )

    # Inpsyt API 결과
    total_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="총점",
    )

    # 감사 필드
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AssessmentSession("
            f"id={self.id}, "
            f"child_id={self.child_id}, "
            f"type={self.assessment_type}, "
            f"status={self.status}"
            f")>"
        )


# =============================================================================
# 심리검사 결과 모델
# =============================================================================


class AssessmentResultORM(SoulEBase):
    """심리검사 결과 ORM 모델 (읽기 전용).

    Soul-E의 assessment_results 테이블과 매핑됩니다.
    """

    __tablename__ = "assessment_results"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        comment="결과 고유 식별자",
    )
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="검사 세션 ID",
    )

    # 검사 정보
    assessment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="검사 유형",
    )
    result_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="결과 스키마 버전",
    )

    # 점수 데이터
    total_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="총점",
    )
    max_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="최대 가능 점수",
    )
    scale_scores: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="척도별 원점수",
    )
    t_scores: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="척도별 T점수 및 백분위",
    )

    # 해석 및 요약
    interpretation: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="해석 결과",
    )
    summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="요약 정보",
    )

    # 리포트 URL
    report_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Inpsyt PDF 리포트 URL",
    )

    # 감사 필드
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    session: Mapped["AssessmentSessionORM"] = relationship(
        "AssessmentSessionORM",
        foreign_keys=[session_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AssessmentResult("
            f"id={self.id}, "
            f"session_id={self.session_id}, "
            f"type={self.assessment_type}, "
            f"total_score={self.total_score}"
            f")>"
        )


# =============================================================================
# KPRC T점수 추출 모델
# =============================================================================


class KprcTScoreExtractionORM(SoulEBase):
    """KPRC T점수 추출 결과 ORM 모델 (읽기 전용).

    Soul-E의 kprc_t_score_extractions 테이블과 매핑됩니다.
    """

    __tablename__ = "kprc_t_score_extractions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        comment="추출 결과 고유 식별자",
    )
    assessment_result_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("assessment_results.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="검사 결과 ID",
    )

    # KPRC 13개 척도 T점수
    ers_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icn_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    f_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vdl_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdl_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anx_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dep_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    som_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dlq_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hpr_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fam_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soc_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    psy_t_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 추출 메타데이터
    extraction_status: Mapped[TScoreExtractionStatus] = mapped_column(
        Enum(TScoreExtractionStatus, native_enum=False),
        nullable=False,
        comment="추출 상태",
    )
    extraction_confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="추출 신뢰도 (0.0-1.0)",
    )
    raw_extraction_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="GPT Vision API 원본 응답",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="실패 시 에러 메시지",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="재시도 횟수",
    )

    # 바우처 판별 캐시
    meets_voucher_criteria: Mapped[bool | None] = mapped_column(
        nullable=True,
        comment="KPRC 바우처 조건 충족 여부",
    )
    voucher_criteria_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="바우처 조건 충족 상세",
    )

    # 감사 필드
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="추출 완료 시간",
    )

    # Relationship
    assessment_result: Mapped["AssessmentResultORM"] = relationship(
        "AssessmentResultORM",
        foreign_keys=[assessment_result_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<KprcTScoreExtraction("
            f"id={self.id}, "
            f"result_id={self.assessment_result_id}, "
            f"status={self.extraction_status}, "
            f"meets_voucher={self.meets_voucher_criteria}"
            f")>"
        )

    def get_all_t_scores(self) -> dict[str, int | None]:
        """모든 T점수를 딕셔너리로 반환."""
        return {
            "ERS": self.ers_t_score,
            "ICN": self.icn_t_score,
            "F": self.f_t_score,
            "VDL": self.vdl_t_score,
            "PDL": self.pdl_t_score,
            "ANX": self.anx_t_score,
            "DEP": self.dep_t_score,
            "SOM": self.som_t_score,
            "DLQ": self.dlq_t_score,
            "HPR": self.hpr_t_score,
            "FAM": self.fam_t_score,
            "SOC": self.soc_t_score,
            "PSY": self.psy_t_score,
        }
