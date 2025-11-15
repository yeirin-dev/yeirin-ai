"""OpenAI client for LLM-based recommendations."""

import json
from typing import Any

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.institution.models import Institution
from yeirin_ai.domain.recommendation.models import InstitutionRecommendation


class OpenAIRecommendationClient:
    """OpenAI 기반 상담 센터 추천 클라이언트."""

    def __init__(self) -> None:
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens

    async def recommend_institutions(
        self,
        counsel_request: str,
        institutions: list[Institution],
        max_recommendations: int = 5,
    ) -> list[InstitutionRecommendation]:
        """
        Get institution recommendations using OpenAI.

        Args:
            counsel_request: 상담 의뢰지 텍스트
            institutions: 추천 대상 기관 목록
            max_recommendations: 최대 추천 개수

        Returns:
            추천된 기관 목록 (점수 순으로 정렬됨)
        """
        # Build prompt with institution context
        institutions_context = self._build_institutions_context(institutions)
        prompt = self._build_prompt(counsel_request, institutions_context, max_recommendations)

        # Call OpenAI API
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 아동·청소년 상담 전문가입니다. "
                        "상담 의뢰 내용을 분석하여 최적의 상담 기관을 추천해야 합니다. "
                        "각 기관의 특성과 강점을 고려하여 점수를 매기고, "
                        "추천 이유를 명확히 설명해야 합니다."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response is empty")

        result = json.loads(content)
        return self._parse_recommendations(result, institutions)

    def _build_institutions_context(self, institutions: list[Institution]) -> str:
        """Build institution context for prompt."""
        context_parts = []
        for idx, inst in enumerate(institutions, 1):
            context_parts.append(
                f"""
기관 {idx}:
- ID: {inst.id}
- 센터명: {inst.center_name}
- 주소: {inst.address}
- 소개: {inst.introduction}
- 운영 바우처: {', '.join(v.value for v in inst.operating_vouchers)}
- 품질 인증: {'있음' if inst.is_quality_certified else '없음'}
- 상담사 수: {inst.counselor_count}명
- 상담사 자격증: {', '.join(inst.counselor_certifications)}
- 주요 대상군: {inst.primary_target_group}
- 부차 대상군: {inst.secondary_target_group or '없음'}
- 종합심리검사: {'가능' if inst.can_provide_comprehensive_test else '불가능'}
- 제공 서비스: {', '.join(s.value for s in inst.provided_services)}
- 특수 치료: {', '.join(t.value for t in inst.special_treatments)}
- 부모 상담: {'가능' if inst.can_provide_parent_counseling else '불가능'}
- 평균 별점: {inst.average_rating:.1f}/5.0 ({inst.review_count}개 리뷰)
""".strip()
            )
        return "\n\n".join(context_parts)

    def _build_prompt(
        self, counsel_request: str, institutions_context: str, max_recommendations: int
    ) -> str:
        """Build prompt for OpenAI."""
        return f"""
다음 상담 의뢰 내용을 분석하고, 아래 기관들 중 가장 적합한 {max_recommendations}곳을 추천해주세요.

## 상담 의뢰 내용:
{counsel_request}

## 추천 대상 기관 목록:
{institutions_context}

## 요청사항:
1. 상담 의뢰 내용의 핵심 문제와 니즈를 파악하세요
2. 각 기관의 강점과 특성을 고려하여 적합도를 평가하세요
3. 가장 적합한 {max_recommendations}개 기관을 선정하고 점수(0.0-1.0)를 매기세요
4. 각 기관을 추천하는 구체적인 이유를 설명하세요

응답은 반드시 다음 JSON 형식으로 제공해주세요:
{{
  "recommendations": [
    {{
      "institution_id": "기관 ID",
      "score": 0.95,
      "reasoning": "추천 이유를 구체적으로 설명"
    }}
  ]
}}

점수가 높은 순서대로 정렬하여 응답해주세요.
""".strip()

    def _parse_recommendations(
        self, result: dict[str, Any], institutions: list[Institution]
    ) -> list[InstitutionRecommendation]:
        """Parse OpenAI response to recommendation objects."""
        # Create institution lookup
        inst_lookup = {inst.id: inst for inst in institutions}

        # Parse recommendations
        recommendations = []
        for rec in result.get("recommendations", []):
            institution_id = rec["institution_id"]
            institution = inst_lookup.get(institution_id)

            if not institution:
                continue

            recommendations.append(
                InstitutionRecommendation(
                    institution_id=institution_id,
                    center_name=institution.center_name,
                    score=float(rec["score"]),
                    reasoning=rec["reasoning"],
                    address=institution.address,
                    average_rating=institution.average_rating,
                )
            )

        # Sort by score descending
        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations
