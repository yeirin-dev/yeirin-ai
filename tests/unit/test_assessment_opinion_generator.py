"""검사 소견 생성기 테스트.

AssessmentOpinionGenerator의 SDQ-A 및 CRTES-R 소견 생성 로직을 테스트합니다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yeirin_ai.infrastructure.llm.assessment_opinion_generator import (
    AssessmentOpinion,
    AssessmentOpinionGenerator,
    ChildContext,
    CrtesRScores,
    SdqAScores,
)


class TestChildContext:
    """ChildContext 데이터 클래스 테스트."""

    def test_MALE_성별을_한국어로_변환한다(self) -> None:
        """MALE 성별이 '남'으로 변환된다."""
        # Given
        context = ChildContext(name="홍길동", gender="MALE")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == "남"

    def test_FEMALE_성별을_한국어로_변환한다(self) -> None:
        """FEMALE 성별이 '여'로 변환된다."""
        # Given
        context = ChildContext(name="홍길순", gender="FEMALE")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == "여"

    def test_한글_성별은_그대로_반환한다(self) -> None:
        """'남'/'여' 형식은 그대로 반환된다."""
        # Given
        context = ChildContext(name="홍길동", gender="남")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == "남"

    def test_성별_없으면_빈_문자열_반환한다(self) -> None:
        """성별이 None이면 빈 문자열을 반환한다."""
        # Given
        context = ChildContext(name="홍길동")

        # When
        result = context.get_gender_korean()

        # Then
        assert result == ""


class TestSdqAScores:
    """SDQ-A 점수 데이터 클래스 테스트."""

    def test_강점_수준_1은_양호로_표시한다(self) -> None:
        """강점 수준 1은 '양호'로 표시된다."""
        # Given
        scores = SdqAScores(
            strengths_score=8,
            strengths_level=1,
            difficulties_score=10,
            difficulties_level=1,
        )

        # When & Then
        assert scores.strengths_level_text == "양호"

    def test_강점_수준_2는_경계선으로_표시한다(self) -> None:
        """강점 수준 2는 '경계선'으로 표시된다."""
        # Given
        scores = SdqAScores(
            strengths_score=5,
            strengths_level=2,
            difficulties_score=15,
            difficulties_level=2,
        )

        # When & Then
        assert scores.strengths_level_text == "경계선"

    def test_강점_수준_3은_주의_필요로_표시한다(self) -> None:
        """강점 수준 3은 '주의 필요'로 표시된다."""
        # Given
        scores = SdqAScores(
            strengths_score=2,
            strengths_level=3,
            difficulties_score=25,
            difficulties_level=3,
        )

        # When & Then
        assert scores.strengths_level_text == "주의 필요"

    def test_난점_수준_텍스트를_올바르게_반환한다(self) -> None:
        """난점 수준별 텍스트를 올바르게 반환한다."""
        # Given
        scores = SdqAScores(
            strengths_score=8,
            strengths_level=1,
            difficulties_score=25,
            difficulties_level=3,
        )

        # When & Then
        assert scores.difficulties_level_text == "주의 필요"


class TestCrtesRScores:
    """CRTES-R 점수 데이터 클래스 테스트."""

    def test_정상_수준을_한국어로_변환한다(self) -> None:
        """normal 수준이 '정상 범위'로 변환된다."""
        # Given
        scores = CrtesRScores(total_score=20, risk_level="normal")

        # When
        result = scores.risk_level_korean

        # Then
        assert result == "정상 범위"

    def test_주의_수준을_한국어로_변환한다(self) -> None:
        """caution 수준이 '주의 필요'로 변환된다."""
        # Given
        scores = CrtesRScores(total_score=45, risk_level="caution")

        # When
        result = scores.risk_level_korean

        # Then
        assert result == "주의 필요"

    def test_고위험_수준을_한국어로_변환한다(self) -> None:
        """high_risk 수준이 '고위험'으로 변환된다."""
        # Given
        scores = CrtesRScores(total_score=70, risk_level="high_risk")

        # When
        result = scores.risk_level_korean

        # Then
        assert result == "고위험"


class TestAssessmentOpinionGeneratorSdqA:
    """SDQ-A 소견 생성 테스트."""

    @pytest.fixture
    def generator(self) -> AssessmentOpinionGenerator:
        """테스트용 생성기 인스턴스."""
        with patch("yeirin_ai.infrastructure.llm.assessment_opinion_generator.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"
            return AssessmentOpinionGenerator()

    @pytest.fixture
    def sample_sdq_a_scores(self) -> SdqAScores:
        """샘플 SDQ-A 점수."""
        return SdqAScores(
            strengths_score=8,
            strengths_level=1,
            strengths_level_description="타인의 감정을 잘 헤아리고 배려합니다.",
            difficulties_score=22,
            difficulties_level=3,
            difficulties_level_description="정서 조절에 어려움이 있습니다.",
        )

    @pytest.fixture
    def sample_child_context(self) -> ChildContext:
        """샘플 아동 컨텍스트."""
        return ChildContext(
            name="홍길동",
            age=10,
            gender="MALE",
        )

    def test_기본_강점_설명을_반환한다(self, generator: AssessmentOpinionGenerator) -> None:
        """강점 수준별 기본 설명을 반환한다."""
        # When & Then
        assert "양호" in generator._get_default_strengths_description(1)
        assert "보통" in generator._get_default_strengths_description(2)
        assert "부족" in generator._get_default_strengths_description(3)

    def test_기본_난점_설명을_반환한다(self, generator: AssessmentOpinionGenerator) -> None:
        """난점 수준별 기본 설명을 반환한다."""
        # When & Then
        assert "양호" in generator._get_default_difficulties_description(1)
        assert "경계선" in generator._get_default_difficulties_description(2)
        assert "어려움" in generator._get_default_difficulties_description(3)

    def test_SDQ_A_프롬프트를_올바르게_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_sdq_a_scores: SdqAScores,
        sample_child_context: ChildContext,
    ) -> None:
        """SDQ-A 프롬프트가 필요한 정보를 포함한다."""
        # When
        prompt = generator._build_sdq_a_prompt(sample_sdq_a_scores, sample_child_context)

        # Then
        assert "홍길동" in prompt
        assert "10세" in prompt
        assert "남" in prompt
        assert "강점" in prompt
        assert "난점" in prompt
        assert "8점" in prompt
        assert "22점" in prompt

    @pytest.mark.asyncio
    async def test_SDQ_A_기본_소견을_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_sdq_a_scores: SdqAScores,
        sample_child_context: ChildContext,
    ) -> None:
        """API 실패시 기본 소견을 생성한다."""
        # When
        result = generator._create_default_sdq_a_opinion(
            sample_sdq_a_scores,
            sample_child_context,
        )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert len(result.summary_lines) == 3
        assert "홍길동" in result.expert_opinion
        assert result.confidence_score == 0.6

    @pytest.mark.asyncio
    async def test_SDQ_A_소견을_성공적으로_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_sdq_a_scores: SdqAScores,
        sample_child_context: ChildContext,
    ) -> None:
        """OpenAI API 호출 성공시 소견을 반환한다."""
        # Given
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary_lines": ["1줄 강점", "2줄 관심", "3줄 조언"], '
                    '"expert_opinion": "종합 소견입니다.", '
                    '"key_findings": ["발견1", "발견2"], '
                    '"recommendations": ["권장1", "권장2"], '
                    '"confidence_score": 0.85}'
                )
            )
        ]

        with patch.object(
            generator.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            # When
            result = await generator.generate_sdq_a_opinion(
                sample_sdq_a_scores,
                sample_child_context,
            )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert len(result.summary_lines) == 3
        assert result.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_SDQ_A_API_실패시_기본_소견을_반환한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_sdq_a_scores: SdqAScores,
        sample_child_context: ChildContext,
    ) -> None:
        """OpenAI API 실패시 기본 소견으로 폴백한다."""
        # Given
        with patch.object(
            generator.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            # When
            result = await generator.generate_sdq_a_opinion(
                sample_sdq_a_scores,
                sample_child_context,
            )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert result.confidence_score == 0.6  # 기본 신뢰도


class TestAssessmentOpinionGeneratorCrtesR:
    """CRTES-R 소견 생성 테스트."""

    @pytest.fixture
    def generator(self) -> AssessmentOpinionGenerator:
        """테스트용 생성기 인스턴스."""
        with patch("yeirin_ai.infrastructure.llm.assessment_opinion_generator.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"
            return AssessmentOpinionGenerator()

    @pytest.fixture
    def sample_crtes_r_scores(self) -> CrtesRScores:
        """샘플 CRTES-R 점수."""
        return CrtesRScores(
            total_score=45,
            risk_level="caution",
            risk_level_description="일부 스트레스 반응이 관찰됩니다.",
        )

    @pytest.fixture
    def sample_child_context(self) -> ChildContext:
        """샘플 아동 컨텍스트."""
        return ChildContext(
            name="홍길동",
            age=11,
            gender="FEMALE",
        )

    def test_기본_위험_설명을_반환한다(self, generator: AssessmentOpinionGenerator) -> None:
        """위험 수준별 기본 설명을 반환한다."""
        # When & Then
        assert "정상" in generator._get_default_risk_description("normal")
        assert "관심" in generator._get_default_risk_description("caution")
        assert "전문" in generator._get_default_risk_description("high_risk")

    def test_CRTES_R_프롬프트를_올바르게_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_crtes_r_scores: CrtesRScores,
        sample_child_context: ChildContext,
    ) -> None:
        """CRTES-R 프롬프트가 필요한 정보를 포함한다."""
        # When
        prompt = generator._build_crtes_r_prompt(sample_crtes_r_scores, sample_child_context)

        # Then
        assert "홍길동" in prompt
        assert "11세" in prompt
        assert "여" in prompt
        assert "45점" in prompt
        assert "주의 필요" in prompt

    @pytest.mark.asyncio
    async def test_CRTES_R_기본_소견을_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_crtes_r_scores: CrtesRScores,
        sample_child_context: ChildContext,
    ) -> None:
        """API 실패시 기본 소견을 생성한다."""
        # When
        result = generator._create_default_crtes_r_opinion(
            sample_crtes_r_scores,
            sample_child_context,
        )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert len(result.summary_lines) == 3
        assert "홍길동" in result.expert_opinion
        assert "45" in result.expert_opinion
        assert result.confidence_score == 0.6

    @pytest.mark.asyncio
    async def test_CRTES_R_소견을_성공적으로_생성한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_crtes_r_scores: CrtesRScores,
        sample_child_context: ChildContext,
    ) -> None:
        """OpenAI API 호출 성공시 소견을 반환한다."""
        # Given
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"summary_lines": ["1줄 상태", "2줄 회복", "3줄 지지"], '
                    '"expert_opinion": "CRTES-R 종합 소견입니다.", '
                    '"key_findings": ["발견1", "발견2"], '
                    '"recommendations": ["권장1", "권장2"], '
                    '"confidence_score": 0.9}'
                )
            )
        ]

        with patch.object(
            generator.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            # When
            result = await generator.generate_crtes_r_opinion(
                sample_crtes_r_scores,
                sample_child_context,
            )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert len(result.summary_lines) == 3
        assert result.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_CRTES_R_API_실패시_기본_소견을_반환한다(
        self,
        generator: AssessmentOpinionGenerator,
        sample_crtes_r_scores: CrtesRScores,
        sample_child_context: ChildContext,
    ) -> None:
        """OpenAI API 실패시 기본 소견으로 폴백한다."""
        # Given
        with patch.object(
            generator.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            # When
            result = await generator.generate_crtes_r_opinion(
                sample_crtes_r_scores,
                sample_child_context,
            )

        # Then
        assert isinstance(result, AssessmentOpinion)
        assert result.confidence_score == 0.6  # 기본 신뢰도


class TestOpinionParsing:
    """소견 파싱 테스트."""

    @pytest.fixture
    def generator(self) -> AssessmentOpinionGenerator:
        """테스트용 생성기 인스턴스."""
        with patch("yeirin_ai.infrastructure.llm.assessment_opinion_generator.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_model = "gpt-4o-mini"
            return AssessmentOpinionGenerator()

    def test_정상_응답을_파싱한다(self, generator: AssessmentOpinionGenerator) -> None:
        """정상 JSON 응답을 AssessmentOpinion으로 파싱한다."""
        # Given
        result = {
            "summary_lines": ["줄1", "줄2", "줄3"],
            "expert_opinion": "전문가 소견",
            "key_findings": ["발견1", "발견2"],
            "recommendations": ["권장1", "권장2"],
            "confidence_score": 0.85,
        }

        # When
        opinion = generator._parse_opinion(result)

        # Then
        assert opinion.summary_lines == ["줄1", "줄2", "줄3"]
        assert opinion.expert_opinion == "전문가 소견"
        assert opinion.key_findings == ["발견1", "발견2"]
        assert opinion.recommendations == ["권장1", "권장2"]
        assert opinion.confidence_score == 0.85

    def test_빈_응답을_파싱한다(self, generator: AssessmentOpinionGenerator) -> None:
        """빈 딕셔너리를 기본값으로 파싱한다."""
        # Given
        result = {}

        # When
        opinion = generator._parse_opinion(result)

        # Then
        assert opinion.summary_lines == []
        assert opinion.expert_opinion == ""
        assert opinion.key_findings == []
        assert opinion.recommendations == []
        assert opinion.confidence_score == 0.0
