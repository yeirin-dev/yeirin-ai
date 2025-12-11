"""통합 보고서 도메인 모델.

yeirin에서 상담의뢰지 생성 시 전달받는 데이터와
통합 보고서 생성 결과를 정의합니다.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RequestDate(BaseModel):
    """의뢰 일자."""

    year: int = Field(..., description="년도")
    month: int = Field(..., ge=1, le=12, description="월")
    day: int = Field(..., ge=1, le=31, description="일")

    def to_date(self) -> date:
        """date 객체로 변환."""
        return date(self.year, self.month, self.day)

    def to_korean_string(self) -> str:
        """한국어 날짜 문자열로 변환."""
        return f"{self.year}년 {self.month}월 {self.day}일"


class CoverInfo(BaseModel):
    """표지 정보."""

    requestDate: RequestDate = Field(..., description="의뢰 일자")
    centerName: str = Field(..., description="센터명")
    counselorName: str = Field(..., description="담당자 이름")


class ChildInfo(BaseModel):
    """아동 정보."""

    name: str = Field(..., description="아동 이름")
    gender: str = Field(..., description="성별 (MALE/FEMALE)")
    age: int = Field(..., ge=0, description="연령")
    grade: str = Field(..., description="학년")


class BasicInfo(BaseModel):
    """기본 정보."""

    childInfo: ChildInfo = Field(..., description="아동 정보")
    careType: str = Field(..., description="센터 이용 기준")
    priorityReason: str | None = Field(None, description="우선돌봄 세부 사유")


class PsychologicalInfo(BaseModel):
    """정서·심리 관련 정보."""

    medicalHistory: str = Field(..., description="기존 아동 병력")
    specialNotes: str = Field(..., description="병력 외 특이사항")


class RequestMotivation(BaseModel):
    """의뢰 동기 및 상담 목표."""

    motivation: str = Field(..., description="의뢰 동기")
    goals: str = Field(..., description="보호자 및 의뢰자의 목표")


class KprcSummary(BaseModel):
    """KPRC 검사소견 (yeirin-ai 생성)."""

    summaryLines: list[str] | None = Field(None, description="요약 문장 (최대 5줄)")
    expertOpinion: str | None = Field(None, description="전문가 소견")
    keyFindings: list[str] | None = Field(None, description="핵심 발견 사항")
    recommendations: list[str] | None = Field(None, description="권장 사항")
    confidenceScore: float | None = Field(None, ge=0.0, le=1.0, description="신뢰도 점수")


class IntegratedReportRequest(BaseModel):
    """통합 보고서 생성 요청.

    yeirin에서 상담의뢰지 생성 후 전달하는 데이터입니다.
    """

    counsel_request_id: str = Field(..., description="상담의뢰지 ID (yeirin)")
    child_id: str = Field(..., description="아동 ID")
    child_name: str = Field(..., description="아동 이름")

    # 상담의뢰지 폼 데이터
    cover_info: CoverInfo = Field(..., description="표지 정보")
    basic_info: BasicInfo = Field(..., description="기본 정보")
    psychological_info: PsychologicalInfo = Field(..., description="정서심리 정보")
    request_motivation: RequestMotivation = Field(..., description="의뢰 동기")

    # KPRC 검사 데이터 (필수)
    kprc_summary: KprcSummary = Field(..., description="KPRC 검사소견")
    assessment_report_s3_key: str = Field(..., description="KPRC PDF S3 key")

    class Config:
        """Pydantic 설정."""

        json_schema_extra = {
            "example": {
                "counsel_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "child_id": "123e4567-e89b-12d3-a456-426614174001",
                "child_name": "홍길동",
                "cover_info": {
                    "requestDate": {"year": 2025, "month": 1, "day": 15},
                    "centerName": "서울아동발달센터",
                    "counselorName": "김선생",
                },
                "basic_info": {
                    "childInfo": {
                        "name": "홍길동",
                        "gender": "MALE",
                        "age": 10,
                        "grade": "초4",
                    },
                    "careType": "PRIORITY",
                    "priorityReason": "BASIC_LIVELIHOOD",
                },
                "psychological_info": {
                    "medicalHistory": "ADHD 진단 이력",
                    "specialNotes": "학교 적응에 어려움",
                },
                "request_motivation": {
                    "motivation": "행동 교정 필요",
                    "goals": "감정 조절 능력 향상",
                },
                "kprc_summary": {
                    "summaryLines": ["전반적 적응 수준 양호", "또래 관계 어려움 관찰"],
                    "expertOpinion": "본 아동은 KPRC 검사 결과...",
                    "keyFindings": ["정서적 안정감 높음"],
                    "recommendations": ["사회성 향상 프로그램 권장"],
                    "confidenceScore": 0.85,
                },
                "assessment_report_s3_key": "assessment-reports/KPRC_홍길동_abc123.pdf",
            }
        }


class IntegratedReportResult(BaseModel):
    """통합 보고서 생성 결과.

    yeirin에 웹훅으로 전달되는 결과입니다.
    """

    counsel_request_id: str = Field(..., description="상담의뢰지 ID")
    integrated_report_s3_key: str | None = Field(None, description="통합 보고서 S3 key")
    status: Literal["completed", "failed"] = Field(..., description="처리 상태")
    error_message: str | None = Field(None, description="에러 메시지 (실패 시)")

    class Config:
        """Pydantic 설정."""

        json_schema_extra = {
            "example": {
                "counsel_request_id": "123e4567-e89b-12d3-a456-426614174000",
                "integrated_report_s3_key": "integrated-reports/IR_홍길동_abc123_20250115.pdf",
                "status": "completed",
                "error_message": None,
            }
        }
