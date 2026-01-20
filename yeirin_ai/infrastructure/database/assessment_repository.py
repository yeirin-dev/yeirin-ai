"""Soul-E 검사 데이터 Repository (읽기 전용).

Soul-E의 검사 데이터를 조회하는 Repository입니다.
"""

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yeirin_ai.infrastructure.database.soul_e_models import (
    AssessmentResultORM,
    AssessmentSessionORM,
    AssessmentStatus,
    KprcTScoreExtractionORM,
    TScoreExtractionStatus,
)

logger = structlog.get_logger(__name__)


class AssessmentRepository:
    """Soul-E 검사 데이터 조회 Repository (읽기 전용)."""

    def __init__(self, session: AsyncSession):
        """Repository 초기화.

        Args:
            session: Soul-E DB AsyncSession
        """
        self._session = session

    async def get_completed_sessions_by_child_id(
        self,
        child_id: str,
    ) -> list[AssessmentSessionORM]:
        """아동 ID로 완료된 검사 세션 목록 조회.

        Args:
            child_id: yeirin DB의 아동 ID

        Returns:
            완료된 검사 세션 목록
        """
        stmt = (
            select(AssessmentSessionORM)
            .where(AssessmentSessionORM.child_id == child_id)
            .where(AssessmentSessionORM.status == AssessmentStatus.COMPLETED)
            .order_by(AssessmentSessionORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_result_by_session_id(
        self,
        session_id: str | UUID,
    ) -> AssessmentResultORM | None:
        """세션 ID로 검사 결과 조회.

        Args:
            session_id: 검사 세션 ID

        Returns:
            검사 결과 ORM 또는 None
        """
        session_id_str = str(session_id)
        stmt = (
            select(AssessmentResultORM)
            .where(AssessmentResultORM.session_id == session_id_str)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_result_with_t_score_extraction(
        self,
        session_id: str | UUID,
    ) -> tuple[AssessmentResultORM | None, KprcTScoreExtractionORM | None]:
        """세션 ID로 검사 결과와 T점수 추출 데이터를 함께 조회.

        Args:
            session_id: 검사 세션 ID

        Returns:
            (검사 결과, KPRC T점수 추출) 튜플
        """
        session_id_str = str(session_id)

        # 검사 결과 조회
        result_stmt = (
            select(AssessmentResultORM)
            .where(AssessmentResultORM.session_id == session_id_str)
        )
        result = await self._session.execute(result_stmt)
        assessment_result = result.scalar_one_or_none()

        if not assessment_result:
            return None, None

        # KPRC T점수 추출 데이터 조회
        t_score_stmt = (
            select(KprcTScoreExtractionORM)
            .where(KprcTScoreExtractionORM.assessment_result_id == assessment_result.id)
            .where(
                KprcTScoreExtractionORM.extraction_status == TScoreExtractionStatus.COMPLETED
            )
        )
        t_score_result = await self._session.execute(t_score_stmt)
        t_score_extraction = t_score_result.scalar_one_or_none()

        return assessment_result, t_score_extraction

    async def get_latest_result_by_child_and_type(
        self,
        child_id: str,
        assessment_type: str,
    ) -> tuple[AssessmentSessionORM | None, AssessmentResultORM | None]:
        """아동 ID와 검사 유형으로 가장 최신 검사 결과 조회.

        Args:
            child_id: yeirin DB의 아동 ID
            assessment_type: 검사 유형 (예: 'KPRC_CO_SG_E', 'SDQ_KO', 'CRTES_R')

        Returns:
            (세션, 결과) 튜플
        """
        # 최신 완료 세션 조회
        session_stmt = (
            select(AssessmentSessionORM)
            .where(AssessmentSessionORM.child_id == child_id)
            .where(AssessmentSessionORM.assessment_type.ilike(f"%{assessment_type}%"))
            .where(AssessmentSessionORM.status == AssessmentStatus.COMPLETED)
            .order_by(AssessmentSessionORM.created_at.desc())
            .limit(1)
        )
        session_result = await self._session.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            return None, None

        # 해당 세션의 결과 조회
        result = await self.get_result_by_session_id(session.id)
        return session, result

    async def get_kprc_t_scores_by_child(
        self,
        child_id: str,
    ) -> dict[str, int | None] | None:
        """아동 ID로 KPRC T점수 조회.

        Args:
            child_id: yeirin DB의 아동 ID

        Returns:
            T점수 딕셔너리 또는 None
        """
        # KPRC 세션 조회
        session, result = await self.get_latest_result_by_child_and_type(
            child_id=child_id,
            assessment_type="KPRC",
        )

        if not result:
            logger.info(
                "[ASSESSMENT_REPO] KPRC 결과 없음",
                extra={"child_id": child_id},
            )
            return None

        # T점수 추출 데이터 조회
        t_score_stmt = (
            select(KprcTScoreExtractionORM)
            .where(KprcTScoreExtractionORM.assessment_result_id == result.id)
            .where(
                KprcTScoreExtractionORM.extraction_status == TScoreExtractionStatus.COMPLETED
            )
        )
        t_score_result = await self._session.execute(t_score_stmt)
        t_score_extraction = t_score_result.scalar_one_or_none()

        if t_score_extraction:
            logger.info(
                "[ASSESSMENT_REPO] KPRC T점수 추출 데이터 발견",
                extra={
                    "child_id": child_id,
                    "extraction_id": t_score_extraction.id,
                    "meets_voucher": t_score_extraction.meets_voucher_criteria,
                },
            )
            return t_score_extraction.get_all_t_scores()

        # T점수 추출 데이터가 없으면 assessment_results.t_scores 사용
        if result.t_scores:
            logger.info(
                "[ASSESSMENT_REPO] assessment_results.t_scores 사용",
                extra={"child_id": child_id, "result_id": result.id},
            )
            # t_scores 구조: {"ANX": {"t_score": 65, "percentile": 93}, ...}
            t_scores = {}
            for scale, data in result.t_scores.items():
                if isinstance(data, dict) and "t_score" in data:
                    t_scores[scale] = data["t_score"]
                elif isinstance(data, int):
                    t_scores[scale] = data
            return t_scores

        logger.warning(
            "[ASSESSMENT_REPO] T점수 데이터 없음",
            extra={"child_id": child_id, "result_id": result.id},
        )
        return None

    async def get_sdq_scores_by_child(
        self,
        child_id: str,
    ) -> dict | None:
        """아동 ID로 SDQ 검사 점수 조회.

        Args:
            child_id: yeirin DB의 아동 ID

        Returns:
            SDQ 점수 정보 딕셔너리 또는 None
            {
                "total_score": int,
                "max_score": int,
                "scale_scores": {
                    "prosocial": int,  # 친사회적 행동 (강점)
                    "emotional": int,  # 정서 문제 (난점)
                    "conduct": int,    # 행동 문제 (난점)
                    "hyperactivity": int,  # 과잉행동 (난점)
                    "peer": int,       # 또래 문제 (난점)
                },
                "interpretation": dict,
            }
        """
        session, result = await self.get_latest_result_by_child_and_type(
            child_id=child_id,
            assessment_type="SDQ",
        )

        if not result:
            logger.info(
                "[ASSESSMENT_REPO] SDQ 결과 없음",
                extra={"child_id": child_id},
            )
            return None

        logger.info(
            "[ASSESSMENT_REPO] SDQ 결과 발견",
            extra={
                "child_id": child_id,
                "result_id": result.id,
                "total_score": result.total_score,
                "max_score": result.max_score,
                "has_scale_scores": bool(result.scale_scores),
            },
        )

        return {
            "total_score": result.total_score,
            "max_score": result.max_score,
            "scale_scores": result.scale_scores,
            "interpretation": result.interpretation,
        }

    async def get_crtes_r_scores_by_child(
        self,
        child_id: str,
    ) -> dict | None:
        """아동 ID로 CRTES-R 검사 점수 조회.

        Args:
            child_id: yeirin DB의 아동 ID

        Returns:
            CRTES-R 점수 정보 딕셔너리 또는 None
            {
                "total_score": int,
                "max_score": int,
                "interpretation": dict,
            }
        """
        session, result = await self.get_latest_result_by_child_and_type(
            child_id=child_id,
            assessment_type="CRTES",
        )

        if not result:
            logger.info(
                "[ASSESSMENT_REPO] CRTES-R 결과 없음",
                extra={"child_id": child_id},
            )
            return None

        logger.info(
            "[ASSESSMENT_REPO] CRTES-R 결과 발견",
            extra={
                "child_id": child_id,
                "result_id": result.id,
                "total_score": result.total_score,
                "max_score": result.max_score,
            },
        )

        return {
            "total_score": result.total_score,
            "max_score": result.max_score,
            "interpretation": result.interpretation,
        }

    async def get_all_assessment_data_by_child(
        self,
        child_id: str,
    ) -> dict:
        """아동 ID로 모든 검사 데이터 조회.

        Args:
            child_id: yeirin DB의 아동 ID

        Returns:
            모든 검사 데이터 딕셔너리
            {
                "kprc": {...} | None,
                "sdq": {...} | None,
                "crtes_r": {...} | None,
            }
        """
        kprc_t_scores = await self.get_kprc_t_scores_by_child(child_id)
        sdq_scores = await self.get_sdq_scores_by_child(child_id)
        crtes_r_scores = await self.get_crtes_r_scores_by_child(child_id)

        return {
            "kprc": {"t_scores": kprc_t_scores} if kprc_t_scores else None,
            "sdq": sdq_scores,
            "crtes_r": crtes_r_scores,
        }
