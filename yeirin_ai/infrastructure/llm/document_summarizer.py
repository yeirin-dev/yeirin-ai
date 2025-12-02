"""OpenAI 기반 문서 요약 클라이언트.

KPRC 심리검사 보고서의 '종합해석'을 분석하여
예이린만의 재해석으로 3줄 소견을 생성합니다.
"""

import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.domain.document.models import DocumentSummary, DocumentType


@dataclass
class ChildInfo:
    """MSA에서 전달받은 아동 정보."""

    name: str
    age: int | None = None
    gender: str | None = None  # "남" or "여"
    assessment_type: str = "KPRC"


class DocumentSummarizerClient:
    """OpenAI 기반 문서 요약 클라이언트.

    PDF '종합해석' 섹션과 MSA에서 전달받은 아동 정보를 결합하여
    예이린만의 재해석 소견을 생성합니다.
    """

    def __init__(self) -> None:
        """OpenAI 클라이언트를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = 0.4  # 약간의 창의성을 위해 조정
        self.max_tokens = settings.openai_max_tokens

    async def summarize_document(
        self,
        text_content: str,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        child_name: str | None = None,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """문서 텍스트를 요약합니다. (기존 호환용)

        Args:
            text_content: PDF에서 추출한 텍스트 내용
            document_type: 문서 유형
            child_name: 아동 이름
            include_recommendations: 권장 사항 포함 여부

        Returns:
            예이린 재해석 형태의 문서 요약
        """
        child_info = ChildInfo(name=child_name or "아동")
        return await self.create_yeirin_summary(
            interpretation_text=text_content,
            child_info=child_info,
            document_type=document_type,
            include_recommendations=include_recommendations,
        )

    async def create_yeirin_summary(
        self,
        interpretation_text: str,
        child_info: ChildInfo,
        document_type: DocumentType = DocumentType.KPRC_REPORT,
        include_recommendations: bool = True,
    ) -> DocumentSummary:
        """종합해석 텍스트와 아동 정보로 예이린 재해석 소견을 생성합니다.

        Args:
            interpretation_text: PDF '종합해석' 섹션 텍스트
            child_info: MSA에서 전달받은 아동 정보
            document_type: 문서 유형
            include_recommendations: 권장 사항 포함 여부

        Returns:
            예이린 재해석 형태의 문서 요약

        Raises:
            ValueError: OpenAI 응답이 비어있는 경우
        """
        # 프롬프트 생성
        prompt = self._build_yeirin_prompt(
            interpretation_text, child_info, include_recommendations
        )

        # OpenAI API 호출
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self._get_yeirin_system_prompt(),
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
        return self._parse_summary(result, document_type)

    def _get_yeirin_system_prompt(self) -> str:
        """예이린 재해석용 시스템 프롬프트를 반환합니다."""
        return """당신은 '예이린(Yeirin)' AI 심리상담 플랫폼의 전문 분석가입니다.

아동·청소년 심리검사 결과의 '종합해석'을 바탕으로,
부모님께 전달할 따뜻하고 희망적인 3줄 소견을 작성합니다.

## 예이린 재해석 원칙:

1. **아이 중심**: 검사 결과가 아닌 '아이'에 초점을 맞춤
2. **강점 우선**: 긍정적인 면을 먼저 언급하고, 주의점은 성장 기회로 표현
3. **실천 가능**: 부모님이 당장 실천할 수 있는 구체적 조언 포함
4. **따뜻한 어조**: 전문적이되 딱딱하지 않은 친근한 표현 사용
5. **진단 금지**: 절대 진단명이나 장애명을 언급하지 않음

## 작성 형식:

- **1줄**: 아이의 강점과 잠재력 (긍정적 시작)
- **2줄**: 현재 상태에 대한 이해와 관심 필요 영역
- **3줄**: 부모님께 드리는 따뜻한 조언과 격려"""

    def _build_yeirin_prompt(
        self,
        interpretation_text: str,
        child_info: ChildInfo,
        include_recommendations: bool,
    ) -> str:
        """예이린 재해석 프롬프트를 생성합니다."""
        # 아동 정보 문자열 구성
        child_desc_parts = [f"이름: {child_info.name}"]
        if child_info.age:
            child_desc_parts.append(f"나이: {child_info.age}세")
        if child_info.gender:
            child_desc_parts.append(f"성별: {child_info.gender}")
        child_desc_parts.append(f"검사: {child_info.assessment_type}")
        child_description = " | ".join(child_desc_parts)

        recommendation_instruction = ""
        if include_recommendations:
            recommendation_instruction = """
4. 가정에서 실천할 수 있는 구체적인 권장 사항 2개를 제시해주세요."""

        return f"""## 아동 정보 (MSA 제공):
{child_description}

