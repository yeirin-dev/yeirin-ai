"""KPRC T점수 추출 API 라우터.

GPT Vision을 사용하여 KPRC 보고서 PDF에서 T점수를 추출합니다.
"""

import asyncio
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from yeirin_ai.core.models.api import (
    KprcExtractionCallbackDTO,
    KprcTScoreDTO,
    KprcTScoreExtractionRequestDTO,
    KprcTScoreExtractionResponseDTO,
)
from yeirin_ai.infrastructure.llm.kprc_vision_extractor import (
    KprcVisionExtractor,
    KprcVisionExtractorError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kprc", tags=["kprc"])


@router.post(
    "/extract-t-scores",
    response_model=KprcTScoreExtractionResponseDTO,
    summary="KPRC T점수 추출",
    description="KPRC 보고서 PDF 2페이지에서 GPT Vision을 사용하여 T점수를 추출합니다.",
)
async def extract_t_scores(
    request: KprcTScoreExtractionRequestDTO,
    background_tasks: BackgroundTasks,
) -> KprcTScoreExtractionResponseDTO:
    """KPRC T점수 추출 API.

    PDF URL에서 KPRC 보고서를 다운로드하고 2페이지의 T점수 프로파일을
    GPT Vision으로 분석하여 13개 척도의 T점수를 추출합니다.

    Args:
        request: 추출 요청 (PDF URL, 콜백 URL)
        background_tasks: 백그라운드 작업 큐

    Returns:
        추출 결과 (T점수, 바우처 조건 충족 여부)

    Raises:
        HTTPException: 400 - 유효성 검증 실패, 500 - 서비스 오류
    """
    extractor = KprcVisionExtractor()

    try:
        # T점수 추출 실행
        result = await extractor.extract_t_scores_from_url(request.pdf_url)

        # 바우처 조건 확인
        meets_criteria, risk_scales = result.check_voucher_criteria()

        # T점수 DTO 생성
        t_scores_dto = KprcTScoreDTO(
            ers_t_score=result.ers_t_score,
            icn_t_score=result.icn_t_score,
            f_t_score=result.f_t_score,
            vdl_t_score=result.vdl_t_score,
            pdl_t_score=result.pdl_t_score,
            anx_t_score=result.anx_t_score,
            dep_t_score=result.dep_t_score,
            som_t_score=result.som_t_score,
            dlq_t_score=result.dlq_t_score,
            hpr_t_score=result.hpr_t_score,
            fam_t_score=result.fam_t_score,
            soc_t_score=result.soc_t_score,
            psy_t_score=result.psy_t_score,
        )

        response = KprcTScoreExtractionResponseDTO(
            assessment_result_id=request.assessment_result_id,
            status="COMPLETED",
            t_scores=t_scores_dto,
            confidence=result.confidence,
            meets_voucher_criteria=meets_criteria,
            risk_scales=risk_scales,
        )

        # 콜백 URL이 있으면 백그라운드에서 전송
        if request.callback_url:
            callback_data = KprcExtractionCallbackDTO(
                assessment_result_id=request.assessment_result_id,
                status="COMPLETED",
                t_scores=t_scores_dto,
                confidence=result.confidence,
                meets_voucher_criteria=meets_criteria,
                voucher_criteria_details={
                    "risk_scales": risk_scales,
                    "raw_response": result.raw_response,
                },
            )
            background_tasks.add_task(
                _send_callback,
                callback_url=request.callback_url,
                callback_data=callback_data,
            )

        logger.info(
            f"KPRC T점수 추출 성공: assessment_result_id={request.assessment_result_id}, "
            f"confidence={result.confidence:.2f}, meets_criteria={meets_criteria}"
        )

        return response

    except KprcVisionExtractorError as e:
        logger.error(f"KPRC T점수 추출 실패: {e}")

        error_response = KprcTScoreExtractionResponseDTO(
            assessment_result_id=request.assessment_result_id,
            status="FAILED",
            t_scores=None,
            confidence=0.0,
            meets_voucher_criteria=False,
            risk_scales=[],
            error_message=str(e),
        )

        # 실패 시에도 콜백 전송
        if request.callback_url:
            callback_data = KprcExtractionCallbackDTO(
                assessment_result_id=request.assessment_result_id,
                status="FAILED",
                error_message=str(e),
            )
            background_tasks.add_task(
                _send_callback,
                callback_url=request.callback_url,
                callback_data=callback_data,
            )

        return error_response

    except Exception as e:
        logger.exception("KPRC T점수 추출 중 예상치 못한 오류")
        raise HTTPException(
            status_code=500,
            detail=f"내부 서버 오류: {str(e)}",
        ) from e


async def _send_callback(
    callback_url: str,
    callback_data: KprcExtractionCallbackDTO,
    max_retries: int = 3,
    retry_delays: tuple[int, ...] = (60, 300, 900),
) -> None:
    """콜백 URL로 결과를 전송합니다.

    Args:
        callback_url: 콜백 URL
        callback_data: 전송할 데이터
        max_retries: 최대 재시도 횟수
        retry_delays: 재시도 간격 (초)
    """
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    callback_url,
                    json=callback_data.model_dump(),
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(
                    f"콜백 전송 성공: {callback_url}, "
                    f"assessment_result_id={callback_data.assessment_result_id}"
                )
                return

        except httpx.HTTPError as e:
            logger.warning(
                f"콜백 전송 실패 (시도 {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                logger.info(f"{delay}초 후 재시도...")
                await asyncio.sleep(delay)

    logger.error(
        f"콜백 전송 최종 실패: {callback_url}, "
        f"assessment_result_id={callback_data.assessment_result_id}"
    )
