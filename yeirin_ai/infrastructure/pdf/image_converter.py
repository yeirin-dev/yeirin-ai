"""PDF 페이지를 이미지로 변환하는 모듈.

GPT Vision API를 위해 PDF 특정 페이지를 고해상도 이미지로 변환합니다.
"""

import base64
from dataclasses import dataclass

import fitz  # PyMuPDF

from yeirin_ai.infrastructure.pdf.extractor import PDFExtractionError


@dataclass
class PageImage:
    """PDF 페이지 이미지 정보."""

    page_number: int
    width: int
    height: int
    base64_png: str
    mime_type: str = "image/png"

    @property
    def data_url(self) -> str:
        """Data URL 형식으로 반환합니다."""
        return f"data:{self.mime_type};base64,{self.base64_png}"


class PDFImageConverter:
    """PDF 페이지를 이미지로 변환하는 클래스.

    PyMuPDF를 사용하여 PDF 페이지를 고해상도 PNG 이미지로 변환합니다.
    GPT Vision API 전송에 최적화된 해상도와 포맷을 사용합니다.
    """

    # GPT Vision에 적합한 기본 DPI (해상도)
    DEFAULT_DPI = 150
    # 최대 이미지 크기 (GPT Vision API 제한 고려)
    MAX_DIMENSION = 2048

    def __init__(self, dpi: int = DEFAULT_DPI) -> None:
        """변환기를 초기화합니다.

        Args:
            dpi: 변환 해상도 (기본값: 150 DPI)
        """
        self.dpi = dpi
        # fitz에서 사용하는 zoom 계수 (72 DPI 기준)
        self.zoom = dpi / 72.0

    def convert_page_to_image(
        self,
        pdf_bytes: bytes,
        page_number: int = 2,
    ) -> PageImage:
        """PDF 특정 페이지를 이미지로 변환합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터
            page_number: 변환할 페이지 번호 (1부터 시작, 기본값: 2)

        Returns:
            PageImage: 변환된 이미지 정보

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                # 페이지 번호 검증
                if page_number < 1 or page_number > len(doc):
                    raise PDFExtractionError(
                        f"페이지 번호가 유효하지 않습니다: {page_number} (총 {len(doc)} 페이지)"
                    )

                page = doc[page_number - 1]  # 0-indexed

                # 변환 매트릭스 설정 (해상도 조절)
                mat = fitz.Matrix(self.zoom, self.zoom)

                # 페이지를 픽스맵으로 변환
                pixmap = page.get_pixmap(matrix=mat, alpha=False)

                # 이미지 크기 제한 적용
                if pixmap.width > self.MAX_DIMENSION or pixmap.height > self.MAX_DIMENSION:
                    pixmap = self._resize_pixmap(pixmap)

                # PNG 바이트로 변환
                png_bytes = pixmap.tobytes("png")

                # Base64 인코딩
                base64_png = base64.b64encode(png_bytes).decode("utf-8")

                return PageImage(
                    page_number=page_number,
                    width=pixmap.width,
                    height=pixmap.height,
                    base64_png=base64_png,
                )
            finally:
                doc.close()

        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except PDFExtractionError:
            raise
        except Exception as e:
            raise PDFExtractionError(f"PDF 이미지 변환 중 오류 발생: {e}") from e

    def _resize_pixmap(self, pixmap: fitz.Pixmap) -> fitz.Pixmap:
        """픽스맵을 최대 크기에 맞게 리사이즈합니다.

        Args:
            pixmap: 원본 픽스맵

        Returns:
            리사이즈된 픽스맵
        """
        width, height = pixmap.width, pixmap.height

        # 비율 유지하며 최대 크기 계산
        if width > height:
            scale = self.MAX_DIMENSION / width
        else:
            scale = self.MAX_DIMENSION / height

        new_width = int(width * scale)
        new_height = int(height * scale)

        # 리사이즈된 픽스맵 생성
        # fitz에서 직접 리사이즈하는 방법: 원본 pixmap을 irect로 변환
        pix_resized = fitz.Pixmap(pixmap, new_width, new_height)
        return pix_resized

    def convert_multiple_pages(
        self,
        pdf_bytes: bytes,
        page_numbers: list[int],
    ) -> list[PageImage]:
        """여러 페이지를 이미지로 변환합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터
            page_numbers: 변환할 페이지 번호 리스트 (1부터 시작)

        Returns:
            변환된 PageImage 리스트

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                images: list[PageImage] = []

                for page_number in page_numbers:
                    if page_number < 1 or page_number > len(doc):
                        continue  # 유효하지 않은 페이지는 건너뜀

                    page = doc[page_number - 1]
                    mat = fitz.Matrix(self.zoom, self.zoom)
                    pixmap = page.get_pixmap(matrix=mat, alpha=False)

                    if pixmap.width > self.MAX_DIMENSION or pixmap.height > self.MAX_DIMENSION:
                        pixmap = self._resize_pixmap(pixmap)

                    png_bytes = pixmap.tobytes("png")
                    base64_png = base64.b64encode(png_bytes).decode("utf-8")

                    images.append(
                        PageImage(
                            page_number=page_number,
                            width=pixmap.width,
                            height=pixmap.height,
                            base64_png=base64_png,
                        )
                    )

                return images
            finally:
                doc.close()

        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except Exception as e:
            raise PDFExtractionError(f"PDF 이미지 변환 중 오류 발생: {e}") from e

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """PDF 페이지 수를 반환합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터

        Returns:
            페이지 수

        Raises:
            PDFExtractionError: PDF 처리 실패 시
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()
            return page_count
        except fitz.FileDataError as e:
            raise PDFExtractionError(f"PDF 데이터를 처리할 수 없습니다: {e}") from e
        except Exception as e:
            raise PDFExtractionError(f"PDF 처리 중 오류 발생: {e}") from e
