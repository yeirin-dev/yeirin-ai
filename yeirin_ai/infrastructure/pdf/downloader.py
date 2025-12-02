"""PDF 다운로드 서비스.

Inpsyt 심리검사 결과 페이지에서 PDF를 자동으로 다운로드합니다.
Playwright를 사용하여 브라우저 자동화를 수행합니다.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)


class PDFDownloadError(Exception):
    """PDF 다운로드 실패 예외."""

    pass


class InpsytPDFDownloader:
    """Inpsyt 심리검사 결과 PDF 다운로더.

    Playwright를 사용하여 Inpsyt 결과 페이지에서 PDF를 다운로드합니다.
    OZViewer의 Save 버튼을 클릭하여 실제 PDF 파일을 다운로드합니다.

    사용 예시:
        downloader = InpsytPDFDownloader(download_dir="/app/reports")
        pdf_path = await downloader.download_report(
            report_url="https://dev.inpsyt.co.kr/front/inpsyt/testing/resultMain/xxx/HTML5",
            session_id="uuid-here",
            child_name="홍길동"
        )
    """

    # OZViewer 로드 대기 시간 (초)
    VIEWER_LOAD_TIMEOUT: Final[int] = 60
    # 다운로드 대기 시간 (초)
    DOWNLOAD_TIMEOUT: Final[int] = 60
    # 페이지 렌더링 안정화 대기 (초)
    RENDER_STABILIZATION_DELAY: Final[float] = 3.0

    def __init__(
        self,
        download_dir: str | Path = "./data/reports",
        headless: bool = True,
    ) -> None:
        """PDF 다운로더를 초기화합니다.

        Args:
            download_dir: PDF 저장 디렉토리 경로
            headless: 헤드리스 브라우저 모드 사용 여부
        """
        self.download_dir = Path(download_dir)
        self.headless = headless
        self._ensure_download_dir()

    def _ensure_download_dir(self) -> None:
        """다운로드 디렉토리가 존재하는지 확인하고 생성합니다."""
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info("PDF 다운로드 디렉토리 확인됨: %s", str(self.download_dir))

    def _generate_filename(
        self,
        session_id: str,
        child_name: str,
        assessment_type: str = "KPRC",
    ) -> str:
        """PDF 파일명을 생성합니다.

        형식: {assessment_type}_{child_name}_{session_id}_{timestamp}.pdf

        Args:
            session_id: 검사 세션 ID
            child_name: 아동 이름
            assessment_type: 검사 유형 코드

        Returns:
            생성된 파일명
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 파일명에 사용할 수 없는 문자 제거
        safe_name = "".join(c for c in child_name if c.isalnum() or c in "가-힣")
        safe_session = session_id[:8] if len(session_id) > 8 else session_id

        return f"{assessment_type}_{safe_name}_{safe_session}_{timestamp}.pdf"

    async def download_report(
        self,
        report_url: str,
        session_id: str,
        child_name: str,
        assessment_type: str = "KPRC",
    ) -> Path:
        """Inpsyt 결과 페이지에서 PDF를 다운로드합니다.

        OZViewer의 Save 버튼을 클릭하여 실제 PDF 파일을 다운로드합니다.

        Args:
            report_url: Inpsyt 결과 페이지 URL
            session_id: 검사 세션 ID (파일명 생성용)
            child_name: 아동 이름 (파일명 생성용)
            assessment_type: 검사 유형 코드

        Returns:
            저장된 PDF 파일 경로

        Raises:
            PDFDownloadError: 다운로드 실패 시
            ImportError: Playwright가 설치되지 않은 경우
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            logger.error("Playwright가 설치되지 않음: %s", str(e))
            raise ImportError(
                "Playwright가 필요합니다. 'pip install playwright && playwright install chromium' 실행"
            ) from e

        filename = self._generate_filename(session_id, child_name, assessment_type)
        output_path = self.download_dir / filename

        logger.info(
            "PDF 다운로드 시작: url=%s, output=%s, session_id=%s",
            report_url,
            str(output_path),
            session_id,
        )

        try:
            async with async_playwright() as p:
                # EC2 헤드리스 환경에서 한글 폰트 렌더링을 위한 설정
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--font-render-hinting=none",
                        "--disable-font-subpixel-positioning",
                        "--lang=ko-KR",
                    ],
                )

                try:
                    # 한글 PDF 생성을 위해 한국어 환경으로 설정
                    # OZViewer 서버가 Accept-Language 헤더를 보고 PDF 인코딩을 결정함
                    context = await browser.new_context(
                        viewport={"width": 1400, "height": 900},
                        accept_downloads=True,
                        locale="ko-KR",
                        extra_http_headers={
                            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                        },
                    )
                    page = await context.new_page()

                    # 1. 페이지 로드
                    logger.debug("페이지 로드 시작: %s", report_url)
                    await page.goto(
                        report_url,
                        wait_until="networkidle",
                        timeout=self.VIEWER_LOAD_TIMEOUT * 1000,
                    )
                    await asyncio.sleep(self.RENDER_STABILIZATION_DELAY)

                    # 2. Save 버튼 클릭
                    save_btn = await page.query_selector("input.btnSAVEAS")
                    if not save_btn:
                        raise PDFDownloadError("Save 버튼을 찾을 수 없습니다")

                    await save_btn.click()
                    logger.debug("Save 버튼 클릭 완료")
                    await asyncio.sleep(2)

                    # 3. OK 버튼 클릭 및 다운로드 대기
                    async with page.expect_download(
                        timeout=self.DOWNLOAD_TIMEOUT * 1000
                    ) as download_info:
                        ok_btn = await page.query_selector('button:has-text("OK")')
                        if not ok_btn:
                            # 한글 "확인" 버튼도 시도
                            ok_btn = await page.query_selector('button:has-text("확인")')
                        if not ok_btn:
                            raise PDFDownloadError("OK/확인 버튼을 찾을 수 없습니다")

                        await ok_btn.click()
                        logger.debug("OK 버튼 클릭 완료")

                    download = await download_info.value
                    logger.debug("다운로드 시작됨: %s", download.suggested_filename)

                    # 4. 파일 저장
                    await download.save_as(output_path)

                    logger.info(
                        "PDF 다운로드 완료: output=%s, size=%d",
                        str(output_path),
                        output_path.stat().st_size,
                    )

                    return output_path

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(
                "PDF 다운로드 실패: error=%s, url=%s, session_id=%s",
                str(e),
                report_url,
                session_id,
            )
            raise PDFDownloadError(f"PDF 다운로드 실패: {e}") from e

    async def download_report_as_bytes(
        self,
        report_url: str,
        session_id: str,
        child_name: str,
        assessment_type: str = "KPRC",
    ) -> bytes:
        """Inpsyt 결과 페이지에서 PDF를 다운로드하여 바이트로 반환합니다.

        OZViewer의 Save 버튼을 클릭하여 실제 PDF 파일을 다운로드합니다.

        Args:
            report_url: Inpsyt 결과 페이지 URL
            session_id: 검사 세션 ID (로깅용)
            child_name: 아동 이름 (로깅용)
            assessment_type: 검사 유형 코드

        Returns:
            PDF 바이트 데이터

        Raises:
            PDFDownloadError: 다운로드 실패 시
            ImportError: Playwright가 설치되지 않은 경우
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            logger.error("Playwright가 설치되지 않음: %s", str(e))
            raise ImportError(
                "Playwright가 필요합니다. 'pip install playwright && playwright install chromium' 실행"
            ) from e

        logger.info(
            "PDF 다운로드 시작 (바이트 모드): url=%s, session_id=%s",
            report_url,
            session_id,
        )

        try:
            async with async_playwright() as p:
                # EC2 헤드리스 환경에서 한글 폰트 렌더링을 위한 설정
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--font-render-hinting=none",
                        "--disable-font-subpixel-positioning",
                        "--lang=ko-KR",
                    ],
                )

                try:
                    # 한글 PDF 생성을 위해 한국어 환경으로 설정
                    # OZViewer 서버가 Accept-Language 헤더를 보고 PDF 인코딩을 결정함
                    context = await browser.new_context(
                        viewport={"width": 1400, "height": 900},
                        accept_downloads=True,
                        locale="ko-KR",
                        extra_http_headers={
                            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                        },
                    )
                    page = await context.new_page()

                    # 1. 페이지 로드
                    await page.goto(
                        report_url,
                        wait_until="networkidle",
                        timeout=self.VIEWER_LOAD_TIMEOUT * 1000,
                    )
                    await asyncio.sleep(self.RENDER_STABILIZATION_DELAY)

                    # 2. Save 버튼 클릭
                    save_btn = await page.query_selector("input.btnSAVEAS")
                    if not save_btn:
                        raise PDFDownloadError("Save 버튼을 찾을 수 없습니다")

                    await save_btn.click()
                    await asyncio.sleep(2)

                    # 3. OK 버튼 클릭 및 다운로드 대기
                    async with page.expect_download(
                        timeout=self.DOWNLOAD_TIMEOUT * 1000
                    ) as download_info:
                        ok_btn = await page.query_selector('button:has-text("OK")')
                        if not ok_btn:
                            ok_btn = await page.query_selector('button:has-text("확인")')
                        if not ok_btn:
                            raise PDFDownloadError("OK/확인 버튼을 찾을 수 없습니다")

                        await ok_btn.click()

                    download = await download_info.value

                    # 4. 임시 파일에서 바이트 읽기
                    temp_path = await download.path()
                    if temp_path:
                        pdf_bytes = Path(temp_path).read_bytes()
                    else:
                        raise PDFDownloadError("다운로드된 파일 경로를 찾을 수 없습니다")

                    logger.info(
                        "PDF 다운로드 완료 (바이트 모드): session_id=%s, size=%d",
                        session_id,
                        len(pdf_bytes),
                    )

                    return pdf_bytes

                finally:
                    await browser.close()

        except Exception as e:
            logger.error(
                "PDF 다운로드 실패: error=%s, url=%s, session_id=%s",
                str(e),
                report_url,
                session_id,
            )
            raise PDFDownloadError(f"PDF 다운로드 실패: {e}") from e
