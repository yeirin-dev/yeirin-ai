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


class ProtectedChildInfo(BaseModel):
    """보호대상 아동 정보.

    새 문서 포맷의 '보호대상 아동 기준' 섹션에서 사용됩니다.
    - 아동 양육시설 (CHILD_FACILITY)
    - 공동생활가정/그룹홈 (GROUP_HOME)
    """

    type: Literal["CHILD_FACILITY", "GROUP_HOME"] | None = Field(
        None, description="보호대상 유형 (아동양육시설/공동생활가정)"
    )
    reason: Literal[
        "GUARDIAN_ABSENCE", "ABUSE", "ILLNESS_RUNAWAY", "LOCAL_GOVERNMENT"
    ] | None = Field(None, description="보호 사유")

    @property
    def type_korean(self) -> str:
        """보호대상 유형 한국어."""
        type_map = {
            "CHILD_FACILITY": "아동 양육시설",
            "GROUP_HOME": "공동생활가정(그룹홈)",
        }
        return type_map.get(self.type or "", "")

    @property
    def reason_korean(self) -> str:
        """보호 사유 한국어."""
        reason_map = {
            "GUARDIAN_ABSENCE": "보호자 없거나 이탈",
            "ABUSE": "아동학대",
            "ILLNESS_RUNAWAY": "보호자 질병 또는 아동 가출",
            "LOCAL_GOVERNMENT": "지자체장 인정",
        }
        return reason_map.get(self.reason or "", "")


class BasicInfo(BaseModel):
    """기본 정보."""

    childInfo: ChildInfo = Field(..., description="아동 정보")
    careType: str = Field(..., description="센터 이용 기준")
    priorityReasons: list[str] | None = Field(None, description="우선돌봄 세부 사유 (복수 선택 가능)")
    protectedChildInfo: ProtectedChildInfo | None = Field(
        None, description="보호대상 아동 정보 (새 문서 포맷)"
    )


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
    """CRTES-R 검사소견 (아동 외상 반응 척도).

    아동이 경험한 스트레스 상황에 대한 정서적 반응을 측정합니다.
    """

    assessmentType: Literal["CRTES_R"] = Field("CRTES_R", description="검사 유형")
    totalScore: int | None = Field(None, ge=0, le=115, description="총점")
    riskLevel: Literal["normal", "caution", "high_risk"] | None = Field(
        None, description="위험 수준"
    )
    riskLevelDescription: str | None = Field(
        None, description="위험 수준 설명"
    )

    @property
    def risk_level_korean(self) -> str:
        """위험 수준 한국어 텍스트."""
        level_map = {
            "normal": "정상 범위",
            "caution": "주의 필요",
            "high_risk": "고위험",
        }
        return level_map.get(self.riskLevel or "", "미정")


class SdqASummary(BaseAssessmentSummary):
    """SDQ-A 검사소견 (강점·난점 설문지).

    새 문서 포맷에서는 강점/난점을 분리하여 표시합니다:
    - 강점 (사회지향 행동): 0-10점, Level 1-3
    - 난점 (외현화/내현화): 0-40점, Level 1-3
    """

    assessmentType: Literal["SDQ_A"] = Field("SDQ_A", description="검사 유형")

    # 강점 (사회지향 행동)
    strengthsScore: int | None = Field(None, ge=0, le=10, description="강점 총점")
    strengthsLevel: int | None = Field(None, ge=1, le=3, description="강점 수준 (1-3)")
    strengthsLevelDescription: str | None = Field(
        None, description="강점 수준 설명 (예: '타인의 감정을 잘 헤아리고...')"
    )

    # 난점 (외현화 + 내현화)
    difficultiesScore: int | None = Field(None, ge=0, le=40, description="난점 총점")
    difficultiesLevel: int | None = Field(None, ge=1, le=3, description="난점 수준 (1-3)")
    difficultiesLevelDescription: str | None = Field(
        None, description="난점 수준 설명 (예: '또래관계와 감정, 행동의 조절에...')"
    )

    # 하위 호환성을 위한 별칭 프로퍼티
    @property
    def strengths_level_text(self) -> str:
        """강점 수준 텍스트."""
        level_map = {1: "양호", 2: "경계선", 3: "주의 필요"}
        return level_map.get(self.strengthsLevel or 0, "미정")

    @property
    def difficulties_level_text(self) -> str:
        """난점 수준 텍스트."""
        level_map = {1: "양호", 2: "경계선", 3: "주의 필요"}
        return level_map.get(self.difficultiesLevel or 0, "미정")


# =============================================================================
# 첨부 검사 결과 모델
# =============================================================================


class KprcTScores(BaseModel):
    """KPRC T점수 (GPT Vision으로 PDF에서 추출).

    바우처 추천 대상 판별 기준:
    - ERS ≤ 30T (자아탄력성 - 낮을수록 위험)
    - 나머지 12개 척도 중 하나라도 ≥ 65T
    """

    ers_t_score: int | None = Field(None, description="자아탄력성 T점수 (≤30T 위험)")
    icn_t_score: int | None = Field(None, description="비일관성 T점수")
    f_t_score: int | None = Field(None, description="비전형 T점수")
    vdl_t_score: int | None = Field(None, description="자기보호 T점수")
    pdl_t_score: int | None = Field(None, description="타인보호 T점수")
    anx_t_score: int | None = Field(None, description="불안 T점수")
    dep_t_score: int | None = Field(None, description="우울 T점수")
    som_t_score: int | None = Field(None, description="신체화 T점수")
    dlq_t_score: int | None = Field(None, description="비행 T점수")
    hpr_t_score: int | None = Field(None, description="과잉행동 T점수")
    fam_t_score: int | None = Field(None, description="가족관계 T점수")
    soc_t_score: int | None = Field(None, description="사회관계 T점수")
    psy_t_score: int | None = Field(None, description="정신증 T점수")


class VoucherCriteria(BaseModel):
    """바우처 기준 충족 정보."""

    meets_criteria: bool = Field(..., description="바우처 기준 충족 여부")
    risk_scales: list[str] = Field(
        default_factory=list, description="기준 충족 척도 목록 (예: ['ERS', 'ANX'])"
    )


class SdqScaleScore(BaseModel):
    """SDQ-A 강점/난점 개별 점수."""

    score: int | None = Field(None, description="점수")
    maxScore: int | None = Field(None, description="만점")
    level: int | None = Field(None, ge=1, le=3, description="수준 (1: 양호, 2: 경계선, 3: 위험)")
    levelDescription: str | None = Field(None, description="수준 설명")


class SdqScaleScores(BaseModel):
    """SDQ-A 강점/난점 분리 점수.

    - 강점 (사회지향 행동): 0-10점
    - 난점 (외현화+내현화): 0-40점
    """

    strengths: SdqScaleScore | None = Field(None, description="강점 점수 (0-10점)")
    difficulties: SdqScaleScore | None = Field(None, description="난점 점수 (0-40점)")


class AttachedAssessment(BaseModel):
    """첨부된 개별 검사 결과 정보."""

    assessmentType: str = Field(..., description="검사 유형 (KPRC_CO_SG_E, CRTES_R, SDQ_A)")
    assessmentName: str = Field(..., description="검사명 (예: KPRC 인성평정척도)")
    reportS3Key: str | None = Field(None, description="검사 결과 PDF S3 키 (KPRC만 있음, CRTES-R/SDQ-A는 없음)")
    resultId: str = Field(..., description="검사 결과 ID")
    totalScore: int | None = Field(None, description="총점")
    maxScore: int | None = Field(None, description="만점")
    overallLevel: Literal["normal", "caution", "clinical"] | None = Field(
        None, description="전반적 수준"
    )
    scoredAt: str | None = Field(None, description="채점 일시")
    summary: BaseAssessmentSummary | None = Field(None, description="AI 생성 요약")
    # KPRC T점수 (GPT Vision 추출 결과)
    kprcTScores: KprcTScores | None = Field(None, description="KPRC T점수 (바우처 판별용)")
    voucherCriteria: VoucherCriteria | None = Field(None, description="바우처 기준 충족 정보")
    # SDQ-A scaleScores (강점/난점 분리 점수)
    sdqScaleScores: SdqScaleScores | None = Field(None, description="SDQ-A 강점/난점 점수")


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


# =============================================================================
# AI 대화 분석 모델
# =============================================================================


