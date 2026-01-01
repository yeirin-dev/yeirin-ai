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


class BirthDate(BaseModel):
    """생년월일."""

    year: int = Field(..., description="년도")
    month: int = Field(..., ge=1, le=12, description="월")
    day: int = Field(..., ge=1, le=31, description="일")

    def to_korean_string(self) -> str:
        """한국어 날짜 문자열로 변환 (YYYY년 MM월 DD일)."""
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
    birthDate: BirthDate | None = Field(None, description="생년월일 (government doc용)")


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


# =============================================================================
# 검사 유형 상수
# =============================================================================

ASSESSMENT_TYPES = {
    "KPRC": "KPRC_CO_SG_E",
    "CRTES_R": "CRTES_R",
    "SDQ_A": "SDQ_A",
}


# =============================================================================
# 검사 소견 모델
# =============================================================================


class BaseAssessmentSummary(BaseModel):
    """공통 검사소견 필드."""

    summaryLines: list[str] | None = Field(None, description="요약 문장 (최대 5줄)")
    expertOpinion: str | None = Field(None, description="전문가 소견")
    keyFindings: list[str] | None = Field(None, description="핵심 발견 사항")
    recommendations: list[str] | None = Field(None, description="권장 사항")
    confidenceScore: float | None = Field(None, ge=0.0, le=1.0, description="신뢰도 점수")


class KprcSummary(BaseAssessmentSummary):
    """KPRC 검사소견 (yeirin-ai 생성)."""

    assessmentType: Literal["KPRC_CO_SG_E"] | None = Field(None, description="검사 유형")


class CrtesRSummary(BaseAssessmentSummary):
    """CRTES-R 검사소견 (아동 외상 반응 척도)."""

    assessmentType: Literal["CRTES_R"] = Field("CRTES_R", description="검사 유형")
    totalScore: int | None = Field(None, ge=0, le=115, description="총점")
    riskLevel: Literal["normal", "caution", "high_risk"] | None = Field(None, description="위험 수준")


class SdqASummary(BaseAssessmentSummary):
    """SDQ-A 검사소견 (강점·난점 설문지)."""

    assessmentType: Literal["SDQ_A"] = Field("SDQ_A", description="검사 유형")
    difficultiesScore: int | None = Field(None, ge=0, le=40, description="난점 총점")
    strengthsScore: int | None = Field(None, ge=0, le=10, description="강점 총점")
    difficultiesLevel: Literal["normal", "borderline", "abnormal"] | None = Field(
        None, description="난점 수준"
    )
    strengthsLevel: Literal["normal", "borderline", "abnormal"] | None = Field(
        None, description="강점 수준"
    )


# =============================================================================
# 첨부 검사 결과 모델
# =============================================================================


class AttachedAssessment(BaseModel):
    """첨부된 개별 검사 결과 정보."""

    assessmentType: str = Field(..., description="검사 유형 (KPRC_CO_SG_E, CRTES_R, SDQ_A)")
    assessmentName: str = Field(..., description="검사명 (예: KPRC 인성평정척도)")
    reportS3Key: str = Field(..., description="검사 결과 PDF S3 키")
    resultId: str = Field(..., description="검사 결과 ID")
    totalScore: int | None = Field(None, description="총점")
    maxScore: int | None = Field(None, description="만점")
    overallLevel: Literal["normal", "caution", "clinical"] | None = Field(
        None, description="전반적 수준"
    )
    scoredAt: str | None = Field(None, description="채점 일시")
    summary: BaseAssessmentSummary | None = Field(None, description="AI 생성 요약")


# =============================================================================
# 사회서비스 이용 추천서 (Government Doc) 전용 모델
# =============================================================================


class GuardianInfo(BaseModel):
    """보호자 정보 (사회서비스 이용 추천서용).

    테이블 1: 대상자 인적사항의 보호자 관련 정보
    """

    name: str = Field(..., description="보호자 성명")
    phoneNumber: str = Field(..., description="전화번호 (휴대전화)")
    homePhone: str | None = Field(None, description="자택 전화번호")
    address: str = Field(..., description="주소")
    addressDetail: str | None = Field(None, description="상세 주소")
    relationToChild: str = Field(..., description="이용자와의 관계 (부모, 담임교사 등)")