## 검사 종합해석 (PDF 추출):
{interpretation_text}

## 요청사항:
1. 위 종합해석을 바탕으로 **예이린 재해석 3줄 소견**을 작성해주세요.
   - 1줄: 아이의 강점과 잠재력
   - 2줄: 관심이 필요한 영역 (성장 기회로 표현)
   - 3줄: 부모님께 드리는 따뜻한 조언
2. 전문가 종합 소견을 3-4문장으로 작성해주세요.
3. 핵심 발견 사항 2-3개를 정리해주세요.{recommendation_instruction}

응답은 반드시 다음 JSON 형식으로:
{{
  "summary_lines": [
    "1줄: 강점과 잠재력",
    "2줄: 관심 필요 영역",
    "3줄: 부모님께 조언"
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

    def _get_system_prompt(self, document_type: DocumentType) -> str:
        """문서 유형별 시스템 프롬프트를 반환합니다."""
        if document_type == DocumentType.KPRC_REPORT:
            return """당신은 20년 경력의 아동·청소년 임상심리 전문가입니다.
KPRC(한국 아동 인성 검사) 결과 보고서를 분석하여 부모님께 전달할 수 있는
전문적이면서도 이해하기 쉬운 소견을 작성해야 합니다.

작성 원칙:
1. 전문 용어는 최소화하고, 사용 시 괄호 안에 쉬운 설명을 추가
2. 아동의 강점을 먼저 언급하고, 주의가 필요한 부분을 부드럽게 설명
3. 부모님이 가정에서 실천할 수 있는 구체적인 조언 포함
4. 희망적이고 건설적인 어조 유지
5. 절대 진단명을 언급하지 않음 (상담 권유는 가능)"""

        if document_type == DocumentType.COUNSEL_REPORT:
            return """당신은 아동·청소년 상담 전문가입니다.
상담 결과 보고서를 분석하여 보호자에게 전달할
전문적이면서도 따뜻한 소견을 작성해야 합니다."""

        return """당신은 문서 분석 전문가입니다.
주어진 문서를 분석하여 핵심 내용을 요약해야 합니다."""

    def _build_prompt(
        self,
        text_content: str,
        document_type: DocumentType,
        include_recommendations: bool,
    ) -> str:
        """요약 요청 프롬프트를 생성합니다."""
        recommendation_instruction = ""
        if include_recommendations:
            recommendation_instruction = """
5. 가정에서 실천할 수 있는 권장 사항 2-3가지를 제시해주세요."""

        if document_type == DocumentType.KPRC_REPORT:
            return f"""다음 KPRC 심리검사 결과 보고서를 분석해주세요.

## 보고서 내용:
{text_content}

## 요청사항:
1. 검사 결과의 핵심을 정확히 3줄로 요약해주세요 (각 줄은 한 문장)
2. 부모님께 전달할 전문가 소견을 작성해주세요 (3-5문장)
3. 핵심 발견 사항을 2-4개 항목으로 정리해주세요
4. 요약의 신뢰도를 0.0-1.0 사이로 평가해주세요{recommendation_instruction}

응답은 반드시 다음 JSON 형식으로 제공해주세요:
{{
  "summary_lines": [
    "첫 번째 요약 문장",
    "두 번째 요약 문장",
    "세 번째 요약 문장"
  ],
  "expert_opinion": "부모님께 전달할 전문가 소견 전문",
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

        # 기타 문서 유형
        return f"""다음 문서를 분석하고 요약해주세요.

## 문서 내용:
{text_content}

## 요청사항:
1. 핵심 내용을 3줄로 요약해주세요
2. 종합 소견을 작성해주세요
3. 핵심 사항을 정리해주세요
4. 요약 신뢰도를 평가해주세요{recommendation_instruction}

응답은 반드시 다음 JSON 형식으로 제공해주세요:
{{
  "summary_lines": ["요약1", "요약2", "요약3"],
  "expert_opinion": "종합 소견",
  "key_findings": ["핵심1", "핵심2"],
  "recommendations": ["권장1", "권장2"],
  "confidence_score": 0.85
}}
""".strip()

    def _parse_summary(
        self, result: dict[str, Any], document_type: DocumentType
    ) -> DocumentSummary:
        """OpenAI 응답을 DocumentSummary 객체로 변환합니다."""
        return DocumentSummary(
            document_type=document_type,
            summary_lines=result.get("summary_lines", []),
            expert_opinion=result.get("expert_opinion", ""),
            key_findings=result.get("key_findings", []),
            recommendations=result.get("recommendations", []),
            confidence_score=float(result.get("confidence_score", 0.0)),
        )
