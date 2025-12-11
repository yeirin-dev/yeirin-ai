"""DOCX to PDF 변환.

Gotenberg API를 사용하여 DOCX를 PDF로 변환합니다.
https://gotenberg.dev/docs/routes#convert-with-libreoffice
"""

import logging

import httpx

from yeirin_ai.core.config.settings import settings

logger = logging.getLogger(__name__)


class PdfConverterError(Exception):
    """PDF 변환 에러."""

    pass


class DocxToPdfConverter:
    """DOCX to PDF 변환기.

    Gotenberg Docker 컨테이너의 LibreOffice API를 사용합니다.

    사용법:
        converter = DocxToPdfConverter()
        pdf_bytes = await converter.convert(docx_bytes)

    환경 변수:
        GOTENBERG_URL: Gotenberg 서버 URL (기본: http://localhost:3000)
    """

    def __init__(self, timeout: int = 60) -> None:
        """초기화.

        Args:
            timeout: 변환 타임아웃 (초)
        """
        self.timeout = timeout
        self.gotenberg_url = settings.gotenberg_url.rstrip("/")

    async def convert(self, docx_bytes: bytes) -> bytes:
        """DOCX 바이트를 PDF로 변환합니다.

        Gotenberg의 LibreOffice 변환 API를 사용합니다.
        POST /forms/libreoffice/convert

        Args:
            docx_bytes: DOCX 파일 바이트 데이터

        Returns:
            PDF 파일 바이트 데이터

        Raises:
            PdfConverterError: 변환 실패 시
        """
        url = f"{self.gotenberg_url}/forms/libreoffice/convert"

        logger.info(
            "[PDF_CONVERTER] Gotenberg 변환 요청",
            extra={
                "gotenberg_url": self.gotenberg_url,
                "docx_size": len(docx_bytes),
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # multipart/form-data로 파일 전송
                files = {
                    "files": ("document.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                }

                response = await client.post(url, files=files)

                if response.status_code != 200:
                    error_detail = response.text[:500] if response.text else "No details"
                    raise PdfConverterError(
                        f"Gotenberg 변환 실패 (HTTP {response.status_code}): {error_detail}"
                    )

                pdf_bytes = response.content

                if not pdf_bytes or len(pdf_bytes) < 100:
                    raise PdfConverterError("Gotenberg에서 유효한 PDF가 반환되지 않았습니다")

                logger.info(
                    "[PDF_CONVERTER] DOCX → PDF 변환 완료",
                    extra={"pdf_size": len(pdf_bytes)},
                )

                return pdf_bytes

        except httpx.TimeoutException:
            raise PdfConverterError(f"Gotenberg 변환 타임아웃 ({self.timeout}초 초과)")
        except httpx.ConnectError:
            raise PdfConverterError(
                f"Gotenberg 서버에 연결할 수 없습니다: {self.gotenberg_url}. "
                "Gotenberg Docker 컨테이너가 실행 중인지 확인하세요."
            )
        except Exception as e:
            if isinstance(e, PdfConverterError):
                raise
            raise PdfConverterError(f"PDF 변환 중 오류: {e}") from e

    async def health_check(self) -> bool:
        """Gotenberg 서버 상태를 확인합니다.

        Returns:
            서버가 정상이면 True
        """
        url = f"{self.gotenberg_url}/health"

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
