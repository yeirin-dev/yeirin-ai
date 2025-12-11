"""PDF 텍스트 추출기.

PyMuPDF(fitz)를 사용하여 PDF 파일에서 텍스트를 추출합니다.
"""

from pathlib import Path
from typing import BinaryIO

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """PDF 추출 실패 예외."""

    pass


class PDFExtractor:
    """PDF 텍스트 추출기.

    PyMuPDF를 사용하여 PDF 파일에서 텍스트를 추출합니다.
    한글 문서 처리에 최적화되어 있습니다.
    """

    def __init__(self, max_pages: int = 50) -> None:
        """추출기를 초기화합니다.

        Args:
            max_pages: 처리할 최대 페이지 수
        """
        self.max_pages = max_pages

    def extract_from_path(self, file_path: str | Path) -> str:
        """파일 경로에서 PDF 텍스트를 추출합니다.

        Args:
            file_path: PDF 파일 경로

        Returns:
            추출된 텍스트

        Raises:
            PDFExtractionError: PDF 처리 실패 시
            FileNotFoundError: 파일이 존재하지 않는 경우
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

        if not path.suffix.lower() == ".pdf":
            raise PDFExtractionError(f"PDF 파일이 아닙니다: {path}")

        try:
            doc = fitz.open(str(path))
            return self._extract_text(doc)
        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 파일을 열 수 없습니다: {e}") from e
        except Exception as e:
            raise PDFExtractionError(f"PDF 처리 중 오류 발생: {e}") from e

    def extract_from_bytes(self, pdf_bytes: bytes) -> str:
        """바이트 데이터에서 PDF 텍스트를 추출합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터

        Returns:
            추출된 텍스트

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            return self._extract_text(doc)
        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except Exception as e:
            raise PDFExtractionError(f"PDF 처리 중 오류 발생: {e}") from e

    def extract_from_file(self, file_obj: BinaryIO) -> str:
        """파일 객체에서 PDF 텍스트를 추출합니다.

        Args:
            file_obj: PDF 파일 객체 (바이너리 모드)

        Returns:
            추출된 텍스트

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        pdf_bytes = file_obj.read()
        return self.extract_from_bytes(pdf_bytes)

    def _extract_text(self, doc: fitz.Document) -> str:
        """fitz.Document에서 텍스트를 추출합니다.

        Args:
            doc: PyMuPDF Document 객체

        Returns:
            추출된 텍스트
        """
        try:
            pages_text: list[str] = []
            page_count = min(len(doc), self.max_pages)

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text("text")

                # 텍스트 정제
                cleaned_text = self._clean_text(text)
                if cleaned_text:
                    pages_text.append(f"[페이지 {page_num + 1}]\n{cleaned_text}")

            return "\n\n".join(pages_text)
        finally:
            doc.close()

    def _clean_text(self, text: str) -> str:
        """추출된 텍스트를 정제합니다.

        Args:
            text: 원본 텍스트

        Returns:
            정제된 텍스트
        """
        # 연속된 공백 제거
        lines = text.split("\n")
        cleaned_lines: list[str] = []

        for line in lines:
            # 앞뒤 공백 제거
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)

        return "\n".join(cleaned_lines)

    def extract_page_from_bytes(self, pdf_bytes: bytes, page_number: int) -> str:
        """바이트 데이터에서 특정 페이지 텍스트만 추출합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터
            page_number: 추출할 페이지 번호 (1부터 시작)

        Returns:
            해당 페이지의 텍스트

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                if page_number < 1 or page_number > len(doc):
                    raise PDFExtractionError(
                        f"페이지 번호가 유효하지 않습니다: {page_number} (총 {len(doc)} 페이지)"
                    )

                page = doc[page_number - 1]  # 0-indexed
                text = page.get_text("text")
                return self._clean_text(text)
            finally:
                doc.close()
        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(f"PDF 처리 중 오류 발생: {e}") from e

    def extract_section_from_bytes(
        self,
        pdf_bytes: bytes,
        section_keyword: str,
        page_number: int | None = None,
    ) -> str:
        """바이트 데이터에서 특정 섹션 텍스트를 추출합니다.

        KPRC 보고서의 '종합해석' 등 특정 섹션을 추출할 때 사용합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터
            section_keyword: 추출할 섹션 키워드 (예: "종합해석", "검사결과")
            page_number: 특정 페이지에서만 찾을 경우 (None이면 전체 검색)

        Returns:
            해당 섹션의 텍스트 (키워드부터 다음 주요 섹션까지)

        Raises:
            PDFExtractionError: PDF 처리 실패 또는 섹션을 찾을 수 없는 경우
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                # 검색할 페이지 범위 결정
                if page_number:
                    if page_number < 1 or page_number > len(doc):
                        raise PDFExtractionError(
                            f"페이지 번호가 유효하지 않습니다: {page_number}"
                        )
                    pages_to_search = [page_number - 1]  # 0-indexed
                else:
                    pages_to_search = list(range(min(len(doc), self.max_pages)))

                # 각 페이지에서 섹션 찾기
                for page_idx in pages_to_search:
                    page = doc[page_idx]
                    text = page.get_text("text")

                    # 섹션 키워드 찾기
                    if section_keyword in text:
                        section_text = self._extract_section_text(text, section_keyword)
                        if section_text:
                            return section_text

                raise PDFExtractionError(
                    f"'{section_keyword}' 섹션을 찾을 수 없습니다"
                )
            finally:
                doc.close()
        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(f"PDF 처리 중 오류 발생: {e}") from e

    def _extract_section_text(self, full_text: str, section_keyword: str) -> str:
        """전체 텍스트에서 특정 섹션만 추출합니다.

        Args:
            full_text: 페이지 전체 텍스트
            section_keyword: 시작 섹션 키워드

        Returns:
            섹션 텍스트 (키워드부터 다음 주요 섹션 또는 페이지 끝까지)
        """
        # KPRC 보고서의 주요 섹션 키워드들
        section_markers = [
            "종합해석",
            "검사결과",
            "척도해석",
            "프로파일",
            "검사개요",
            "부가정보",
            "참고사항",
            "※",  # 주석/참고 시작
        ]

        lines = full_text.split("\n")
        section_started = False
        section_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # 섹션 시작 찾기
            if section_keyword in stripped and not section_started:
                section_started = True
                section_lines.append(stripped)
                continue

            if section_started:
                # 다른 주요 섹션 키워드를 만나면 종료
                is_new_section = any(
                    marker in stripped and marker != section_keyword
                    for marker in section_markers
                )
                if is_new_section and len(section_lines) > 1:
                    break

                if stripped:
                    section_lines.append(stripped)

        return "\n".join(section_lines)

    def get_metadata(self, file_path: str | Path) -> dict[str, str | int]:
        """PDF 메타데이터를 추출합니다.

        Args:
            file_path: PDF 파일 경로

        Returns:
            메타데이터 딕셔너리
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {path}")

        try:
            doc = fitz.open(str(path))
            metadata = doc.metadata or {}
            page_count = len(doc)
            doc.close()

            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "page_count": page_count,
            }
        except Exception as e:
            raise PDFExtractionError(f"메타데이터 추출 실패: {e}") from e
