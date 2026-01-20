"""통합 전문 소견 생성기.

검사 데이터(KPRC, SDQ-A, CRTES-R)와 Soul-E 대화 분석을 바탕으로
전문적이고 자연스러운 통합 소견을 생성합니다.
"""

import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================


@dataclass
class IntegratedOpinionInput:
    """통합 소견 생성 입력 데이터."""

    child_name: str
    child_age: int | None = None
    child_gender: str | None = None

    # KPRC 데이터
    kprc_t_scores: dict[str, int | None] | None = None
    kprc_risk_scales: list[str] | None = None
    kprc_summary: str | None = None

    # SDQ-A 데이터
    sdq_strength_score: int | None = None
    sdq_difficulty_score: int | None = None
    sdq_summary_strength: str | None = None
    sdq_summary_difficulty: str | None = None

    # CRTES-R 데이터
    crtes_r_score: int | None = None
    crtes_r_summary: str | None = None

    # 대화 분석 데이터
    conversation_summary: str | None = None
    emotional_keywords: list[str] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)

    # 바우처 결과
    is_voucher_eligible: bool = False
    voucher_eligible_assessments: list[str] = field(default_factory=list)


@dataclass
class IntegratedOpinion:
    """생성된 통합 소견."""

    full_text: str
    voucher_statement: str


# =============================================================================
# 소견 생성기
# =============================================================================


class IntegratedOpinionGenerator:
    """통합 전문 소견 생성기.

    검사 데이터와 AI 대화 분석을 종합하여
    예이린 스타일의 통합 전문 소견을 생성합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = 0.5
        self.max_tokens = 1500

    async def generate(self, input_data: IntegratedOpinionInput) -> IntegratedOpinion:
        """통합 전문 소견을 생성합니다.

        Args:
            input_data: 통합 소견 생성 입력 데이터

        Returns:
            생성된 통합 소견
        """
        logger.info(
            "[INTEGRATED_OPINION] 통합 소견 생성 시작",
            extra={"child_name": input_data.child_name},
        )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(input_data)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            opinion_text = response.choices[0].message.content or ""
            voucher_statement = self._get_voucher_statement(input_data)

            # 바우처 문구를 소견 끝에 추가
            full_text = f"{opinion_text.strip()}\n\n{voucher_statement}"

            logger.info(
                "[INTEGRATED_OPINION] 통합 소견 생성 완료",
                extra={
                    "child_name": input_data.child_name,
                    "opinion_length": len(full_text),
                },
            )

            return IntegratedOpinion(
                full_text=full_text,
                voucher_statement=voucher_statement,
            )

        except Exception as e:
            logger.error(
                "[INTEGRATED_OPINION] 통합 소견 생성 실패",
                extra={"child_name": input_data.child_name, "error": str(e)},
            )
            # 폴백 소견 반환
            return self._create_fallback_opinion(input_data)

    def _build_system_prompt(self) -> str:
        """시스템 프롬프트를 생성합니다."""
        return """당신은 예이린 사회적협동조합의 아동심리 전문가입니다.
아동의 심리검사 결과와 AI 상담 대화 분석을 바탕으로 통합 전문 소견을 작성합니다.

## 작성 원칙:
1. 전문적이면서도 따뜻하고 희망적인 어조로 작성
2. 검사 결과를 자연스럽게 통합하여 설명 (검사별로 나누지 않음)
3. 아동의 강점과 어려움을 균형있게 서술
4. 구체적인 지원 방향과 권고 사항 제시
5. 400-600자 분량 (5-7문단)

## 출력 구조:
1. 인사말 (예이린 사회적협동조합 소개)
2. 검사 방법론 간략 설명 (표준화 심리검사 + AI 대화 분석)
3. 아동의 정서 상태 종합 평가 (검사 결과 통합)
4. 대화에서 발견된 특징 (있는 경우)
5. 전문적 권고사항 (심리상담 서비스 필요성, 지원 방향)
6. 마무리 인사

