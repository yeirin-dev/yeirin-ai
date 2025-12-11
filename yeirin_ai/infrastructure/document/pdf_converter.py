"""DOCX to PDF 변환.

LibreOffice headless 모드를 사용하여 DOCX를 PDF로 변환합니다.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class PdfConverterError(Exception):
    """PDF 변환 에러."""

    pass


class DocxToPdfConverter:
    """DOCX to PDF 변환기.

    LibreOffice의 headless 모드를 사용합니다.
    서버 환경에서는 libreoffice-writer 패키지가 설치되어 있어야 합니다.

    사용법:
        converter = DocxToPdfConverter()
        pdf_bytes = await converter.convert(docx_bytes)
    """

    # LibreOffice 실행 파일 경로 (환경에 따라 다름)
    LIBREOFFICE_PATHS = [
        "/usr/bin/libreoffice",  # Linux
        "/usr/bin/soffice",  # Linux alternative
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
    ]

    def __init__(self, timeout: int = 60) -> None:
        """초기화.

        Args:
            timeout: 변환 타임아웃 (초)
        """
        self.timeout = timeout
        self._libreoffice_path: str | None = None

    def _find_libreoffice(self) -> str:
        """LibreOffice 실행 파일을 찾습니다."""
        if self._libreoffice_path:
            return self._libreoffice_path

        for path in self.LIBREOFFICE_PATHS:
            if os.path.exists(path):
                self._libreoffice_path = path
                logger.info(f"LibreOffice 경로 발견: {path}")
                return path

        # 환경 변수에서 찾기
        env_path = os.environ.get("LIBREOFFICE_PATH")
        if env_path and os.path.exists(env_path):
            self._libreoffice_path = env_path
            return env_path

        raise PdfConverterError(
            "LibreOffice를 찾을 수 없습니다. "
            "libreoffice-writer 패키지를 설치하거나 "
            "LIBREOFFICE_PATH 환경 변수를 설정하세요."
        )

    async def convert(self, docx_bytes: bytes) -> bytes:
        """DOCX 바이트를 PDF로 변환합니다.

        Args:
            docx_bytes: DOCX 파일 바이트 데이터

        Returns:
            PDF 파일 바이트 데이터

        Raises:
            PdfConverterError: 변환 실패 시
        """
        libreoffice = self._find_libreoffice()

        # 임시 디렉토리에서 작업
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 입력 DOCX 파일 저장
            docx_path = temp_path / "input.docx"
            docx_path.write_bytes(docx_bytes)

            # LibreOffice headless 명령 실행
            cmd = [
                libreoffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_path),
                str(docx_path),
            ]

            logger.debug(f"LibreOffice 명령 실행: {' '.join(cmd)}")

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )

                if process.returncode != 0:
                    error_msg = stderr.decode("utf-8", errors="replace")
                    raise PdfConverterError(
                        f"LibreOffice 변환 실패 (코드: {process.returncode}): {error_msg}"
                    )

                # 출력 PDF 파일 읽기
                pdf_path = temp_path / "input.pdf"
                if not pdf_path.exists():
                    raise PdfConverterError("PDF 파일이 생성되지 않았습니다")

                pdf_bytes = pdf_path.read_bytes()

                logger.info(
                    "DOCX → PDF 변환 완료",
                    extra={"pdf_size": len(pdf_bytes)},
                )

                return pdf_bytes

            except asyncio.TimeoutError:
                raise PdfConverterError(
                    f"PDF 변환 타임아웃 ({self.timeout}초 초과)"
                )
            except Exception as e:
                if isinstance(e, PdfConverterError):
                    raise
                raise PdfConverterError(f"PDF 변환 중 오류: {e}") from e

    async def convert_file(self, docx_path: Path) -> bytes:
        """DOCX 파일을 PDF로 변환합니다.

        Args:
            docx_path: DOCX 파일 경로

        Returns:
            PDF 파일 바이트 데이터
        """
        if not docx_path.exists():
            raise PdfConverterError(f"파일을 찾을 수 없습니다: {docx_path}")

        docx_bytes = docx_path.read_bytes()
        return await self.convert(docx_bytes)
