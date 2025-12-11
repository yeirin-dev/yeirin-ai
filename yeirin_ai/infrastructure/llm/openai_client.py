"""OpenAI 클라이언트 - LLM 기반 추천 시스템.

GPT-4o-mini를 활용하여 상담 의뢰지를 분석하고
최적의 바우처 상담 기관을 추천합니다.
"""

import json
from typing import Any

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.institution.models import Institution
from yeirin_ai.domain.recommendation.models import InstitutionRecommendation


class OpenAIRecommendationClient:
    """OpenAI 기반 상담 기관 추천 클라이언트.

    상담 의뢰지 텍스트와 기관 정보를 분석하여
    의미론적 매칭을 수행합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트를 초기화합니다."""
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
        """OpenAI를 사용하여 기관을 추천합니다.

        Args:
            counsel_request: 상담 의뢰지 텍스트
            institutions: 추천 대상 기관 목록
            max_recommendations: 최대 추천 개수

        Returns:
            추천된 기관 목록 (점수 순으로 정렬됨)

        Raises:
            ValueError: OpenAI 응답이 비어있는 경우
        """
        # 실제 기관 수와 max_recommendations 중 작은 값 사용
        actual_max = min(max_recommendations, len(institutions))

        # 기관 컨텍스트로 프롬프트 생성
        institutions_context = self._build_institutions_context(institutions)
        prompt = self._build_prompt(counsel_request, institutions_context, actual_max)

        # OpenAI API 호출
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

        # 응답 파싱
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI 응답이 비어있습니다")

        result = json.loads(content)
        return self._parse_recommendations(result, institutions)

    def _build_institutions_context(self, institutions: list[Institution]) -> str:
        """프롬프트용 기관 컨텍스트를 생성합니다.

        Args:
            institutions: 기관 목록

        Returns:
            기관 정보가 포함된 텍스트
        """
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
        """OpenAI API용 프롬프트를 생성합니다.

        Args:
            counsel_request: 상담 의뢰지 텍스트
            institutions_context: 기관 컨텍스트
            max_recommendations: 최대 추천 개수

        Returns:
            완성된 프롬프트 문자열
        """
        return f"""
다음 상담 의뢰 내용을 분석하고, 아래 기관들 중 가장 적합한 기관을 추천해주세요.

## 상담 의뢰 내용:
{counsel_request}

## 추천 대상 기관 목록:
{institutions_context}

## 중요 규칙:
- 반드시 위 "추천 대상 기관 목록"에 있는 기관만 추천하세요
- 목록에 없는 기관 ID를 생성하거나 추천하면 안 됩니다
- 같은 기관을 중복 추천하지 마세요
- 현재 목록에 {max_recommendations}개 기관이 있으므로 최대 {max_recommendations}개까지만 추천하세요

## 요청사항:
1. 상담 의뢰 내용의 핵심 문제와 니즈를 파악하세요
2. 각 기관의 강점과 특성을 고려하여 적합도를 평가하세요
3. 가장 적합한 기관을 선정하고 점수(0.0-1.0)를 매기세요
4. 각 기관을 추천하는 구체적인 이유를 설명하세요

응답은 반드시 다음 JSON 형식으로 제공해주세요:
{{
  "recommendations": [
    {{
      "institution_id": "위 목록에 있는 정확한 기관 ID",
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
        """OpenAI 응답을 추천 객체로 변환합니다.

        Args:
            result: OpenAI 응답 JSON
            institutions: 기관 목록

        Returns:
            추천 결과 객체 목록
        """
        # 기관 조회용 딕셔너리 생성
        inst_lookup = {inst.id: inst for inst in institutions}

        # 추천 결과 파싱 (중복 방지)
        recommendations = []
        seen_ids: set[str] = set()

        for rec in result.get("recommendations", []):
            institution_id = rec["institution_id"]

            # 중복 체크
            if institution_id in seen_ids:
                continue

            institution = inst_lookup.get(institution_id)

            # 목록에 없는 기관 ID는 무시
            if not institution:
                continue

            seen_ids.add(institution_id)
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

        # 점수 내림차순 정렬
        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations
