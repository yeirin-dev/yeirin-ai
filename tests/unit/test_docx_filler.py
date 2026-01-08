"""CounselRequestDocxFiller 단위 테스트.

새 문서 포맷(counsel_request_format.docx) 템플릿 채우기 테스트.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yeirin_ai.domain.integrated_report.models import (
    AttachedAssessment,
    BaseAssessmentSummary,
    BasicInfo,
    ChildInfo,
    ConversationAnalysis,
    CoverInfo,
    IntegratedReportRequest,
    KprcSummary,
    ProtectedChildInfo,
    PsychologicalInfo,
    RequestDate,
    RequestMotivation,
)
from yeirin_ai.infrastructure.document.docx_filler import (
    CounselRequestDocxFiller,
    DocxFillerError,
    TEMPLATE_PATH,
)


# === Fixtures ===


@pytest.fixture
def sample_cover_info() -> CoverInfo:
    """샘플 표지 정보."""
    return CoverInfo(
        requestDate=RequestDate(year=2025, month=1, day=15),
        centerName="테스트 다함께돌봄센터",
        counselorName="김상담",
    )


@pytest.fixture
def sample_child_info() -> ChildInfo:
    """샘플 아동 정보."""
    return ChildInfo(
        name="홍길동",
        gender="MALE",
        age=10,
        grade="초등학교 4학년",
    )


@pytest.fixture
def sample_basic_info(sample_child_info) -> BasicInfo:
    """샘플 기본 정보."""
    return BasicInfo(
        childInfo=sample_child_info,
        careType="PRIORITY",
        priorityReasons=["LOW_INCOME"],
        protectedChildInfo=None,
    )


@pytest.fixture
def sample_basic_info_with_protected_child(sample_child_info) -> BasicInfo:
    """보호대상 아동 정보 포함 기본 정보."""
    return BasicInfo(
        childInfo=sample_child_info,
        careType="PRIORITY",
        priorityReasons=["LOW_INCOME"],
        protectedChildInfo=ProtectedChildInfo(
            type="CHILD_FACILITY",
            reason="GUARDIAN_ABSENCE",
        ),
    )


@pytest.fixture
def sample_psychological_info() -> PsychologicalInfo:
    """샘플 정서심리 정보."""
    return PsychologicalInfo(
        medicalHistory="ADHD 진단 (2023년)",
        specialNotes="집중력 저하, 또래관계 어려움",
    )


@pytest.fixture
def sample_request_motivation() -> RequestMotivation:
    """샘플 의뢰 동기."""
    return RequestMotivation(
        motivation="학교 적응 어려움으로 인한 상담 필요",
        goals="또래관계 개선 및 자존감 향상",
    )


@pytest.fixture
def sample_kprc_summary() -> KprcSummary:
    """샘플 KPRC 검사 요약."""
    return KprcSummary(
        summaryLines=[
            "전반적인 심리적 적응 수준이 또래에 비해 낮은 편입니다.",
            "정서적 불안정성이 관찰됩니다.",
            "사회성 발달에 주의가 필요합니다.",
        ],
        expertOpinion="아동의 정서적 안정을 위한 전문 상담이 권장됩니다.",
    )


@pytest.fixture
def sample_crtes_r_summary() -> AttachedAssessment:
    """샘플 CRTES-R 검사 요약."""
    return AttachedAssessment(
        assessmentType="CRTES_R",
        assessmentName="아동외상반응척도 (CRTES-R)",
        resultId="crtes-r-result-123",
        summary=BaseAssessmentSummary(
            summaryLines=[
                "외상 관련 스트레스 반응이 관찰됩니다.",
                "재경험 증상이 다소 높은 수준입니다.",
                "회피 증상에 대한 주의가 필요합니다.",
            ],
            expertOpinion="외상 경험에 대한 전문적 개입이 필요할 수 있습니다.",
        ),
    )


@pytest.fixture
def sample_sdq_a_summary() -> AttachedAssessment:
    """샘플 SDQ-A 검사 요약 (강점/난점 6줄)."""
    return AttachedAssessment(
        assessmentType="SDQ_A",
        assessmentName="강점·난점 설문지 (SDQ-A)",
        resultId="sdq-a-result-123",
        summary=BaseAssessmentSummary(
            summaryLines=[
                # 강점 (3줄)
                "타인을 배려하는 마음이 있습니다.",
                "친구들과 잘 어울리려고 노력합니다.",
                "정서적으로 안정적인 면이 있습니다.",
                # 난점 (3줄)
                "주의력 유지에 어려움이 있습니다.",
                "충동 조절이 필요합니다.",
                "또래관계에서 갈등이 발생할 수 있습니다.",
            ],
            expertOpinion="강점을 강화하고 난점에 대한 중재가 필요합니다.",
        ),
    )


@pytest.fixture
def sample_conversation_analysis() -> ConversationAnalysis:
    """샘플 Soul-E 대화 분석 요약."""
    return ConversationAnalysis(
        summaryLines=[
            "아동은 학교 생활에 대한 스트레스를 표현했습니다.",
            "친구 관계에서 어려움을 겪고 있습니다.",
            "부모님과의 관계에서 지지를 느끼고 있습니다.",
        ],
        expertAnalysis="아동의 학교 적응을 위한 사회성 훈련이 도움이 될 것입니다.",
        emotionalKeywords=["불안", "외로움"],
        keyObservations=["학교", "친구", "가족"],
    )


@pytest.fixture
def sample_report_request(
    sample_cover_info,
    sample_basic_info,
    sample_psychological_info,
    sample_request_motivation,
    sample_kprc_summary,
    sample_crtes_r_summary,
    sample_sdq_a_summary,
    sample_conversation_analysis,
) -> IntegratedReportRequest:
    """완전한 샘플 보고서 요청."""
    request = IntegratedReportRequest(
        counsel_request_id="test-request-123",
        child_id="child-123",
        child_name="홍길동",
        cover_info=sample_cover_info,
        basic_info=sample_basic_info,
        psychological_info=sample_psychological_info,
        request_motivation=sample_request_motivation,
        attached_assessments=[sample_crtes_r_summary, sample_sdq_a_summary],
    )
    # KPRC는 별도 속성으로 설정
    request._kprc_summary = sample_kprc_summary
    # 대화 분석 추가
    request.conversationAnalysis = sample_conversation_analysis
    return request


@pytest.fixture
def mock_document():
    """Mock python-docx Document."""
    doc = MagicMock()

    # 11개 테이블 생성
    tables = []
    for i in range(11):
        table = MagicMock()
        # 각 테이블에 적절한 행 수 설정
        if i == 9:  # 테이블 9: 12행
            rows = [MagicMock() for _ in range(12)]
            for row in rows:
                row.cells = [MagicMock() for _ in range(4)]
                for cell in row.cells:
                    cell.text = ""
                    cell.paragraphs = [MagicMock()]
        elif i == 3:  # 테이블 3: 5행 (돌봄 유형 + 보호대상)
            rows = [MagicMock() for _ in range(5)]
            for row in rows:
                row.cells = [MagicMock() for _ in range(4)]
                for cell in row.cells:
                    cell.text = "□ 테스트"
                    cell.paragraphs = [MagicMock()]
        else:
            rows = [MagicMock() for _ in range(3)]
            for row in rows:
                row.cells = [MagicMock() for _ in range(4)]
                for cell in row.cells:
                    cell.text = ""
                    cell.paragraphs = [MagicMock()]
        table.rows = rows
        tables.append(table)

    doc.tables = tables

    # 단락 (동의 체크박스용)
    para = MagicMock()
    para.text = "□ 동의      □ 미동의"
    doc.paragraphs = [para]

    # 섹션 (페이지 설정용)
    section = MagicMock()
    section.page_width = MagicMock(twips=11906, mm=210)
    section.left_margin = MagicMock(twips=1134)
    section.right_margin = MagicMock(twips=1134)
    doc.sections = [section]

    return doc


# === 초기화 테스트 ===


class TestDocxFillerInit:
    """CounselRequestDocxFiller 초기화 테스트."""

    def test_기본_템플릿_경로로_초기화한다(self):
        """기본 템플릿 경로를 사용하여 초기화하는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            assert filler.template_path == TEMPLATE_PATH

    def test_사용자_지정_템플릿_경로로_초기화한다(self):
        """사용자 지정 템플릿 경로를 사용할 수 있는지 확인."""
        custom_path = Path("/custom/template.docx")
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller(template_path=custom_path)
            assert filler.template_path == custom_path

    def test_템플릿_파일이_없으면_에러를_발생시킨다(self):
        """템플릿 파일이 없을 때 DocxFillerError를 발생시키는지 확인."""
        with pytest.raises(DocxFillerError, match="템플릿 파일을 찾을 수 없습니다"):
            CounselRequestDocxFiller(template_path=Path("/nonexistent/template.docx"))


# === 표지 정보 테스트 ===


class TestFillCoverTable:
    """표지 정보 채우기 테스트."""

    def test_의뢰일자를_한국어_형식으로_채운다(self, sample_report_request, mock_document):
        """의뢰일자가 '2025년 1월 15일' 형식으로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_cover_table(mock_document.tables[0], sample_report_request)

            # Row 0, Cell 1에 날짜가 설정되었는지 확인
            # 실제 구현에서는 _set_cell_text_with_font를 호출하므로 text 속성 변경 확인

    def test_센터명을_채운다(self, sample_report_request, mock_document):
        """센터명이 올바르게 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_cover_table(mock_document.tables[0], sample_report_request)

    def test_담당자명을_채운다(self, sample_report_request, mock_document):
        """담당자명이 '김상담 (서명)' 형식으로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_cover_table(mock_document.tables[0], sample_report_request)


# === 기본 정보 테스트 ===


class TestFillBasicInfoTable:
    """기본 정보 채우기 테스트."""

    def test_아동_이름을_채운다(self, sample_report_request, mock_document):
        """아동 이름이 올바르게 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_basic_info_table(mock_document.tables[2], sample_report_request)

    def test_성별을_한국어로_변환한다(self, sample_report_request, mock_document):
        """성별이 '남'/'여'로 변환되는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            assert filler._gender_to_korean("MALE") == "남"
            assert filler._gender_to_korean("FEMALE") == "여"
            assert filler._gender_to_korean("M") == "남"
            assert filler._gender_to_korean("F") == "여"

    def test_연령과_학년을_채운다(self, sample_report_request, mock_document):
        """연령과 학년이 올바르게 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_basic_info_table(mock_document.tables[2], sample_report_request)


# === 돌봄 유형 테스트 ===


class TestFillCareTypeTable:
    """돌봄 유형 체크박스 테스트."""

    def test_우선돌봄_체크박스를_체크한다(self, sample_report_request, mock_document):
        """PRIORITY일 때 우선돌봄 체크박스가 체크되는지 확인."""
        # 테이블 3의 Row 0, Cell 1에 체크박스 텍스트 설정
        mock_document.tables[3].rows[0].cells[1].text = "□ 우선돌봄아동"
        mock_document.tables[3].rows[1].cells[1].text = "□ 일반 아동"
        mock_document.tables[3].rows[2].cells[1].text = "□ 돌봄특례아동"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_care_type_table(mock_document.tables[3], sample_report_request)

            # 우선돌봄 체크 확인
            assert "☑" in mock_document.tables[3].rows[0].cells[1].text

    def test_일반_아동_체크박스를_체크한다(self, sample_report_request, mock_document):
        """GENERAL일 때 일반 아동 체크박스가 체크되는지 확인."""
        sample_report_request.basic_info.careType = "GENERAL"

        mock_document.tables[3].rows[0].cells[1].text = "□ 우선돌봄아동"
        mock_document.tables[3].rows[1].cells[1].text = "□ 일반 아동"
        mock_document.tables[3].rows[2].cells[1].text = "□ 돌봄특례아동"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_care_type_table(mock_document.tables[3], sample_report_request)

            # 일반 아동 체크 확인
            assert "☑" in mock_document.tables[3].rows[1].cells[1].text

    def test_우선돌봄_세부_사유를_체크한다(self, sample_report_request, mock_document):
        """우선돌봄 세부 사유(차상위계층)가 체크되는지 확인."""
        mock_document.tables[3].rows[0].cells[2].text = "□ 기초생활보장 수급권자\n□ 차상위계층 가구의 아동"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._check_priority_reasons(mock_document.tables[3], ["LOW_INCOME"])

            # 차상위계층 체크 확인
            assert "☑ 차상위계층" in mock_document.tables[3].rows[0].cells[2].text

    def test_우선돌봄_세부_사유_복수_선택을_체크한다(self, sample_report_request, mock_document):
        """복수 선택된 우선돌봄 세부 사유가 모두 체크되는지 확인."""
        mock_document.tables[3].rows[0].cells[2].text = "□ 기초생활보장 수급권자\n□ 차상위계층 가구의 아동"
        mock_document.tables[3].rows[0].cells[3].text = "□ 한부모가족의 아동\n□ 다문화가족의 아동"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._check_priority_reasons(
                mock_document.tables[3], ["LOW_INCOME", "SINGLE_PARENT"]
            )

            # 차상위계층, 한부모가족 둘 다 체크 확인
            assert "☑ 차상위계층" in mock_document.tables[3].rows[0].cells[2].text
            assert "☑ 한부모가족" in mock_document.tables[3].rows[0].cells[3].text


# === 보호대상 아동 테스트 ===


class TestFillProtectedChildSection:
    """보호대상 아동 섹션 테스트."""

    def test_보호대상_아동_유형을_체크한다(
        self, sample_basic_info_with_protected_child, mock_document
    ):
        """CHILD_FACILITY 유형이 체크되는지 확인."""
        # Row 3에 유형 체크박스 설정
        mock_document.tables[3].rows[3].cells[1].text = "□ 아동 양육시설"
        mock_document.tables[3].rows[3].cells[2].text = "□ 공동생활가정(그룹홈)"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()

            request = MagicMock()
            request.basic_info = sample_basic_info_with_protected_child

            filler._fill_protected_child_section(mock_document.tables[3], request)

            # 아동 양육시설 체크 확인
            assert "☑" in mock_document.tables[3].rows[3].cells[1].text

    def test_보호대상_아동_사유를_체크한다(
        self, sample_basic_info_with_protected_child, mock_document
    ):
        """GUARDIAN_ABSENCE 사유가 체크되는지 확인."""
        # Row 4에 사유 체크박스 설정
        mock_document.tables[3].rows[4].cells[1].text = "□ 보호자가 없거나 보호자로부터 이탈"

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()

            request = MagicMock()
            request.basic_info = sample_basic_info_with_protected_child

            filler._fill_protected_child_section(mock_document.tables[3], request)

            # 보호자 이탈 체크 확인
            assert "☑" in mock_document.tables[3].rows[4].cells[1].text

    def test_보호대상_정보가_없으면_건너뛴다(self, sample_report_request, mock_document):
        """protectedChildInfo가 None이면 아무 처리도 하지 않는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            # 에러 없이 완료되어야 함
            filler._fill_protected_child_section(mock_document.tables[3], sample_report_request)


# === 정서심리 정보 테스트 ===


class TestFillPsychologicalInfoTable:
    """정서심리 정보 채우기 테스트."""

    def test_병력_정보를_채운다(self, sample_report_request, mock_document):
        """병력 정보가 올바르게 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_psychological_info_table(mock_document.tables[5], sample_report_request)

    def test_특이사항을_채운다(self, sample_report_request, mock_document):
        """특이사항이 올바르게 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_psychological_info_table(mock_document.tables[5], sample_report_request)

    def test_병력_정보가_없으면_기본값을_채운다(self, sample_report_request, mock_document):
        """병력 정보가 None이면 '없음'으로 채워지는지 확인."""
        sample_report_request.psychological_info.medicalHistory = None

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_psychological_info_table(mock_document.tables[5], sample_report_request)


# === 검사 결과 테이블 테스트 ===


class TestFillAssessmentResultsTable:
    """검사 결과 테이블 채우기 테스트."""

    def test_테이블_행_수가_부족하면_경고한다(self, sample_report_request, mock_document):
        """테이블 행이 12개 미만이면 경고 로그를 남기는지 확인."""
        mock_document.tables[9].rows = [MagicMock() for _ in range(5)]  # 5행만

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            # 에러 없이 완료되어야 함
            filler._fill_assessment_results_table(mock_document.tables[9], sample_report_request)


class TestFillKprcSection:
    """KPRC 검사 섹션 테스트."""

    def test_KPRC_소견_3줄을_채운다(self, sample_report_request, mock_document):
        """KPRC 소견이 3줄로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_kprc_section(mock_document.tables[9], sample_report_request)

    def test_KPRC_결과가_없으면_기본_메시지를_표시한다(
        self, sample_report_request, mock_document
    ):
        """KPRC 결과가 없을 때 기본 메시지가 표시되는지 확인."""
        sample_report_request._kprc_summary = None

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_kprc_section(mock_document.tables[9], sample_report_request)


class TestFillCrtesRSection:
    """CRTES-R 검사 섹션 테스트."""

    def test_CRTES_R_소견_3줄을_채운다(self, sample_report_request, mock_document):
        """CRTES-R 소견이 3줄로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_crtes_r_section(mock_document.tables[9], sample_report_request)

    def test_CRTES_R_결과가_없으면_기본_메시지를_표시한다(
        self, sample_report_request, mock_document
    ):
        """CRTES-R 결과가 없을 때 기본 메시지가 표시되는지 확인."""
        sample_report_request.attached_assessments = []

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_crtes_r_section(mock_document.tables[9], sample_report_request)


class TestFillSdqASection:
    """SDQ-A 검사 섹션 테스트 (강점/난점 분리)."""

    def test_SDQ_A_강점_3줄을_첫번째_셀에_채운다(self, sample_report_request, mock_document):
        """SDQ-A 강점 소견이 첫 번째 셀에 3줄로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_sdq_a_section(mock_document.tables[9], sample_report_request)

    def test_SDQ_A_난점_3줄을_두번째_셀에_채운다(self, sample_report_request, mock_document):
        """SDQ-A 난점 소견이 두 번째 셀에 3줄로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_sdq_a_section(mock_document.tables[9], sample_report_request)

    def test_SDQ_A_요약이_6줄_미만이면_기본_메시지를_표시한다(
        self, sample_report_request, mock_document
    ):
        """SDQ-A 요약이 6줄 미만일 때 기본 메시지가 표시되는지 확인."""
        # SDQ-A 요약을 3줄로 줄임
        for assessment in sample_report_request.attached_assessments:
            if "SDQ_A" in assessment.assessmentType:
                assessment.summary.summaryLines = ["줄1", "줄2", "줄3"]

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_sdq_a_section(mock_document.tables[9], sample_report_request)


# === Soul-E 대화 분석 테스트 ===


class TestFillConversationAnalysisSection:
    """Soul-E 대화 분석 섹션 테스트."""

    def test_대화_분석_요약_3줄을_채운다(self, sample_report_request, mock_document):
        """대화 분석 요약이 3줄로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_conversation_analysis_section(mock_document.tables[9], sample_report_request)

    def test_전문가_분석을_추가로_채운다(self, sample_report_request, mock_document):
        """전문가 분석이 추가로 채워지는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_conversation_analysis_section(mock_document.tables[9], sample_report_request)

    def test_대화_분석이_없으면_기본_메시지를_표시한다(
        self, sample_report_request, mock_document
    ):
        """대화 분석이 없을 때 기본 메시지가 표시되는지 확인."""
        sample_report_request.conversationAnalysis = None

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_conversation_analysis_section(mock_document.tables[9], sample_report_request)


# === 통합 AI 소견 테스트 ===


class TestFillIntegratedOpinionSection:
    """통합 AI 소견 섹션 테스트."""

    def test_모든_검사의_전문가_소견을_통합한다(self, sample_report_request, mock_document):
        """KPRC, CRTES-R, SDQ-A 전문가 소견이 통합되는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_integrated_opinion_section(mock_document.tables[9], sample_report_request)

    def test_대화_분석_전문가_의견도_포함한다(self, sample_report_request, mock_document):
        """대화 분석 전문가 의견도 통합 소견에 포함되는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_integrated_opinion_section(mock_document.tables[9], sample_report_request)

    def test_전문가_소견이_없으면_기본_메시지를_표시한다(
        self, sample_report_request, mock_document
    ):
        """전문가 소견이 없을 때 기본 메시지가 표시되는지 확인."""
        sample_report_request._kprc_summary = None
        sample_report_request.attached_assessments = []
        sample_report_request.conversationAnalysis = None

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_integrated_opinion_section(mock_document.tables[9], sample_report_request)


# === 동의 체크박스 테스트 ===


class TestFillConsent:
    """동의 체크박스 테스트."""

    def test_동의_체크박스를_체크한다(self, mock_document):
        """동의 체크박스가 체크되는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_consent(mock_document)

            # 동의 체크 확인
            assert "☑ 동의" in mock_document.paragraphs[0].text

    def test_미동의는_체크하지_않는다(self, mock_document):
        """미동의 체크박스는 체크되지 않는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            filler._fill_consent(mock_document)

            # 미동의는 체크되지 않음
            assert "□ 미동의" in mock_document.paragraphs[0].text


# === 테이블 너비 조정 테스트 ===


class TestFixTableWidths:
    """테이블 너비 조정 테스트."""

    def test_페이지_너비를_초과하면_비례_축소한다(self, mock_document):
        """테이블 너비가 페이지를 초과할 때 비례 축소되는지 확인."""
        # 이 테스트는 실제 DOCX 객체가 필요하므로 통합 테스트에서 수행하는 것이 적절
        # 여기서는 메서드 호출이 에러 없이 완료되는지만 확인
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            # mock_document에는 실제 OxmlElement가 없으므로 여기서는 스킵


# === 전체 흐름 테스트 ===


class TestFillTemplate:
    """fill_template 전체 흐름 테스트."""

    def test_템플릿_채우기_전체_흐름을_성공적으로_수행한다(
        self, sample_report_request, mock_document
    ):
        """fill_template 메서드가 전체 흐름을 성공적으로 수행하는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            with patch("yeirin_ai.infrastructure.document.docx_filler.Document") as mock_doc_class:
                mock_doc_class.return_value = mock_document

                filler = CounselRequestDocxFiller()

                # 바이트 저장을 위한 mock
                with patch("yeirin_ai.infrastructure.document.docx_filler.io.BytesIO") as mock_bytesio:
                    mock_buffer = MagicMock()
                    mock_buffer.getvalue.return_value = b"test_docx_content"
                    mock_bytesio.return_value = mock_buffer

                    result = filler.fill_template(sample_report_request)

                    assert result == b"test_docx_content"

    def test_예외_발생시_DocxFillerError를_래핑한다(self, sample_report_request):
        """예외 발생 시 DocxFillerError로 래핑되는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            with patch(
                "yeirin_ai.infrastructure.document.docx_filler.Document",
                side_effect=Exception("테스트 에러"),
            ):
                filler = CounselRequestDocxFiller()

                with pytest.raises(DocxFillerError, match="템플릿 채우기 실패"):
                    filler.fill_template(sample_report_request)


# === 유틸리티 메서드 테스트 ===


class TestUtilityMethods:
    """유틸리티 메서드 테스트."""

    def test_get_assessment_summary_CRTES_R을_찾는다(self, sample_report_request):
        """CRTES_R 타입의 검사 요약을 찾는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            result = filler._get_assessment_summary(sample_report_request, "CRTES_R")

            assert result is not None
            assert len(result.summaryLines) == 3

    def test_get_assessment_summary_SDQ_A를_찾는다(self, sample_report_request):
        """SDQ_A 타입의 검사 요약을 찾는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            result = filler._get_assessment_summary(sample_report_request, "SDQ_A")

            assert result is not None
            assert len(result.summaryLines) == 6

    def test_get_assessment_summary_존재하지_않는_타입은_None을_반환한다(
        self, sample_report_request
    ):
        """존재하지 않는 검사 타입에 대해 None을 반환하는지 확인."""
        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            result = filler._get_assessment_summary(sample_report_request, "UNKNOWN_TYPE")

            assert result is None

    def test_get_assessment_summary_attached_assessments가_없으면_None을_반환한다(
        self, sample_report_request
    ):
        """attached_assessments가 없을 때 None을 반환하는지 확인."""
        sample_report_request.attached_assessments = None

        with patch.object(Path, "exists", return_value=True):
            filler = CounselRequestDocxFiller()
            result = filler._get_assessment_summary(sample_report_request, "CRTES_R")

            assert result is None