class ConversationAnalysis(BaseModel):
    """Soul-E AI 대화 분석 결과.

    새 문서 포맷의 '4.2 AI 기반 아동 마음건강 대화 분석 요약' 섹션에서 사용됩니다.
    """

    # 3줄 요약 (예이린 스타일)
    summaryLines: list[str] | None = Field(
        None, description="3줄 요약 (긍정적 특성/관심 영역/기대 성장)"
    )

    # 전문가 종합 분석 (3-4문장)
    expertAnalysis: str | None = Field(
        None, description="전문가 종합 분석 (3-4문장)"
    )

    # 주요 관찰 사항
    keyObservations: list[str] | None = Field(
        None, description="대화에서 발견된 주요 특성 (2-3가지)"
    )

    # 정서 상태 키워드
    emotionalKeywords: list[str] | None = Field(
        None, description="정서 상태 키워드 (예: 불안, 또래갈등)"
    )

    # 권장 상담 영역
    recommendedFocusAreas: list[str] | None = Field(
        None, description="권장 상담 영역 (2-3가지)"
    )

    # 분석 신뢰도
    confidenceScore: float | None = Field(
        None, ge=0.0, le=1.0, description="분석 신뢰도 (0.0 ~ 1.0)"
    )

    # 대화 세션/메시지 수 (참고용)
    sessionCount: int | None = Field(None, description="대화 세션 수")
    messageCount: int | None = Field(None, description="대화 메시지 수")


class VoucherEligibilityResult(BaseModel):
    """바우처 추천 대상 통합 판별 결과.

    3개 검사(KPRC, SDQ-A, CRTES-R) 중 하나라도 기준 충족 시 추천 대상입니다.

    바우처 기준:
    - KPRC: ERS ≤30T 또는 10개 척도 중 ≥65T (ICN, F 제외)
    - SDQ-A: 강점 ≤4점 (level 2) 또는 난점 ≥17점 (level 2)
    - CRTES-R: 총점 ≥23점 (중등도군 이상)
    """

    is_eligible: bool = Field(..., description="바우처 추천 대상 여부 (OR 조건)")
    eligible_assessments: list[str] = Field(
        default_factory=list, description="기준 충족 검사 목록 (KPRC, SDQ_A, CRTES_R)"
    )
    kprc_eligible: bool | None = Field(None, description="KPRC 기준 충족 여부")
    kprc_risk_scales: list[str] | None = Field(None, description="KPRC 위험 척도 목록")
    sdq_a_eligible: bool | None = Field(None, description="SDQ-A 기준 충족 여부")
    sdq_a_reason: str | None = Field(None, description="SDQ-A 충족 사유 (강점/난점)")
    crtes_r_eligible: bool | None = Field(None, description="CRTES-R 기준 충족 여부")
    crtes_r_score: int | None = Field(None, description="CRTES-R 총점")


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

    # Soul-E AI 대화 분석 결과 (새 문서 포맷)
    conversationAnalysis: ConversationAnalysis | None = Field(
        None, description="AI 대화 분석 결과 (섹션 4.2)"
    )

    # 바우처 추천 대상 통합 판별 결과 (서비스 레이어에서 설정)
    voucher_eligibility: VoucherEligibilityResult | None = Field(
        None, description="바우처 추천 대상 통합 판별 결과 (KPRC, SDQ-A, CRTES-R 통합)"
    )

    def get_assessment_pdfs_s3_keys(self) -> list[tuple[str, str]]:
        """모든 검사 결과 PDF의 S3 키를 반환합니다.

        CRTES-R, SDQ-A는 PDF가 없으므로 제외됩니다.

        Returns:
            (검사 유형, S3 키) 튜플 리스트
        """
        s3_keys: list[tuple[str, str]] = []

        # 새 방식: attached_assessments 사용 (PDF가 있는 것만)
        if self.attached_assessments:
            for assessment in self.attached_assessments:
                if assessment.reportS3Key:
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
        # 새 방식: attached_assessments에서 KPRC 찾기 (자가보고형/교사평정형 모두 지원)
        if self.attached_assessments:
            for assessment in self.attached_assessments:
                if assessment.assessmentType.startswith("KPRC") and assessment.summary:
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
                    "priorityReasons": ["BASIC_LIVELIHOOD", "SINGLE_PARENT"],
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
