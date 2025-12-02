"""PDF 추출기 테스트."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yeirin_ai.infrastructure.pdf.extractor import PDFExtractionError, PDFExtractor


class TestPDFExtractor:
    """PDFExtractor 테스트."""

    def test_추출기를_초기화한다(self) -> None:
        """추출기가 올바르게 초기화된다."""
        extractor = PDFExtractor(max_pages=10)
        assert extractor.max_pages == 10

    def test_기본_최대_페이지는_50이다(self) -> None:
        """기본 최대 페이지 수는 50이다."""
        extractor = PDFExtractor()
        assert extractor.max_pages == 50

    def test_존재하지_않는_파일은_FileNotFoundError를_발생시킨다(self) -> None:
        """존재하지 않는 파일 경로는 FileNotFoundError를 발생시킨다."""
        extractor = PDFExtractor()

        with pytest.raises(FileNotFoundError, match="PDF 파일을 찾을 수 없습니다"):
            extractor.extract_from_path("/nonexistent/path/file.pdf")

    def test_PDF가_아닌_파일은_PDFExtractionError를_발생시킨다(self, tmp_path: Path) -> None:
        """PDF가 아닌 파일은 PDFExtractionError를 발생시킨다."""
        # Given
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is not a PDF")

        extractor = PDFExtractor()

        # When & Then
        with pytest.raises(PDFExtractionError, match="PDF 파일이 아닙니다"):
            extractor.extract_from_path(txt_file)

    def test_빈_바이트는_PDFExtractionError를_발생시킨다(self) -> None:
        """빈 바이트 데이터는 PDFExtractionError를 발생시킨다."""
        extractor = PDFExtractor()

        with pytest.raises(PDFExtractionError):
            extractor.extract_from_bytes(b"")

    def test_잘못된_PDF_바이트는_PDFExtractionError를_발생시킨다(self) -> None:
        """유효하지 않은 PDF 바이트는 PDFExtractionError를 발생시킨다."""
        extractor = PDFExtractor()

        with pytest.raises(PDFExtractionError, match="PDF 데이터를 처리할 수 없습니다"):
            extractor.extract_from_bytes(b"This is not a PDF content")

    def test_텍스트_정제가_올바르게_동작한다(self) -> None:
        """텍스트 정제 로직이 올바르게 동작한다."""
        extractor = PDFExtractor()

        # Given
        raw_text = """
        Line 1 with spaces

        Line 2


        Line 3
        """

        # When
        cleaned = extractor._clean_text(raw_text)

        # Then
        lines = cleaned.split("\n")
        assert "Line 1 with spaces" in lines
        assert "Line 2" in lines
        assert "Line 3" in lines
        # 빈 줄은 제거됨
        assert "" not in lines

    @patch("yeirin_ai.infrastructure.pdf.extractor.fitz")
    def test_extract_from_bytes가_fitz를_호출한다(self, mock_fitz: MagicMock) -> None:
        """extract_from_bytes가 fitz.open을 올바르게 호출한다."""
        # Given
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Test content"
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz.open.return_value = mock_doc

        extractor = PDFExtractor()
        pdf_bytes = b"%PDF-1.4 fake content"

        # When
        result = extractor.extract_from_bytes(pdf_bytes)

        # Then
        mock_fitz.open.assert_called_once_with(stream=pdf_bytes, filetype="pdf")
        assert "Test content" in result

    @patch("yeirin_ai.infrastructure.pdf.extractor.fitz")
    def test_여러_페이지를_추출한다(self, mock_fitz: MagicMock) -> None:
        """여러 페이지의 텍스트를 모두 추출한다."""
        # Given
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=3)

        pages = []
        for i in range(3):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Page {i + 1} content"
            pages.append(mock_page)

        mock_doc.__getitem__ = lambda self, idx: pages[idx]
        mock_fitz.open.return_value = mock_doc

        extractor = PDFExtractor()

        # When
        result = extractor.extract_from_bytes(b"%PDF-1.4")

        # Then
        assert "[페이지 1]" in result
        assert "Page 1 content" in result
        assert "[페이지 2]" in result
        assert "Page 2 content" in result
        assert "[페이지 3]" in result
        assert "Page 3 content" in result

    @patch("yeirin_ai.infrastructure.pdf.extractor.fitz")
    def test_최대_페이지_수를_초과하지_않는다(self, mock_fitz: MagicMock) -> None:
        """max_pages 설정을 초과하는 페이지는 추출하지 않는다."""
        # Given
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)

        pages = []
        for i in range(100):
            mock_page = MagicMock()
            mock_page.get_text.return_value = f"Page {i + 1}"
            pages.append(mock_page)

        mock_doc.__getitem__ = lambda self, idx: pages[idx]
        mock_fitz.open.return_value = mock_doc

        extractor = PDFExtractor(max_pages=5)

        # When
        result = extractor.extract_from_bytes(b"%PDF-1.4")

        # Then
        assert "[페이지 5]" in result
        assert "[페이지 6]" not in result
