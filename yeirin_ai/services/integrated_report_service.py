"""통합 보고서 생성 서비스.

상담의뢰지 PDF와 KPRC 검사지 PDF를 병합하여
통합 보고서를 생성하고 S3에 업로드합니다.
"""

import logging
import time
from datetime import datetime

import httpx

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.integrated_report.models import (
    BaseAssessmentSummary,
    IntegratedReportRequest,
    IntegratedReportResult,
    VoucherEligibilityResult,
)
from yeirin_ai.infrastructure.document import CounselRequestDocxFiller, DocxToPdfConverter
from yeirin_ai.infrastructure.document.government_docx_filler import GovernmentDocxFiller
from yeirin_ai.infrastructure.llm.assessment_opinion_generator import (
    AssessmentOpinionGenerator,
    KprcTScoresData,
    SdqAScores,
)
from yeirin_ai.infrastructure.llm.assessment_opinion_generator import (
    ChildContext as AssessmentChildContext,
)
from yeirin_ai.infrastructure.llm.integrated_opinion_generator import (
    IntegratedOpinionGenerator,
    IntegratedOpinionInput,
)
from yeirin_ai.infrastructure.llm.recommender_opinion_generator import (
    ChildContext,
    RecommenderOpinion,
    RecommenderOpinionGenerator,
)
from yeirin_ai.infrastructure.pdf import PDFMerger
from yeirin_ai.services.assessment_data_service import (
    AssessmentDataService,
    CrtesRAssessmentData,
    KprcAssessmentData,
    SdqAssessmentData,
)

logger = logging.getLogger(__name__)


def _format_bytes(size: int) -> str:
    """바이트 크기를 읽기 쉬운 형식으로 변환."""
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _format_duration(seconds: float) -> str:
    """소요 시간을 읽기 쉬운 형식으로 변환."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


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
        self.government_docx_filler = GovernmentDocxFiller()
        self.pdf_converter = DocxToPdfConverter()
        self.pdf_merger = PDFMerger()
        self.recommender_opinion_generator = RecommenderOpinionGenerator()
        self.assessment_opinion_generator = AssessmentOpinionGenerator()
        self.assessment_data_service = AssessmentDataService()
        self.integrated_opinion_generator = IntegratedOpinionGenerator()

    async def process(self, request: IntegratedReportRequest) -> IntegratedReportResult:
        """통합 보고서를 생성합니다.

        Args:
            request: 통합 보고서 생성 요청

        Returns:
            생성 결과 (S3 key 포함)
        """
        total_start = time.time()
        assessment_keys = request.get_assessment_pdfs_s3_keys()
        logger.info(
            "[INTEGRATED_REPORT] 처리 시작",
            extra={
                "counsel_request_id": request.counsel_request_id,
                "child_name": request.child_name,
                "assessment_count": len(assessment_keys),
                "assessment_types": [t for t, _ in assessment_keys],
            },
        )

        try:
            # PDF 목록 (병합 순서: 사회서비스 이용 추천서 → 상담의뢰지 → KPRC)
            pdfs_to_merge: list[bytes] = []
            step_durations: dict[str, str] = {}

            # 1. 사회서비스 이용 추천서 생성 (Optional: guardian_info 또는 institution_info가 있는 경우)
            has_government_doc = request.guardian_info is not None or request.institution_info is not None
            if has_government_doc:
                step1_start = time.time()
                logger.info("[INTEGRATED_REPORT] Step 1: 사회서비스 이용 추천서 생성 시작...")

                # 1-0. Soul-E 대화내역 기반 추천자 의견 생성
                recommender_opinion: RecommenderOpinion | None = None
                if request.child_id:
                    try:
                        logger.info(
                            "[INTEGRATED_REPORT] Step 1-0: 추천자 의견 AI 생성 시작...",
                            extra={"child_id": request.child_id},
                        )
                        opinion_start = time.time()

                        # 아동 컨텍스트 구성
                        child_context = ChildContext(
                            name=request.child_name,
                            age=request.basic_info.childInfo.age if request.basic_info else None,
                            gender=request.basic_info.childInfo.gender if request.basic_info else None,
                            goals=request.request_motivation.goals if request.request_motivation else None,
                        )

                        # Soul-E 대화내역 기반 추천자 의견 생성
                        recommender_opinion = await self.recommender_opinion_generator.generate_from_child_id(
                            child_id=request.child_id,
                            child_context=child_context,
                        )

                        opinion_duration = time.time() - opinion_start
                        logger.info(
                            "[INTEGRATED_REPORT] Step 1-0 완료: 추천자 의견 AI 생성",
                            extra={
                                "child_id": request.child_id,
                                "opinion_length": len(recommender_opinion.opinion_text),
                                "confidence": recommender_opinion.confidence_score,
                                "duration": _format_duration(opinion_duration),
                            },
                        )
                    except Exception as e:
                        logger.warning(
                            "[INTEGRATED_REPORT] 추천자 의견 생성 실패, 기본 로직 사용",
                            extra={"child_id": request.child_id, "error": str(e)},
                        )
                        # 실패해도 계속 진행 (기존 KPRC 기반 로직 사용)
                        recommender_opinion = None

                # 1-1. Government DOCX 템플릿 채우기
                government_docx_bytes = self.government_docx_filler.fill_template(
                    request, recommender_opinion=recommender_opinion
                )
                logger.debug(
                    "[INTEGRATED_REPORT] 사회서비스 추천서 DOCX 생성 완료",
                    extra={"docx_size": _format_bytes(len(government_docx_bytes))},
                )

                # 1-2. Government DOCX → PDF 변환
                government_pdf_bytes = await self.pdf_converter.convert(government_docx_bytes)
                pdfs_to_merge.append(government_pdf_bytes)

                step1_duration = time.time() - step1_start
                step_durations["government_doc"] = _format_duration(step1_duration)
                logger.info(
                    "[INTEGRATED_REPORT] Step 1 완료: 사회서비스 이용 추천서 PDF 생성",
                    extra={
                        "pdf_size": _format_bytes(len(government_pdf_bytes)),
                        "pdf_size_bytes": len(government_pdf_bytes),
                        "duration": _format_duration(step1_duration),
                    },
                )
            else:
                logger.info(
                    "[INTEGRATED_REPORT] Step 1 건너뜀: 사회서비스 이용 추천서 데이터 없음",
                    extra={"has_guardian_info": False, "has_institution_info": False},
                )

            # 1.5. SDQ-A/CRTES-R 요약 자동 생성 (summary가 없는 경우)
            await self._generate_missing_assessment_summaries(request)

            # 2. 상담의뢰지 DOCX 템플릿 채우기
            step2_start = time.time()
            logger.info("[INTEGRATED_REPORT] Step 2: 상담의뢰지 DOCX 템플릿 채우기 시작...")
            counsel_docx_bytes = self.docx_filler.fill_template(request)
            logger.debug(
                "[INTEGRATED_REPORT] 상담의뢰지 DOCX 생성 완료",
                extra={"docx_size": _format_bytes(len(counsel_docx_bytes))},
            )

            # 2-2. 상담의뢰지 DOCX → PDF 변환 (Gotenberg)
            counsel_pdf_bytes = await self.pdf_converter.convert(counsel_docx_bytes)
            pdfs_to_merge.append(counsel_pdf_bytes)

            step2_duration = time.time() - step2_start
            step_durations["counsel_request"] = _format_duration(step2_duration)
            logger.info(
                "[INTEGRATED_REPORT] Step 2 완료: 상담의뢰지 PDF 생성",
                extra={
                    "pdf_size": _format_bytes(len(counsel_pdf_bytes)),
                    "pdf_size_bytes": len(counsel_pdf_bytes),
                    "duration": _format_duration(step2_duration),
                },
            )

            # 3. 검사 결과 PDF 다운로드 (S3 via yeirin presigned URL)
            step3_start = time.time()
            assessment_s3_keys = request.get_assessment_pdfs_s3_keys()
            assessment_count = len(assessment_s3_keys)

            logger.info(
                "[INTEGRATED_REPORT] Step 3: 검사 결과 PDF 다운로드 시작...",
                extra={
                    "assessment_count": assessment_count,
                    "assessment_types": [t for t, _ in assessment_s3_keys],
                },
            )

            assessment_pdfs: list[bytes] = []
            for assessment_type, s3_key in assessment_s3_keys:
                logger.debug(
                    f"[INTEGRATED_REPORT] {assessment_type} PDF 다운로드 중...",
                    extra={"s3_key": s3_key},
                )
                pdf_bytes = await self._download_assessment_pdf(s3_key, assessment_type)
                assessment_pdfs.append(pdf_bytes)
                pdfs_to_merge.append(pdf_bytes)

            step3_duration = time.time() - step3_start
            step_durations["assessment_download"] = _format_duration(step3_duration)
            logger.info(
                "[INTEGRATED_REPORT] Step 3 완료: 검사 결과 PDF 다운로드",
                extra={
                    "assessment_count": assessment_count,
                    "total_size": _format_bytes(sum(len(pdf) for pdf in assessment_pdfs)),
                    "duration": _format_duration(step3_duration),
                },
            )

            # 4. PDF 병합 using PyMuPDF
            step4_start = time.time()
            pdf_count = len(pdfs_to_merge)

            # 병합 설명 생성
            assessment_type_names = [t for t, _ in assessment_s3_keys]
            assessments_desc = " + ".join(assessment_type_names) if assessment_type_names else "검사 결과"
            merge_description = (
                f"사회서비스 추천서 + 상담의뢰지 + {assessments_desc}"
                if has_government_doc
                else f"상담의뢰지 + {assessments_desc}"
            )
            logger.info(
                f"[INTEGRATED_REPORT] Step 4: PDF 병합 시작 (PyMuPDF) - {merge_description}...",
                extra={
                    "pdf_count": pdf_count,
                    "pdf_sizes": [_format_bytes(len(pdf)) for pdf in pdfs_to_merge],
                },
            )
            merged_pdf_bytes = self.pdf_merger.merge_with_metadata(
                pdfs=pdfs_to_merge,
                title=f"통합 보고서 - {request.child_name}",
                author="예이린 AI 시스템",
                subject=f"상담의뢰지 및 심리검사({assessments_desc}) 통합 보고서",
            )
            step4_duration = time.time() - step4_start
            step_durations["pdf_merge"] = _format_duration(step4_duration)
            logger.info(
                "[INTEGRATED_REPORT] Step 4 완료: PDF 병합",
                extra={
                    "merged_size": _format_bytes(len(merged_pdf_bytes)),
                    "merged_size_bytes": len(merged_pdf_bytes),
                    "duration": _format_duration(step4_duration),
                },
            )

            # 5. S3 업로드 (yeirin 백엔드 internal API 경유)
            step5_start = time.time()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in request.child_name if c.isalnum() or c in "가-힣")
            output_filename = f"IR_{safe_name}_{request.counsel_request_id[:8]}_{timestamp}.pdf"
            logger.info(
                "[INTEGRATED_REPORT] Step 5: S3 업로드 시작...",
                extra={
                    "output_file": output_filename,
                    "file_size": _format_bytes(len(merged_pdf_bytes)),
                },
            )

            s3_key = await self._upload_to_yeirin(
                pdf_bytes=merged_pdf_bytes,
                filename=output_filename,
            )
            step5_duration = time.time() - step5_start
            step_durations["s3_upload"] = _format_duration(step5_duration)
            logger.info(
                "[INTEGRATED_REPORT] Step 5 완료: S3 업로드",
                extra={
                    "s3_key": s3_key,
                    "duration": _format_duration(step5_duration),
                },
            )

            total_duration = time.time() - total_start
            logger.info(
                "[INTEGRATED_REPORT] 처리 완료 ✅",
                extra={
                    "counsel_request_id": request.counsel_request_id,
                    "s3_key": s3_key,
                    "total_duration": _format_duration(total_duration),
                    "has_government_doc": has_government_doc,
                    "assessment_count": assessment_count,
                    "assessment_types": assessment_type_names,
                    "pdf_count": pdf_count,
                    "step_durations": step_durations,
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

    async def _download_assessment_pdf(
        self, s3_key: str, assessment_type: str = "UNKNOWN"
    ) -> bytes:
        """검사 결과 PDF를 S3에서 다운로드합니다.

        yeirin 백엔드의 presigned URL API를 통해
        S3 key로부터 presigned URL을 생성하고 다운로드합니다.

        Args:
            s3_key: 검사 결과 PDF의 S3 객체 키
            assessment_type: 검사 유형 (로깅용, KPRC_CO_SG_E, CRTES_R, SDQ_A)

        Returns:
            PDF 바이트 데이터

        Raises:
            IntegratedReportServiceError: 다운로드 실패 시
        """
        log_prefix = f"[ASSESSMENT_DOWNLOAD:{assessment_type}]"

        try:
            # 1. Presigned URL 생성 (yeirin 백엔드 API)
            logger.debug(
                f"{log_prefix} Presigned URL 생성 요청",
                extra={"s3_key": s3_key},
            )
            presigned_url_start = time.time()
            presigned_url = await self._get_presigned_url(s3_key)
            presigned_url_duration = time.time() - presigned_url_start
            logger.debug(
                f"{log_prefix} Presigned URL 생성 완료",
                extra={"duration": _format_duration(presigned_url_duration)},
            )

            # 2. PDF 다운로드
            download_start = time.time()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(presigned_url)
                response.raise_for_status()

                pdf_bytes = response.content
                download_duration = time.time() - download_start

                if not pdf_bytes:
                    raise IntegratedReportServiceError(
                        f"다운로드된 {assessment_type} PDF가 비어있습니다"
                    )

                logger.debug(
                    f"{log_prefix} PDF 다운로드 완료",
                    extra={
                        "size": _format_bytes(len(pdf_bytes)),
                        "duration": _format_duration(download_duration),
                    },
                )

                return pdf_bytes

        except httpx.HTTPStatusError as e:
            logger.error(
                f"{log_prefix} HTTP 에러",
                extra={
                    "status_code": e.response.status_code,
                    "s3_key": s3_key,
                },
            )
            raise IntegratedReportServiceError(
                f"{assessment_type} PDF 다운로드 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            logger.error(
                f"{log_prefix} 다운로드 실패",
                extra={"s3_key": s3_key, "error": str(e)},
            )
            raise IntegratedReportServiceError(
                f"{assessment_type} PDF 다운로드 실패: {e}"
            ) from e

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

        logger.debug(
            "[PRESIGNED_URL] yeirin API 호출",
            extra={"url": url, "s3_key": s3_key},
        )

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
                    logger.error(
                        "[PRESIGNED_URL] 응답에 URL 없음",
                        extra={"response": result},
                    )
                    raise IntegratedReportServiceError("Presigned URL이 응답에 없습니다")

                logger.debug("[PRESIGNED_URL] URL 생성 성공")
                return presigned_url

        except httpx.HTTPStatusError as e:
            logger.error(
                "[PRESIGNED_URL] HTTP 에러",
                extra={
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:200] if e.response.text else None,
                },
            )
            raise IntegratedReportServiceError(
                f"Presigned URL 생성 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            logger.error(
                "[PRESIGNED_URL] 생성 실패",
                extra={"error": str(e)},
            )
            raise IntegratedReportServiceError(f"Presigned URL 생성 실패: {e}") from e

    async def _upload_to_yeirin(self, pdf_bytes: bytes, filename: str) -> str:
        """통합 보고서 PDF를 yeirin 백엔드에 업로드합니다.

        Args:
            pdf_bytes: PDF 바이트 데이터
            filename: 저장할 파일명

        Returns:
            업로드된 PDF의 S3 키 (integrated-reports/ 디렉터리)

        Raises:
            IntegratedReportServiceError: 업로드 실패 시
        """
        url = f"{settings.yeirin_backend_url}/api/v1/upload/internal/pdf"

        logger.debug(
            "[S3_UPLOAD] yeirin API 호출",
            extra={
                "url": url,
                "filename": filename,
                "file_size": _format_bytes(len(pdf_bytes)),
                "upload_folder": "integrated-reports",
            },
        )

        try:
            upload_start = time.time()
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {
                    "file": (filename, pdf_bytes, "application/pdf"),
                }
                headers = {
                    "X-Internal-Api-Key": settings.internal_api_secret,
                    "X-Upload-Folder": "integrated-reports",  # 통합 보고서 전용 디렉터리
                }

                response = await client.post(url, files=files, headers=headers)
                response.raise_for_status()

                upload_duration = time.time() - upload_start
                result = response.json()
                s3_key = result.get("key")

                if not s3_key:
                    logger.error(
                        "[S3_UPLOAD] 응답에 S3 키 없음",
                        extra={"response": result},
                    )
                    raise IntegratedReportServiceError("S3 키가 응답에 없습니다")

                logger.debug(
                    "[S3_UPLOAD] 업로드 성공",
                    extra={
                        "s3_key": s3_key,
                        "duration": _format_duration(upload_duration),
                    },
                )
                return s3_key

        except httpx.HTTPStatusError as e:
            logger.error(
                "[S3_UPLOAD] HTTP 에러",
                extra={
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:200] if e.response.text else None,
                },
            )
            raise IntegratedReportServiceError(
                f"S3 업로드 HTTP 에러: {e.response.status_code}"
            ) from e
        except Exception as e:
            if isinstance(e, IntegratedReportServiceError):
                raise
            logger.error(
                "[S3_UPLOAD] 업로드 실패",
                extra={"error": str(e)},
            )
            raise IntegratedReportServiceError(f"S3 업로드 실패: {e}") from e

    async def _generate_missing_assessment_summaries(
        self, request: IntegratedReportRequest
    ) -> None:
        """모든 검사 결과의 요약을 100% DB 데이터 기반으로 즉시 생성합니다.

        MSA request 데이터를 사용하지 않고, soul-e DB에서 직접 조회하여 사용합니다.
        - KPRC: DB T점수 → 첫 줄 바우처 조건 + T점수 기반 소견
        - CRTES-R: DB 총점 → 첫 줄 총점/115 + 점수 기반 소견
        - SDQ-A: DB scale_scores → 강점(X/10) + 난점(X/40) 분리

        Args:
            request: 통합 보고서 생성 요청 (in-place 수정됨)
        """
        if not request.attached_assessments:
            return

        if not request.child_id:
            logger.warning(
                "[INTEGRATED_REPORT] child_id 없음, 검사 요약 생성 불가",
            )
            return

        # 아동 컨텍스트 구성 (AssessmentOpinionGenerator용 - goals 없음)
        assessment_child_context = AssessmentChildContext(
            name=request.child_name,
            age=request.basic_info.childInfo.age if request.basic_info else None,
            gender=request.basic_info.childInfo.gender if request.basic_info else None,
        )

        # Soul-E DB에서 모든 검사 데이터 개별 조회 (100% ORM 의존)
        logger.info(
            "[INTEGRATED_REPORT] Soul-E DB에서 검사 데이터 조회 시작 (100% ORM 의존)",
            extra={"child_id": request.child_id},
        )

        # 각 검사 타입별로 개별 조회 (타입 안전성 보장)
        kprc_db_data = await self.assessment_data_service.get_kprc_data(request.child_id)
        sdq_db_data = await self.assessment_data_service.get_sdq_data(request.child_id)
        crtes_r_db_data = await self.assessment_data_service.get_crtes_r_data(request.child_id)

        logger.info(
            "[INTEGRATED_REPORT] Soul-E DB 검사 데이터 조회 완료",
            extra={
                "child_id": request.child_id,
                "has_kprc": kprc_db_data is not None,
                "has_sdq": sdq_db_data is not None,
                "has_crtes_r": crtes_r_db_data is not None,
            },
        )

        for assessment in request.attached_assessments:
            assessment_type = assessment.assessmentType
            generated_summary: BaseAssessmentSummary | None = None

            # SDQ-A 검사 요약 생성 (100% DB 데이터 사용)
            if assessment_type == "SDQ_A":
                logger.info(
                    "[INTEGRATED_REPORT] SDQ-A 요약 생성 시작 (100% DB 데이터)",
                    extra={
                        "child_id": request.child_id,
                        "has_db_data": sdq_db_data is not None,
                    },
                )

                if sdq_db_data is not None:
                    try:
                        opinion_start = time.time()

                        # DB에서 강점/난점 점수 사용
                        strengths_score = sdq_db_data.strength_score
                        difficulties_score = sdq_db_data.difficulty_score

                        logger.info(
                            "[INTEGRATED_REPORT] SDQ-A DB 데이터",
                            extra={
                                "strength_score": strengths_score,
                                "difficulty_score": difficulties_score,
                                "total_score": sdq_db_data.total_score,
                                "scale_scores": sdq_db_data.scale_scores,
                            },
                        )

                        # 강점 또는 난점 점수가 하나라도 있으면 분리 표시
                        # 없는 점수는 0으로 기본값 설정
                        if strengths_score is not None or difficulties_score is not None:
                            strengths_score = strengths_score if strengths_score is not None else 0
                            difficulties_score = difficulties_score if difficulties_score is not None else 0
                            # 강점/난점 분리 소견 생성 (첫 줄에 점수 포함)
                            sdq_scores = SdqAScores(
                                strengths_score=strengths_score,
                                strengths_level=1,  # DB에서 level 정보가 없으면 기본값
                                difficulties_score=difficulties_score,
                                difficulties_level=1,
                                strengths_level_description=None,
                                difficulties_level_description=None,
                            )
                            opinion = await self.assessment_opinion_generator.generate_sdq_a_opinion(
                                scores=sdq_scores,
                                child_context=assessment_child_context,
                            )

                            # 첫 줄에 점수 추가
                            strength_score_line = f"{strengths_score}/10점"
                            difficulty_score_line = f"{difficulties_score}/40점"

                            existing_lines = opinion.summary_lines if opinion.summary_lines else []
                            # LLM이 생성한 첫 줄(점수+이모지)을 건너뛰고 2-3번째 줄만 사용
                            # 강점: [0]=점수줄(스킵), [1]=해석1, [2]=해석2
                            # 난점: [3]=점수줄(스킵), [4]=해석1, [5]=해석2
                            strength_opinion_lines = existing_lines[1:3] if len(existing_lines) >= 3 else []
                            difficulty_opinion_lines = existing_lines[4:6] if len(existing_lines) >= 6 else []

                            new_summary_lines = [
                                strength_score_line,
                                strength_opinion_lines[0] if len(strength_opinion_lines) > 0 else "",
                                strength_opinion_lines[1] if len(strength_opinion_lines) > 1 else "",
                                difficulty_score_line,
                                difficulty_opinion_lines[0] if len(difficulty_opinion_lines) > 0 else "",
                                difficulty_opinion_lines[1] if len(difficulty_opinion_lines) > 1 else "",
                            ]

                            generated_summary = BaseAssessmentSummary(
                                summaryLines=new_summary_lines,
                                expertOpinion=opinion.expert_opinion,
                                keyFindings=opinion.key_findings,
                                recommendations=opinion.recommendations,
                                confidenceScore=opinion.confidence_score,
                            )

                            logger.info(
                                "[INTEGRATED_REPORT] SDQ-A 강점/난점 분리 소견 생성 완료 (DB 데이터)",
                                extra={
                                    "strengths_score": f"{strengths_score}/10",
                                    "difficulties_score": f"{difficulties_score}/40",
                                },
                            )
                        elif sdq_db_data.total_score is not None:
                            # 강점/난점 없고 총점만 있는 경우
                            opinion = await self.assessment_opinion_generator.generate_sdq_a_summary_simple(
                                total_score=sdq_db_data.total_score,
                                max_score=sdq_db_data.max_score,
                                overall_level=None,
                                child_context=assessment_child_context,
                            )

                            total_score = sdq_db_data.total_score
                            max_score = sdq_db_data.max_score or 50

                            existing_lines = opinion.summary_lines if opinion.summary_lines else []
                            # LLM이 생성한 첫 줄(점수+이모지)을 건너뛰고 2-3번째 줄만 사용
                            opinion_lines = existing_lines[1:3] if len(existing_lines) >= 3 else []

                            # 세부 점수 없이 총점만 있는 경우 - 적절한 형식으로 표시
                            # 강점: -/10점, 난점: -/40점 (세부 점수 없음)
                            new_summary_lines = [
                                "-/10점",
                                opinion_lines[0] if len(opinion_lines) > 0 else f"(총점 {total_score}/{max_score}점 기준)",
                                opinion_lines[1] if len(opinion_lines) > 1 else "",
                                "-/40점",
                                opinion_lines[0] if len(opinion_lines) > 0 else f"(총점 {total_score}/{max_score}점 기준)",
                                opinion_lines[1] if len(opinion_lines) > 1 else "",
                            ]

                            generated_summary = BaseAssessmentSummary(
                                summaryLines=new_summary_lines,
                                expertOpinion=opinion.expert_opinion,
                                keyFindings=opinion.key_findings,
                                recommendations=opinion.recommendations,
                                confidenceScore=opinion.confidence_score,
                            )

                            logger.info(
                                "[INTEGRATED_REPORT] SDQ-A 총점 기반 요약 생성 완료 (DB 데이터)",
                                extra={"total_score": f"{total_score}/{max_score}"},
                            )
                        else:
                            generated_summary = BaseAssessmentSummary(
                                summaryLines=["검사 결과가 없습니다.", "", "", "검사 결과가 없습니다.", "", ""],
                                expertOpinion="",
                                keyFindings=[],
                                recommendations=[],
                                confidenceScore=0.0,
                            )

                        opinion_duration = time.time() - opinion_start
                        logger.info(
                            "[INTEGRATED_REPORT] SDQ-A 요약 생성 완료",
                            extra={"duration": _format_duration(opinion_duration)},
                        )

                    except Exception as e:
                        logger.warning(
                            "[INTEGRATED_REPORT] SDQ-A 요약 생성 실패",
                            extra={"error": str(e)},
                        )
                        generated_summary = BaseAssessmentSummary(
                            summaryLines=["검사 결과가 없습니다.", "", "", "검사 결과가 없습니다.", "", ""],
                            expertOpinion="",
                            keyFindings=[],
                            recommendations=[],
                            confidenceScore=0.0,
                        )
                else:
                    logger.info(
                        "[INTEGRATED_REPORT] SDQ-A DB 데이터 없음",
                        extra={"child_id": request.child_id},
                    )
                    generated_summary = BaseAssessmentSummary(
                        summaryLines=["검사 결과가 없습니다.", "", "", "검사 결과가 없습니다.", "", ""],
                        expertOpinion="",
                        keyFindings=[],
                        recommendations=[],
                        confidenceScore=0.0,
                    )

            # CRTES-R 검사 요약 생성 (100% DB 데이터 사용)
            elif assessment_type == "CRTES_R":
                logger.info(
                    "[INTEGRATED_REPORT] CRTES-R 요약 생성 시작 (100% DB 데이터)",
                    extra={
                        "child_id": request.child_id,
                        "has_db_data": crtes_r_db_data is not None,
                    },
                )

                if crtes_r_db_data is not None and crtes_r_db_data.total_score is not None:
                    try:
                        opinion_start = time.time()

                        total_score = crtes_r_db_data.total_score
                        max_score = crtes_r_db_data.max_score or 115

                        logger.info(
                            "[INTEGRATED_REPORT] CRTES-R DB 데이터",
                            extra={
                                "total_score": total_score,
                                "max_score": max_score,
                            },
                        )

                        opinion = await self.assessment_opinion_generator.generate_crtes_r_summary_simple(
                            total_score=total_score,
                            max_score=max_score,
                            overall_level=None,
                            child_context=assessment_child_context,
                        )

                        score_line = f"{total_score}/115점"
                        existing_lines = opinion.summary_lines if opinion.summary_lines else []
                        # LLM이 생성한 첫 줄(점수+이모지)을 건너뛰고 2-3번째 줄만 사용
                        opinion_lines = existing_lines[1:3] if len(existing_lines) >= 3 else []

                        new_summary_lines = [
                            score_line,
                            opinion_lines[0] if len(opinion_lines) > 0 else "",
                            opinion_lines[1] if len(opinion_lines) > 1 else "",
                        ]

                        generated_summary = BaseAssessmentSummary(
                            summaryLines=new_summary_lines,
                            expertOpinion=opinion.expert_opinion,
                            keyFindings=opinion.key_findings,
                            recommendations=opinion.recommendations,
                            confidenceScore=opinion.confidence_score,
                        )

                        opinion_duration = time.time() - opinion_start
                        logger.info(
                            "[INTEGRATED_REPORT] CRTES-R 요약 생성 완료 (DB 데이터)",
                            extra={
                                "duration": _format_duration(opinion_duration),
                                "total_score": f"{total_score}/115",
                            },
                        )

                    except Exception as e:
                        logger.warning(
                            "[INTEGRATED_REPORT] CRTES-R 요약 생성 실패",
                            extra={"error": str(e)},
                        )
                        generated_summary = BaseAssessmentSummary(
                            summaryLines=["검사 결과가 없습니다.", "", ""],
                            expertOpinion="",
                            keyFindings=[],
                            recommendations=[],
                            confidenceScore=0.0,
                        )
                else:
                    logger.info(
                        "[INTEGRATED_REPORT] CRTES-R DB 데이터 없음",
                        extra={"child_id": request.child_id},
                    )
                    generated_summary = BaseAssessmentSummary(
                        summaryLines=["검사 결과가 없습니다.", "", ""],
                        expertOpinion="",
                        keyFindings=[],
                        recommendations=[],
                        confidenceScore=0.0,
                    )

            # KPRC 검사 요약 생성 (100% DB 데이터 사용)
            elif assessment_type.startswith("KPRC"):
                logger.info(
                    "[INTEGRATED_REPORT] KPRC 요약 생성 시작 (100% DB 데이터)",
                    extra={
                        "child_id": request.child_id,
                        "assessment_type": assessment_type,
                        "has_db_data": kprc_db_data is not None,
                    },
                )

                if kprc_db_data is not None and kprc_db_data.t_scores:
                    try:
                        opinion_start = time.time()

                        t_scores = kprc_db_data.t_scores

                        logger.info(
                            "[INTEGRATED_REPORT] KPRC DB T점수 데이터",
                            extra={
                                "t_scores": t_scores,
                                "meets_voucher": kprc_db_data.meets_voucher_criteria,
                                "risk_scales": kprc_db_data.risk_scales,
                            },
                        )

                        # KprcTScoresData 변환 (DB 데이터 → LLM 입력)
                        t_scores_data = KprcTScoresData(
                            ers_t_score=t_scores.get("ERS"),
                            icn_t_score=t_scores.get("ICN"),
                            f_t_score=t_scores.get("F"),
                            vdl_t_score=t_scores.get("VDL"),
                            pdl_t_score=t_scores.get("PDL"),
                            anx_t_score=t_scores.get("ANX"),
                            dep_t_score=t_scores.get("DEP"),
                            som_t_score=t_scores.get("SOM"),
                            dlq_t_score=t_scores.get("DLQ"),
                            hpr_t_score=t_scores.get("HPR"),
                            fam_t_score=t_scores.get("FAM"),
                            soc_t_score=t_scores.get("SOC"),
                            psy_t_score=t_scores.get("PSY"),
                        )

                        opinion = await self.assessment_opinion_generator.generate_kprc_summary(
                            t_scores=t_scores_data,
                            child_context=assessment_child_context,
                        )

                        generated_summary = BaseAssessmentSummary(
                            summaryLines=opinion.summary_lines[:3] if opinion.summary_lines else [],
                            expertOpinion=opinion.expert_opinion,
                            keyFindings=opinion.key_findings,
                            recommendations=opinion.recommendations,
                            confidenceScore=opinion.confidence_score,
                        )

                        opinion_duration = time.time() - opinion_start
                        logger.info(
                            "[INTEGRATED_REPORT] KPRC 요약 생성 완료 (DB 데이터)",
                            extra={
                                "duration": _format_duration(opinion_duration),
                                "meets_voucher": kprc_db_data.meets_voucher_criteria,
                                "risk_scales": kprc_db_data.risk_scales,
                            },
                        )

                    except Exception as e:
                        logger.warning(
                            "[INTEGRATED_REPORT] KPRC 요약 생성 실패",
                            extra={"error": str(e)},
                        )
                        generated_summary = BaseAssessmentSummary(
                            summaryLines=["검사 결과가 없습니다.", "", ""],
                            expertOpinion="",
                            keyFindings=[],
                            recommendations=[],
                            confidenceScore=0.0,
                        )
                else:
                    logger.info(
                        "[INTEGRATED_REPORT] KPRC DB 데이터 없음",
                        extra={"child_id": request.child_id},
                    )
                    generated_summary = BaseAssessmentSummary(
                        summaryLines=["검사 결과가 없습니다.", "", ""],
                        expertOpinion="",
                        keyFindings=[],
                        recommendations=[],
                        confidenceScore=0.0,
                    )

            # 생성된 요약을 assessment에 할당 (항상 덮어쓰기)
            if generated_summary:
                assessment.summary = generated_summary

        # 통합 바우처 추천 대상 판별 (3개 검사 OR 조건)
        voucher_eligibility = self._calculate_combined_voucher_eligibility(
            kprc_db_data=kprc_db_data,
            sdq_db_data=sdq_db_data,
            crtes_r_db_data=crtes_r_db_data,
        )
        request.voucher_eligibility = voucher_eligibility

        logger.info(
            "[INTEGRATED_REPORT] 통합 바우처 추천 대상 판별 완료",
            extra={
                "child_id": request.child_id,
                "is_eligible": voucher_eligibility.is_eligible,
                "eligible_assessments": voucher_eligibility.eligible_assessments,
            },
        )

        # 통합 전문 소견 생성 (LLM 기반)
        await self._generate_integrated_opinion(
            request=request,
            kprc_db_data=kprc_db_data,
            sdq_db_data=sdq_db_data,
            crtes_r_db_data=crtes_r_db_data,
        )

    async def _generate_integrated_opinion(
        self,
        request: IntegratedReportRequest,
        kprc_db_data: KprcAssessmentData | None,
        sdq_db_data: SdqAssessmentData | None,
        crtes_r_db_data: CrtesRAssessmentData | None,
    ) -> None:
        """통합 전문 소견을 LLM으로 생성합니다.

        검사 데이터와 대화 분석을 종합하여 전문적이고 자연스러운
        통합 소견을 생성합니다.

        Args:
            request: 통합 보고서 생성 요청 (in-place 수정됨)
            kprc_db_data: KPRC 검사 데이터
            sdq_db_data: SDQ-A 검사 데이터
            crtes_r_db_data: CRTES-R 검사 데이터
        """
        logger.info(
            "[INTEGRATED_OPINION] 통합 전문 소견 생성 시작",
            extra={"child_id": request.child_id, "child_name": request.child_name},
        )

        opinion_start = time.time()

        try:
            # 입력 데이터 구성
            # KPRC 데이터
            kprc_t_scores: dict[str, int | None] | None = None
            kprc_risk_scales: list[str] | None = None
            kprc_summary: str | None = None

            if kprc_db_data is not None:
                kprc_t_scores = kprc_db_data.t_scores
                kprc_risk_scales = kprc_db_data.risk_scales

            # KPRC 소견 추출 (attached_assessments에서)
            if request.attached_assessments:
                for assessment in request.attached_assessments:
                    if assessment.assessmentType.startswith("KPRC") and assessment.summary:
                        kprc_summary = assessment.summary.expertOpinion

            # SDQ-A 데이터
            sdq_strength_score: int | None = None
            sdq_difficulty_score: int | None = None
            sdq_summary_strength: str | None = None
            sdq_summary_difficulty: str | None = None

            if sdq_db_data is not None:
                sdq_strength_score = sdq_db_data.strength_score
                sdq_difficulty_score = sdq_db_data.difficulty_score

            # SDQ-A 소견 추출 (attached_assessments에서)
            if request.attached_assessments:
                for assessment in request.attached_assessments:
                    if assessment.assessmentType == "SDQ_A" and assessment.summary:
                        sdq_summary_strength = assessment.summary.expertOpinion
                        sdq_summary_difficulty = assessment.summary.expertOpinion

            # CRTES-R 데이터
            crtes_r_score: int | None = None
            crtes_r_summary: str | None = None

            if crtes_r_db_data is not None:
                crtes_r_score = crtes_r_db_data.total_score

            # CRTES-R 소견 추출 (attached_assessments에서)
            if request.attached_assessments:
                for assessment in request.attached_assessments:
                    if assessment.assessmentType == "CRTES_R" and assessment.summary:
                        crtes_r_summary = assessment.summary.expertOpinion

            # 대화 분석 데이터
            conversation_summary: str | None = None
            emotional_keywords: list[str] = []
            key_topics: list[str] = []

            if request.conversationAnalysis:
                # 전문가 분석이 있으면 사용, 없으면 요약 라인 결합
                if request.conversationAnalysis.expertAnalysis:
                    conversation_summary = request.conversationAnalysis.expertAnalysis
                elif request.conversationAnalysis.summaryLines:
                    conversation_summary = " ".join(request.conversationAnalysis.summaryLines)

                if request.conversationAnalysis.emotionalKeywords:
                    emotional_keywords = request.conversationAnalysis.emotionalKeywords

                if request.conversationAnalysis.recommendedFocusAreas:
                    key_topics = request.conversationAnalysis.recommendedFocusAreas
                elif request.conversationAnalysis.keyObservations:
                    key_topics = request.conversationAnalysis.keyObservations

            # 바우처 정보
            is_voucher_eligible = False
            voucher_eligible_assessments: list[str] = []

            if request.voucher_eligibility:
                is_voucher_eligible = request.voucher_eligibility.is_eligible
                voucher_eligible_assessments = request.voucher_eligibility.eligible_assessments

            # IntegratedOpinionInput 생성
            input_data = IntegratedOpinionInput(
                child_name=request.child_name,
                child_age=request.basic_info.childInfo.age if request.basic_info else None,
                child_gender=request.basic_info.childInfo.gender if request.basic_info else None,
                kprc_t_scores=kprc_t_scores,
                kprc_risk_scales=kprc_risk_scales,
                kprc_summary=kprc_summary,
                sdq_strength_score=sdq_strength_score,
                sdq_difficulty_score=sdq_difficulty_score,
                sdq_summary_strength=sdq_summary_strength,
                sdq_summary_difficulty=sdq_summary_difficulty,
                crtes_r_score=crtes_r_score,
                crtes_r_summary=crtes_r_summary,
                conversation_summary=conversation_summary,
                emotional_keywords=emotional_keywords,
                key_topics=key_topics,
                is_voucher_eligible=is_voucher_eligible,
                voucher_eligible_assessments=voucher_eligible_assessments,
            )

            # LLM 통합 소견 생성
            opinion = await self.integrated_opinion_generator.generate(input_data)

            # request에 통합 소견 저장
            request.integrated_opinion = opinion.full_text

            opinion_duration = time.time() - opinion_start
            logger.info(
                "[INTEGRATED_OPINION] 통합 전문 소견 생성 완료",
                extra={
                    "child_id": request.child_id,
                    "opinion_length": len(opinion.full_text),
                    "duration": _format_duration(opinion_duration),
                },
            )

        except Exception as e:
            logger.error(
                "[INTEGRATED_OPINION] 통합 전문 소견 생성 실패",
                extra={"child_id": request.child_id, "error": str(e)},
            )
            # 실패 시에도 계속 진행 (integrated_opinion은 None으로 유지)

    def _calculate_combined_voucher_eligibility(
        self,
        kprc_db_data: KprcAssessmentData | None,
        sdq_db_data: SdqAssessmentData | None,
        crtes_r_db_data: CrtesRAssessmentData | None,
    ) -> VoucherEligibilityResult:
        """통합 바우처 추천 대상 판별.

        3개 검사(KPRC, SDQ-A, CRTES-R) 중 하나라도 기준 충족 시 추천 대상입니다.

        바우처 기준 (OR 조건):
        - KPRC: ERS ≤30T 또는 10개 척도 중 ≥65T (ICN, F 제외)
        - SDQ-A: 강점 ≤4점 (level 2 이상) 또는 난점 ≥17점 (level 2 이상)
        - CRTES-R: 총점 ≥23점 (중등도군 이상)

        Args:
            kprc_db_data: KPRC 검사 데이터
            sdq_db_data: SDQ-A 검사 데이터
            crtes_r_db_data: CRTES-R 검사 데이터

        Returns:
            통합 바우처 추천 대상 판별 결과
        """
        eligible_assessments: list[str] = []

        # 1. KPRC 판별 (assessment_data_service에서 이미 계산됨)
        kprc_eligible: bool | None = None
        kprc_risk_scales: list[str] | None = None

        if kprc_db_data is not None:
            kprc_eligible = kprc_db_data.meets_voucher_criteria
            kprc_risk_scales = kprc_db_data.risk_scales
            if kprc_eligible:
                eligible_assessments.append("KPRC")

        # 2. SDQ-A 판별
        # 기준: 강점 ≤4점 (level 2 이상) OR 난점 ≥17점 (level 2 이상)
        sdq_a_eligible: bool | None = None
        sdq_a_reason: str | None = None

        if sdq_db_data is not None:
            strength_score = sdq_db_data.strength_score
            difficulty_score = sdq_db_data.difficulty_score

            # 강점이 낮을수록 위험 (≤4점이 level 2 이상)
            strength_risk = strength_score is not None and strength_score <= 4
            # 난점이 높을수록 위험 (≥17점이 level 2 이상)
            difficulty_risk = difficulty_score is not None and difficulty_score >= 17

            if strength_risk or difficulty_risk:
                sdq_a_eligible = True
                reasons = []
                if strength_risk:
                    reasons.append(f"강점 {strength_score}점 (≤4)")
                if difficulty_risk:
                    reasons.append(f"난점 {difficulty_score}점 (≥17)")
                sdq_a_reason = ", ".join(reasons)
                eligible_assessments.append("SDQ_A")
            else:
                sdq_a_eligible = False

        # 3. CRTES-R 판별
        # 기준: 총점 ≥23점 (중등도군 이상)
        crtes_r_eligible: bool | None = None
        crtes_r_score: int | None = None

        if crtes_r_db_data is not None:
            crtes_r_score = crtes_r_db_data.total_score
            if crtes_r_score is not None and crtes_r_score >= 23:
                crtes_r_eligible = True
                eligible_assessments.append("CRTES_R")
            else:
                crtes_r_eligible = False

        # 최종 판별 (OR 조건: 하나라도 충족하면 추천 대상)
        is_eligible = len(eligible_assessments) > 0

        return VoucherEligibilityResult(
            is_eligible=is_eligible,
            eligible_assessments=eligible_assessments,
            kprc_eligible=kprc_eligible,
            kprc_risk_scales=kprc_risk_scales,
            sdq_a_eligible=sdq_a_eligible,
            sdq_a_reason=sdq_a_reason,
            crtes_r_eligible=crtes_r_eligible,
            crtes_r_score=crtes_r_score,
        )


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
            "integrated_report_s3_key": result.integrated_report_s3_key,
            "error_message": result.error_message,
        },
    )

    try:
        webhook_start = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = result.model_dump()
            logger.debug(
                "[WEBHOOK] 요청 페이로드",
                extra={"payload": payload},
            )

            response = await client.post(
                webhook_url,
                json=payload,
                headers={"X-Internal-Api-Key": settings.internal_api_secret},
            )
            response.raise_for_status()

            webhook_duration = time.time() - webhook_start
            logger.info(
                "[WEBHOOK] 완료 Webhook 전송 성공 ✅",
                extra={
                    "counsel_request_id": result.counsel_request_id,
                    "status_code": response.status_code,
                    "duration": _format_duration(webhook_duration),
                },
            )

    except httpx.HTTPStatusError as e:
        logger.error(
            "[WEBHOOK] HTTP 에러",
            extra={
                "counsel_request_id": result.counsel_request_id,
                "status_code": e.response.status_code,
                "response_text": e.response.text[:200] if e.response.text else None,
            },
        )
    except Exception as e:
        logger.error(
            "[WEBHOOK] 완료 Webhook 전송 실패 ❌",
            extra={
                "counsel_request_id": result.counsel_request_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
