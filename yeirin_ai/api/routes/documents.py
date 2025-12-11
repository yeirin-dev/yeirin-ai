"""문서 처리 API 라우터.

PDF 요약 및 첨삭 기능 엔드포인트를 제공합니다.
"""

from enum import Enum
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from yeirin_ai.domain.document.models import DocumentSummary, DocumentType
from yeirin_ai.services.document_service import DocumentService, DocumentServiceError

router = APIRouter(prefix="/documents", tags=["documents"])


# =============================================================================
# 요청/응답 모델
# =============================================================================


class DocumentTypeInput(str, Enum):
    """문서 유형 입력."""

    KPRC_REPORT = "kprc_report"
    COUNSEL_REQUEST = "counsel_request"
    COUNSEL_REPORT = "counsel_report"
    OTHER = "other"


class SummarizeTextRequest(BaseModel):
    """텍스트 요약 요청."""

    text_content: str = Field(..., min_length=10, description="요약할 텍스트 내용")
    document_type: DocumentTypeInput = Field(
        default=DocumentTypeInput.KPRC_REPORT,
        description="문서 유형",
    )
    child_name: str | None = Field(
        default=None,
        description="아동 이름 (익명화 처리용)",
    )
    include_recommendations: bool = Field(
        default=True,
        description="권장 사항 포함 여부",
    )


class SummarizePathRequest(BaseModel):
    """파일 경로 요약 요청 (내부 서비스용)."""

    file_path: str = Field(..., description="PDF 파일 경로")
    document_type: DocumentTypeInput = Field(
        default=DocumentTypeInput.KPRC_REPORT,
        description="문서 유형",
    )
    child_name: str | None = Field(
        default=None,
        description="아동 이름 (익명화 처리용)",
    )
    include_recommendations: bool = Field(
        default=True,
        description="권장 사항 포함 여부",
    )


class AsyncSummarizeRequest(BaseModel):
    """비동기 요약 요청 (soul-e 연동용)."""

    session_id: str = Field(..., description="검사 세션 ID")
    child_name: str = Field(..., description="아동 이름")
    assessment_type: str = Field(..., description="검사 유형")
    report_url: str = Field(..., description="Inpsyt 리포트 URL")


class AsyncSummarizeResponse(BaseModel):
    """비동기 요약 요청 응답."""

    status: str = Field(..., description="요청 상태")
    session_id: str = Field(..., description="검사 세션 ID")
    message: str = Field(..., description="응답 메시지")


class DocumentSummaryResponse(BaseModel):
    """문서 요약 응답."""

    document_type: str = Field(..., description="문서 유형")
    summary_lines: list[str] = Field(..., description="3줄 요약")
    expert_opinion: str = Field(..., description="전문가 소견")
    key_findings: list[str] = Field(..., description="핵심 발견 사항")
    recommendations: list[str] = Field(..., description="권장 사항")
    confidence_score: float = Field(..., description="요약 신뢰도")

    @classmethod
    def from_domain(cls, summary: DocumentSummary) -> "DocumentSummaryResponse":
        """도메인 모델에서 응답 모델을 생성합니다."""
        return cls(
            document_type=summary.document_type.value,
            summary_lines=summary.summary_lines,
            expert_opinion=summary.expert_opinion,
            key_findings=summary.key_findings,
            recommendations=summary.recommendations,
            confidence_score=summary.confidence_score,
        )


# =============================================================================
# 의존성
# =============================================================================


def get_document_service() -> DocumentService:
    """DocumentService 인스턴스를 생성합니다."""
    return DocumentService()


# =============================================================================
# 엔드포인트
# =============================================================================


@router.post(
    "/summarize/upload",
    response_model=DocumentSummaryResponse,
    summary="PDF 업로드 요약",
    description="업로드된 PDF 파일을 분석하여 전문가 소견 형태로 3줄 요약합니다",
)
async def summarize_uploaded_pdf(
    file: Annotated[UploadFile, File(description="PDF 파일")],
    document_type: Annotated[
        DocumentTypeInput, Form(description="문서 유형")
    ] = DocumentTypeInput.KPRC_REPORT,
    child_name: Annotated[str | None, Form(description="아동 이름")] = None,
    include_recommendations: Annotated[
        bool, Form(description="권장 사항 포함")
    ] = True,
) -> DocumentSummaryResponse:
    """업로드된 PDF 파일을 요약합니다.

    KPRC 심리검사 보고서 등의 PDF를 업로드하면
    전문가 소견 형태의 3줄 요약을 생성합니다.
    """
    # 파일 유효성 검사
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일만 업로드 가능합니다",
        )

    if file.size and file.size > 10 * 1024 * 1024:  # 10MB 제한
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 크기는 10MB를 초과할 수 없습니다",
        )

    try:
        service = get_document_service()
        pdf_bytes = await file.read()

        summary = await service.summarize_pdf_from_bytes(
            pdf_bytes=pdf_bytes,
            document_type=DocumentType(document_type.value),
            child_name=child_name,
            include_recommendations=include_recommendations,
        )

        return DocumentSummaryResponse.from_domain(summary)

    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류: {e}",
        ) from e