class InstitutionInfo(BaseModel):
    """기관/작성자 정보 (사회서비스 이용 추천서용).

    테이블 3: 작성자 정보
    """

    institutionName: str = Field(..., description="소속기관명")
    phoneNumber: str = Field(..., description="기관 연락처")
    address: str = Field(..., description="기관 소재지")
    addressDetail: str | None = Field(None, description="상세 주소")
    writerPosition: str = Field(..., description="직 또는 자격 (담임교사, 사회복지사 등)")
    writerName: str = Field(..., description="작성자 성명")
    relationToChild: str = Field(..., description="이용자와의 관계")


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

    # 첨부된 검사 결과들 (최대 3개: KPRC, CRTES-R, SDQ-A)
    attached_assessments: list[AttachedAssessment] | None = Field(
        None, description="첨부된 검사 결과 목록 (최대 3개)"
    )

    # ⚠️ 하위 호환성: 기존 필드 유지 (deprecated)
    # 새 코드에서는 attached_assessments 사용
    kprc_summary: KprcSummary | None = Field(
        None, description="[Deprecated] KPRC 검사소견 (attached_assessments 사용 권장)"
    )
    assessment_report_s3_key: str | None = Field(
        None, description="[Deprecated] KPRC PDF S3 key (attached_assessments 사용 권장)"
    )

    # 사회서비스 이용 추천서 (Government Doc) 데이터 - Optional
    guardian_info: GuardianInfo | None = Field(
        None, description="보호자 정보 (사회서비스 이용 추천서용)"
    )
    institution_info: InstitutionInfo | None = Field(
        None, description="기관/작성자 정보 (사회서비스 이용 추천서용)"
    )

    def get_assessment_pdfs_s3_keys(self) -> list[tuple[str, str]]:
        """모든 검사 결과 PDF의 S3 키를 반환합니다.

        Returns:
            (검사 유형, S3 키) 튜플 리스트
        """
        s3_keys: list[tuple[str, str]] = []

        # 새 방식: attached_assessments 사용
        if self.attached_assessments:
            for assessment in self.attached_assessments:
                s3_keys.append((assessment.assessmentType, assessment.reportS3Key))

        # 하위 호환: legacy 필드 사용 (attached_assessments가 없는 경우)
        elif self.assessment_report_s3_key:
            s3_keys.append(("KPRC_CO_SG_E", self.assessment_report_s3_key))

        return s3_keys

    def get_kprc_summary_for_doc(self) -> KprcSummary | None:
        """문서 생성용 KPRC 요약을 반환합니다.

        attached_assessments에서 KPRC를 찾거나, legacy 필드를 사용합니다.

        Returns:
            KPRC 검사소견 또는 None
        """
        # 새 방식: attached_assessments에서 KPRC 찾기
        if self.attached_assessments:
            for assessment in self.attached_assessments:
                if assessment.assessmentType == "KPRC_CO_SG_E" and assessment.summary:
                    return KprcSummary(
                        summaryLines=assessment.summary.summaryLines,
                        expertOpinion=assessment.summary.expertOpinion,
                        keyFindings=assessment.summary.keyFindings,
                        recommendations=assessment.summary.recommendations,
                        confidenceScore=assessment.summary.confidenceScore,
                    )

        # 하위 호환: legacy 필드 사용
        return self.kprc_summary

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
                        "birthDate": {"year": 2015, "month": 3, "day": 15},
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
                "guardian_info": {
                    "name": "홍부모",
                    "phoneNumber": "010-1234-5678",
                    "homePhone": "02-1234-5678",
                    "address": "서울시 강남구 테헤란로 123",
                    "addressDetail": "101동 1001호",
                    "relationToChild": "부",
                },
                "institution_info": {
                    "institutionName": "서울초등학교",
                    "phoneNumber": "02-123-4567",
                    "address": "서울시 강남구 학동로 456",
                    "addressDetail": None,
                    "writerPosition": "담임교사",
                    "writerName": "김선생",
                    "relationToChild": "담임교사",
                },
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
