"""검사 데이터 조회 서비스.

Soul-E DB에서 검사 데이터를 조회하여 상담의뢰지 생성에 활용합니다.
MSA 요청 데이터가 불완전할 경우 DB에서 직접 조회하여 보완합니다.
"""

from dataclasses import dataclass

import logging

from yeirin_ai.infrastructure.database.assessment_repository import AssessmentRepository
from yeirin_ai.infrastructure.database.soul_e_connection import SoulEAsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class KprcAssessmentData:
    """KPRC 검사 데이터."""

    t_scores: dict[str, int | None]
    meets_voucher_criteria: bool
    risk_scales: list[str]


@dataclass
class SdqAssessmentData:
    """SDQ 검사 데이터."""

    total_score: int | None
    max_score: int | None
    scale_scores: dict | None
    strength_score: int | None  # prosocial
    difficulty_score: int | None  # emotional + conduct + hyperactivity + peer
    interpretation: dict | None


@dataclass
class CrtesRAssessmentData:
    """CRTES-R 검사 데이터."""

    total_score: int | None
    max_score: int | None
    interpretation: dict | None


class AssessmentDataService:
    """검사 데이터 조회 서비스.

    Soul-E DB에서 검사 데이터를 조회합니다.
    """

    async def get_kprc_data(self, child_id: str) -> KprcAssessmentData | None:
        """KPRC 검사 데이터 조회.

        Args:
            child_id: 아동 ID

        Returns:
            KPRC 검사 데이터 또는 None
        """
        async with SoulEAsyncSessionLocal() as session:
            repo = AssessmentRepository(session)
            t_scores = await repo.get_kprc_t_scores_by_child(child_id)

            if not t_scores:
                logger.info(
                    "[ASSESSMENT_DATA_SERVICE] KPRC 데이터 없음",
                    extra={"child_id": child_id},
                )
                return None

            # 바우처 조건 판별
            meets_criteria, risk_scales = self._check_voucher_criteria(t_scores)

            logger.info(
                "[ASSESSMENT_DATA_SERVICE] KPRC 데이터 조회 완료",
                extra={
                    "child_id": child_id,
                    "t_scores": t_scores,
                    "meets_voucher_criteria": meets_criteria,
                    "risk_scales": risk_scales,
                },
            )

            return KprcAssessmentData(
                t_scores=t_scores,
                meets_voucher_criteria=meets_criteria,
                risk_scales=risk_scales,
            )

    async def get_sdq_data(self, child_id: str) -> SdqAssessmentData | None:
        """SDQ 검사 데이터 조회.

        Args:
            child_id: 아동 ID

        Returns:
            SDQ 검사 데이터 또는 None
        """
        async with SoulEAsyncSessionLocal() as session:
            repo = AssessmentRepository(session)
            sdq_data = await repo.get_sdq_scores_by_child(child_id)

            if not sdq_data:
                logger.info(
                    "[ASSESSMENT_DATA_SERVICE] SDQ 데이터 없음",
                    extra={"child_id": child_id},
                )
                return None

            # 강점/난점 점수 계산
            scale_scores = sdq_data.get("scale_scores") or {}
            strength_score = None
            difficulty_score = None

            if scale_scores:
                # SDQ scale_scores 구조에 따라 점수 추출
                # 구조: {"prosocial": X, "emotional": X, "conduct": X, "hyperactivity": X, "peer": X}
                # 또는 중첩 구조: {"prosocial": {"score": X}, ...}
                strength_score = self._extract_scale_score(scale_scores, "prosocial")
                difficulty_score = sum(
                    filter(
                        None,
                        [
                            self._extract_scale_score(scale_scores, "emotional"),
                            self._extract_scale_score(scale_scores, "conduct"),
                            self._extract_scale_score(scale_scores, "hyperactivity"),
                            self._extract_scale_score(scale_scores, "peer"),
                        ],
                    )
                )

            logger.info(
                "[ASSESSMENT_DATA_SERVICE] SDQ 데이터 조회 완료",
                extra={
                    "child_id": child_id,
                    "total_score": sdq_data.get("total_score"),
                    "strength_score": strength_score,
                    "difficulty_score": difficulty_score,
                },
            )

            return SdqAssessmentData(
                total_score=sdq_data.get("total_score"),
                max_score=sdq_data.get("max_score"),
                scale_scores=scale_scores,
                strength_score=strength_score,
                difficulty_score=difficulty_score,
                interpretation=sdq_data.get("interpretation"),
            )

    async def get_crtes_r_data(self, child_id: str) -> CrtesRAssessmentData | None:
        """CRTES-R 검사 데이터 조회.

        Args:
            child_id: 아동 ID

        Returns:
            CRTES-R 검사 데이터 또는 None
        """
        async with SoulEAsyncSessionLocal() as session:
            repo = AssessmentRepository(session)
            crtes_data = await repo.get_crtes_r_scores_by_child(child_id)

            if not crtes_data:
                logger.info(
                    "[ASSESSMENT_DATA_SERVICE] CRTES-R 데이터 없음",
                    extra={"child_id": child_id},
                )
                return None

            logger.info(
                "[ASSESSMENT_DATA_SERVICE] CRTES-R 데이터 조회 완료",
                extra={
                    "child_id": child_id,
                    "total_score": crtes_data.get("total_score"),
                    "max_score": crtes_data.get("max_score"),
                },
            )

            return CrtesRAssessmentData(
                total_score=crtes_data.get("total_score"),
                max_score=crtes_data.get("max_score"),
                interpretation=crtes_data.get("interpretation"),
            )

    async def get_all_assessment_data(
        self,
        child_id: str,
    ) -> dict[str, KprcAssessmentData | SdqAssessmentData | CrtesRAssessmentData | None]:
        """모든 검사 데이터 조회.

        Args:
            child_id: 아동 ID

        Returns:
            모든 검사 데이터 딕셔너리
        """
        kprc_data = await self.get_kprc_data(child_id)
        sdq_data = await self.get_sdq_data(child_id)
        crtes_r_data = await self.get_crtes_r_data(child_id)

        return {
            "kprc": kprc_data,
            "sdq": sdq_data,
            "crtes_r": crtes_r_data,
        }

    def _check_voucher_criteria(
        self,
        t_scores: dict[str, int | None],
    ) -> tuple[bool, list[str]]:
        """KPRC 바우처 조건 충족 여부 판별.

        조건: ERS ≤ 30T 또는 나머지 12개 척도 중 하나라도 ≥ 65T

        Args:
            t_scores: T점수 딕셔너리

        Returns:
            (충족 여부, 충족 척도 목록)
        """
        risk_scales: list[str] = []

        # ERS는 낮을수록 위험 (≤30T)
        ers = t_scores.get("ERS")
        if ers is not None and ers <= 30:
            risk_scales.append("ERS")

        # 나머지 12개 척도는 높을수록 위험 (≥65T)
        high_risk_scale_names = [
            "ICN", "F", "VDL", "PDL", "ANX", "DEP",
            "SOM", "DLQ", "HPR", "FAM", "SOC", "PSY",
        ]

        for scale_name in high_risk_scale_names:
            score = t_scores.get(scale_name)
            if score is not None and score >= 65:
                risk_scales.append(scale_name)

        return len(risk_scales) > 0, risk_scales

    def _extract_scale_score(self, scale_scores: dict, key: str) -> int | None:
        """척도 점수 추출 (다양한 구조 지원).

        Args:
            scale_scores: 척도 점수 딕셔너리
            key: 척도 이름

        Returns:
            점수 또는 None
        """
        value = scale_scores.get(key)
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            return value.get("score") or value.get("raw_score")
        return None
