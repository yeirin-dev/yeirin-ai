"""OpenAI 기반 추천자 의견 생성기.

Soul-E 대화내역을 분석하여 사회서비스 이용 추천서의
'③ 추천자 의견' 섹션에 들어갈 전문가 의견을 생성합니다.
"""

import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.infrastructure.external.soul_e_client import (
    ConversationHistory,
    SoulEClient,
)

logger = logging.getLogger(__name__)


@dataclass
class ChildContext:
    """아동 컨텍스트 정보."""

    name: str
    age: int | None = None
    gender: str | None = None
    goals: str | None = None  # 상담 목표


@dataclass
class RecommenderOpinion:
    """생성된 추천자 의견."""

    opinion_text: str  # 전문가 의견 텍스트
    key_observations: list[str]  # 주요 관찰 사항
    service_needs: list[str]  # 필요한 서비스 분야
    confidence_score: float  # 신뢰도 점수 (0.0 ~ 1.0)


class RecommenderOpinionGenerator:
    """추천자 의견 생성기.

    Soul-E 대화내역을 기반으로 AI가 분석한
    전문가 수준의 추천자 의견을 생성합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = 0.5  # 전문적이지만 약간의 자연스러움
        self.max_tokens = 1500
        self.soul_e_client = SoulEClient()

    async def generate_from_child_id(
        self,
        child_id: str,
        child_context: ChildContext,
    ) -> RecommenderOpinion:
        """아동 ID로 대화내역을 조회하여 추천자 의견을 생성합니다.

        Args:
            child_id: 아동 ID (UUID)
            child_context: 아동 컨텍스트 정보

        Returns:
            RecommenderOpinion 객체
        """
        # Soul-E에서 대화내역 조회
        logger.info(
            "추천자 의견 생성 시작",
            extra={"child_id": child_id, "child_name": child_context.name},
        )

        try:
            history = await self.soul_e_client.get_conversation_history(
                child_id=child_id,
                max_messages=50,  # 최근 50개 메시지
                include_metadata=False,
            )

            if not history.messages:
                logger.warning(
                    "대화내역이 없어 기본 의견 생성",
                    extra={"child_id": child_id},
                )
                return self._create_default_opinion(child_context)

            # 대화내역으로 의견 생성
            return await self.generate_from_conversation(history, child_context)

        except Exception as e:
            logger.error(
                "추천자 의견 생성 실패, 기본 의견 반환",
                extra={"child_id": child_id, "error": str(e)},
            )
            return self._create_default_opinion(child_context)

    async def generate_from_conversation(
        self,
        history: ConversationHistory,
        child_context: ChildContext,
    ) -> RecommenderOpinion:
        """대화내역을 분석하여 추천자 의견을 생성합니다.

        Args:
            history: Soul-E 대화내역
            child_context: 아동 컨텍스트 정보

        Returns:
            RecommenderOpinion 객체

        Raises:
            ValueError: OpenAI 응답이 비어있는 경우
        """
        # 대화내역 포맷
        conversation_text = self.soul_e_client.format_conversation_for_analysis(
            history, max_chars=6000
        )

        # 프롬프트 생성
        prompt = self._build_prompt(conversation_text, child_context)

        logger.info(
            "OpenAI 추천자 의견 생성 요청",
            extra={
                "child_name": child_context.name,
                "messages_count": len(history.messages),
            },
        )

        # OpenAI API 호출
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_system_prompt(),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

        # 응답 파싱
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI 응답이 비어있습니다")

        result = json.loads(content)

        opinion = RecommenderOpinion(
            opinion_text=result.get("opinion_text", ""),
            key_observations=result.get("key_observations", []),
            service_needs=result.get("service_needs", []),
            confidence_score=float(result.get("confidence_score", 0.7)),
        )

        logger.info(
            "추천자 의견 생성 완료",
            extra={
                "child_name": child_context.name,
                "opinion_length": len(opinion.opinion_text),
                "confidence": opinion.confidence_score,
            },
        )

        return opinion

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트를 반환합니다."""
        return """당신은 아동·청소년 심리상담 전문가입니다.

AI 상담사 '소울이'와 아동 사이의 대화내역을 분석하여,
사회서비스 이용 추천서의 '추천자 의견' 란에 작성할
전문가 수준의 소견을 작성해야 합니다.

## 작성 원칙:

1. **전문성**: 공식 문서에 적합한 전문적인 어조로 작성
2. **객관성**: 대화내역에서 관찰된 구체적인 내용에 기반
3. **긍정적 관점**: 아동의 강점과 성장 가능성을 함께 언급
4. **구체성**: 필요한 서비스 분야를 명확하게 제시
5. **진단 금지**: 특정 진단명이나 장애명은 언급하지 않음

## 문서 맥락:

이 의견은 '사회서비스 이용 추천서'에 들어갑니다.
- 목적: 아동에게 적절한 심리상담 서비스를 연결하기 위함
- 수신자: 바우처 상담기관 및 관련 행정기관
- 형식: 공식 추천 문서"""

    def _build_prompt(
        self,
        conversation_text: str,
        child_context: ChildContext,
    ) -> str:
        """프롬프트를 생성합니다."""
        # 아동 정보 문자열 구성
        child_desc_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_desc_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_desc_parts.append(f"성별: {child_context.gender}")
        child_description = " | ".join(child_desc_parts)

        goals_section = ""
        if child_context.goals:
            goals_section = f"""
## 상담 목표:
{child_context.goals}
"""

        return f"""## 아동 정보:
{child_description}
{goals_section}
## 소울이(AI 상담사)와의 대화내역:
{conversation_text}

## 요청사항:

위 대화내역을 분석하여 다음 내용을 작성해주세요:

1. **추천자 의견 (opinion_text)**:
   - 3-4문단으로 구성
   - 첫 문단: 아동의 전반적인 상태와 강점
   - 둘째 문단: 대화에서 관찰된 주요 특성 및 관심 필요 영역
   - 셋째 문단: 서비스 지원이 필요한 분야와 기대 효과
   - (선택) 넷째 문단: 종합 의견 및 권고사항

2. **주요 관찰 사항 (key_observations)**:
   - 대화에서 발견된 주요 특성 2-3가지

3. **필요 서비스 분야 (service_needs)**:
   - 권장되는 서비스/지원 분야 2-3가지

4. **신뢰도 점수 (confidence_score)**:
   - 대화내역 분량과 내용에 따른 분석 신뢰도 (0.0 ~ 1.0)

응답은 반드시 다음 JSON 형식으로:
{{
  "opinion_text": "추천자 의견 전문 (3-4문단)",
  "key_observations": [
    "관찰 사항 1",
    "관찰 사항 2"
  ],
  "service_needs": [
    "필요 서비스 1",
    "필요 서비스 2"
  ],
  "confidence_score": 0.85
}}
""".strip()

    def _create_default_opinion(self, child_context: ChildContext) -> RecommenderOpinion:
        """대화내역이 없을 때 기본 의견을 생성합니다."""
        name = child_context.name

        default_text = f"""{name} 아동에 대한 심리상담 서비스 이용을 추천합니다.

본 추천은 보호자의 요청 및 초기 상담 결과를 바탕으로 작성되었습니다. \
아동의 정서적 안정과 건강한 발달을 위해 전문 상담 서비스가 도움이 될 것으로 판단됩니다.

아동·청소년 전문 상담 서비스를 통해 아동의 심리적 안녕감 향상과 \
사회적 적응 능력 발달에 긍정적인 효과가 기대됩니다. \
정기적인 상담 세션을 통해 아동의 상태를 지속적으로 모니터링하고 \
필요시 추가적인 지원 방안을 마련하시기를 권고드립니다."""

        return RecommenderOpinion(
            opinion_text=default_text,
            key_observations=[
                "보호자 요청에 따른 상담 서비스 연계 필요",
                "아동의 정서적 안정 지원 필요",
            ],
            service_needs=[
                "아동·청소년 심리상담",
                "정서 지원 서비스",
            ],
            confidence_score=0.5,
        )
