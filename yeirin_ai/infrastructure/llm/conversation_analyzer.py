"""OpenAI 기반 Soul-E 대화 분석기.

Soul-E(AI 상담사)와 아동 간의 대화내역을 분석하여
'AI 기반 아동 마음건강 대화 분석 요약' 섹션에 들어갈
전문가 수준의 분석 요약을 생성합니다.
"""

import json
import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.infrastructure.external.soul_e_client import (
    ConversationHistory,
    SoulEClient,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터 클래스
# =============================================================================


@dataclass
class ChildContext:
    """아동 컨텍스트 정보."""

    name: str
    age: int | None = None
    gender: str | None = None  # "남" or "여" or "MALE" or "FEMALE"
    goals: str | None = None  # 상담 목표

    def get_gender_korean(self) -> str:
        """성별을 한국어로 변환."""
        if self.gender in ("MALE", "남"):
            return "남"
        if self.gender in ("FEMALE", "여"):
            return "여"
        return ""


@dataclass
class ConversationAnalysis:
    """대화 분석 결과.

    새 문서 포맷의 '4.2 AI 기반 아동 마음건강 대화 분석 요약' 섹션에 사용됩니다.
    """

    # 3줄 요약 (예이린 스타일)
    summary_lines: list[str] = field(default_factory=list)

    # 전문가 종합 분석 (3-4문장)
    expert_analysis: str = ""

    # 주요 관찰 사항 (대화에서 발견된 특성)
    key_observations: list[str] = field(default_factory=list)

    # 정서 상태 키워드 (예: "불안", "우울", "또래갈등")
    emotional_keywords: list[str] = field(default_factory=list)

    # 권장 상담 영역
    recommended_focus_areas: list[str] = field(default_factory=list)

    # 분석 신뢰도 (0.0 ~ 1.0)
    confidence_score: float = 0.0

    # 대화 세션 수 (참고용)
    session_count: int = 0

    # 대화 메시지 수 (참고용)
    message_count: int = 0


# =============================================================================
# 대화 분석기
# =============================================================================


class ConversationAnalyzer:
    """Soul-E 대화 분석기.

    Soul-E 대화내역을 AI로 분석하여
    아동의 정서 상태와 상담 필요 영역을 요약합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트와 Soul-E 클라이언트를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = 0.4
        self.max_tokens = 1500
        self.soul_e_client = SoulEClient()

    async def analyze_from_child_id(
        self,
        child_id: str,
        child_context: ChildContext,
    ) -> ConversationAnalysis:
        """아동 ID로 대화내역을 조회하여 분석합니다.

        Args:
            child_id: 아동 ID (UUID)
            child_context: 아동 컨텍스트 정보

        Returns:
            ConversationAnalysis 객체
        """
        logger.info(
            "Soul-E 대화 분석 시작",
            extra={"child_id": child_id, "child_name": child_context.name},
        )

        try:
            # Soul-E에서 대화내역 조회
            history = await self.soul_e_client.get_conversation_history(
                child_id=child_id,
                max_messages=100,  # 최근 100개 메시지
                include_metadata=False,
            )

            if not history.messages:
                logger.info(
                    "대화내역이 없어 기본 분석 생성",
                    extra={"child_id": child_id},
                )
                return self._create_default_analysis(child_context)

            # 대화내역으로 분석 수행
            return await self.analyze_conversation(history, child_context)

        except Exception as e:
            logger.error(
                "Soul-E 대화 분석 실패",
                extra={"child_id": child_id, "error": str(e)},
            )
            return self._create_default_analysis(child_context)

    async def analyze_conversation(
        self,
        history: ConversationHistory,
        child_context: ChildContext,
    ) -> ConversationAnalysis:
        """대화내역을 분석하여 요약을 생성합니다.

        Args:
            history: Soul-E 대화내역
            child_context: 아동 컨텍스트 정보

        Returns:
            ConversationAnalysis 객체
        """
        # 대화내역 포맷
        conversation_text = self.soul_e_client.format_conversation_for_analysis(
            history, max_chars=6000
        )

        # 프롬프트 생성
        prompt = self._build_prompt(conversation_text, child_context)

        logger.info(
            "OpenAI 대화 분석 요청",
            extra={
                "child_name": child_context.name,
                "messages_count": len(history.messages),
                "sessions_count": len(history.sessions),
            },
        )

        try:
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

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI 응답이 비어있습니다")

            result = json.loads(content)
            analysis = self._parse_analysis(result, history)

            logger.info(
                "Soul-E 대화 분석 완료",
                extra={
                    "child_name": child_context.name,
                    "confidence": analysis.confidence_score,
                },
            )
            return analysis

        except Exception as e:
            logger.error(
                "OpenAI 대화 분석 실패",
                extra={"child_name": child_context.name, "error": str(e)},
            )
            return self._create_default_analysis(child_context, history)

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트를 반환합니다."""
        return """당신은 아동 심리 분석 전문가입니다.

AI 상담사 '소울이'와 아동 사이의 대화내역을 분석하여,
상담의뢰지에 포함될 '아동 마음건강 대화 분석 요약'을 작성합니다.

## 핵심 원칙 (반드시 준수):

1. **사실 기반 기술**: 대화에서 직접 관찰된 내용만 기술. 추론하거나 가정하지 않음
2. **아동 이름 정확히 사용**: 아동 정보에 제공된 이름 전체를 그대로 사용
3. **강점 우선**: 아동의 긍정적인 면을 먼저 언급
4. **성장 관점**: 어려움도 성장 가능성으로 표현
5. **진단 금지**: 장애명이나 진단명 절대 사용 금지
6. **따뜻한 어조**: 전문적이되 희망적인 표현

## 중요 제약사항:

- 대화에서 언급되지 않은 내용(예: 친구 관계, 가족 관계 등)을 임의로 추가하지 않음
- 아동이 실제로 말한 키워드와 주제만 언급
- 대화 내용이 적을 경우, 관찰 가능한 범위 내에서만 분석

## 분석 영역 (대화에서 관찰된 경우에만):

- **정서 상태**: 대화에서 관찰되는 감정 패턴
- **대인 관계**: 또래, 가족 관계에 대한 언급 (언급된 경우에만)
- **자아 인식**: 자신에 대한 생각과 태도
- **스트레스 요인**: 힘들어하는 상황이나 주제
- **대처 방식**: 어려움에 대응하는 방식
- **강점 영역**: 관심사, 잘하는 것, 좋아하는 것

## 작성 형식:

- **1줄**: 아이의 긍정적 특성과 강점
- **2줄**: 대화에서 관찰된 관심 필요 영역 (실제 언급된 내용만)
- **3줄**: 상담을 통해 기대되는 성장"""

    def _build_prompt(
        self,
        conversation_text: str,
        child_context: ChildContext,
    ) -> str:
        """분석 프롬프트를 생성합니다."""
        # 아동 정보 구성
        child_parts = [f"이름: {child_context.name}"]
        if child_context.age:
            child_parts.append(f"나이: {child_context.age}세")
        if child_context.gender:
            child_parts.append(f"성별: {child_context.get_gender_korean()}")
        child_desc = " | ".join(child_parts)

        goals_section = ""
        if child_context.goals:
            goals_section = f"""
## 상담 목표:
{child_context.goals}
"""

        return f"""## 중요 지침:
- 아동 이름을 정확히 "{child_context.name}"로 사용하세요 (절대 줄이거나 변형하지 말 것)
- 대화에서 직접 언급된 내용만 분석에 포함하세요 (언급되지 않은 친구 관계, 가족 문제 등 추가 금지)

## 아동 정보:
{child_desc}
{goals_section}
## 소울이(AI 상담사)와의 대화내역:
{conversation_text}

## 요청사항:

위 대화내역을 분석하여 다음 내용을 작성해주세요:

1. **3줄 요약 (summary_lines)** - 아동 이름을 정확히 "{child_context.name}"로 사용:
   - 1줄: 아이의 긍정적 특성과 강점
   - 2줄: 대화에서 실제로 언급된 관심 필요 영역 (언급되지 않은 내용 추가 금지)
   - 3줄: 상담을 통해 기대되는 성장

2. **전문가 종합 분석 (expert_analysis)**:
   - 3-4문장으로 대화 내용을 종합 분석
   - 대화에서 직접 관찰된 내용만 기술 (추론이나 가정 금지)
   - 아동의 정서 상태와 상담 필요성 기술

3. **주요 관찰 사항 (key_observations)**:
   - 대화에서 발견된 주요 특성 2-3가지

4. **정서 상태 키워드 (emotional_keywords)**:
   - 대화에서 직접 파악된 주요 정서 키워드 1-3개
   - 대화에서 실제로 언급된 키워드만 사용 (대화 내용이 적으면 키워드도 적게)

5. **권장 상담 영역 (recommended_focus_areas)**:
   - 상담에서 다루면 좋을 영역 2-3개

6. **분석 신뢰도 (confidence_score)**:
   - 대화 분량과 내용에 따른 분석 신뢰도 (0.0 ~ 1.0)
   - 대화가 1-2개뿐이면 0.3 이하, 5개 이상이면 0.5 이상으로 설정

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": [
    "{child_context.name} 아동은 ... (긍정적 특성과 강점)",
    "대화에서 ... (실제 언급된 관심 필요 영역만)",
    "상담을 통해 ... (기대되는 성장)"
  ],
  "expert_analysis": "{child_context.name} 아동이 ... (대화에서 관찰된 내용 기반 종합 분석)",
  "key_observations": [
    "대화에서 관찰된 사항 1",
    "대화에서 관찰된 사항 2"
  ],
  "emotional_keywords": [
    "대화에서 직접 파악된 키워드"
  ],
  "recommended_focus_areas": [
    "대화 내용 기반 권장 영역"
  ],
  "confidence_score": 0.5
}}
""".strip()

    def _parse_analysis(
        self,
        result: dict,
        history: ConversationHistory | None = None,
    ) -> ConversationAnalysis:
        """OpenAI 응답을 ConversationAnalysis 객체로 변환."""
        return ConversationAnalysis(
            summary_lines=result.get("summary_lines", []),
            expert_analysis=result.get("expert_analysis", ""),
            key_observations=result.get("key_observations", []),
            emotional_keywords=result.get("emotional_keywords", []),
            recommended_focus_areas=result.get("recommended_focus_areas", []),
            confidence_score=float(result.get("confidence_score", 0.0)),
            session_count=len(history.sessions) if history else 0,
            message_count=len(history.messages) if history else 0,
        )

    def _create_default_analysis(
        self,
        child_context: ChildContext,
        history: ConversationHistory | None = None,
    ) -> ConversationAnalysis:
        """대화내역이 없거나 분석 실패 시 기본 분석을 생성합니다."""
        name = child_context.name

        return ConversationAnalysis(
            summary_lines=[
                f"{name} 아동은 AI 상담사 소울이와의 대화를 통해 자신을 표현하는 경험을 하였습니다.",
                "아동의 정서 상태와 필요에 대한 추가적인 탐색이 도움이 될 수 있습니다.",
                "전문 상담을 통해 아동의 건강한 성장과 발달을 지원할 수 있습니다.",
            ],
            expert_analysis=(
                f"{name} 아동이 AI 상담사 소울이와 대화한 기록을 바탕으로 분석하였습니다. "
                "아동의 정서적 상태와 관심 영역에 대한 이해를 높이기 위해 "
                "전문 상담사와의 심층적인 상담이 권장됩니다."
            ),
            key_observations=[
                "AI 상담사와의 대화 참여",
                "추가적인 정서 탐색 필요",
            ],
            emotional_keywords=["정서 지원 필요"],
            recommended_focus_areas=[
                "아동 정서 상태 탐색",
                "라포 형성 및 신뢰 관계 구축",
            ],
            confidence_score=0.4,
            session_count=len(history.sessions) if history else 0,
            message_count=len(history.messages) if history else 0,
        )
