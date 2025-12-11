"""통합 보고서 생성 서비스.

상담의뢰지 PDF와 KPRC 검사지 PDF를 병합하여
통합 보고서를 생성하고 S3에 업로드합니다.
"""

import logging
from datetime import datetime

import httpx

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.integrated_report.models import (
    IntegratedReportRequest,
    IntegratedReportResult,
)
from yeirin_ai.infrastructure.document import CounselRequestDocxFiller, DocxToPdfConverter
from yeirin_ai.infrastructure.pdf import PDFMerger

logger = logging.getLogger(__name__)


class IntegratedReportServiceError(Exception):
    """통합 보고서 서비스 에러."""

    pass


class IntegratedReportService:
    """통합 보고서 생성 서비스.

    상담의뢰지 데이터를 DOCX 템플릿에 채우고,
    PDF로 변환 후 KPRC 검사지와 병합하여
    통합 보고서를 생성합니다.

    사용법:
        service = IntegratedReportService()
        result = await service.process(request)
    """

    def __init__(self) -> None:
        """서비스 초기화."""
        self.docx_filler = CounselRequestDocxFiller()
        self.pdf_converter = DocxToPdfConverter()
        self.pdf_merger = PDFMerger()

    async def process(self, request: IntegratedReportRequest) -> IntegratedReportResult:
        """통합 보고서를 생성합니다.

        Args:
            request: 통합 보고서 생성 요청

        Returns:
            생성 결과 (S3 key 포함)
        """
        logger.info(
            "[INTEGRATED_REPORT] 처리 시작",
            extra={
                "counsel_request_id": request.counsel_request_id,
                "child_name": request.child_name,
            },
        )

        try:
            # 1. DOCX 템플릿 채우기
            logger.info("[INTEGRATED_REPORT] Step 1: DOCX 템플릿 채우기...")
            docx_bytes = self.docx_filler.fill_template(request)
            logger.info(
                "[INTEGRATED_REPORT] Step 1 완료: DOCX 생성",
                extra={"docx_size": len(docx_bytes)},
            )

            # 2. DOCX → PDF 변환
            logger.info("[INTEGRATED_REPORT] Step 2: DOCX → PDF 변환...")
            counsel_pdf_bytes = await self.pdf_converter.convert(docx_bytes)
            logger.info(
                "[INTEGRATED_REPORT] Step 2 완료: 상담의뢰지 PDF 생성",
                extra={"pdf_size": len(counsel_pdf_bytes)},
            )

            # 3. KPRC PDF 다운로드
            logger.info("[INTEGRATED_REPORT] Step 3: KPRC PDF 다운로드...")
            kprc_pdf_bytes = await self._download_kprc_pdf(request.assessment_report_s3_key)
            logger.info(
                "[INTEGRATED_REPORT] Step 3 완료: KPRC PDF 다운로드",
                extra={"pdf_size": len(kprc_pdf_bytes)},
            )

            # 4. PDF 병합 (상담의뢰지 + KPRC)
            logger.info("[INTEGRATED_REPORT] Step 4: PDF 병합...")
            merged_pdf_bytes = self.pdf_merger.merge_with_metadata(
                pdfs=[counsel_pdf_bytes, kprc_pdf_bytes],
                title=f"통합 보고서 - {request.child_name}",
                author="예이린 AI 시스템",
                subject="상담의뢰지 및 KPRC 검사 통합 보고서",
            )
            logger.info(
                "[INTEGRATED_REPORT] Step 4 완료: PDF 병합",
                extra={"merged_size": len(merged_pdf_bytes)},
            )

            # 5. S3 업로드
            logger.info("[INTEGRATED_REPORT] Step 5: S3 업로드...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in request.child_name if c.isalnum() or c in "가-힣")
            filename = f"IR_{safe_name}_{request.counsel_request_id[:8]}_{timestamp}.pdf"

            s3_key = await self._upload_to_yeirin(
                pdf_bytes=merged_pdf_bytes,
                filename=filename,
            )
            logger.info(
                "[INTEGRATED_REPORT] Step 5 완료: S3 업로드",
                extra={"s3_key": s3_key},
            )

            logger.info(
                "[INTEGRATED_REPORT] 처리 완료",
                extra={
                    "counsel_request_id": request.counsel_request_id,
                    "s3_key": s3_key,
                },
            )

            return IntegratedReportResult(
                counsel_request_id=request.counsel_request_id,
                integrated_report_s3_key=s3_key,
                status="completed",
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "[INTEGRATED_REPORT] 처리 실패",
                extra={
                    "counsel_request_id": request.counsel_request_id,
                    "error": error_msg,
                },
                exc_info=True,
            )

            return IntegratedReportResult(
                counsel_request_id=request.counsel_request_id,
                integrated_report_s3_key=None,
                status="failed",
                error_message=error_msg,
            )

    async def _download_kprc_pdf(self, s3_key: str) -> bytes:
        """KPRC PDF를 S3에서 다운로드합니다.

        yeirin 백엔드의 presigned URL API를 통해
        S3 key로부터 presigned URL을 생성하고 다운로드합니다.

        Args:
            s3_key: KPRC PDF의 S3 객체 키

        Returns:
            PDF 바이트 데이터

        Raises:
            IntegratedReportServiceError: 다운로드 실패 시
        """
        try:
            # 1. Presigned URL 생성 (yeirin 백엔드 API)
            presigned_url = await self._get_presigned_url(s3_key)

            # 2. PDF 다운로드
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(presigned_url)
                response.raise_for_status()

                pdf_bytes = response.content

                if not pdf_bytes:
                    raise IntegratedReportServiceError("다운로드된 PDF가 비어있습니다")

                return pdf_bytes

        except httpx.HTTPStatusError as e:
            raise IntegratedReportServiceError(
                f"KPRC PDF 다운로드 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            raise IntegratedReportServiceError(f"KPRC PDF 다운로드 실패: {e}") from e

    async def _get_presigned_url(self, s3_key: str) -> str:
        """yeirin 백엔드를 통해 S3 Presigned URL을 생성합니다.

        내부 API 키를 사용하여 인증합니다.

        Args:
            s3_key: S3 객체 키

        Returns:
            Presigned URL

        Raises:
            IntegratedReportServiceError: URL 생성 실패 시
        """
        url = f"{settings.yeirin_backend_url}/api/v1/upload/internal/presigned-url"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={"key": s3_key, "expiresIn": 3600},
                    headers={"X-Internal-Api-Key": settings.internal_api_secret},
                )
                response.raise_for_status()

                result = response.json()
                presigned_url = result.get("url")

                if not presigned_url:
                    raise IntegratedReportServiceError("Presigned URL이 응답에 없습니다")

                return presigned_url

        except httpx.HTTPStatusError as e:
            raise IntegratedReportServiceError(
                f"Presigned URL 생성 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            raise IntegratedReportServiceError(f"Presigned URL 생성 실패: {e}") from e

    async def _upload_to_yeirin(self, pdf_bytes: bytes, filename: str) -> str:
        """통합 보고서 PDF를 yeirin 백엔드에 업로드합니다.

        Args:
            pdf_bytes: PDF 바이트 데이터
            filename: 저장할 파일명

        Returns:
            업로드된 PDF의 S3 키

        Raises:
            IntegratedReportServiceError: 업로드 실패 시
        """
        url = f"{settings.yeirin_backend_url}/api/v1/upload/internal/pdf"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {
                    "file": (filename, pdf_bytes, "application/pdf"),
                }
                headers = {
                    "X-Internal-Api-Key": settings.internal_api_secret,
                }

                response = await client.post(url, files=files, headers=headers)
                response.raise_for_status()

                result = response.json()
                s3_key = result.get("key")

                if not s3_key:
                    raise IntegratedReportServiceError("S3 키가 응답에 없습니다")

                return s3_key

        except httpx.HTTPStatusError as e:
            raise IntegratedReportServiceError(
                f"S3 업로드 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            raise IntegratedReportServiceError(f"S3 업로드 실패: {e}") from e


# =============================================================================
# 백그라운드 태스크 함수
# =============================================================================


async def process_integrated_report_async(
    request: IntegratedReportRequest,
) -> IntegratedReportResult:
    """통합 보고서를 생성합니다 (비동기).

    Args:
        request: 통합 보고서 생성 요청

    Returns:
        생성 결과
    """
    service = IntegratedReportService()
    result = await service.process(request)

    # yeirin에 완료 Webhook 전송
    await _send_completion_webhook(result)

    return result


def process_integrated_report_sync(request_dict: dict) -> None:
    """통합 보고서를 생성합니다 (동기 래퍼).

    FastAPI BackgroundTasks에서 호출되는 동기 함수입니다.

    Args:
        request_dict: 통합 보고서 생성 요청 딕셔너리
    """
    import asyncio

    logger.info(
        "[SYNC_WRAPPER] 동기 래퍼 함수 시작",
        extra={"counsel_request_id": request_dict.get("counsel_request_id")},
    )

    try:
        request = IntegratedReportRequest(**request_dict)
        asyncio.run(process_integrated_report_async(request))

        logger.info(
            "[SYNC_WRAPPER] 동기 래퍼 함수 완료",
            extra={"counsel_request_id": request_dict.get("counsel_request_id")},
        )
    except Exception as e:
        logger.error(
            "[SYNC_WRAPPER] 동기 래퍼 함수 실패",
            extra={
                "counsel_request_id": request_dict.get("counsel_request_id"),
                "error": str(e),
            },
            exc_info=True,
        )


async def _send_completion_webhook(result: IntegratedReportResult) -> None:
    """yeirin에 완료 Webhook을 전송합니다.

    Args:
        result: 통합 보고서 생성 결과
    """
    webhook_url = f"{settings.yeirin_backend_url}/api/v1/webhook/integrated-report-complete"

    logger.info(
        "[WEBHOOK] 완료 Webhook 전송 시작",
        extra={
            "webhook_url": webhook_url,
            "counsel_request_id": result.counsel_request_id,
            "status": result.status,
        },
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=result.model_dump(),
                headers={"X-Internal-Api-Key": settings.internal_api_secret},
            )
            response.raise_for_status()

            logger.info(
                "[WEBHOOK] 완료 Webhook 전송 성공",
                extra={"counsel_request_id": result.counsel_request_id},
            )

    except Exception as e:
        logger.error(
            "[WEBHOOK] 완료 Webhook 전송 실패",
            extra={
                "counsel_request_id": result.counsel_request_id,
                "error": str(e),
            },
            exc_info=True,
        )