## 주의사항:
- "KPRC 검사에서...", "SDQ-A 검사 결과..." 등 검사명을 직접 언급하지 않음
- 자연스러운 문장으로 검사 결과를 통합하여 서술
- 아동의 이름을 사용하여 개인화된 소견 작성
- 부정적인 내용도 희망적인 관점에서 서술
- 바우처 관련 내용은 포함하지 않음 (별도 추가됨)"""

    def _build_user_prompt(self, data: IntegratedOpinionInput) -> str:
        """사용자 프롬프트를 생성합니다."""
        sections = [f"## 아동 정보\n아동명: {data.child_name}"]

        if data.child_age:
            sections.append(f"나이: {data.child_age}세")
        if data.child_gender:
            gender_korean = "남" if data.child_gender in ("MALE", "남") else "여"
            sections.append(f"성별: {gender_korean}")

        # KPRC 정보
        if data.kprc_t_scores:
            kprc_info = ["\n## KPRC 검사 결과 (인성평정척도)"]
            kprc_info.append("주요 T점수:")
            for scale, score in data.kprc_t_scores.items():
                if score is not None:
                    # 위험 척도 표시
                    risk_marker = ""
                    if scale == "ERS" and score <= 30:
                        risk_marker = " (⚠️ 위험)"
                    elif scale not in ("ERS", "ICN", "F") and score >= 65:
                        risk_marker = " (⚠️ 위험)"
                    kprc_info.append(f"  - {scale}: {score}T{risk_marker}")

            if data.kprc_risk_scales:
                kprc_info.append(f"위험 기준 충족 척도: {', '.join(data.kprc_risk_scales)}")
            if data.kprc_summary:
                kprc_info.append(f"요약: {data.kprc_summary}")
            sections.append("\n".join(kprc_info))

        # SDQ-A 정보
        if data.sdq_strength_score is not None or data.sdq_difficulty_score is not None:
            sdq_info = ["\n## SDQ-A 검사 결과 (강점·난점 설문지)"]
            if data.sdq_strength_score is not None:
                strength_risk = " (⚠️ 낮음)" if data.sdq_strength_score <= 4 else ""
                sdq_info.append(f"강점 점수: {data.sdq_strength_score}/10점{strength_risk}")
            if data.sdq_difficulty_score is not None:
                difficulty_risk = " (⚠️ 높음)" if data.sdq_difficulty_score >= 17 else ""
                sdq_info.append(f"난점 점수: {data.sdq_difficulty_score}/40점{difficulty_risk}")
            if data.sdq_summary_strength:
                sdq_info.append(f"강점 소견: {data.sdq_summary_strength}")
            if data.sdq_summary_difficulty:
                sdq_info.append(f"난점 소견: {data.sdq_summary_difficulty}")
            sections.append("\n".join(sdq_info))

        # CRTES-R 정보
        if data.crtes_r_score is not None:
            crtes_info = ["\n## CRTES-R 검사 결과 (아동 외상 반응 척도)"]
            risk_level = ""
            if data.crtes_r_score <= 16:
                risk_level = "정상군"
            elif data.crtes_r_score <= 22:
                risk_level = "경미군"
            elif data.crtes_r_score <= 30:
                risk_level = "중등도군 (⚠️)"
            else:
                risk_level = "중증군 (⚠️)"
            crtes_info.append(f"총점: {data.crtes_r_score}/115점 ({risk_level})")
            if data.crtes_r_summary:
                crtes_info.append(f"요약: {data.crtes_r_summary}")
            sections.append("\n".join(crtes_info))

        # 대화 분석 정보
        if data.conversation_summary or data.emotional_keywords or data.key_topics:
            conv_info = ["\n## 소울이(AI) 대화 분석"]
            if data.conversation_summary:
                conv_info.append(f"대화 요약: {data.conversation_summary}")
            if data.emotional_keywords:
                conv_info.append(f"감정 키워드: {', '.join(data.emotional_keywords)}")
            if data.key_topics:
                conv_info.append(f"주요 주제: {', '.join(data.key_topics)}")
            sections.append("\n".join(conv_info))

        sections.append("\n---")
        sections.append(
            f"위 정보를 바탕으로 {data.child_name} 아동에 대한 "
            "통합 전문 소견을 작성해주세요."
        )

        return "\n".join(sections)

    def _get_voucher_statement(self, data: IntegratedOpinionInput) -> str:
        """바우처 추천 문구를 생성합니다."""
        if data.is_voucher_eligible:
            return "이 아동은 바우처 추천 대상입니다."
        else:
            return "이 아동은 바우처 추천 대상이 아닙니다."

    def _create_fallback_opinion(self, data: IntegratedOpinionInput) -> IntegratedOpinion:
        """폴백 소견을 생성합니다."""
        voucher_statement = self._get_voucher_statement(data)

        fallback_text = f"""안녕하세요, 예이린 사회적협동조합입니다.
{data.child_name} 아동에 대해 표준화 심리검사와 예이린 AI 상담 서비스를 바탕으로 분석한 결과를 안내드립니다.

검사는 아동의 정서적 어려움을 다각도로 파악할 수 있는 표준화된 심리검사와 함께, 예이린 AI '소울이'와의 대화 내용을 분석하여 아동이 실제로 경험하고 있는 정서적 반응과 표현 양상을 파악하였습니다.

종합적인 검사 결과를 바탕으로, {data.child_name} 아동은 전문 심리상담 서비스를 통한 지속적인 정서적 지원이 권장됩니다. 전문 상담사와의 상담을 통해 아동의 건강한 정서 발달을 도울 수 있습니다.

앞으로도 예이린은 아이들의 건강한 성장을 위해 최선을 다하겠습니다. 감사합니다.

{voucher_statement}"""

        return IntegratedOpinion(
            full_text=fallback_text,
            voucher_statement=voucher_statement,
        )