@router.post(
    "/summarize/text",
    response_model=DocumentSummaryResponse,
    summary="텍스트 요약",
    description="텍스트 내용을 분석하여 전문가 소견 형태로 3줄 요약합니다",
)
async def summarize_text(
    request: SummarizeTextRequest,
) -> DocumentSummaryResponse:
    """텍스트 내용을 요약합니다.

    PDF에서 추출된 텍스트나 직접 입력한 텍스트를
    전문가 소견 형태로 요약합니다.
    """
    try:
        service = get_document_service()

        summary = await service.summarize_text(
            text_content=request.text_content,
            document_type=DocumentType(request.document_type.value),
            child_name=request.child_name,
            include_recommendations=request.include_recommendations,
        )

        return DocumentSummaryResponse.from_domain(summary)

    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류: {e}",
        ) from e


@router.post(
    "/summarize/path",
    response_model=DocumentSummaryResponse,
    summary="파일 경로 요약 (내부 서비스용)",
    description="서버 내 PDF 파일 경로를 지정하여 요약합니다 (MSA 연동용)",
)
async def summarize_from_path(
    request: SummarizePathRequest,
) -> DocumentSummaryResponse:
    """파일 경로의 PDF를 요약합니다.

    soul-e 백엔드에서 다운로드한 PDF 파일의 경로를 전달받아
    요약을 생성합니다. MSA 내부 통신용 엔드포인트입니다.
    """
    try:
        service = get_document_service()

        summary = await service.summarize_pdf_from_path(
            file_path=request.file_path,
            document_type=DocumentType(request.document_type.value),
            child_name=request.child_name,
            include_recommendations=request.include_recommendations,
        )

        return DocumentSummaryResponse.from_domain(summary)

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 오류: {e}",
        ) from e


@router.post(
    "/summarize/async",
    response_model=AsyncSummarizeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="비동기 요약 요청 (soul-e 연동용)",
    description="PDF 다운로드 및 요약을 백그라운드로 처리합니다",
)
async def request_async_summarize(
    request: AsyncSummarizeRequest,
    background_tasks: BackgroundTasks,
) -> AsyncSummarizeResponse:
    """검사 결과 PDF 요약을 백그라운드로 처리합니다.

    soul-e에서 검사 완료 후 호출됩니다:
    1. 요청 수신 → 즉시 202 Accepted 응답
    2. 백그라운드에서 PDF 다운로드 및 요약 처리
    3. 완료 후 soul-e에 Webhook 또는 결과 저장
    """
    import logging

    from yeirin_ai.services.document_service import process_assessment_summary_sync

    logger = logging.getLogger(__name__)

    print(f"[API] ========== 비동기 요약 요청 수신 ==========", flush=True)
    print(f"[API] session_id={request.session_id}", flush=True)
    print(f"[API] report_url={request.report_url}", flush=True)

    logger.info(
        "[API] 비동기 요약 요청 수신",
        extra={
            "session_id": request.session_id,
            "child_name": request.child_name,
            "report_url": request.report_url,
        },
    )

    # FastAPI BackgroundTasks 사용 (동기 래퍼 함수)
    print("[API] BackgroundTasks.add_task() 호출", flush=True)
    background_tasks.add_task(
        process_assessment_summary_sync,
        session_id=request.session_id,
        child_name=request.child_name,
        assessment_type=request.assessment_type,
        report_url=request.report_url,
    )

    print("[API] 백그라운드 태스크 등록 완료", flush=True)
    logger.info("[API] 백그라운드 태스크 등록 완료", extra={"session_id": request.session_id})

    return AsyncSummarizeResponse(
        status="accepted",
        session_id=request.session_id,
        message="요약 요청이 수락되었습니다. 백그라운드에서 처리됩니다.",
    )
