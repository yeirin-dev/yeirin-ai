"""문서 처리 서비스.

PDF 요약 및 첨삭 기능을 제공하는 서비스 레이어입니다.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

import httpx

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.document.models import DocumentSummary, DocumentType
from yeirin_ai.infrastructure.llm.document_summarizer import DocumentSummarizerClient
from yeirin_ai.infrastructure.pdf import (
    InpsytPDFDownloader,
    PDFDownloadError,
    PDFExtractionError,
    PDFExtractor,
)

logger = logging.getLogger(__name__)


class DocumentServiceError(Exception):
    """문서 서비스 에러."""

    pass


class DocumentService:
    """문서 처리 서비스.

    PDF 추출 및 AI 요약 기능을 통합하여
    문서 처리 워크플로우를 제공합니다.
    """

    def __init__(self) -> None:
        """서비스를 초기화합니다."""
        self.pdf_extractor = PDFExtractor(max_pages=50)
        self.summarizer = DocumentSummarizerClient()

    async def summarize_pdf_from_path(
        self,
        file_path: str | Path,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        child_name: str | None = None,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """파일 경로의 PDF를 요약합니다.

        Args:
            file_path: PDF 파일 경로
            document_type: 문서 유형
            child_name: 아동 이름 (익명화 처리용)
            include_recommendations: 권장 사항 포함 여부

        Returns:
            전문가 소견 형태의 문서 요약

        Raises:
            DocumentServiceError: 처리 실패 시
        """
        try:
            # PDF에서 텍스트 추출
            text_content = self.pdf_extractor.extract_from_path(file_path)

            if not text_content.strip():
                raise DocumentServiceError("PDF에서 텍스트를 추출할 수 없습니다")

            # AI 요약 생성
            return await self.summarizer.summarize_document(
                text_content=text_content,
                document_type=document_type,
                child_name=child_name,
                include_recommendations=include_recommendations,
            )

        except PDFExtractionError as e:
            raise DocumentServiceError(f"PDF 추출 실패: {e}") from e
        except Exception as e:
            raise DocumentServiceError(f"문서 처리 중 오류 발생: {e}") from e

    async def summarize_pdf_from_bytes(
        self,
        pdf_bytes: bytes,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        child_name: str | None = None,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """바이트 데이터의 PDF를 요약합니다.

        Args:
            pdf_bytes: PDF 파일 바이트 데이터
            document_type: 문서 유형
            child_name: 아동 이름 (익명화 처리용)
            include_recommendations: 권장 사항 포함 여부

        Returns:
            전문가 소견 형태의 문서 요약

        Raises:
            DocumentServiceError: 처리 실패 시
        """
        try:
            # PDF에서 '종합해석' 섹션만 추출 (토큰 절약)
            try:
                text_content = self.pdf_extractor.extract_section_from_bytes(
                    pdf_bytes=pdf_bytes,
                    section_keyword="종합해석",
                    page_number=3,  # KPRC 보고서 3페이지
                )
            except PDFExtractionError:
                # 3페이지에 없으면 전체에서 검색
                try:
                    text_content = self.pdf_extractor.extract_section_from_bytes(
                        pdf_bytes=pdf_bytes,
                        section_keyword="종합해석",
                        page_number=None,
                    )
                except PDFExtractionError:
                    # 폴백: 3페이지 전체 텍스트
                    text_content = self.pdf_extractor.extract_page_from_bytes(
                        pdf_bytes=pdf_bytes,
                        page_number=3,
                    )

            # 추출된 텍스트 로깅 (디버깅용)
            print(f"[PDF_EXTRACT] ========== 추출된 종합해석 ==========", flush=True)
            print(f"[PDF_EXTRACT] 텍스트 길이: {len(text_content)} 문자", flush=True)
            print(f"[PDF_EXTRACT] 내용:\n{text_content[:500]}...", flush=True)
            print(f"[PDF_EXTRACT] ==========================================", flush=True)

            if not text_content.strip():
                raise DocumentServiceError("PDF에서 텍스트를 추출할 수 없습니다")

            # AI 요약 생성
            return await self.summarizer.summarize_document(
                text_content=text_content,
                document_type=document_type,
                child_name=child_name,
                include_recommendations=include_recommendations,
            )

        except PDFExtractionError as e:
            raise DocumentServiceError(f"PDF 추출 실패: {e}") from e
        except Exception as e:
            raise DocumentServiceError(f"문서 처리 중 오류 발생: {e}") from e

    async def summarize_pdf_from_file(
        self,
        file_obj: BinaryIO,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        child_name: str | None = None,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """파일 객체의 PDF를 요약합니다.

        Args:
            file_obj: PDF 파일 객체
            document_type: 문서 유형
            child_name: 아동 이름 (익명화 처리용)
            include_recommendations: 권장 사항 포함 여부

        Returns:
            전문가 소견 형태의 문서 요약

        Raises:
            DocumentServiceError: 처리 실패 시
        """
        try:
            # PDF에서 텍스트 추출
            text_content = self.pdf_extractor.extract_from_file(file_obj)

            if not text_content.strip():
                raise DocumentServiceError("PDF에서 텍스트를 추출할 수 없습니다")

            # AI 요약 생성
            return await self.summarizer.summarize_document(
                text_content=text_content,
                document_type=document_type,
                child_name=child_name,
                include_recommendations=include_recommendations,
            )

        except PDFExtractionError as e:
            raise DocumentServiceError(f"PDF 추출 실패: {e}") from e
        except Exception as e:
            raise DocumentServiceError(f"문서 처리 중 오류 발생: {e}") from e

    async def summarize_text(
        self,
        text_content: str,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        child_name: str | None = None,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """텍스트를 직접 요약합니다.

        Args:
            text_content: 요약할 텍스트 내용
            document_type: 문서 유형
            child_name: 아동 이름 (익명화 처리용)
            include_recommendations: 권장 사항 포함 여부

        Returns:
            전문가 소견 형태의 문서 요약

        Raises:
            DocumentServiceError: 처리 실패 시
        """
        if not text_content.strip():
            raise DocumentServiceError("텍스트 내용이 비어있습니다")

        try:
            return await self.summarizer.summarize_document(
                text_content=text_content,
                document_type=document_type,
                child_name=child_name,
                include_recommendations=include_recommendations,
            )
        except Exception as e:
            raise DocumentServiceError(f"요약 생성 중 오류 발생: {e}") from e


# =============================================================================
# 백그라운드 태스크 함수
# =============================================================================


async def process_assessment_summary(
    session_id: str,
    child_name: str,
    assessment_type: str,
    report_url: str,
) -> None:
    """검사 결과 PDF를 다운로드하고 요약을 생성합니다.

    백그라운드 태스크로 실행되며, 완료 후 soul-e에 Webhook으로 결과를 전송합니다.

    Args:
        session_id: 검사 세션 ID
        child_name: 아동 이름
        assessment_type: 검사 유형
        report_url: Inpsyt 리포트 URL
    """
    from datetime import datetime

    logger.info(
        "[BACKGROUND] ========== 백그라운드 태스크 시작 =========="
    )
    logger.info(
        "[BACKGROUND] 태스크 파라미터",
        extra={
            "session_id": session_id,
            "child_name": child_name,
            "assessment_type": assessment_type,
            "report_url": report_url,
        },
    )

    summary_result = None
    error_message = None
    pdf_url = None  # S3에 업로드된 PDF URL

    try:
        # 1. PDF 다운로드 (Playwright 사용하여 웹 페이지를 PDF로 변환)
        logger.info("[BACKGROUND] Step 1: PDF 다운로드 시작...")
        pdf_bytes = await _download_pdf_from_url(
            url=report_url,
            session_id=session_id,
            child_name=child_name,
        )

        if not pdf_bytes:
            logger.error("[BACKGROUND] Step 1 실패: PDF 다운로드 결과가 None")
            raise DocumentServiceError("PDF 다운로드 실패")

        logger.info(
            "[BACKGROUND] Step 1 완료: PDF 다운로드 성공",
            extra={"session_id": session_id, "pdf_size": len(pdf_bytes)},
        )

        # 1.5. PDF를 yeirin 백엔드 → S3/MinIO에 업로드
        from datetime import datetime as dt

        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in child_name if c.isalnum() or c in "가-힣")
        pdf_filename = f"KPRC_{safe_name}_{session_id[:8]}_{timestamp}.pdf"

        logger.info("[BACKGROUND] Step 1.5: S3 업로드 시작...")
        pdf_url = await _upload_pdf_to_yeirin(
            pdf_bytes=pdf_bytes,
            filename=pdf_filename,
        )

        if pdf_url:
            logger.info(
                "[BACKGROUND] Step 1.5 완료: S3 업로드 성공",
                extra={"pdf_url": pdf_url},
            )
        else:
            logger.warning(
                "[BACKGROUND] Step 1.5 실패: S3 업로드 실패, 계속 진행",
                extra={"session_id": session_id},
            )

        # 2. '종합해석' 섹션 추출
        logger.info("[BACKGROUND] Step 2: '종합해석' 섹션 추출 시작...")
        pdf_extractor = PDFExtractor(max_pages=10)

        # 3페이지에서 '종합해석' 섹션 추출 시도
        try:
            interpretation_text = pdf_extractor.extract_section_from_bytes(
                pdf_bytes=pdf_bytes,
                section_keyword="종합해석",
                page_number=3,  # KPRC 보고서의 종합해석은 보통 3페이지
            )
        except PDFExtractionError:
            # 3페이지에 없으면 전체에서 '종합해석' 검색
            logger.warning("[BACKGROUND] 3페이지에서 '종합해석' 못 찾음, 전체 검색...")
            try:
                interpretation_text = pdf_extractor.extract_section_from_bytes(
                    pdf_bytes=pdf_bytes,
                    section_keyword="종합해석",
                    page_number=None,
                )
            except PDFExtractionError:
                # 폴백: 3페이지 전체 텍스트만 사용 (토큰 절약)
                logger.warning("[BACKGROUND] '종합해석' 섹션 못 찾음, 3페이지 전체 사용")
                interpretation_text = pdf_extractor.extract_page_from_bytes(
                    pdf_bytes=pdf_bytes,
                    page_number=3,
                )

        print(f"[BACKGROUND] 추출된 종합해석 ({len(interpretation_text)}자):", flush=True)
        print(f"{interpretation_text[:500]}...", flush=True)

        # 3. 예이린 재해석 소견 생성
        logger.info("[BACKGROUND] Step 3: 예이린 재해석 소견 생성 시작...")
        from yeirin_ai.infrastructure.llm.document_summarizer import (
            ChildInfo,
            DocumentSummarizerClient,
        )

        summarizer = DocumentSummarizerClient()
        child_info = ChildInfo(
            name=child_name,
            assessment_type=assessment_type,
        )

        summary = await summarizer.create_yeirin_summary(
            interpretation_text=interpretation_text,
            child_info=child_info,
            document_type=DocumentType.KPRC_REPORT,
            include_recommendations=True,
        )

        summary_result = {
            "document_type": summary.document_type.value,
            "summary_lines": summary.summary_lines,
            "expert_opinion": summary.expert_opinion,
            "key_findings": summary.key_findings,
            "recommendations": summary.recommendations,
            "confidence_score": summary.confidence_score,
            "generated_at": datetime.now(UTC).isoformat(),
            "pdf_url": pdf_url,  # S3에 업로드된 PDF URL
        }

        # 요약 결과 상세 로깅
        print(f"[BACKGROUND] ========== 요약 결과 ==========", flush=True)
        print(f"[BACKGROUND] summary_lines: {summary.summary_lines}", flush=True)
        print(f"[BACKGROUND] expert_opinion: {summary.expert_opinion}", flush=True)
        print(f"[BACKGROUND] key_findings: {summary.key_findings}", flush=True)
        print(f"[BACKGROUND] recommendations: {summary.recommendations}", flush=True)
        print(f"[BACKGROUND] confidence_score: {summary.confidence_score}", flush=True)
        print(f"[BACKGROUND] pdf_url: {pdf_url}", flush=True)

        logger.info(
            "[BACKGROUND] Step 3 완료: 예이린 재해석 소견 생성 성공",
            extra={"session_id": session_id, "confidence_score": summary.confidence_score},
        )

    except Exception as e:
        error_message = str(e)
        logger.error(
            "[BACKGROUND] 에러 발생",
            extra={"session_id": session_id, "error": error_message},
            exc_info=True,
        )

    # 4. soul-e에 결과 전송 (Webhook)
    logger.info("[BACKGROUND] Step 4: Webhook 전송 시작...")
    await _send_summary_webhook(
        session_id=session_id,
        summary_result=summary_result,
        error_message=error_message,
    )
    logger.info("[BACKGROUND] ========== 백그라운드 태스크 완료 ==========")


async def _upload_pdf_to_yeirin(
    pdf_bytes: bytes,
    filename: str,
) -> str | None:
    """PDF를 yeirin 메인 백엔드에 업로드합니다.

    MSA 패턴: yeirin-ai → yeirin → S3/MinIO

    Args:
        pdf_bytes: PDF 바이트 데이터
        filename: 저장할 파일명 (예: KPRC_홍길동_abc123.pdf)

    Returns:
        업로드된 PDF의 URL 또는 None (실패 시)
    """
    upload_url = f"{settings.yeirin_backend_url}/api/v1/upload/internal/pdf"
    logger.info(
        "[PDF_UPLOAD] yeirin 백엔드로 PDF 업로드 시작",
        extra={"upload_url": upload_url, "file_name": filename, "pdf_size": len(pdf_bytes)},
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # multipart/form-data로 파일 전송
            files = {
                "file": (filename, pdf_bytes, "application/pdf"),
            }
            headers = {
                "X-Internal-Api-Key": settings.internal_api_secret,
            }

            response = await client.post(upload_url, files=files, headers=headers)
            response.raise_for_status()

            result = response.json()
            # S3 key를 사용 (presigned URL은 1시간 후 만료되므로 저장에 부적합)
            # key는 영구적이며, 필요 시 presigned URL을 생성할 수 있음
            pdf_key = result.get("key")

            logger.info(
                "[PDF_UPLOAD] 업로드 성공",
                extra={"pdf_key": pdf_key},
            )
            return pdf_key

    except httpx.HTTPStatusError as e:
        logger.error(
            "[PDF_UPLOAD] HTTP 에러",
            extra={
                "status_code": e.response.status_code,
                "response_body": e.response.text[:500] if e.response.text else "empty",
            },
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            "[PDF_UPLOAD] 업로드 실패",
            extra={"error_type": type(e).__name__, "error": str(e)},
            exc_info=True,
        )
        return None


async def _download_pdf_from_url(
    url: str,
    session_id: str = "unknown",
    child_name: str = "unknown",
) -> bytes | None:
    """URL에서 PDF를 다운로드합니다.

    Inpsyt 리포트 URL은 웹 페이지 형식이므로,
    Playwright를 사용하여 브라우저에서 PDF로 렌더링합니다.

    Args:
        url: Inpsyt 리포트 URL (웹 페이지)
        session_id: 검사 세션 ID (로깅용)
        child_name: 아동 이름 (로깅용)

    Returns:
        PDF 바이트 데이터 또는 None
    """
    logger.info("[PDF_DOWNLOAD] InpsytPDFDownloader 초기화 중...")
    try:
        downloader = InpsytPDFDownloader(headless=True)
        logger.info(
            "[PDF_DOWNLOAD] download_report_as_bytes 호출 시작",
            extra={"url": url, "session_id": session_id},
        )
        pdf_bytes = await downloader.download_report_as_bytes(
            report_url=url,
            session_id=session_id,
            child_name=child_name,
        )
        logger.info(
            "[PDF_DOWNLOAD] 다운로드 성공",
            extra={"pdf_size": len(pdf_bytes) if pdf_bytes else 0},
        )
        return pdf_bytes

    except PDFDownloadError as e:
        logger.error(
            "[PDF_DOWNLOAD] PDFDownloadError",
            extra={"url": url, "error": str(e)},
            exc_info=True,
        )
        return None
    except ImportError as e:
        logger.error(
            "[PDF_DOWNLOAD] ImportError (Playwright 미설치)",
            extra={"url": url, "error": str(e)},
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            "[PDF_DOWNLOAD] 예상치 못한 오류",
            extra={"url": url, "error_type": type(e).__name__, "error": str(e)},
            exc_info=True,
        )
        return None


def process_assessment_summary_sync(
    session_id: str,
    child_name: str,
    assessment_type: str,
    report_url: str,
) -> None:
    """검사 결과 PDF를 다운로드하고 요약을 생성합니다 (동기 래퍼).

    FastAPI BackgroundTasks에서 호출되는 동기 함수입니다.
    내부적으로 asyncio.run()을 사용하여 비동기 함수를 실행합니다.

    Args:
        session_id: 검사 세션 ID
        child_name: 아동 이름
        assessment_type: 검사 유형
        report_url: Inpsyt 리포트 URL
    """
    import asyncio
    import sys

    # 확실한 출력을 위해 print + flush
    print(f"[SYNC_WRAPPER] ========== 동기 래퍼 함수 시작 ==========", flush=True)
    print(f"[SYNC_WRAPPER] session_id={session_id}", flush=True)
    print(f"[SYNC_WRAPPER] child_name={child_name}", flush=True)
    print(f"[SYNC_WRAPPER] report_url={report_url}", flush=True)
    sys.stdout.flush()

    logger.info(
        "[SYNC_WRAPPER] 동기 래퍼 함수 시작",
        extra={
            "session_id": session_id,
            "child_name": child_name,
            "report_url": report_url,
        },
    )

    try:
        # 새 이벤트 루프 생성하여 비동기 함수 실행
        print("[SYNC_WRAPPER] asyncio.run() 호출 시작", flush=True)
        asyncio.run(
            process_assessment_summary(
                session_id=session_id,
                child_name=child_name,
                assessment_type=assessment_type,
                report_url=report_url,
            )
        )
        print("[SYNC_WRAPPER] asyncio.run() 완료", flush=True)
        logger.info("[SYNC_WRAPPER] 동기 래퍼 함수 완료", extra={"session_id": session_id})
    except Exception as e:
        print(f"[SYNC_WRAPPER] 에러 발생: {e}", flush=True)
        import traceback
        traceback.print_exc()
        logger.error(
            "[SYNC_WRAPPER] 동기 래퍼 함수 실패",
            extra={"session_id": session_id, "error": str(e)},
            exc_info=True,
        )


async def _send_summary_webhook(
    session_id: str,
    summary_result: dict | None,
    error_message: str | None,
) -> None:
    """soul-e에 요약 결과를 Webhook으로 전송합니다.

    Args:
        session_id: 검사 세션 ID
        summary_result: 요약 결과 (성공 시)
        error_message: 에러 메시지 (실패 시)
    """
    from yeirin_ai.core.config.settings import settings

    webhook_url = settings.soul_e_webhook_url
    logger.info(
        "[WEBHOOK] Webhook URL 확인",
        extra={"webhook_url": webhook_url},
    )

    if not webhook_url:
        logger.warning(
            "[WEBHOOK] SOUL_E_WEBHOOK_URL 미설정, Webhook 전송 건너뜀",
            extra={"session_id": session_id},
        )
        return

    payload = {
        "session_id": session_id,
        "status": "completed" if summary_result else "failed",
        "summary": summary_result,
        "error": error_message,
    }

    target_url = f"{webhook_url}/api/v1/assessment/sessions/{session_id}/summary-callback"
    logger.info(
        "[WEBHOOK] 전송 시작",
        extra={"target_url": target_url, "status": payload["status"]},
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(target_url, json=payload)
            logger.info(
                "[WEBHOOK] 응답 수신",
                extra={
                    "status_code": response.status_code,
                    "response_body": response.text[:500] if response.text else "empty",
                },
            )
            response.raise_for_status()

            logger.info(
                "[WEBHOOK] 전송 성공",
                extra={"session_id": session_id, "status": payload["status"]},
            )

    except Exception as e:
        logger.error(
            "[WEBHOOK] 전송 실패",
            extra={"session_id": session_id, "error_type": type(e).__name__, "error": str(e)},
            exc_info=True,
        )
