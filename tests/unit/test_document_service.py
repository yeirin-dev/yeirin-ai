"""문서 서비스 테스트."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from yeirin_ai.domain.document.models import DocumentSummary, DocumentType
from yeirin_ai.services.document_service import DocumentService, DocumentServiceError


class TestDocumentService:
    """DocumentService 테스트."""

    @pytest.fixture
    def mock_pdf_extractor(self) -> MagicMock:
        """Mock PDF 추출기."""
        return MagicMock()

    @pytest.fixture
    def mock_summarizer(self) -> AsyncMock:
        """Mock 문서 요약기."""
        return AsyncMock()

    @pytest.fixture
    def sample_summary(self) -> DocumentSummary:
        """샘플 요약 결과."""
        return DocumentSummary(
            document_type=DocumentType.KPRC_REPORT,
            summary_lines=[
                "아동은 전반적으로 정상 발달 범위에 있습니다.",
                "주의력 영역에서 약간의 어려움이 관찰됩니다.",
                "사회성 발달은 우수한 수준입니다.",
            ],
            expert_opinion="본 검사 결과, 아동은 전반적으로 안정적인 발달을 보이고 있습니다.",
            key_findings=["주의력 저하", "사회성 우수"],
            recommendations=["집중력 훈련 권장"],
            confidence_score=0.9,
        )

    async def test_텍스트_요약이_성공한다(self, sample_summary: DocumentSummary) -> None:
        """텍스트 요약이 성공적으로 수행된다."""
        # Given
        service = DocumentService()
        service.summarizer.summarize_document = AsyncMock(return_value=sample_summary)

        # When
        result = await service.summarize_text(
            text_content="테스트 문서 내용입니다. 충분히 긴 텍스트입니다.",
            document_type=DocumentType.KPRC_REPORT,
        )

        # Then
        assert result.document_type == DocumentType.KPRC_REPORT
        assert len(result.summary_lines) == 3
        assert result.confidence_score == 0.9

    async def test_빈_텍스트는_에러를_발생시킨다(self) -> None:
        """빈 텍스트는 DocumentServiceError를 발생시킨다."""
        service = DocumentService()

        with pytest.raises(DocumentServiceError, match="텍스트 내용이 비어있습니다"):
            await service.summarize_text(text_content="")

    async def test_공백만_있는_텍스트는_에러를_발생시킨다(self) -> None:
        """공백만 있는 텍스트는 DocumentServiceError를 발생시킨다."""
        service = DocumentService()

        with pytest.raises(DocumentServiceError, match="텍스트 내용이 비어있습니다"):
            await service.summarize_text(text_content="   \n\t  ")

    async def test_PDF_경로에서_요약한다(
        self, tmp_path: Path, sample_summary: DocumentSummary
    ) -> None:
        """파일 경로의 PDF를 요약한다."""
        # Given
        service = DocumentService()
        service.pdf_extractor.extract_from_path = MagicMock(
            return_value="추출된 텍스트 내용"
        )
        service.summarizer.summarize_document = AsyncMock(return_value=sample_summary)

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")

        # When
        result = await service.summarize_pdf_from_path(
            file_path=str(pdf_path),
            document_type=DocumentType.KPRC_REPORT,
        )

        # Then
        assert result.document_type == DocumentType.KPRC_REPORT
        service.pdf_extractor.extract_from_path.assert_called_once()

    async def test_PDF_바이트에서_요약한다(self, sample_summary: DocumentSummary) -> None:
        """바이트 데이터의 PDF를 요약한다."""
        # Given
        service = DocumentService()
        service.pdf_extractor.extract_from_bytes = MagicMock(
            return_value="추출된 텍스트 내용"
        )
        service.summarizer.summarize_document = AsyncMock(return_value=sample_summary)

        # When
        result = await service.summarize_pdf_from_bytes(
            pdf_bytes=b"%PDF-1.4 test content",
            document_type=DocumentType.KPRC_REPORT,
        )

        # Then
        assert result.document_type == DocumentType.KPRC_REPORT
        service.pdf_extractor.extract_from_bytes.assert_called_once()

    async def test_PDF에서_텍스트가_추출되지_않으면_에러가_발생한다(self) -> None:
        """PDF에서 텍스트가 추출되지 않으면 에러가 발생한다."""
        # Given
        service = DocumentService()
        service.pdf_extractor.extract_from_bytes = MagicMock(return_value="")

        # When & Then
        with pytest.raises(DocumentServiceError, match="텍스트를 추출할 수 없습니다"):
            await service.summarize_pdf_from_bytes(
                pdf_bytes=b"%PDF-1.4",
                document_type=DocumentType.KPRC_REPORT,
            )

    async def test_아동_이름_익명화가_전달된다(self, sample_summary: DocumentSummary) -> None:
        """아동 이름이 요약기에 전달된다."""
        # Given
        service = DocumentService()
        service.summarizer.summarize_document = AsyncMock(return_value=sample_summary)

        # When
        await service.summarize_text(
            text_content="테스트 문서 내용입니다.",
            child_name="홍길동",
        )

        # Then
        call_args = service.summarizer.summarize_document.call_args
        assert call_args.kwargs["child_name"] == "홍길동"

    async def test_권장사항_포함_여부가_전달된다(self, sample_summary: DocumentSummary) -> None:
        """권장사항 포함 여부가 요약기에 전달된다."""
        # Given
        service = DocumentService()
        service.summarizer.summarize_document = AsyncMock(return_value=sample_summary)

        # When
        await service.summarize_text(
            text_content="테스트 문서 내용입니다.",
            include_recommendations=False,
        )

        # Then
        call_args = service.summarizer.summarize_document.call_args
        assert call_args.kwargs["include_recommendations"] is False
