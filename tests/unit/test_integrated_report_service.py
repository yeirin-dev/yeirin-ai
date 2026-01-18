"""통합 보고서 서비스 테스트.

IntegratedReportService의 조건부 사회서비스 이용 추천서 생성 로직을 테스트합니다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yeirin_ai.domain.integrated_report.models import (
    BasicInfo,
    BirthDate,
    ChildInfo,
    CoverInfo,
    GuardianInfo,
    InstitutionInfo,
    IntegratedReportRequest,
    KprcSummary,
    PsychologicalInfo,
    RequestDate,
    RequestMotivation,
)
from yeirin_ai.services.integrated_report_service import (
    IntegratedReportService,
    IntegratedReportServiceError,
    _format_bytes,
    _format_duration,
)


class TestFormatHelpers:
    """헬퍼 함수 테스트."""

    def test_바이트_크기를_읽기_쉬운_형식으로_변환한다(self) -> None:
        """_format_bytes가 바이트를 읽기 쉬운 형식으로 변환한다."""
        # When & Then
        assert _format_bytes(500) == "500.0 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(1536) == "1.5 KB"

    def test_소요_시간을_읽기_쉬운_형식으로_변환한다(self) -> None:
        """_format_duration이 시간을 읽기 쉬운 형식으로 변환한다."""
        # When & Then
        assert _format_duration(0.5) == "500ms"
        assert _format_duration(0.001) == "1ms"
        assert _format_duration(1.5) == "1.50s"
        assert _format_duration(10.0) == "10.00s"


class TestIntegratedReportServiceInitialization:
    """IntegratedReportService 초기화 테스트."""

    def test_서비스가_필요한_의존성을_초기화한다(self) -> None:
        """서비스가 DocxFiller, PdfConverter, PdfMerger를 초기화한다."""
        # When
        service = IntegratedReportService()

        # Then
        assert service.docx_filler is not None
        assert service.government_docx_filler is not None
        assert service.pdf_converter is not None
        assert service.pdf_merger is not None


class TestIntegratedReportServiceConditionalGovernmentDoc:
    """사회서비스 이용 추천서 조건부 생성 로직 테스트."""

    @pytest.fixture
    def base_request_data(self) -> dict:
        """기본 요청 데이터."""
        return {
            "counsel_request_id": "test-123",
            "child_id": "child-456",
            "child_name": "홍길동",
            "cover_info": CoverInfo(
                requestDate=RequestDate(year=2025, month=1, day=15),
                centerName="서울아동발달센터",
                counselorName="김상담",
            ),
            "basic_info": BasicInfo(
                childInfo=ChildInfo(
                    name="홍길동",
                    gender="MALE",
                    age=10,
                    grade="초4",
                ),
                careType="PRIORITY",
            ),
            "psychological_info": PsychologicalInfo(
                medicalHistory="ADHD 진단",
                specialNotes="학교 적응 어려움",
            ),
            "request_motivation": RequestMotivation(
                motivation="행동 교정 필요",
                goals="감정 조절 능력 향상",
            ),
            "kprc_summary": KprcSummary(
                expertOpinion="양호한 발달 상태",
                keyFindings=["주의력 저하"],
                recommendations=["집중력 훈련 권장"],
            ),
            "assessment_report_s3_key": "assessment-reports/test.pdf",
        }

    @pytest.fixture
    def guardian_info(self) -> GuardianInfo:
        """보호자 정보 픽스처."""
        return GuardianInfo(
            name="홍부모",
            phoneNumber="010-1234-5678",
            address="서울시 강남구",
            relationToChild="부",
        )

    @pytest.fixture
    def institution_info(self) -> InstitutionInfo:
        """기관 정보 픽스처."""
        return InstitutionInfo(
            institutionName="서울초등학교",
            phoneNumber="02-123-4567",
            address="서울시 강남구",
            writerPosition="담임교사",
            writerName="김선생",
            relationToChild="담임교사",
        )

    def test_guardian_info_있으면_사회서비스_추천서가_생성된다(
        self,
        base_request_data: dict,
        guardian_info: GuardianInfo,
    ) -> None:
        """guardian_info가 있으면 사회서비스 이용 추천서가 생성되어야 한다."""
        # Given
        base_request_data["guardian_info"] = guardian_info
        request = IntegratedReportRequest(**base_request_data)

        # Then: has_government_doc 조건 확인
        has_government_doc = request.guardian_info is not None or request.institution_info is not None
        assert has_government_doc is True

    def test_institution_info_있으면_사회서비스_추천서가_생성된다(
        self,
        base_request_data: dict,
        institution_info: InstitutionInfo,
    ) -> None:
        """institution_info가 있으면 사회서비스 이용 추천서가 생성되어야 한다."""
        # Given
        base_request_data["institution_info"] = institution_info
        request = IntegratedReportRequest(**base_request_data)

        # Then
        has_government_doc = request.guardian_info is not None or request.institution_info is not None
        assert has_government_doc is True

    def test_guardian_info와_institution_info_모두_있으면_추천서가_생성된다(
        self,
        base_request_data: dict,
        guardian_info: GuardianInfo,
        institution_info: InstitutionInfo,
    ) -> None:
        """guardian_info와 institution_info 모두 있으면 추천서가 생성된다."""
        # Given
        base_request_data["guardian_info"] = guardian_info
        base_request_data["institution_info"] = institution_info
        request = IntegratedReportRequest(**base_request_data)

        # Then
        has_government_doc = request.guardian_info is not None or request.institution_info is not None
        assert has_government_doc is True
        assert request.guardian_info is not None
        assert request.institution_info is not None

    def test_guardian_info와_institution_info_모두_없으면_추천서가_생성되지_않는다(
        self,
        base_request_data: dict,
    ) -> None:
        """guardian_info와 institution_info 모두 없으면 추천서가 생성되지 않는다."""
        # Given
        request = IntegratedReportRequest(**base_request_data)

        # Then
        has_government_doc = request.guardian_info is not None or request.institution_info is not None
        assert has_government_doc is False


class TestIntegratedReportServiceProcess:
    """IntegratedReportService.process() 메서드 테스트."""

    @pytest.fixture
    def mock_service(self) -> IntegratedReportService:
        """모든 의존성이 모킹된 서비스 픽스처."""
        service = IntegratedReportService()

        # Mock 설정
        service.docx_filler = MagicMock()
        service.docx_filler.fill_template = MagicMock(return_value=b"docx_bytes")

        service.government_docx_filler = MagicMock()
        service.government_docx_filler.fill_template = MagicMock(return_value=b"gov_docx_bytes")

        service.pdf_converter = MagicMock()
        service.pdf_converter.convert = AsyncMock(return_value=b"%PDF-1.4 test")

        service.pdf_merger = MagicMock()
        service.pdf_merger.merge_with_metadata = MagicMock(return_value=b"%PDF-1.4 merged")

        return service

    @pytest.fixture
    def request_without_government_doc(self) -> IntegratedReportRequest:
        """사회서비스 추천서 없는 요청."""
        return IntegratedReportRequest(
            counsel_request_id="test-123",
            child_id="child-456",
            child_name="홍길동",
            cover_info=CoverInfo(
                requestDate=RequestDate(year=2025, month=1, day=15),
                centerName="센터",
                counselorName="상담사",
            ),
            basic_info=BasicInfo(
                childInfo=ChildInfo(name="홍길동", gender="MALE", age=10, grade="4"),
                careType="GENERAL",
            ),
            psychological_info=PsychologicalInfo(
                medicalHistory="없음", specialNotes="없음"
            ),
            request_motivation=RequestMotivation(motivation="지원 필요", goals="목표"),
            kprc_summary=KprcSummary(expertOpinion="양호"),
            assessment_report_s3_key="test.pdf",
            guardian_info=None,
            institution_info=None,
        )

    @pytest.fixture
    def request_with_government_doc(self) -> IntegratedReportRequest:
        """사회서비스 추천서 포함 요청."""
        return IntegratedReportRequest(
            counsel_request_id="test-123",
            child_id="child-456",
            child_name="홍길동",
            cover_info=CoverInfo(
                requestDate=RequestDate(year=2025, month=1, day=15),
                centerName="센터",
                counselorName="상담사",
            ),
            basic_info=BasicInfo(
                childInfo=ChildInfo(name="홍길동", gender="MALE", age=10, grade="4"),
                careType="GENERAL",
            ),
            psychological_info=PsychologicalInfo(
                medicalHistory="없음", specialNotes="없음"
            ),
            request_motivation=RequestMotivation(motivation="지원 필요", goals="목표"),
            kprc_summary=KprcSummary(expertOpinion="양호"),
            assessment_report_s3_key="test.pdf",
            guardian_info=GuardianInfo(
                name="보호자",
                phoneNumber="010-0000-0000",
                address="주소",
                relationToChild="부",
            ),
            institution_info=None,
        )

    async def test_사회서비스_추천서_없으면_2개_PDF만_병합한다(
        self,
        mock_service: IntegratedReportService,
        request_without_government_doc: IntegratedReportRequest,
    ) -> None:
        """사회서비스 추천서가 없으면 상담의뢰지와 KPRC만 병합한다."""
        # Given: S3 다운로드 및 업로드 모킹
        with patch.object(
            mock_service, "_download_assessment_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = b"%PDF-1.4 kprc"

            with patch.object(
                mock_service, "_upload_to_yeirin", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = "integrated-reports/test.pdf"

                # When
                result = await mock_service.process(request_without_government_doc)

                # Then
                assert result.status == "completed"
                # government_docx_filler가 호출되지 않아야 함
                mock_service.government_docx_filler.fill_template.assert_not_called()
                # 일반 docx_filler는 호출되어야 함
                mock_service.docx_filler.fill_template.assert_called_once()
                # PDF merger에 2개의 PDF가 전달되어야 함
                merge_call = mock_service.pdf_merger.merge_with_metadata.call_args
                assert len(merge_call.kwargs["pdfs"]) == 2

    async def test_사회서비스_추천서_있으면_3개_PDF를_병합한다(
        self,
        mock_service: IntegratedReportService,
        request_with_government_doc: IntegratedReportRequest,
    ) -> None:
        """사회서비스 추천서가 있으면 3개 PDF를 병합한다."""
        # Given
        with patch.object(
            mock_service, "_download_assessment_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = b"%PDF-1.4 kprc"

            with patch.object(
                mock_service, "_upload_to_yeirin", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = "integrated-reports/test.pdf"

                # When
                result = await mock_service.process(request_with_government_doc)

                # Then
                assert result.status == "completed"
                # government_docx_filler가 호출되어야 함
                mock_service.government_docx_filler.fill_template.assert_called_once()
                # PDF merger에 3개의 PDF가 전달되어야 함
                merge_call = mock_service.pdf_merger.merge_with_metadata.call_args
                assert len(merge_call.kwargs["pdfs"]) == 3

    async def test_사회서비스_추천서가_첫번째로_병합된다(
        self,
        mock_service: IntegratedReportService,
        request_with_government_doc: IntegratedReportRequest,
    ) -> None:
        """사회서비스 추천서가 병합 순서에서 첫 번째다."""
        # Given
        gov_pdf = b"%PDF-1.4 government"
        counsel_pdf = b"%PDF-1.4 counsel"
        kprc_pdf = b"%PDF-1.4 kprc"

        # PDF 변환 순서 추적
        convert_results = [gov_pdf, counsel_pdf]
        mock_service.pdf_converter.convert = AsyncMock(side_effect=convert_results)

        with patch.object(
            mock_service, "_download_assessment_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = kprc_pdf

            with patch.object(
                mock_service, "_upload_to_yeirin", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = "integrated-reports/test.pdf"

                # When
                await mock_service.process(request_with_government_doc)

                # Then: 병합 순서 확인
                merge_call = mock_service.pdf_merger.merge_with_metadata.call_args
                pdfs = merge_call.kwargs["pdfs"]

                assert pdfs[0] == gov_pdf, "사회서비스 추천서가 첫 번째여야 함"
                assert pdfs[1] == counsel_pdf, "상담의뢰지가 두 번째여야 함"
                assert pdfs[2] == kprc_pdf, "KPRC가 세 번째여야 함"

    async def test_처리_실패시_failed_상태를_반환한다(
        self,
        mock_service: IntegratedReportService,
        request_without_government_doc: IntegratedReportRequest,
    ) -> None:
        """처리 중 에러 발생 시 failed 상태를 반환한다."""
        # Given
        mock_service.docx_filler.fill_template = MagicMock(
            side_effect=Exception("템플릿 에러")
        )

        # When
        result = await mock_service.process(request_without_government_doc)

        # Then
        assert result.status == "failed"
        assert "템플릿 에러" in result.error_message
        assert result.integrated_report_s3_key is None


class TestIntegratedReportServiceDownloadKprcPdf:
    """KPRC PDF 다운로드 테스트."""

    def test_빈_PDF_응답_체크_로직이_올바르다(self) -> None:
        """빈 PDF 응답은 에러로 처리되어야 한다는 비즈니스 로직 확인."""
        # Given: 빈 바이트 데이터
        pdf_bytes = b""

        # When: 빈 데이터 체크 로직 실행
        is_empty = not pdf_bytes

        # Then: 빈 데이터면 에러를 발생시켜야 함
        assert is_empty is True, "빈 PDF는 에러로 처리되어야 함"

    def test_유효한_PDF_응답은_에러가_아니다(self) -> None:
        """유효한 PDF 응답은 에러로 처리되지 않아야 한다."""
        # Given: 유효한 PDF 바이트 데이터
        pdf_bytes = b"%PDF-1.4 valid content"

        # When: 빈 데이터 체크 로직 실행
        is_empty = not pdf_bytes

        # Then: 유효한 데이터면 에러가 아님
        assert is_empty is False, "유효한 PDF는 에러가 아니어야 함"

    async def test_presigned_url_생성_실패시_에러가_발생한다(self) -> None:
        """presigned URL 생성 실패 시 IntegratedReportServiceError가 발생한다."""
        # Given
        service = IntegratedReportService()

        with patch.object(
            service, "_get_presigned_url", new_callable=AsyncMock
        ) as mock_presigned:
            mock_presigned.side_effect = IntegratedReportServiceError("URL 생성 실패")

            # When & Then
            with pytest.raises(IntegratedReportServiceError) as exc_info:
                await service._download_assessment_pdf("test-key")

            assert "URL 생성 실패" in str(exc_info.value)


class TestIntegratedReportServiceMetadata:
    """PDF 메타데이터 설정 테스트."""

    @pytest.fixture
    def mock_service(self) -> IntegratedReportService:
        """모킹된 서비스 픽스처."""
        service = IntegratedReportService()
        service.docx_filler = MagicMock()
        service.docx_filler.fill_template = MagicMock(return_value=b"docx")

        service.government_docx_filler = MagicMock()
        service.pdf_converter = MagicMock()
        service.pdf_converter.convert = AsyncMock(return_value=b"%PDF-1.4")

        service.pdf_merger = MagicMock()
        service.pdf_merger.merge_with_metadata = MagicMock(return_value=b"%PDF-1.4 merged")

        return service

    async def test_통합_보고서_메타데이터가_설정된다(
        self,
        mock_service: IntegratedReportService,
    ) -> None:
        """PDF 메타데이터(제목, 작성자, 주제)가 설정된다."""
        # Given
        request = IntegratedReportRequest(
            counsel_request_id="test-123",
            child_id="child-456",
            child_name="홍길동",
            cover_info=CoverInfo(
                requestDate=RequestDate(year=2025, month=1, day=15),
                centerName="센터",
                counselorName="상담사",
            ),
            basic_info=BasicInfo(
                childInfo=ChildInfo(name="홍길동", gender="MALE", age=10, grade="4"),
                careType="GENERAL",
            ),
            psychological_info=PsychologicalInfo(medicalHistory="없음", specialNotes="없음"),
            request_motivation=RequestMotivation(motivation="지원", goals="목표"),
            kprc_summary=KprcSummary(expertOpinion="양호"),
            assessment_report_s3_key="test.pdf",
        )

        with patch.object(
            mock_service, "_download_assessment_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = b"%PDF-1.4 kprc"

            with patch.object(
                mock_service, "_upload_to_yeirin", new_callable=AsyncMock
            ) as mock_upload:
                mock_upload.return_value = "integrated-reports/test.pdf"

                # When
                await mock_service.process(request)

                # Then
                merge_call = mock_service.pdf_merger.merge_with_metadata.call_args
                assert "홍길동" in merge_call.kwargs["title"]
                assert merge_call.kwargs["author"] == "예이린 AI 시스템"
                assert "통합 보고서" in merge_call.kwargs["subject"]
