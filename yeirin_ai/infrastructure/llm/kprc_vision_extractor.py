"""KPRC T점수 GPT Vision 추출기.

GPT Vision API를 사용하여 KPRC 결과 보고서 PDF에서
T점수 프로파일을 자동으로 추출합니다.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from yeirin_ai.core.config.settings import settings
from yeirin_ai.infrastructure.pdf.extractor import PDFExtractionError
from yeirin_ai.infrastructure.pdf.image_converter import PDFImageConverter

logger = logging.getLogger(__name__)


@dataclass
class KprcTScoreResult:
    """KPRC T점수 추출 결과."""

    # 타당도척도 (2개)
    icn_t_score: int | None = None  # 비일관성 (높을수록 위험: ≥65T)
    f_t_score: int | None = None  # 저빈도 (높을수록 위험: ≥65T)

    # 자아탄력성척도 (1개)
    ers_t_score: int | None = None  # 자아탄력성 (낮을수록 위험: ≤30T)

    # 발달척도 (2개)
    vdl_t_score: int | None = None  # 언어발달 (높을수록 위험: ≥65T)
    pdl_t_score: int | None = None  # 운동발달 (높을수록 위험: ≥65T)

    # 임상척도 (8개)
    anx_t_score: int | None = None  # 불안 (높을수록 위험: ≥65T)
    dep_t_score: int | None = None  # 우울 (높을수록 위험: ≥65T)
    som_t_score: int | None = None  # 신체화 (높을수록 위험: ≥65T)
    dlq_t_score: int | None = None  # 비행 (높을수록 위험: ≥65T)
    hpr_t_score: int | None = None  # 과잉행동 (높을수록 위험: ≥65T)
    fam_t_score: int | None = None  # 가족관계 (높을수록 위험: ≥65T)
    soc_t_score: int | None = None  # 사회관계 (높을수록 위험: ≥65T)
    psy_t_score: int | None = None  # 정신증 (높을수록 위험: ≥65T)

    # 추출 메타데이터
    confidence: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환합니다."""
        return {
            "ers_t_score": self.ers_t_score,
            "icn_t_score": self.icn_t_score,
            "f_t_score": self.f_t_score,
            "vdl_t_score": self.vdl_t_score,
            "pdl_t_score": self.pdl_t_score,
            "anx_t_score": self.anx_t_score,
            "dep_t_score": self.dep_t_score,
            "som_t_score": self.som_t_score,
            "dlq_t_score": self.dlq_t_score,
            "hpr_t_score": self.hpr_t_score,
            "fam_t_score": self.fam_t_score,
            "soc_t_score": self.soc_t_score,
            "psy_t_score": self.psy_t_score,
            "confidence": self.confidence,
        }

    def check_voucher_criteria(self) -> tuple[bool, list[str]]:
        """바우처 조건 충족 여부를 확인합니다.

        KPRC 바우처 조건:
        - ERS ≤ 30T (자아탄력성이 낮음)
        - 또는 나머지 12개 척도 중 하나라도 ≥ 65T

        Returns:
            (충족 여부, 위험 척도 목록)
        """
        risk_scales: list[str] = []

        # ERS는 낮을수록 위험
        if self.ers_t_score is not None and self.ers_t_score <= 30:
            risk_scales.append("ERS")

        # 나머지 척도는 높을수록 위험
        high_risk_scales = [
            ("ICN", self.icn_t_score),
            ("F", self.f_t_score),
            ("VDL", self.vdl_t_score),
            ("PDL", self.pdl_t_score),
            ("ANX", self.anx_t_score),
            ("DEP", self.dep_t_score),
            ("SOM", self.som_t_score),
            ("DLQ", self.dlq_t_score),
            ("HPR", self.hpr_t_score),
            ("FAM", self.fam_t_score),
            ("SOC", self.soc_t_score),
            ("PSY", self.psy_t_score),
        ]

        for scale_name, score in high_risk_scales:
            if score is not None and score >= 65:
                risk_scales.append(scale_name)

        return len(risk_scales) > 0, risk_scales


class KprcVisionExtractorError(Exception):
    """KPRC Vision 추출 오류."""

    pass


class KprcVisionExtractor:
    """KPRC T점수 Vision 추출기.

    GPT Vision API를 사용하여 KPRC 보고서 2페이지의
    T점수 프로파일 그래프에서 점수를 추출합니다.
    """

    # GPT Vision 모델 (gpt-4o가 더 정확함)
    VISION_MODEL = "gpt-4o"

    # 추출 프롬프트
    EXTRACTION_PROMPT = """당신은 심리검사 보고서 분석 전문가입니다.
이 이미지는 KPRC(한국아동인성검사) 결과 보고서의 2페이지입니다.

## 이미지 구조
이미지에는 다음 요소가 있습니다:
1. **T점수 프로파일 그래프**: 상단의 선 그래프
2. **T점수 테이블**: 그래프 아래의 표 (가장 중요!)

## 핵심 지시사항
⚠️ 반드시 **테이블의 "T점수" 행**에서 값을 읽으세요.
그래프가 아닌 테이블 하단의 숫자 값이 정확합니다.

## 테이블 구조 (왼쪽→오른쪽 순서)
테이블 열 순서:
| ICN | F | ERS | VDL | PDL | ANX | DEP | SOM | DLQ | HPR | FAM | SOC | PSY |
|비일관성|저빈도|자아탄력성|언어발달|운동발달|불안|우울|신체화|비행|과잉행동|가족관계|사회관계|정신증|

테이블 행 구조:
- **척도**: 영문 약어 (ICN, F, ERS...)
- **한글명**: 비일관성, 저빈도, 자아탄력성척도, 언어발달, 운동발달, 불안, 우울...
- **원점수**: 원래 점수 (무시)
- **T점수**: ← 이 행의 값을 추출하세요!

## 13개 척도 설명

### 타당도척도 (2개)
1. **ICN** (비일관성): 응답의 일관성
2. **F** (저빈도): 비전형적 응답 패턴

### 자아탄력성척도 (1개)
3. **ERS** (자아탄력성): 심리적 건강성 (낮을수록 위험)

### 발달척도 (2개)
4. **VDL** (언어발달): 언어 발달 수준
5. **PDL** (운동발달): 운동 발달 수준

### 임상척도 (8개)
6. **ANX** (불안): 불안 수준
7. **DEP** (우울): 우울 수준
8. **SOM** (신체화): 신체 증상 호소
9. **DLQ** (비행): 규칙 위반 행동
10. **HPR** (과잉행동): 주의력 및 활동 조절 문제
11. **FAM** (가족관계): 가족 관계 문제
12. **SOC** (사회관계): 또래 관계 문제
13. **PSY** (정신증): 현실 검증력 문제

## 추출 규칙
1. 테이블의 **T점수 행**에서 각 열의 숫자를 읽으세요
2. T점수는 일반적으로 30~80 범위입니다
3. 열 순서: ICN → F → ERS → VDL → PDL → ANX → DEP → SOM → DLQ → HPR → FAM → SOC → PSY
4. 값이 명확하지 않으면 null로 표시
5. 모든 값을 정수로 반환하세요

## 응답 형식 (JSON만 반환)
```json
{
  "icn_t_score": 숫자,
  "f_t_score": 숫자,
  "ers_t_score": 숫자,
  "vdl_t_score": 숫자,
  "pdl_t_score": 숫자,
  "anx_t_score": 숫자,
  "dep_t_score": 숫자,
  "som_t_score": 숫자,
  "dlq_t_score": 숫자,
  "hpr_t_score": 숫자,
  "fam_t_score": 숫자,
  "soc_t_score": 숫자,
  "psy_t_score": 숫자,
  "confidence": 0.0~1.0
}
```

신뢰도 기준:
- 1.0: 모든 값이 테이블에서 명확히 읽힘
- 0.8: 대부분 명확, 일부 추정
- 0.5: 다수가 불명확
- 0.0: 테이블을 찾을 수 없음"""

    def __init__(self) -> None:
        """추출기를 초기화합니다."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.image_converter = PDFImageConverter(dpi=200)  # 높은 해상도로 추출

    async def extract_t_scores(self, pdf_bytes: bytes) -> KprcTScoreResult:
        """PDF에서 KPRC T점수를 추출합니다.

        Args:
            pdf_bytes: KPRC 보고서 PDF 바이트

        Returns:
            추출된 T점수 결과

        Raises:
            KprcVisionExtractorError: 추출 실패 시
        """
        try:
            # 1. PDF 2페이지를 이미지로 변환
            page_image = self.image_converter.convert_page_to_image(
                pdf_bytes=pdf_bytes,
                page_number=2,  # KPRC 프로파일은 2페이지에 있음
            )
            logger.info(
                f"PDF 이미지 변환 완료: {page_image.width}x{page_image.height}px"
            )

            # 2. GPT Vision API 호출
            response = await self.client.chat.completions.create(
                model=self.VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.EXTRACTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": page_image.data_url,
                                    "detail": "high",  # 고해상도 분석
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                temperature=0.1,  # 낮은 temperature로 정확한 추출
            )

            # 3. 응답 파싱
            content = response.choices[0].message.content
            if not content:
                raise KprcVisionExtractorError("GPT Vision 응답이 비어있습니다")

            logger.debug(f"GPT Vision 원본 응답: {content}")

            # JSON 파싱 (마크다운 코드블록 처리)
            json_content = self._extract_json_from_response(content)
            result_data = json.loads(json_content)

            # 4. 결과 객체 생성
            result = KprcTScoreResult(
                ers_t_score=self._parse_score(result_data.get("ers_t_score")),
                icn_t_score=self._parse_score(result_data.get("icn_t_score")),
                f_t_score=self._parse_score(result_data.get("f_t_score")),
                vdl_t_score=self._parse_score(result_data.get("vdl_t_score")),
                pdl_t_score=self._parse_score(result_data.get("pdl_t_score")),
                anx_t_score=self._parse_score(result_data.get("anx_t_score")),
                dep_t_score=self._parse_score(result_data.get("dep_t_score")),
                som_t_score=self._parse_score(result_data.get("som_t_score")),
                dlq_t_score=self._parse_score(result_data.get("dlq_t_score")),
                hpr_t_score=self._parse_score(result_data.get("hpr_t_score")),
                fam_t_score=self._parse_score(result_data.get("fam_t_score")),
                soc_t_score=self._parse_score(result_data.get("soc_t_score")),
                psy_t_score=self._parse_score(result_data.get("psy_t_score")),
                confidence=float(result_data.get("confidence", 0.0)),
                raw_response=result_data,
            )

            logger.info(
                f"T점수 추출 완료 (신뢰도: {result.confidence:.2f})"
            )
            return result

        except PDFExtractionError as e:
            raise KprcVisionExtractorError(f"PDF 처리 실패: {e}") from e
        except json.JSONDecodeError as e:
            raise KprcVisionExtractorError(f"JSON 파싱 실패: {e}") from e
        except Exception as e:
            logger.exception("T점수 추출 중 예상치 못한 오류")
            raise KprcVisionExtractorError(f"T점수 추출 실패: {e}") from e

    def _extract_json_from_response(self, content: str) -> str:
        """응답에서 JSON 부분만 추출합니다.

        GPT가 마크다운 코드블록으로 감싸서 응답할 수 있습니다.

        Args:
            content: GPT 응답 텍스트

        Returns:
            JSON 문자열
        """
        # 마크다운 코드블록 제거
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        return content.strip()

    def _parse_score(self, value: Any) -> int | None:
        """점수 값을 정수로 파싱합니다.

        Args:
            value: 파싱할 값

        Returns:
            정수 점수 또는 None
        """
        if value is None:
            return None
        try:
            score = int(float(value))
            # T점수 범위 검증 (20~100)
            if 20 <= score <= 100:
                return score
            return None
        except (ValueError, TypeError):
            return None

    async def extract_t_scores_from_url(self, pdf_url: str) -> KprcTScoreResult:
        """URL에서 PDF를 다운로드하여 T점수를 추출합니다.

        Args:
            pdf_url: PDF 파일 URL (S3 등)

        Returns:
            추출된 T점수 결과

        Raises:
            KprcVisionExtractorError: 추출 실패 시
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
                pdf_bytes = response.content

            return await self.extract_t_scores(pdf_bytes)

        except httpx.HTTPError as e:
            raise KprcVisionExtractorError(f"PDF 다운로드 실패: {e}") from e
