"""OpenAI 기반 검사 소견 생성기.

SDQ-A (강점·난점 설문지), CRTES-R (아동 외상 반응 척도),
KPRC (한국 아동·청소년 인성평정척도) 검사 결과를
분석하여 예이린만의 재해석 소견을 생성합니다.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================


@dataclass
class ChildContext:
    """MSA에서 전달받은 아동 정보."""

    name: str
    age: int | None = None
    gender: str | None = None  # "남" or "여" or "MALE" or "FEMALE"

    def get_gender_korean(self) -> str:
        """성별을 한국어로 변환."""
        if self.gender in ("MALE", "남"):
            return "남"
        if self.gender in ("FEMALE", "여"):
            return "여"
        return ""


@dataclass
class SdqAScores:
    """SDQ-A 검사 점수 정보.

    Soul-E에서 계산된 강점/난점 분리 점수와 수준을 담습니다.
    """

    # 강점 (사회지향 행동)
    strengths_score: int  # 0-10
    strengths_level: int  # 1, 2, 3

    # 난점 (외현화 + 내현화)
    difficulties_score: int  # 0-40
    difficulties_level: int  # 1, 2, 3

    # 수준 설명 (선택, 기본값 있음)
    strengths_level_description: str | None = None
    difficulties_level_description: str | None = None

    @property
    def strengths_level_text(self) -> str:
        """강점 수준 텍스트."""
        level_map = {
            1: "양호",
            2: "경계선",
            3: "주의 필요",
        }
        return level_map.get(self.strengths_level, "미정")

    @property
    def difficulties_level_text(self) -> str:
        """난점 수준 텍스트."""
        level_map = {
            1: "양호",
            2: "경계선",
            3: "주의 필요",
        }
        return level_map.get(self.difficulties_level, "미정")


@dataclass
class CrtesRScores:
    """CRTES-R 검사 점수 정보.

    외상 반응 척도 점수와 위험 수준을 담습니다.
    """

    total_score: int  # 0-115 (최대 점수)
    risk_level: Literal["normal", "caution", "high_risk"]
    risk_level_description: str | None = None

    @property
    def risk_level_korean(self) -> str:
        """위험 수준 한국어 텍스트."""
        level_map = {
            "normal": "정상 범위",
            "caution": "주의 필요",
            "high_risk": "고위험",
        }
        return level_map.get(self.risk_level, "미정")


@dataclass
class KprcTScoresData:
    """KPRC T점수 데이터.

    13개 척도의 T점수를 담습니다.
    - ERS (자아탄력성): ≤30T가 위험 (낮을수록 위험)
    - 나머지 12개 척도: ≥65T가 위험 (높을수록 위험)
    """

    ers_t_score: int | None = None  # 자아탄력성
    icn_t_score: int | None = None  # 비일관성
    f_t_score: int | None = None  # 비전형
    vdl_t_score: int | None = None  # 자기보호
    pdl_t_score: int | None = None  # 타인보호
    anx_t_score: int | None = None  # 불안
    dep_t_score: int | None = None  # 우울
    som_t_score: int | None = None  # 신체화
    dlq_t_score: int | None = None  # 비행
    hpr_t_score: int | None = None  # 과잉행동
    fam_t_score: int | None = None  # 가족관계
    soc_t_score: int | None = None  # 사회관계
    psy_t_score: int | None = None  # 정신증

    # 척도명 매핑
    SCALE_NAMES: dict = field(default_factory=lambda: {
        "ers": "자아탄력성",
        "icn": "비일관성",
        "f": "비전형",
        "vdl": "자기보호",
        "pdl": "타인보호",
        "anx": "불안",
        "dep": "우울",
        "som": "신체화",
        "dlq": "비행",
        "hpr": "과잉행동",
        "fam": "가족관계",
        "soc": "사회관계",
        "psy": "정신증",
    })

    def get_risk_scales(self) -> list[str]:
        """위험 기준을 충족하는 척도 목록을 반환합니다.

        - ERS ≤ 30T (낮을수록 위험)
        - 나머지 12개 척도 ≥ 65T (높을수록 위험)
        """
        risk_scales = []

        # ERS는 낮을수록 위험
        if self.ers_t_score is not None and self.ers_t_score <= 30:
            risk_scales.append("ERS (자아탄력성)")

        # 나머지 척도는 높을수록 위험
        high_risk_scales = [
            ("icn", self.icn_t_score),
            ("f", self.f_t_score),
            ("vdl", self.vdl_t_score),
            ("pdl", self.pdl_t_score),
            ("anx", self.anx_t_score),
            ("dep", self.dep_t_score),
            ("som", self.som_t_score),
            ("dlq", self.dlq_t_score),
            ("hpr", self.hpr_t_score),
            ("fam", self.fam_t_score),
            ("soc", self.soc_t_score),
            ("psy", self.psy_t_score),
        ]

        for scale_key, score in high_risk_scales:
            if score is not None and score >= 65:
                scale_name = self.SCALE_NAMES.get(scale_key, scale_key.upper())
                risk_scales.append(f"{scale_key.upper()} ({scale_name})")

        return risk_scales

    def get_notable_scales(self) -> dict[str, list[tuple[str, int]]]:
        """주목할 만한 척도들을 분류하여 반환합니다.

        Returns:
            {"strength": [(척도명, 점수)], "caution": [(척도명, 점수)], "risk": [(척도명, 점수)]}
        """
        result: dict[str, list[tuple[str, int]]] = {
            "strength": [],  # 강점 (ERS ≥ 50 또는 기타 척도 ≤ 45)
            "caution": [],   # 주의 (ERS 31-40 또는 기타 척도 55-64)
            "risk": [],      # 위험 (ERS ≤ 30 또는 기타 척도 ≥ 65)
        }

        # ERS 분류 (낮을수록 위험)
        if self.ers_t_score is not None:
            if self.ers_t_score >= 50:
                result["strength"].append(("자아탄력성", self.ers_t_score))
            elif self.ers_t_score >= 31:
                result["caution"].append(("자아탄력성", self.ers_t_score))
            else:
                result["risk"].append(("자아탄력성", self.ers_t_score))

        # 나머지 척도 분류 (높을수록 위험)
        other_scales = [
            ("불안", self.anx_t_score),
            ("우울", self.dep_t_score),
            ("신체화", self.som_t_score),
            ("비행", self.dlq_t_score),
            ("과잉행동", self.hpr_t_score),
            ("가족관계", self.fam_t_score),
            ("사회관계", self.soc_t_score),
            ("정신증", self.psy_t_score),
        ]

        for scale_name, score in other_scales:
            if score is None:
                continue
            if score <= 45:
                result["strength"].append((scale_name, score))
            elif score <= 64:
                result["caution"].append((scale_name, score))
            else:
                result["risk"].append((scale_name, score))

        return result

    def has_any_score(self) -> bool:
        """T점수가 하나라도 있는지 확인합니다."""
        return any([
            self.ers_t_score, self.icn_t_score, self.f_t_score,
            self.vdl_t_score, self.pdl_t_score, self.anx_t_score,
            self.dep_t_score, self.som_t_score, self.dlq_t_score,
            self.hpr_t_score, self.fam_t_score, self.soc_t_score,
            self.psy_t_score,
        ])


@dataclass
class AssessmentOpinion:
    """생성된 검사 소견."""

    summary_lines: list[str] = field(default_factory=list)  # 요약 문장 (3줄)
    expert_opinion: str = ""  # 전문가 소견 (3-4문장)
    key_findings: list[str] = field(default_factory=list)  # 핵심 발견 사항
    recommendations: list[str] = field(default_factory=list)  # 권장 사항
    confidence_score: float = 0.0  # 신뢰도 점수


# =============================================================================
# 소견 생성기
# =============================================================================


class AssessmentOpinionGenerator:
    """SDQ-A 및 CRTES-R 검사 소견 생성기.

    검사 점수와 수준 정보를 바탕으로 AI가 분석한
    예이린 스타일의 검사 소견을 생성합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = 0.4  # 약간의 창의성
        self.max_tokens = 1200

    # =========================================================================
    # SDQ-A 소견 생성
    # =========================================================================

    async def generate_sdq_a_opinion(
        self,
        scores: SdqAScores,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """SDQ-A 검사 결과로 소견을 생성합니다.

        Args:
            scores: SDQ-A 점수 정보 (강점/난점 분리)
            child_context: 아동 컨텍스트 정보

        Returns:
            AssessmentOpinion 객체
        """
        logger.info(
            "SDQ-A 소견 생성 시작",
            extra={
                "child_name": child_context.name,
                "strengths_score": scores.strengths_score,
                "difficulties_score": scores.difficulties_score,
            },
        )

        prompt = self._build_sdq_a_prompt(scores, child_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_sdq_a_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            opinion = self._parse_opinion(result)

            logger.info(
                "SDQ-A 소견 생성 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": opinion.confidence_score,
                },
            )
            return opinion

        except Exception as e:
            logger.error(
                "SDQ-A 소견 생성 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_sdq_a_opinion(scores, child_context)

    def _get_sdq_a_system_prompt(self) -> str:
        """SDQ-A 소견용 시스템 프롬프트."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 아동 심리 전문가입니다.

SDQ-A (강점·난점 설문지) 검사 결과를 바탕으로
부모님께 전달할 따뜻하고 이해하기 쉬운 소견을 작성합니다.

## SDQ-A 검사 개요:
- **강점 (사회지향 행동)**: 친사회적 행동, 타인에 대한 배려, 공감 능력 (0-10점)
- **난점 (외현화/내현화)**: 정서적 어려움, 행동 문제, 또래 관계, 과잉행동 (0-40점)

## 예이린 소견 원칙:

1. **수치 증거 우선**: 첫줄에 반드시 점수 명시
2. **강점 우선**: 아이의 긍정적인 면을 먼저 언급
3. **균형 잡힌 해석**: 난점도 성장 기회로 긍정적으로 표현
4. **구체적 조언**: 부모님이 실천 가능한 지원 방법 제시
5. **따뜻한 어조**: 전문적이되 친근하고 희망적인 표현
6. **진단 금지**: 장애명이나 진단명 절대 사용 금지

## 작성 형식 (6줄 - 강점 3줄 + 난점 3줄):

### 강점 (사회지향 행동) - 3줄
- **1줄**: 📊 점수 요약 - "강점 X/10점" 형식으로 시작, 수준 해석 포함
- **2줄**: 아이의 강점과 잠재력 (구체적 행동 예시)
- **3줄**: 강점을 더 발달시키기 위한 부모님 조언

### 난점 (정서/행동 어려움) - 3줄
- **4줄**: 📊 점수 요약 - "난점 Y/40점" 형식으로 시작, 수준 해석 포함
- **5줄**: 관심이 필요한 영역 (성장 기회로 표현)
- **6줄**: 난점 영역에서 부모님이 도울 수 있는 방법"""

    def _build_sdq_a_prompt(
        self,
        scores: SdqAScores,
        child_context: ChildContext,
    ) -> str:
        """SDQ-A 소견 프롬프트 생성."""
        # 아동 정보 구성
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        # 강점 수준 설명
        strengths_desc = scores.strengths_level_description or self._get_default_strengths_description(scores.strengths_level)

        # 난점 수준 설명
        difficulties_desc = scores.difficulties_level_description or self._get_default_difficulties_description(scores.difficulties_level)

        return f"""## 아동 정보:
{child_desc}

## SDQ-A 검사 결과:

### 강점 (사회지향 행동)
- 점수: {scores.strengths_score}점 (만점 10점)
- 수준: {scores.strengths_level_text} (Level {scores.strengths_level})
- 해석: {strengths_desc}

### 난점 (정서/행동 어려움)
- 점수: {scores.difficulties_score}점 (만점 40점)
- 수준: {scores.difficulties_level_text} (Level {scores.difficulties_level})
- 해석: {difficulties_desc}

## 요청사항:

1. 위 검사 결과를 바탕으로 **예이린 재해석 6줄 소견**을 작성해주세요.
   - **강점 3줄**:
     - 1줄: 📊 "강점 {scores.strengths_score}/10점" 형식으로 시작, 수준 해석 포함
     - 2줄: 아이의 강점과 잠재력 (구체적 행동 예시)
     - 3줄: 강점을 더 발달시키기 위한 부모님 조언
   - **난점 3줄**:
     - 4줄: 📊 "난점 {scores.difficulties_score}/40점" 형식으로 시작, 수준 해석 포함
     - 5줄: 관심이 필요한 영역 (성장 기회로 표현)
     - 6줄: 난점 영역에서 부모님이 도울 수 있는 방법

2. 전문가 종합 소견을 3-4문장으로 작성해주세요.
3. 핵심 발견 사항 2개를 정리해주세요.
4. 가정에서 실천할 수 있는 권장 사항 2개를 제시해주세요.

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": [
    "강점 X/10점 - 강점 수준 해석",
    "아이의 강점과 잠재력 설명",
    "강점 발달을 위한 부모님 조언",
    "난점 Y/40점 - 난점 수준 해석",
    "관심 필요 영역 설명",
    "난점 영역 부모님 조언"
  ],
  "expert_opinion": "전문가 종합 소견 (3-4문장)",
  "key_findings": [
    "핵심 발견 1",
    "핵심 발견 2"
  ],
  "recommendations": [
    "권장 사항 1",
    "권장 사항 2"
  ],
  "confidence_score": 0.85
}}
""".strip()

    def _get_default_strengths_description(self, level: int) -> str:
        """강점 수준별 기본 설명."""
        descriptions = {
            1: "타인의 감정을 잘 헤아리고 배려하며, 친사회적 행동이 양호합니다.",
            2: "친사회적 행동이 보통 수준이며, 타인에 대한 관심과 배려를 더 발달시킬 수 있습니다.",
            3: "사회적 상호작용과 타인에 대한 관심이 다소 부족할 수 있어 지원이 도움됩니다.",
        }
        return descriptions.get(level, "")

    def _get_default_difficulties_description(self, level: int) -> str:
        """난점 수준별 기본 설명."""
        descriptions = {
            1: "정서와 행동 조절이 양호하며, 또래 관계도 원만합니다.",
            2: "정서 조절이나 행동 조절에서 경계선 수준의 어려움이 관찰됩니다.",
            3: "또래관계와 감정, 행동의 조절에 어려움이 있어 전문적 지원이 권장됩니다.",
        }
        return descriptions.get(level, "")

    def _create_default_sdq_a_opinion(
        self,
        scores: SdqAScores,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """SDQ-A 기본 소견 생성 (6줄: 강점 3줄 + 난점 3줄)."""
        name = child_context.name

        # 강점 수준 해석
        strengths_level_text = {
            1: "양호한 수준",
            2: "경계선 수준",
            3: "관심이 필요한 수준",
        }.get(scores.strengths_level, "확인 필요")

        # 난점 수준 해석
        difficulties_level_text = {
            1: "양호한 수준",
            2: "경계선 수준",
            3: "관심이 필요한 수준",
        }.get(scores.difficulties_level, "확인 필요")

        return AssessmentOpinion(
            summary_lines=[
                # 강점 3줄
                f"강점 {scores.strengths_score}/10점 - {strengths_level_text}입니다.",
                f"{name} 아동은 사회지향적 행동에서 잠재력을 보입니다.",
                "아이의 강점을 인정하고 격려하면 친사회적 행동이 더욱 발달합니다.",
                # 난점 3줄
                f"난점 {scores.difficulties_score}/40점 - {difficulties_level_text}입니다.",
                "정서·행동 영역에서 세심한 관심과 지지가 도움이 될 수 있습니다.",
                "아이의 감정에 공감하며 대화하는 시간이 건강한 발달에 도움이 됩니다.",
            ],
            expert_opinion=(
                f"{name} 아동의 SDQ-A 검사 결과, "
                f"강점 영역 {scores.strengths_score}점({scores.strengths_level_text}), "
                f"난점 영역 {scores.difficulties_score}점({scores.difficulties_level_text})으로 나타났습니다. "
                "아동의 사회적 강점을 바탕으로 정서적 안정감을 높이는 지원이 권장됩니다."
            ),
            key_findings=[
                f"강점(사회지향 행동): {scores.strengths_level_text} 수준",
                f"난점(정서·행동): {scores.difficulties_level_text} 수준",
            ],
            recommendations=[
                "아이의 긍정적 행동에 대해 구체적으로 칭찬하기",
                "감정 표현을 돕는 대화 시간 갖기",
            ],
            confidence_score=0.6,
        )

    # =========================================================================
    # CRTES-R 소견 생성
    # =========================================================================

    async def generate_crtes_r_opinion(
        self,
        scores: CrtesRScores,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """CRTES-R 검사 결과로 소견을 생성합니다.

        Args:
            scores: CRTES-R 점수 정보 (외상 반응 척도)
            child_context: 아동 컨텍스트 정보

        Returns:
            AssessmentOpinion 객체
        """
        logger.info(
            "CRTES-R 소견 생성 시작",
            extra={
                "child_name": child_context.name,
                "total_score": scores.total_score,
                "risk_level": scores.risk_level,
            },
        )

        prompt = self._build_crtes_r_prompt(scores, child_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_crtes_r_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            opinion = self._parse_opinion(result)

            logger.info(
                "CRTES-R 소견 생성 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": opinion.confidence_score,
                },
            )
            return opinion

        except Exception as e:
            logger.error(
                "CRTES-R 소견 생성 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_crtes_r_opinion(scores, child_context)

    def _get_crtes_r_system_prompt(self) -> str:
        """CRTES-R 소견용 시스템 프롬프트."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 아동 심리 전문가입니다.

CRTES-R (아동 외상 반응 척도) 검사 결과를 바탕으로
부모님께 전달할 전문적이고 정확한 소견을 작성합니다.

## CRTES-R 검사 개요:
- 아동이 경험한 스트레스 상황에 대한 정서적 반응을 측정 (0-115점)
- 침습 증상, 회피 증상, 각성 증상 등을 종합 평가

## 심각도 분류 기준 (매우 중요):
- **경증군 (0-14점)**: 정상 범위, 일상적 관심으로 충분
- **중증도군 (15-27점)**: 주의 필요, 전문 상담 권장
- **중증군 (28점 이상)**: 전문적 개입 필요, 즉각적인 전문 상담 강력 권고

## 예이린 소견 원칙:

1. **수치 증거 우선**: 첫줄에 반드시 "총점 X/115점" 형식으로 점수 명시
2. **심각도에 맞는 표현**:
   - 경증군: 따뜻하고 긍정적인 어조
   - 중증도군: 관심 필요성을 명확히, 전문 상담 권장
   - 중증군: 전문적 개입의 필요성을 분명히 전달, 즉각적 조치 권고
3. **민감한 접근**: 외상 관련 검사이므로 조심스럽되 정확하게 표현
4. **과도한 낙관 금지**: 특히 중증군의 경우 "괜찮다", "회복할 수 있다"는 표현 자제
5. **전문 연계 강조**: 중증도군 이상은 반드시 전문 상담 연계 권고
6. **진단 금지**: PTSD 등 진단명 절대 사용 금지

## 작성 형식:

- **1줄**: 📊 수치 요약 - "총점 X/115점" 형식으로 시작, 심각도 수준 명시
- **2줄**: 아이의 현재 상태에 대한 객관적 설명 (심각도에 맞게)
- **3줄**: 필요한 조치 (심각도에 따라 관심/전문상담권장/즉각적개입권고)
- **4줄**: 부모님께 드리는 구체적인 다음 단계 안내"""

    def _build_crtes_r_prompt(
        self,
        scores: CrtesRScores,
        child_context: ChildContext,
    ) -> str:
        """CRTES-R 소견 프롬프트 생성."""
        # 아동 정보 구성
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        # 위험 수준 설명
        risk_desc = scores.risk_level_description or self._get_default_risk_description(scores.risk_level)

        return f"""## 아동 정보:
{child_desc}

## CRTES-R 검사 결과:

- 총점: {scores.total_score}점
- 수준: {scores.risk_level_korean}
- 해석: {risk_desc}

## 요청사항:

1. 위 검사 결과를 바탕으로 **예이린 재해석 4줄 소견**을 작성해주세요.
   - 1줄: 📊 수치 요약 - 반드시 "총점 {scores.total_score}/115점" 형식으로 시작
   - 2줄: 아이의 현재 상태에 대한 이해와 강점
   - 3줄: 관심이 필요한 영역 (회복 관점으로 표현)
   - 4줄: 부모님께 드리는 지지와 조언

2. 전문가 종합 소견을 3-4문장으로 작성해주세요.
3. 핵심 발견 사항 2개를 정리해주세요.
4. 가정에서 실천할 수 있는 권장 사항 2개를 제시해주세요.

⚠️ 중요: PTSD, 외상후 스트레스 장애 등 진단명을 사용하지 마세요.

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": [
    "1줄: 총점 X/115점 - 수치 요약",
    "2줄: 현재 상태 이해와 강점",
    "3줄: 관심 필요 영역 (회복 관점)",
    "4줄: 부모님께 지지와 조언"
  ],
  "expert_opinion": "전문가 종합 소견 (3-4문장)",
  "key_findings": [
    "핵심 발견 1",
    "핵심 발견 2"
  ],
  "recommendations": [
    "권장 사항 1",
    "권장 사항 2"
  ],
  "confidence_score": 0.85
}}
""".strip()

    def _get_default_risk_description(self, risk_level: str) -> str:
        """위험 수준별 기본 설명."""
        descriptions = {
            "normal": "스트레스 상황에 대한 반응이 정상 범위 내에 있습니다.",
            "caution": "일부 스트레스 반응이 관찰되어 관심과 지지가 필요합니다.",
            "high_risk": "스트레스 반응이 높은 수준으로 전문적인 지원이 권장됩니다.",
        }
        return descriptions.get(risk_level, "")

    def _create_default_crtes_r_opinion(
        self,
        scores: CrtesRScores,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """CRTES-R 기본 소견 생성 - 심각도별 분기 처리."""
        name = child_context.name
        total = scores.total_score

        # 심각도 기준: 경증군(0-14), 중증도군(15-27), 중증군(28+)
        if total <= 14:
            # 경증군 - 정상 범위
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total}/115점 - 경증군(정상 범위)입니다.",
                    f"{name} 아동은 스트레스 상황에서 안정적인 정서 반응을 보이고 있습니다.",
                    "일상적인 관심과 지지가 아동의 건강한 발달에 도움이 됩니다.",
                    "안정적인 환경과 따뜻한 관계를 유지해 주세요.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total}점으로 경증군(정상 범위)에 해당합니다. "
                    "현재 스트레스 반응이 안정적인 수준이며, 일상적인 양육 환경에서 "
                    "건강하게 성장할 수 있습니다."
                ),
                key_findings=[
                    f"스트레스 반응: 경증군(정상 범위, {total}점)",
                    "안정적인 정서 반응 확인",
                ],
                recommendations=[
                    "아이와 규칙적인 대화 시간 갖기",
                    "아이의 감정 표현을 격려하고 수용하기",
                ],
                confidence_score=0.7,
            )
        elif total <= 27:
            # 중증도군 - 주의 필요, 전문 상담 권장
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total}/115점 - 중증도군으로 전문 상담이 권장됩니다.",
                    f"{name} 아동에게서 스트레스 상황에 대한 정서적 반응이 관찰되고 있습니다.",
                    "전문 상담사와의 상담을 통해 아동의 상태를 더 정확히 파악하시기 바랍니다.",
                    "조기에 적절한 지원을 받으면 아동의 안정에 큰 도움이 됩니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total}점으로 중증도군에 해당합니다. "
                    "스트레스 상황에 대한 정서적 반응이 주의가 필요한 수준이므로, "
                    "전문 상담사와의 상담을 통해 아동의 상태를 정확히 평가하고 "
                    "적절한 지원 방안을 모색하시기 바랍니다."
                ),
                key_findings=[
                    f"스트레스 반응: 중증도군({total}점) - 전문 상담 권장",
                    "정서적 지지와 전문적 관심이 필요한 수준",
                ],
                recommendations=[
                    "아동 전문 상담사와의 상담을 조속히 예약하기",
                    "아이가 안전하다고 느낄 수 있는 환경 조성하기",
                ],
                confidence_score=0.6,
            )
        else:
            # 중증군 (28점 이상) - 전문적 개입 강력 권고
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total}/115점 - 중증군으로 즉각적인 전문 상담이 필요합니다.",
                    f"{name} 아동에게서 스트레스 상황에 대한 상당한 정서적 어려움이 관찰됩니다.",
                    "전문 기관에서의 심층 평가와 치료적 개입이 강력히 권장됩니다.",
                    "가능한 빠른 시일 내에 아동 전문 상담 기관에 연락하시기 바랍니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total}점으로 중증군에 해당합니다. "
                    "스트레스 반응이 높은 수준으로, 아동이 상당한 정서적 어려움을 겪고 있을 수 있습니다. "
                    "전문 기관에서의 심층 평가와 체계적인 치료적 지원이 시급히 필요합니다. "
                    "가능한 빨리 아동 전문 상담 기관에 연락하여 전문적인 도움을 받으시기 바랍니다."
                ),
                key_findings=[
                    f"스트레스 반응: 중증군({total}점) - 즉각적 전문 개입 필요",
                    "상당한 정서적 어려움이 관찰됨 - 전문 기관 연계 강력 권고",
                ],
                recommendations=[
                    "즉시 아동 전문 상담 기관에 연락하여 심층 평가 받기",
                    "아이에게 안전하고 예측 가능한 일상 환경 제공하기",
                ],
                confidence_score=0.6,
            )

    # =========================================================================
    # 간소화된 요약 생성 (totalScore, maxScore, overallLevel만 사용)
    # =========================================================================

    async def generate_sdq_a_summary_simple(
        self,
        total_score: int | None,
        max_score: int | None,
        overall_level: str | None,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """간소화된 SDQ-A 요약을 생성합니다.

        상세 점수(강점/난점 분리)가 없는 경우 전체 점수와 수준만으로 요약을 생성합니다.

        Args:
            total_score: 총점 (0-50 범위)
            max_score: 최대 점수 (기본 50)
            overall_level: 전체 수준 ('normal', 'caution', 'clinical' 등)
            child_context: 아동 컨텍스트 정보

        Returns:
            AssessmentOpinion 객체
        """
        logger.info(
            "SDQ-A 간소화 요약 생성 시작",
            extra={
                "child_name": child_context.name,
                "total_score": total_score,
                "overall_level": overall_level,
            },
        )

        # 유효한 점수가 없으면 기본 요약 반환
        if total_score is None:
            return self._create_default_sdq_a_simple_opinion(child_context)

        prompt = self._build_sdq_a_simple_prompt(total_score, max_score, overall_level, child_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_sdq_a_simple_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            opinion = self._parse_opinion(result)

            logger.info(
                "SDQ-A 간소화 요약 생성 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": opinion.confidence_score,
                },
            )
            return opinion

        except Exception as e:
            logger.error(
                "SDQ-A 간소화 요약 생성 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_sdq_a_simple_opinion(child_context, total_score, max_score, overall_level)

    def _get_sdq_a_simple_system_prompt(self) -> str:
        """SDQ-A 간소화 요약용 시스템 프롬프트."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 아동 심리 전문가입니다.

SDQ-A (강점·난점 설문지) 검사의 전체 점수와 수준 정보를 바탕으로
부모님께 전달할 따뜻하고 이해하기 쉬운 요약을 작성합니다.

## SDQ-A 검사 개요:
- 강점(친사회적 행동)과 난점(정서/행동 어려움)을 종합 평가
- 전체 점수가 높을수록 난점이 많음을 의미

## 예이린 요약 원칙:

1. **수치 증거 우선**: 첫줄에 반드시 "총점 X/Y점" 형식으로 점수 명시
2. **강점 우선**: 아이의 긍정적인 면을 먼저 언급
3. **균형 잡힌 해석**: 난점도 성장 기회로 긍정적으로 표현
4. **구체적 조언**: 부모님이 실천 가능한 지원 방법 제시
5. **따뜻한 어조**: 전문적이되 친근하고 희망적인 표현
6. **진단 금지**: 장애명이나 진단명 절대 사용 금지"""

    def _build_sdq_a_simple_prompt(
        self,
        total_score: int,
        max_score: int | None,
        overall_level: str | None,
        child_context: ChildContext,
    ) -> str:
        """SDQ-A 간소화 요약 프롬프트 생성."""
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        # 수준 해석
        level_desc = self._interpret_sdq_a_overall_level(overall_level, total_score, max_score or 50)

        return f"""## 아동 정보:
{child_desc}

## SDQ-A 검사 결과 (요약):

- 총점: {total_score}점 (만점 {max_score or 50}점)
- 전체 수준: {level_desc}

## 요청사항:

위 검사 결과를 바탕으로 다음을 작성해주세요:

1. **요약 6줄** (반드시 6줄 - 강점 3줄 + 난점 3줄):
   - **강점 영역 3줄** (친사회적 행동, 사회지향 행동):
     - 1줄: 📊 "총점 {total_score}/{max_score or 50}점 (강점 영역 양호)" 형식으로 시작
     - 2줄: 아이의 대표적 강점과 잠재력
     - 3줄: 강점을 더 키워줄 수 있는 방법
   - **난점 영역 3줄** (정서적 어려움, 행동 관련 - 성장 기회로 표현):
     - 4줄: 관심이 필요한 영역 설명 (점수 기반 해석)
     - 5줄: 이 영역의 긍정적 의미나 성장 가능성
     - 6줄: 가정에서 도움줄 수 있는 구체적 방법

2. 전문가 종합 소견 (2-3문장)
3. 핵심 발견 사항 2개
4. 가정에서 실천할 수 있는 권장 사항 2개

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": ["강점점수+해석", "강점잠재력", "강점조언", "난점해석", "성장가능성", "난점조언"],
  "expert_opinion": "종합 소견",
  "key_findings": ["발견 1", "발견 2"],
  "recommendations": ["권장 1", "권장 2"],
  "confidence_score": 0.75
}}""".strip()

    def _interpret_sdq_a_overall_level(
        self, overall_level: str | None, total_score: int, max_score: int
    ) -> str:
        """SDQ-A 전체 수준 해석."""
        if overall_level == "normal":
            return "양호 - 정서와 행동이 안정적인 상태입니다."
        if overall_level == "caution":
            return "경계선 - 일부 영역에서 관심과 지지가 필요합니다."
        if overall_level == "clinical":
            return "주의 필요 - 전문적인 관심과 지원이 권장됩니다."

        # overall_level이 없거나 비표준일 경우 점수 기반 해석
        ratio = total_score / max_score if max_score > 0 else 0
        if ratio < 0.3:
            return "양호 - 전반적으로 안정적인 상태로 보입니다."
        if ratio < 0.6:
            return "보통 - 일부 영역에서 관심이 도움될 수 있습니다."
        return "관심 필요 - 정서적 지지와 관심이 권장됩니다."

    def _create_default_sdq_a_simple_opinion(
        self,
        child_context: ChildContext,
        total_score: int | None = None,
        max_score: int | None = None,
        overall_level: str | None = None,
    ) -> AssessmentOpinion:
        """SDQ-A 간소화 기본 요약 생성 (6줄: 강점 3줄 + 난점 3줄)."""
        name = child_context.name

        # 수준에 따른 강점/난점 해석 결정
        # overall_level이 없으면 점수 기반으로 추정
        is_concerning = overall_level in ("caution", "clinical", "borderline", "at_risk")
        if not overall_level and total_score is not None:
            # 총점이 높을수록 난점이 큼 (0-50 기준, 20점 이상이면 주의)
            is_concerning = total_score >= 20

        # SDQ-A는 반드시 6줄 (강점 3줄 + 난점 3줄) 필요
        if is_concerning:
            return AssessmentOpinion(
                summary_lines=[
                    # 강점 영역 (1-3줄)
                    f"강점 - {name} 아동의 친사회적 행동 영역입니다.",
                    "타인에 대한 배려와 협력 능력이 발달할 수 있는 잠재력을 가지고 있습니다.",
                    "아이의 작은 배려 행동을 인정해주시면 강점이 더 발달합니다.",
                    # 난점 영역 (4-6줄)
                    "난점 - 정서·행동 영역에서 관심이 필요한 수준입니다.",
                    "또래 관계나 감정 조절에서 어려움이 관찰될 수 있어 전문적 지원이 권장됩니다.",
                    "전문 상담을 통해 아이의 어려움을 구체적으로 파악하고 맞춤 지원을 받으시기 바랍니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 SDQ-A 검사 결과, 정서·행동 영역에서 "
                    "관심과 지원이 필요한 수준으로 나타났습니다. "
                    "전문 상담을 통해 아동의 구체적인 어려움을 파악하고 "
                    "적절한 지원 방안을 모색하시기 바랍니다."
                ),
                key_findings=[
                    "정서·행동 영역에서 주의 깊은 관찰 필요",
                    "전문 상담을 통한 구체적 평가 권장",
                ],
                recommendations=[
                    "아동 전문 상담사와의 심층 상담 고려하기",
                    "아이의 감정을 있는 그대로 수용하며 대화 시간 갖기",
                ],
                confidence_score=0.5,
            )
        else:
            return AssessmentOpinion(
                summary_lines=[
                    # 강점 영역 (1-3줄)
                    f"강점 - {name} 아동은 타인을 배려하고 도우려는 친사회적 성향을 보입니다.",
                    "또래 관계에서 협력적이며 긍정적인 상호작용을 할 수 있습니다.",
                    "이러한 강점을 인정하고 칭찬해주면 더욱 발전할 수 있습니다.",
                    # 난점 영역 (4-6줄)
                    "난점 - 정서·행동 영역이 양호한 수준입니다.",
                    "아이가 성장하면서 자연스럽게 발달해 나갈 것입니다.",
                    "따뜻한 관심과 일관된 양육이 아이의 안정적 발달에 도움이 됩니다.",
                ],
            expert_opinion=(
                f"{name} 아동의 SDQ-A 검사 결과, 친사회적 행동 영역에서 강점을 보이며 "
                "정서·행동 영역에서는 관심과 지지가 권장됩니다. 아동의 강점을 인정하고 "
                "관심이 필요한 부분을 따뜻하게 지지하는 양육이 권장됩니다."
            ),
            key_findings=[
                "친사회적 행동 영역에서 긍정적 강점 확인",
                "정서·행동 영역에서 관심과 지지 권장",
            ],
            recommendations=[
                "아이의 긍정적 행동에 대해 구체적으로 칭찬하기",
                "감정 표현을 돕는 대화 시간 갖기",
            ],
            confidence_score=0.5,
        )

    async def generate_crtes_r_summary_simple(
        self,
        total_score: int | None,
        max_score: int | None,
        overall_level: str | None,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """간소화된 CRTES-R 요약을 생성합니다.

        상세 점수가 없는 경우 전체 점수와 수준만으로 요약을 생성합니다.

        Args:
            total_score: 총점
            max_score: 최대 점수
            overall_level: 전체 수준 ('normal', 'caution', 'clinical' 등)
            child_context: 아동 컨텍스트 정보

        Returns:
            AssessmentOpinion 객체
        """
        logger.info(
            "CRTES-R 간소화 요약 생성 시작",
            extra={
                "child_name": child_context.name,
                "total_score": total_score,
                "overall_level": overall_level,
            },
        )

        # 유효한 점수가 없으면 기본 요약 반환
        if total_score is None:
            return self._create_default_crtes_r_simple_opinion(child_context)

        prompt = self._build_crtes_r_simple_prompt(total_score, max_score, overall_level, child_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_crtes_r_simple_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            opinion = self._parse_opinion(result)

            logger.info(
                "CRTES-R 간소화 요약 생성 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": opinion.confidence_score,
                },
            )
            return opinion

        except Exception as e:
            logger.error(
                "CRTES-R 간소화 요약 생성 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_crtes_r_simple_opinion(child_context, total_score, max_score, overall_level)

    def _get_crtes_r_simple_system_prompt(self) -> str:
        """CRTES-R 간소화 요약용 시스템 프롬프트."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 아동 심리 전문가입니다.

CRTES-R (아동 외상 반응 척도) 검사의 전체 점수와 수준 정보를 바탕으로
부모님께 전달할 전문적이고 정확한 요약을 작성합니다.

## CRTES-R 검사 개요:
- 아동이 경험한 스트레스 상황에 대한 정서적 반응을 측정 (0-115점)
- 점수가 높을수록 스트레스 반응이 큼

## 심각도 분류 기준 (매우 중요):
- **경증군 (0-14점)**: 정상 범위, 일상적 관심으로 충분
- **중증도군 (15-27점)**: 주의 필요, 전문 상담 권장
- **중증군 (28점 이상)**: 전문적 개입 필요, 즉각적인 전문 상담 강력 권고

## 예이린 요약 원칙:

1. **수치 증거 우선**: 첫줄에 반드시 "총점 X/Y점" 형식으로 점수와 심각도 수준 명시
2. **심각도에 맞는 표현**:
   - 경증군: 따뜻하고 긍정적인 어조
   - 중증도군: 관심 필요성을 명확히, 전문 상담 권장
   - 중증군: 전문적 개입의 필요성을 분명히 전달, 즉각적 조치 권고
3. **과도한 낙관 금지**: 특히 중증군의 경우 "괜찮다", "회복할 수 있다"는 표현 자제
4. **전문 연계 강조**: 중증도군 이상은 반드시 전문 상담 연계 권고
5. **진단 금지**: PTSD 등 진단명 절대 사용 금지"""

    def _build_crtes_r_simple_prompt(
        self,
        total_score: int,
        max_score: int | None,
        overall_level: str | None,
        child_context: ChildContext,
    ) -> str:
        """CRTES-R 간소화 요약 프롬프트 생성."""
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        # 수준 해석
        level_desc = self._interpret_crtes_r_overall_level(overall_level, total_score, max_score or 115)

        return f"""## 아동 정보:
{child_desc}

## CRTES-R 검사 결과 (요약):

- 총점: {total_score}점 (만점 {max_score or 115}점)
- 전체 수준: {level_desc}

## 요청사항:

위 검사 결과를 바탕으로 다음을 작성해주세요:

1. **요약 4줄**:
   - 1줄: 📊 수치 요약 - "총점 {total_score}/{max_score or 115}점" 형식으로 시작
   - 2줄: 아이의 현재 상태에 대한 이해와 강점
   - 3줄: 관심이 필요한 영역 (회복 관점으로 표현)
   - 4줄: 부모님께 드리는 지지와 조언

2. 전문가 종합 소견 (2-3문장)
3. 핵심 발견 사항 2개
4. 가정에서 실천할 수 있는 권장 사항 2개

⚠️ 중요: PTSD, 외상후 스트레스 장애 등 진단명을 사용하지 마세요.

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": ["수치요약", "2줄", "3줄", "4줄"],
  "expert_opinion": "종합 소견",
  "key_findings": ["발견 1", "발견 2"],
  "recommendations": ["권장 1", "권장 2"],
  "confidence_score": 0.75
}}""".strip()

    def _interpret_crtes_r_overall_level(
        self, overall_level: str | None, total_score: int, max_score: int
    ) -> str:
        """CRTES-R 전체 수준 해석."""
        if overall_level == "normal":
            return "정상 범위 - 스트레스 반응이 안정적입니다."
        if overall_level == "caution":
            return "주의 필요 - 일부 스트레스 반응이 관찰되어 관심이 필요합니다."
        if overall_level == "clinical":
            return "고위험 - 전문적인 지원과 상담이 권장됩니다."

        # overall_level이 없거나 비표준일 경우 점수 기반 해석
        ratio = total_score / max_score if max_score > 0 else 0
        if ratio < 0.3:
            return "정상 범위 - 스트레스 반응이 안정적으로 보입니다."
        if ratio < 0.6:
            return "주의 필요 - 일부 영역에서 정서적 지지가 도움될 수 있습니다."
        return "관심 필요 - 전문적인 관심과 지원이 권장됩니다."

    def _create_default_crtes_r_simple_opinion(
        self,
        child_context: ChildContext,
        total_score: int | None = None,
        max_score: int | None = None,
        overall_level: str | None = None,
    ) -> AssessmentOpinion:
        """CRTES-R 간소화 기본 요약 생성 (4줄: 수치 1줄 + 내용 3줄) - 심각도별 분기."""
        name = child_context.name
        max_s = max_score or 115

        # 점수가 없으면 기본 응답
        if total_score is None:
            return AssessmentOpinion(
                summary_lines=[
                    "CRTES-R 검사 결과입니다.",
                    f"{name} 아동의 스트레스 반응 수준이 평가되었습니다.",
                    "검사 결과에 따라 적절한 지원이 권장됩니다.",
                    "전문 상담사와 상담하여 구체적인 지원 방안을 확인하시기 바랍니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사가 완료되었습니다. "
                    "구체적인 점수 정보를 확인하여 적절한 지원 방안을 모색하시기 바랍니다."
                ),
                key_findings=[
                    "CRTES-R 검사 완료",
                    "구체적 점수 확인 필요",
                ],
                recommendations=[
                    "검사 결과에 대해 전문가와 상담하기",
                    "아이의 정서 상태 지속적으로 관찰하기",
                ],
                confidence_score=0.4,
            )

        # 심각도 기준: 경증군(0-14), 중증도군(15-27), 중증군(28+)
        if total_score <= 14:
            # 경증군 - 정상 범위
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total_score}/{max_s}점 - 경증군(정상 범위)입니다.",
                    f"{name} 아동은 스트레스 상황에서 안정적인 정서 반응을 보이고 있습니다.",
                    "일상적인 관심과 지지가 아동의 건강한 발달에 도움이 됩니다.",
                    "안정적인 환경과 따뜻한 관계를 유지해 주세요.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total_score}점으로 경증군(정상 범위)에 해당합니다. "
                    "현재 스트레스 반응이 안정적인 수준입니다."
                ),
                key_findings=[
                    f"스트레스 반응: 경증군(정상 범위, {total_score}점)",
                    "안정적인 정서 반응 확인",
                ],
                recommendations=[
                    "아이와 규칙적인 대화 시간 갖기",
                    "아이의 감정 표현을 격려하고 수용하기",
                ],
                confidence_score=0.6,
            )
        elif total_score <= 27:
            # 중증도군 - 주의 필요, 전문 상담 권장
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total_score}/{max_s}점 - 중증도군으로 전문 상담이 권장됩니다.",
                    f"{name} 아동에게서 스트레스 상황에 대한 정서적 반응이 관찰되고 있습니다.",
                    "전문 상담사와의 상담을 통해 아동의 상태를 더 정확히 파악하시기 바랍니다.",
                    "조기에 적절한 지원을 받으면 아동의 안정에 큰 도움이 됩니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total_score}점으로 중증도군에 해당합니다. "
                    "전문 상담을 통해 아동의 상태를 정확히 평가하시기 바랍니다."
                ),
                key_findings=[
                    f"스트레스 반응: 중증도군({total_score}점) - 전문 상담 권장",
                    "정서적 지지와 전문적 관심이 필요한 수준",
                ],
                recommendations=[
                    "아동 전문 상담사와의 상담을 조속히 예약하기",
                    "아이가 안전하다고 느낄 수 있는 환경 조성하기",
                ],
                confidence_score=0.5,
            )
        else:
            # 중증군 (28점 이상) - 전문적 개입 강력 권고
            return AssessmentOpinion(
                summary_lines=[
                    f"총점 {total_score}/{max_s}점 - 중증군으로 즉각적인 전문 상담이 필요합니다.",
                    f"{name} 아동에게서 스트레스 상황에 대한 상당한 정서적 어려움이 관찰됩니다.",
                    "전문 기관에서의 심층 평가와 치료적 개입이 강력히 권장됩니다.",
                    "가능한 빠른 시일 내에 아동 전문 상담 기관에 연락하시기 바랍니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 CRTES-R 검사 결과, "
                    f"총점 {total_score}점으로 중증군에 해당합니다. "
                    "스트레스 반응이 높은 수준으로 즉각적인 전문 개입이 필요합니다. "
                    "가능한 빨리 아동 전문 상담 기관에 연락하시기 바랍니다."
                ),
                key_findings=[
                    f"스트레스 반응: 중증군({total_score}점) - 즉각적 전문 개입 필요",
                    "상당한 정서적 어려움 관찰 - 전문 기관 연계 강력 권고",
                ],
                recommendations=[
                    "즉시 아동 전문 상담 기관에 연락하여 심층 평가 받기",
                    "아이에게 안전하고 예측 가능한 일상 환경 제공하기",
                ],
                confidence_score=0.5,
            )

    # =========================================================================
    # 공통 유틸리티
    # =========================================================================

    def _parse_opinion(self, result: dict) -> AssessmentOpinion:
        """OpenAI 응답을 AssessmentOpinion 객체로 변환."""
        return AssessmentOpinion(
            summary_lines=result.get("summary_lines", []),
            expert_opinion=result.get("expert_opinion", ""),
            key_findings=result.get("key_findings", []),
            recommendations=result.get("recommendations", []),
            confidence_score=float(result.get("confidence_score", 0.0)),
        )

    # =========================================================================
    # KPRC 소견 생성
    # =========================================================================

    async def generate_kprc_summary(
        self,
        t_scores: KprcTScoresData,
        child_context: ChildContext,
    ) -> AssessmentOpinion:
        """KPRC T점수를 바탕으로 소견을 생성합니다.

        Args:
            t_scores: KPRC T점수 데이터 (13개 척도)
            child_context: 아동 컨텍스트 정보

        Returns:
            AssessmentOpinion 객체
        """
        logger.info(
            "KPRC 소견 생성 시작",
            extra={
                "child_name": child_context.name,
                "has_t_scores": t_scores.has_any_score(),
            },
        )

        # T점수가 없으면 기본 소견 반환
        if not t_scores.has_any_score():
            return self._create_default_kprc_opinion(child_context)

        prompt = self._build_kprc_prompt(t_scores, child_context)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_kprc_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            opinion = self._parse_opinion(result)

            logger.info(
                "KPRC 소견 생성 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": opinion.confidence_score,
                },
            )
            return opinion

        except Exception as e:
            logger.error(
                "KPRC 소견 생성 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_kprc_opinion(child_context, t_scores)

    def _get_kprc_system_prompt(self) -> str:
        """KPRC 소견용 시스템 프롬프트."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 아동 심리 전문가입니다.

KPRC (한국 아동·청소년 인성평정척도) 검사 결과를 바탕으로
부모님께 전달할 따뜻하고 이해하기 쉬운 소견을 작성합니다.

## KPRC 검사 개요:
- 아동·청소년의 인성 특성을 다양한 척도로 측정
- T점수 기준: 평균 50점, 표준편차 10점
- 주요 척도:
  - ERS (자아탄력성): 낮을수록 주의 필요 (≤30T가 위험)
  - ANX (불안), DEP (우울), SOM (신체화): 높을수록 주의 필요 (≥65T가 위험)
  - HPR (과잉행동), DLQ (비행): 높을수록 주의 필요
  - FAM (가족관계), SOC (사회관계): 높을수록 주의 필요

## 예이린 소견 원칙:

1. **T점수 해석**: 주요 척도의 T점수를 명시하되 전문용어는 쉽게 설명
2. **강점 우선**: 아이의 긍정적인 측면(높은 자아탄력성, 낮은 문제행동 등)을 먼저 언급
3. **균형 잡힌 해석**: 관심이 필요한 영역도 성장 기회로 긍정적으로 표현
4. **구체적 조언**: 부모님이 실천 가능한 지원 방법 제시
5. **따뜻한 어조**: 전문적이되 친근하고 희망적인 표현
6. **진단 금지**: 장애명이나 진단명 절대 사용 금지

## 작성 형식:

- **1줄**: 📊 전체 프로파일 요약 (주요 특성 언급)
- **2줄**: 아이의 강점과 잠재력 (긍정적 척도 강조)
- **3줄**: 관심이 필요한 영역 (성장 기회로 표현)
- **4줄**: 부모님께 드리는 따뜻한 조언"""

    def _build_kprc_prompt(
        self,
        t_scores: KprcTScoresData,
        child_context: ChildContext,
    ) -> str:
        """KPRC 소견 프롬프트 생성."""
        # 아동 정보 구성
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        # T점수 정보 구성
        t_score_lines = []
        if t_scores.ers_t_score is not None:
            t_score_lines.append(f"- ERS (자아탄력성): {t_scores.ers_t_score}T")
        if t_scores.anx_t_score is not None:
            t_score_lines.append(f"- ANX (불안): {t_scores.anx_t_score}T")
        if t_scores.dep_t_score is not None:
            t_score_lines.append(f"- DEP (우울): {t_scores.dep_t_score}T")
        if t_scores.som_t_score is not None:
            t_score_lines.append(f"- SOM (신체화): {t_scores.som_t_score}T")
        if t_scores.dlq_t_score is not None:
            t_score_lines.append(f"- DLQ (비행): {t_scores.dlq_t_score}T")
        if t_scores.hpr_t_score is not None:
            t_score_lines.append(f"- HPR (과잉행동): {t_scores.hpr_t_score}T")
        if t_scores.fam_t_score is not None:
            t_score_lines.append(f"- FAM (가족관계): {t_scores.fam_t_score}T")
        if t_scores.soc_t_score is not None:
            t_score_lines.append(f"- SOC (사회관계): {t_scores.soc_t_score}T")
        if t_scores.psy_t_score is not None:
            t_score_lines.append(f"- PSY (정신증): {t_scores.psy_t_score}T")

        t_score_text = "\n".join(t_score_lines) if t_score_lines else "T점수 정보 없음"

        # 주목할 척도 분류
        notable = t_scores.get_notable_scales()
        strength_text = ", ".join([f"{name}({score}T)" for name, score in notable["strength"]]) or "없음"
        caution_text = ", ".join([f"{name}({score}T)" for name, score in notable["caution"]]) or "없음"
        risk_text = ", ".join([f"{name}({score}T)" for name, score in notable["risk"]]) or "없음"

        return f"""## 아동 정보:
{child_desc}

## KPRC T점수 프로파일:

{t_score_text}

## T점수 해석 기준:
- 평균: 50T, 표준편차: 10T
- ERS (자아탄력성): 높을수록 좋음, ≤30T는 관심 필요
- 기타 척도 (ANX, DEP, SOM 등): 낮을수록 좋음, ≥65T는 관심 필요

## 척도 분류:
- 강점 영역: {strength_text}
- 보통/주의 영역: {caution_text}
- 관심 필요 영역: {risk_text}

## 요청사항:

1. 위 KPRC T점수를 바탕으로 **예이린 재해석 4줄 소견**을 작성해주세요.
   - 1줄: 📊 프로파일 요약 - 주요 척도와 전반적 특성 설명
   - 2줄: 아이의 강점과 잠재력 (긍정적 척도 강조)
   - 3줄: 관심이 필요한 영역 (성장 기회로 표현)
   - 4줄: 부모님께 드리는 따뜻한 조언

2. 전문가 종합 소견을 3-4문장으로 작성해주세요.
3. 핵심 발견 사항 2개를 정리해주세요.
4. 가정에서 실천할 수 있는 권장 사항 2개를 제시해주세요.

⚠️ 중요: 진단명(ADHD, 우울증 등)을 사용하지 마세요. T점수는 참고용이며, 아이의 성장 가능성에 초점을 맞춰주세요.

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": [
    "1줄: 프로파일 요약",
    "2줄: 강점과 잠재력",
    "3줄: 관심 필요 영역 (성장 기회)",
    "4줄: 부모님께 조언"
  ],
  "expert_opinion": "전문가 종합 소견 (3-4문장)",
  "key_findings": [
    "핵심 발견 1",
    "핵심 발견 2"
  ],
  "recommendations": [
    "권장 사항 1",
    "권장 사항 2"
  ],
  "confidence_score": 0.85
}}
""".strip()

    def _create_default_kprc_opinion(
        self,
        child_context: ChildContext,
        t_scores: KprcTScoresData | None = None,
    ) -> AssessmentOpinion:
        """KPRC 기본 소견 생성."""
        name = child_context.name

        # T점수 기반 기본 소견 구성
        if t_scores and t_scores.has_any_score():
            notable = t_scores.get_notable_scales()

            # 강점 텍스트
            if notable["strength"]:
                strengths = [name for name, _ in notable["strength"][:2]]
                strength_line = f"{name} 아동은 {', '.join(strengths)} 영역에서 양호한 수준을 보입니다."
            else:
                strength_line = f"{name} 아동은 전반적으로 안정적인 발달을 보이고 있습니다."

            # 주의 영역 텍스트
            if notable["risk"]:
                risks = [name for name, _ in notable["risk"][:2]]
                caution_line = f"{', '.join(risks)} 영역에서 관심과 지지가 도움이 될 수 있습니다."
            elif notable["caution"]:
                cautions = [name for name, _ in notable["caution"][:2]]
                caution_line = f"{', '.join(cautions)} 영역에서 세심한 관심이 권장됩니다."
            else:
                caution_line = "현재 특별히 우려되는 영역은 관찰되지 않았습니다."

            return AssessmentOpinion(
                summary_lines=[
                    f"KPRC 검사 결과, {name} 아동의 인성 프로파일을 확인하였습니다.",
                    strength_line,
                    caution_line,
                    "아이의 강점을 인정하고 격려하는 양육이 건강한 발달에 도움이 됩니다.",
                ],
                expert_opinion=(
                    f"{name} 아동의 KPRC 검사 결과, 전반적인 인성 특성을 평가하였습니다. "
                    "아동의 강점을 바탕으로 관심이 필요한 영역을 따뜻하게 지원하면 "
                    "건강한 발달에 도움이 됩니다."
                ),
                key_findings=[
                    "KPRC 인성 프로파일 평가 완료",
                    "아동의 강점과 관심 필요 영역 확인",
                ],
                recommendations=[
                    "아이의 긍정적 행동과 노력을 구체적으로 칭찬하기",
                    "안정적인 일상 루틴과 따뜻한 관계 유지하기",
                ],
                confidence_score=0.6,
            )

        # T점수 없을 때 기본 소견
        return AssessmentOpinion(
            summary_lines=[
                "KPRC 검사가 완료되었습니다.",
                f"{name} 아동은 다양한 잠재력을 가지고 있습니다.",
                "상세 결과는 전문 상담을 통해 확인하실 수 있습니다.",
                "아이의 강점을 발견하고 격려해주시기 바랍니다.",
            ],
            expert_opinion=(
                f"{name} 아동의 KPRC 검사가 완료되었습니다. "
                "상세한 T점수 프로파일 분석을 통해 아동의 인성 특성을 파악할 수 있습니다. "
                "전문 상담사와 함께 결과를 해석하시면 더욱 도움이 됩니다."
            ),
            key_findings=[
                "KPRC 인성검사 완료",
                "상세 분석을 위한 전문 상담 권장",
            ],
            recommendations=[
                "아이의 다양한 측면에 관심 갖기",
                "긍정적인 양육 환경 유지하기",
            ],
            confidence_score=0.4,
        )
